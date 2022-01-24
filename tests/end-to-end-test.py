import yaml
import json
import DANE
import requests
from es_handler import ESHandler
from time import sleep


class EndToEndTest:
    def __init__(self, cfg_file):
        self.config = self.load_config(cfg_file)
        self.es_handler = ESHandler(self.config["ELASTICSEARCH"])

        # DANE READY ENDPOINT
        self.DANE_READY_ENDPOINT = "{}/ready".format(self.config["DANE_SERVER"])

        # DANE SERVER UI
        self.DANE_MANAGE_ENDPOINT = "{}/manage".format(self.config["DANE_SERVER"])

        # DANE API
        self.DANE_API = "{}/DANE".format(self.config["DANE_SERVER"])
        self.DANE_DOCS_ENDPOINT = "{}/documents".format(self.DANE_API)
        self.DANE_DOC_ENDPOINT = "{}/document/".format(self.DANE_API)
        self.DANE_TASK_ENDPOINT = "{}/task/".format(self.DANE_API)
        self.DANE_SEARCH_ENDPOINT = "{}/search/document/".format(self.DANE_API)

        print(
            "{}\n{}\n{}\n{}\n{}".format(
                self.DANE_READY_ENDPOINT,
                self.DANE_MANAGE_ENDPOINT,
                self.DANE_API,
                self.DANE_DOCS_ENDPOINT,
                self.DANE_TASK_ENDPOINT,
            )
        )

    def load_config(self, cfg_file):
        try:
            with open(cfg_file, "r") as yamlfile:
                return yaml.load(yamlfile, Loader=yaml.FullLoader)
        except FileNotFoundError as e:
            print(e)
        return None

    def run_overall_test(self):
        # 1st test suite (test ready endpoints)
        print("* Checking ready endpoints *")
        ok = self.test_ready_endpoint()
        print("Ready check ok: {}".format(ok))

        # 2nd test suite (test doc CRUD)
        print("* Checking document CRUD *")
        doc_id = self.test_create_doc()
        print("Created doc: {}".format(doc_id is not None))
        if doc_id:
            ok = self.test_get_doc(doc_id)
            print("Retrieved doc: {}".format(ok))
            ok = self.test_delete_doc(doc_id)
            print("Deleted doc: {}".format(ok))

        # 3nd test suite (test task CRUD also influencing worker queues)
        print("* Checking task CRUD *")
        doc_id = self.test_create_doc()
        print("Created doc: {}".format(doc_id is not None))
        if not doc_id:
            print("checking if the doc already exists")
            doc = self.test_search_doc(self.config["TEST_DOC"]["id"])
            print(doc)
            doc_id = doc["_id"] if doc else None
        if doc_id:
            # doc is ok, now create a download task
            task_id = self.test_create_task(doc_id, "DOWNLOAD")
            print("Created task: {}".format(task_id is not None))
            if task_id:
                print("success now monitoring task {}".format(task_id))
                ok = self.test_get_task(task_id)
                print("Get task: {}".format(ok))

                if ok:
                    task_running = True
                    while task_running:
                        result = self.test_get_result(task_id)
                        print(result)
                        print("Get result {}".format(result is not None))
                        task_running = result is None
                        if task_running:
                            print("Waiting for 2 seconds to try again...")
                            sleep(2)  # wait to seconds
                else:
                    print("Could not fetch task after it was created")

                # finally delete the doc after the task has successfully ran (which will delete the task as well)
                ok = self.test_delete_doc(doc_id)
                print("Deleted doc for successfully run task: {}".format(ok))
            else:
                ok = self.test_delete_doc(doc_id)
                print("Deleted doc for task that could not be created: {}".format(ok))
        else:
            print("Could not create the test DANE doc at all")

    def run_asr_test(self):
        # 3nd test suite (test task CRUD also influencing worker queues)
        print("* Checking task CRUD *")
        doc_id = self.test_create_doc()
        print("Created doc: {}".format(doc_id is not None))
        if not doc_id:
            print("checking if the doc already exists")
            doc = self.test_search_doc(self.config["TEST_DOC"]["id"])
            print(doc)
            doc_id = doc["_id"] if doc else None
        if doc_id:
            # doc is ok, now create a download task
            task_id = self.test_create_task(doc_id, "ASR")
            print("Created task: {}".format(task_id is not None))
            if task_id:
                print("SUCCESFULLY CREATED ASR TASK {}".format(task_id))
                print("now monitoring task {}".format(task_id))
                ok = self.test_get_task(task_id)
                print("Get task: {}".format(ok))
                c = 0
                if ok:
                    task_running = True
                    while task_running:
                        result = self.test_get_result(task_id)
                        print("Get result {}".format(result is not None))
                        tasks = self.test_get_tasks_of_doc(doc_id)
                        print(tasks)
                        task_running = result is None
                        if task_running:
                            print("Waiting for 2 seconds to try again (ASR)...")
                            sleep(2)  # wait to seconds
                        else:
                            print("YAY I AM ACTUALLY DONE WITH ASR!")
                        c += 1
                        if c > 430:
                            print("I am fed up with this!")
                            task_running = False
                else:
                    print("could not fetch task?")

        # finally delete the doc after the task has successfully ran (which will delete the task as well)
        ok = self.test_delete_doc(doc_id)
        print("Deleted doc for successfully run task: {}".format(ok))
        print("DONE WITH ASR TEST")

    """
    -------------------------------------- TESTING READY ENDPOINTS -----------------------------------
    """

    # test if both the database & message queue are available
    def test_ready_endpoint(self):
        resp = requests.get(self.DANE_READY_ENDPOINT)
        if resp.status_code == 200:
            data = json.loads(resp.text)
            return (
                "database" in data
                and "messagequeue" in data
                and data["database"] == "200 OK"
                and data["messagequeue"] == "200 OK"
            )
        return False

    """
    -------------------------------------- TESTING DOCS -----------------------------------
    """

    # first create a DANE doc
    def test_create_doc(self):

        dane_doc = json.loads(
            DANE.Document(
                {
                    "id": self.config["TEST_DOC"]["id"],
                    "url": self.config["TEST_DOC"]["url"],
                    "type": self.config["TEST_DOC"]["type"],
                },
                {
                    "id": self.config["TEST_CREATOR"]["id"],
                    "type": self.config["TEST_CREATOR"]["type"],
                },
            ).to_json()
        )

        print(dane_doc)

        resp = requests.post(self.DANE_DOC_ENDPOINT, data=json.dumps(dane_doc))
        if resp.status_code != 200:
            print(str(resp.status_code) + " " + resp.text)
            return None
        data = json.loads(resp.text)
        print(data)
        return data["_id"]

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

    def test_get_doc(
        self, doc_id: str
    ):  # make sure to test that the doc was inserted properly
        url = "{}{}".format(self.DANE_DOC_ENDPOINT, doc_id)
        resp = requests.get(url)
        if resp.status_code == 200:
            print(resp.text)
            data = json.loads(resp.text)
            if all(
                [
                    x in ["_id", "target", "creator", "created_at", "updated_at"]
                    for x in data.keys()
                ]
            ):
                return True
        else:
            print(str(resp.status_code) + " " + resp.text)
        return False

    # first also test if the delete works
    def test_delete_doc(self, doc_id: str):
        url = "{}{}".format(self.DANE_DOC_ENDPOINT, doc_id)
        resp = requests.delete(url)
        if resp.status_code == 200:
            print(resp.text)
            return True
        else:
            print(str(resp.status_code) + " " + resp.text)
        return False

    # Note: there is also /document/{doc_id}/tasks (but has a slower implementation)
    def test_get_tasks_of_doc(self, doc_id: str):
        query = {"query": {"parent_id": {"type": "task", "id": doc_id}}}
        resp = self.es_handler.search(query, self.config["ELASTICSEARCH"]["index"])
        if "hits" in resp:
            tasks = []
            for hit in resp["hits"]:
                if "task" not in hit["_source"]:
                    print("No _source in task hit?")
                    continue
                t = hit["_source"]["task"] if "task" in hit["_source"] else None
                t["created_at"] = (
                    hit["_source"]["created_at"]
                    if "created_at" in hit["_source"]
                    else None
                )
                t["updated_at"] = (
                    hit["_source"]["updated_at"]
                    if "updated_at" in hit["_source"]
                    else None
                )
                if t:
                    tasks.append(t)
            return tasks
        print("No tasks found for doc_id {}".format(doc_id))
        return None

    """
    -------------------------------------- SEARCH TARGET ID (HELPER) -----------------------------------
    """

    """
    {
      "total": 1,
      "hits": [
        {
          "_id": "f298fffaac963b9e1ae7764f7774c234e8c1ab4b",
          "target": {
            "id": "end-to-end-test",
            "url": "http://videohosting.beng.nl/radio-oranje/Radio%20Oranje%2029-aug.-1940_UITZENDING%20RADIO%20ORANJE%20TGV%20ZESTIGSTE%20VERJAARDAG%20KONINGIN%20WILHELMINA%20_%20REDE.mp3",
            "type": "Video"
          },
          "creator": {
            "id": "NISV - Radio Oranje",
            "type": "Organization"
          },
          "created_at": "2021-08-31T08:55:42",
          "updated_at": "2021-08-31T08:55:42"
        }
      ]
    }
    """

    def test_search_doc(self, target_id: str, creator: str = "*"):
        url = "{}?target_id={}&creator_id={}&page=1".format(
            self.DANE_SEARCH_ENDPOINT, target_id, creator
        )
        resp = requests.get(url)
        if resp.status_code != 200:
            print(resp.status_code, resp.text)
            return None
        data = json.loads(resp.text)
        if "hits" in data and "_id" in data["hits"][0]:
            return data["hits"][0]
        print("No hits found?")
        return None

    """
    -------------------------------------- TESTING TASKS -----------------------------------
    """

    """
    {
        "success": [
            {
                "_id": "c48b79650adad39f50c5a27975f9ad0a2860def8",
                "key": "DOWNLOAD",
                "state": "201",
                "msg": "Created",
                "priority": 1,
                "created_at": "2021-08-31T08:50:20",
                "updated_at": "2021-08-31T08:50:20",
                "args": {
                    "*": null
                }
            }
        ],
        "failed": []
    }
    """

    def test_create_task(self, doc_id: str, task_type: str):
        task = {
            "document_id": [doc_id],
            "key": task_type,
        }
        print(task)
        resp = requests.post(self.DANE_TASK_ENDPOINT, data=json.dumps(task))
        if resp.status_code != 200:
            print(resp.status_code, resp.text)
            return None
        data = json.loads(resp.text)
        if "success" in data and len(data["success"]) == 1:
            return data["success"][0]["_id"]
        elif "failed" in data and len(data["failed"]) == 1:
            print(data["failed"])
            return None
        print("No success, no failure, 200, but still not ok?")
        print(data)
        return None

    def test_get_task(
        self, task_id: str
    ):  # make sure to test that the doc was inserted properly
        url = "{}{}".format(self.DANE_TASK_ENDPOINT, task_id)
        print(url)
        resp = requests.get(url)
        if resp.status_code == 200:
            print(resp.text)
            data = json.loads(resp.text)
            print(json.dumps(data))
            # if all([x in ['_id', 'target', 'creator', 'created_at', 'updated_at'] for x in data.keys()]):
            return True
        else:
            print("something went wrong in fetching the task")
            print(str(resp.status_code) + " " + resp.text)
        return False

    def test_delete_task(self, task_id: str):
        url = "{}{}".format(self.DANE_TASK_ENDPOINT, task_id)
        print(url)
        resp = requests.delete(url)
        if resp.status_code == 200:
            print(resp.text)
            return True
        else:
            print(str(resp.status_code) + " " + resp.text)
        return False

    """
    ------------------------- FIND RESULTS ---------------------------
    """

    def test_get_result(self, task_id: str):
        query = {"query": {"parent_id": {"type": "result", "id": task_id}}}
        resp = self.es_handler.search(query, self.config["ELASTICSEARCH"]["index"])
        # print(json.dumps(resp, indent=4, sort_keys=True))
        if "hits" in resp and len(resp["hits"]) == 1:
            hit = resp["hits"][0]
            if "result" not in hit["_source"]:
                print("No source in result hit?")
                return None
            return hit["_source"]["result"] if "result" in hit["_source"] else None
        print("No hits for result")
        return None


if __name__ == "__main__":
    print("starting end to end test")
    e2e = EndToEndTest("config.yml")
    print(
        "************************** RUNNING OVERALL TEST (INCLUDING DOWNLOAD WORKER) **********************"
    )
    e2e.run_overall_test()
    print("************************** RUNNING ASR WORKER TEST **********************")
    e2e.run_asr_test()
