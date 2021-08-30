import yaml
import json
import DANE
import requests

class EndToEndTest():

    def __init__(self, cfg_file):
        self.config = self.load_config(cfg_file)

        # DANE READY ENDPOINT
        self.DANE_READY_ENDPOINT = '{}/ready'.format(self.config['DANE_SERVER'])

        # DANE SERVER UI
        self.DANE_MANAGE_ENDPOINT = '{}/manage'.format(self.config['DANE_SERVER'])

        # DANE API
        self.DANE_API = '{}/DANE'.format(self.config['DANE_SERVER'])
        self.DANE_DOCS_ENDPOINT = '{}/documents'.format(self.DANE_API)
        self.DANE_DOC_ENDPOINT = '{}/document/'.format(self.DANE_API)
        self.DANE_TASK_ENDPOINT = '{}/task/'.format(self.DANE_API)

        print('{}\n{}\n{}\n{}\n{}'.format(
            self.DANE_READY_ENDPOINT,
            self.DANE_MANAGE_ENDPOINT,
            self.DANE_API,
            self.DANE_DOCS_ENDPOINT,
            self.DANE_TASK_ENDPOINT
        ))


    def load_config(self, cfg_file):
        try:
            with open(cfg_file, 'r') as yamlfile:
                return yaml.load(yamlfile, Loader=yaml.FullLoader)
        except FileNotFoundError as e:
            print(e)
        return None

    def run(self):
        ok = self.test_ready_endpoint()
        print('Ready check ok: {}'.format(ok))
        doc_id = self.test_create_doc()
        print('Created doc: {}'.format(doc_id is not None))
        ok = self.test_get_doc(doc_id)
        print('Retrieved doc: {}'.format(ok))
        ok = self.test_delete_doc(doc_id)
        print('Deleted doc: {}'.format(ok))

    # test if both the database & message queue are available
    def test_ready_endpoint(self):
        resp = requests.get(self.DANE_READY_ENDPOINT)
        if resp.status_code == 200:
            data = json.loads(resp.text)
            return 'database' in data and 'messagequeue' in data and \
                data['database'] == '200 OK' and \
                data['messagequeue'] == '200 OK'
        return False

    # first create a DANE doc
    def test_create_doc(self):

        dane_doc = json.loads(DANE.Document({
            'id': self.config['TEST_DOC']['id'],
            'url': self.config['TEST_DOC']['url'],
            'type': self.config['TEST_DOC']['type']
        },
        {
            'id': self.config['TEST_CREATOR']['id'],
            'type': self.config['TEST_CREATOR']['type']
        }).to_json())

        print(dane_doc)

        resp = requests.post(self.DANE_DOC_ENDPOINT, data=json.dumps(dane_doc))
        if resp.status_code != 200:
            print(str(resp.status_code) + " " + resp.text)
            return None
        data = json.loads(resp.text)
        print(data)
        return data['_id']


    """
    {
      "_id": "aa4c2631cf206b8d8bd8ccd77841aa57262a0491",
      "target": {
        "id": "radio-oranje29-aug-1940",
        "url": "http://videohosting.beng.nl/radio-oranje/Radio%20Oranje%2029-aug.-1940_UITZENDING%20RADIO%20ORANJE%20TGV%20ZESTIGSTE%20VERJAARDAG%20KONINGIN%20WILHELMINA%20_%20REDE.mp3",
        "type": "Video"
      },
      "creator": {
        "id": "NISV - Radio Oranje",
        "type": "Organization"
      },
      "created_at": "2021-08-03T13:09:58",
      "updated_at": "2021-08-03T13:09:58"
    }
    """
    def test_get_doc(self, doc_id): #make sure to test that the doc was inserted properly
        url = '{}{}'.format(
            self.DANE_DOC_ENDPOINT,
            doc_id
        )
        resp = requests.get(url)
        if resp.status_code == 200:
            print(resp.text)
            data = json.loads(resp.text)
            if all([x in ['_id', 'target', 'creator', 'created_at', 'updated_at'] for x in data.keys()]):
                return True
        else:
            print(str(resp.status_code) + " " + resp.text)
        return False

    #first also test if the delete works
    def test_delete_doc(self, doc_id):
        url = '{}{}'.format(
            self.DANE_DOC_ENDPOINT,
            doc_id
        )
        print(url)
        resp = requests.delete(url)
        if resp.status_code == 200:
            print(resp.text)
            return True
        else:
            print(str(resp.status_code) + " " + resp.text)
        return False


    # now create a task to test out the doc
    def create_test_task(self):
        """
        print('going to submit ASR for the following doc IDs')
        print(doc_ids)
        doc_ids = doc_ids if type(doc_ids) == list else [doc_ids]
        task = {
            "document_id": doc_ids,
            "key": "ASR",
        }

        r = requests.post(DANE_TASK_ENDPOINT, data=json.dumps(task))
        if r.status_code != 200:
            print(r.status_code, r.text)
            #raise RuntimeError(str(r.status_code) + " " + r.text)
        print(r.text)
        """

    def check_task(self):
        pass

if __name__ == '__main__':
    print('starting end to end test')
    e2e = EndToEndTest('config.yml')
    e2e.run()