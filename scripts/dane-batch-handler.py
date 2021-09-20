import json
import yaml
import elasticsearch
import elasticsearch.helpers
import requests
import DANE
from time import sleep

class DANEBatchHandler():

    def __init__(self, cfg_file):
        self.config = self.load_config(cfg_file)

        self.DANE_DOC_ENDPOINT = '{}/DANE/document/'.format(self.config['DANE_SERVER'])
        self.DANE_DOCS_ENDPOINT = '{}/DANE/documents/'.format(self.config['DANE_SERVER'])
        self.DANE_TASK_ENDPOINT = '{}/DANE/task/'.format(self.config['DANE_SERVER'])

        self.DANE_ES = elasticsearch.Elasticsearch(
            host=self.config['DANE_ES_HOST'],
            port=self.config['DANE_ES_PORT'],
        )


    def load_config(self, cfg_file):
        try:
            with open(cfg_file, 'r') as yamlfile:
                return yaml.load(yamlfile, Loader=yaml.FullLoader)
        except FileNotFoundError as e:
            print(e)
        return None

    """------------------------------------- CREATE DANE DOCS FOR RADIO ORANJE------------------------------- """

    #2101609050155932121 (radio oranje asset ID? low-res geeft 404...)
    def convert_radio_oranje_to_dane_docs(self):
        es = elasticsearch.Elasticsearch([self.config['ES_URL']],
                timeout=30, max_retries=5, retry_on_timeout=True)

        result = elasticsearch.helpers.scan(es,
                index=self.config['ES_INDEX'],
                query=self.config['ES_QUERY'])

        notyielded = 0
        docs = []
        for hit in result:
            if hit['_source']['filename'] is not None:
                source_url = 'http://videohosting.beng.nl/radio-oranje/{}'.format(hit['_source']['filename'])
                print(source_url)
                docs.append(json.loads(DANE.Document(
                    {
                        'id': hit['_id'], #fetch the actual asset ID / carrier number
                        'url': source_url,
                        'type': 'Video'
                    },
                    {
                        'id': 'NISV - Radio Oranje',
                        'type': 'Organization' }
                    ).to_json()))
            else:
                print("WAAAH")
                exit()
        return docs

    # submits the docs to DANE & writes them to the local batch file (INDEX-batch.json)
    def submit_docs(self, docs, batch_id):
        print("Trying to insert {} documents".format(len(docs)))
        r = requests.post(self.DANE_DOCS_ENDPOINT, data=json.dumps(docs))
        if r.status_code != 200:
            raise RuntimeError(str(r.status_code) + " " + r.text)
        print(r.text)

        with open('{}-batch.json'.format(batch_id), 'w') as f:
            f.write(r.text)

    # use to feed the add_asr_task_to_docs() function
    def get_doc_ids_of_batch(self, batch_id):
        batch_data = json.load(open('{}-batch.json'.format(batch_id)))
        if 'success' in batch_data:
            return [doc['_id'] for doc in batch_data['success']]
        return None

    def get_doc(self, doc_id):
        url = '{}{}'.format(self.DANE_DOC_ENDPOINT, doc_id)
        r = requests.get(url)
        if r.status_code == 200:
            return json.loads(r.text)
        return None

    """------------------------------------- TASK CRUD ------------------------------- """

    def add_tasks_to_batch(self, batch_id, task_key):
        print('going to submit {} for the following doc IDs'.format(task_key))
        doc_ids = self.get_doc_ids_of_batch(batch_id)
        task = {
            "document_id": doc_ids,
            "key": task_key, # e.g. ASR, DOWNLOAD
        }

        r = requests.post(self.DANE_TASK_ENDPOINT, data=json.dumps(task))
        if r.status_code != 200:
            print(r.status_code, r.text)
            #raise RuntimeError(str(r.status_code) + " " + r.text)
        print(r.text)

    def get_tasks_of_batch(self, batch_id):
        docs = self.get_doc_ids_of_batch(batch_id)
        all_tasks = []
        for did in docs:
            print('Fetching tasks for doc: {}'.format(did))
            tasks_url = '{}{}/tasks'.format(self.DANE_DOC_ENDPOINT, did)
            resp = requests.get(tasks_url)
            if resp.status_code == 200:
                tasks = json.loads(resp.text)
                all_tasks.extend(tasks)
        return all_tasks

    def delete_task_ids(self, task_ids):
        for tid in task_ids:
            url = '{}{}'.format(self.DANE_TASK_ENDPOINT, tid)
            resp = requests.delete(url)
            print(resp.text)

    def get_parent_doc_id(self, task_id):
        result = self.DANE_ES.get(index=self.config['DANE_ES_INDEX'], id=task_id)
        if '_source' in result and \
            'role' in result['_source'] and \
            'parent' in result['_source']['role']:
                return result['_source']['role']['parent']
        return None

    def clean_tasks_n_results_of_batch(self, batch_id):
        tasks = self.get_tasks_of_batch(batch_id)
        task_ids = [t['_id'] for t in tasks]
        print(task_ids)
        self.delete_task_ids(task_ids)

    """------------------------------------- MONITOR BATCH ------------------------------- """

    def monitor_batch(self, batch_id):
        print('\t\tMONITORING BATCH: {}'.format(batch_id))
        tasks = self.get_tasks_of_batch(batch_id)
        print('FOUND {} TASKS, MONITORING NOW'.format(len(tasks)))
        print('*' * 50)
        status_overview = {}
        for t in tasks:

            if t['key'] in status_overview:
                if t['state'] in status_overview[t['key']]['states']:
                    status_overview[t['key']]['states']['{}'.format(t['state'])]['tasks'].append(t['_id'])
                else:
                    status_overview[t['key']]['states']['{}'.format(t['state'])] = {
                    'msg' : t['msg'],
                    'tasks' : [t['_id']]
                }
            else:
                status_overview[t['key']] = {
                    'states' : {
                        '{}'.format(t['state']) : {
                            'msg' : t['msg'],
                            'tasks' : [t['_id']]
                        }
                    }
                }
            #print('{} => {} ({}): {}'.format(t['_id'], t['key'], t['state'], t['msg']))
        print(json.dumps(status_overview, indent=4, sort_keys=True))
        sleep(10)
        self.monitor_batch(batch_id)
        print('-' * 50)

    def get_failed_download_urls(self, batch_id):
        tasks = self.get_tasks_of_batch(batch_id)
        for t in tasks:
            if t['state'] == '404':
                doc_id = self.get_parent_doc_id(t['_id'])
                doc = self.get_doc(doc_id)
                print(doc['target']['url'])

    # TODO show a list of failed 404 download tasks and match them with dependant tasks that hit a 412
    def correlate_404_unfinished_deps(self, batch_id):
        pass

    # TODO based on the start time of the batch and the amount of finished tasks, estimate the time to finish
    def estimate_progress(self, batch_id):
        pass


if __name__ == '__main__':

    dbh = DANEBatchHandler('config.yml')

    """
    # create & submit the DANE docs for radio oranje
    dane_docs = dbh.convert_radio_oranje_to_dane_docs()
    print('\n'.join([doc['target']['id'] for doc in dane_docs]))
    if dane_docs and len(dane_docs) > 0:
        dbh.submit_docs(dane_docs)
    """
    # assign the ASR task for the entire radio-oranje batch
    #add_tasks_to_batch('radio-oranje', 'ASR')

    # monitor the DANE workers progress of the radio-oranje batch
    dbh.monitor_batch('radio-oranje')

    # show which URLs could not be downloaded for the radio-oranje batch
    #dbh.get_failed_download_urls('radio-oranje')

    # clean up all DANE tasks+results for the radio-oranje batch
    #dbh.clean_tasks_n_results_of_batch('radio-oranje')