import json
import yaml
import elasticsearch
import elasticsearch.helpers
import requests
import DANE
from time import sleep

class DANEBatchHandler():

    # TODO make sure to harmonize/merge the batch_id and the batch_name!
    def __init__(self, cfg_file):
        self.config = self.load_config(cfg_file)
        self.BATCH_ID = self.config['BATCH_ID'] # used to fetch all DANE docs from the batch file {batch_id}-batch.json
        self.BATCH_NAME = self.config['BATCH_NAME'] # used to fetch all DANE tasks from ES via doc.creator.name

        self.DANE_DOC_ENDPOINT = '{}/DANE/document/'.format(self.config['DANE_SERVER'])
        self.DANE_DOCS_ENDPOINT = '{}/DANE/documents/'.format(self.config['DANE_SERVER'])
        self.DANE_TASK_ENDPOINT = '{}/DANE/task/'.format(self.config['DANE_SERVER'])

        self.DANE_ES = elasticsearch.Elasticsearch(
            host=self.config['DANE_ES_HOST'],
            port=self.config['DANE_ES_PORT'],
        )

        self.MONITOR_INTERVAL = self.config['MONITOR_INTERVAL']

        self.ES_QUERY_TIMEOUT = self.config['ES_QUERY_TIMEOUT']

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
    def submit_docs(self, docs):
        print("Trying to insert {} documents".format(len(docs)))
        r = requests.post(self.DANE_DOCS_ENDPOINT, data=json.dumps(docs))
        if r.status_code != 200:
            raise RuntimeError(str(r.status_code) + " " + r.text)
        print(r.text)

        with open('{}-batch.json'.format(self.BATCH_ID), 'w') as f:
            f.write(r.text)

    # use to feed the add_asr_task_to_docs() function
    def get_doc_ids_of_batch(self):
        batch_data = json.load(open('{}-batch.json'.format(self.BATCH_ID)))
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

    def add_tasks_to_batch(self, task_key):
        print('going to submit {} for the following doc IDs'.format(task_key))
        doc_ids = self.get_doc_ids_of_batch(self.BATCH_ID)
        task = {
            "document_id": doc_ids,
            "key": task_key, # e.g. ASR, DOWNLOAD
        }

        r = requests.post(self.DANE_TASK_ENDPOINT, data=json.dumps(task))
        if r.status_code != 200:
            print(r.status_code, r.text)
            #raise RuntimeError(str(r.status_code) + " " + r.text)
        print(r.text)

    def get_tasks_of_batch_old(self):
        docs = self.get_doc_ids_of_batch(self.BATCH_ID)
        all_tasks = []
        print('Fetching tasks for batch: {}'.format(self.BATCH_ID))
        for did in docs:
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

    def clean_tasks_n_results_of_batch(self):
        tasks = self.get_tasks_of_batch(self.BATCH_NAME)
        task_ids = [t['_id'] for t in tasks]
        print(task_ids)
        self.delete_task_ids(task_ids)

    def retry_failed_tasks(self, task_ids):
        for tid in task_ids:
            url = '{}{}/retry'.format(self.DANE_TASK_ENDPOINT, tid)
            resp = requests.get(url)
            print(resp.text)

    """------------------------------------- MONITOR BATCH & STATS ------------------------------- """

    def monitor_batch(self, task_keys=['DOWNLOAD'], verbose=False):
        print('\t\tMONITORING BATCH: {}'.format(self.BATCH_ID))
        tasks = self.get_tasks_of_batch(self.BATCH_NAME)
        print('FOUND {} TASKS, MONITORING NOW'.format(len(tasks)))
        print('*' * 50)
        status_overview = self.generate_tasks_overview(tasks)
        if verbose:
            print(json.dumps(status_overview, indent=4, sort_keys=True))
        for key in task_keys:
            print('Reporting the {} task'.format(key))
            self.generate_progress_report(status_overview, key)
        print('Waiting for {} seconds'.format(self.MONITOR_INTERVAL))
        sleep(self.MONITOR_INTERVAL)
        self.monitor_batch(task_keys, verbose)
        print('-' * 50)

    def generate_tasks_overview(self, tasks):
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
        return status_overview

    def get_failed_download_urls(self):
        tasks = self.get_tasks_of_batch(self.BATCH_NAME)
        for t in tasks:
            if t['state'] == '404':
                doc_id = self.get_parent_doc_id(t['_id'])
                doc = self.get_doc(doc_id)
                print(doc['target']['url'])

    def get_failed_tasks(self, task_key):
        tasks = self.get_tasks_of_batch(self.BATCH_NAME)
        status_overview = self.generate_tasks_overview(tasks)
        failed_tasks = status_overview.get(task_key, {}).get('states', {}).get('500', {}).get('tasks', [])

        print(failed_tasks)
        return failed_tasks

    # TODO show a list of failed 404 download tasks and match them with dependant tasks that hit a 412
    def correlate_404_unfinished_deps(self, task_key):
        tasks = self.get_tasks_of_batch(self.BATCH_NAME)
        status_overview = self.generate_tasks_overview(tasks)
        download_404s = status_overview.get('DOWNLOAD', {}).get('states', {}).get('404', {}).get('tasks', None)
        task_412s = status_overview.get(task_key, {}).get('states', {}).get('412', {}).get('tasks', None)
        parents_404 = set([self.get_parent_doc_id(t) for t in download_404s])
        parents_412 = set([self.get_parent_doc_id(t) for t in task_412s])

        print(parents_404)
        print(parents_412)
        print('what is the difference?')
        if len(parents_404.difference(parents_412)) == 0:
            print('ALL TASKS FAILED BECAUSE OF A FAILED DOWNLOAD')
        else:
            print('CERTAIN TASKS FAILED FOR OTHER REASONS THAN A FAILED DOWNLOAD')

    # TODO based on the start time of the batch and the amount of finished tasks, estimate the time to finish
    def show_batch_progress(self, task_key):
        tasks = self.get_tasks_of_batch(self.BATCH_NAME)
        status_overview = self.generate_tasks_overview(tasks)
        self.generate_progress_report(status_overview, task_key)

    def generate_progress_report(self, status_overview, task_key):
        states = status_overview.get(task_key, {}).get('states', {})
        c_done = 0
        c_queued = 0
        c_problems = 0
        for state in states.keys():
            state_count = len(states[state].get('tasks', []))
            print('# {} tasks: {}'.format(state, state_count))
            if state == '200':
                c_done += state_count
            elif state == '102':
                c_queued += state_count
            else:
                c_problems += state_count

        print('# tasks done: {}'.format(c_done))
        print('# tasks queued: {}'.format(c_queued))
        print('# tasks with some kind of problem: {}'.format(c_problems))

    def get_tasks_of_batch(self, creator_name, all_tasks=[], offset=0, size=200):
        match_creator_query = {
            "bool":{
                "must":[
                    {"query_string":{"default_field":"creator.id","query":"\"{}\"".format(creator_name)}}
                ]
            }
        }
        query = {
            "_source": ["task", "created_at", "updated_at"],
            "from": offset,
            "size": size,
            "query": {
                "bool": {
                    "must": [
                        {
                            "has_parent": {
                                "parent_type": "document",
                                "query": match_creator_query
                            }
                        },
                        {
                            "exists": {
                                "field": "task.key"
                            }
                        }
                    ]
                }
            }
        }

        result = self.DANE_ES.search(
            index=self.config['DANE_ES_INDEX'],
            body=query,
            request_timeout=self.ES_QUERY_TIMEOUT
        )
        if len(result['hits']['hits']) <= 0:
            return all_tasks
        else:
            for hit in result['hits']['hits']:
                all_tasks.append(self.__format_task(hit))
            return self.get_tasks_of_batch(creator_name, all_tasks, offset + size, size)
        print('not sure why, but returning here')
        return all_tasks

    def __format_task(self, es_hit):
        return {
            '_id' : es_hit['_id'],
            'msg' : es_hit['_source']['task']['msg'],
            'state' : es_hit['_source']['task']['state'],
            'priority' : es_hit['_source']['task']['priority'],
            'key' : es_hit['_source']['task']['key'],
            'created_at' : es_hit['_source']['created_at'],
            'updated_at' : es_hit['_source']['updated_at']
        }




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
    #add_tasks_to_batch('ASR')

    # monitor the DANE workers progress of the radio-oranje batch
    dbh.monitor_batch(['DOWNLOAD', 'ASR'])

    # show which URLs could not be downloaded for the radio-oranje batch
    #dbh.get_failed_download_urls()

    # show if the failed downloads also affects all depending tasks
    #dbh.correlate_404_unfinished_deps('ASR')

    # estimate the time it takes to finish the batch
    #dbh.show_batch_progress('ASR')

    # get the failed tasks for a certain task_key
    #failed_tasks = dbh.get_failed_tasks('ASR')
    #dbh.retry_failed_tasks(failed_tasks)

    # clean up all DANE tasks+results for the radio-oranje batch
    #dbh.clean_tasks_n_results_of_batch()