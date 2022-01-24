import json
from elasticsearch import Elasticsearch, TransportError


class ESHandler:
    def __init__(self, config):
        self.config = config
        self.es = Elasticsearch(host=config["host"], port=config["port"])
        print(self.es.info())

    def search(self, query, es_index=None, timeout=50):
        print(json.dumps(query, indent=4, sort_keys=True))
        print(es_index)
        resp = None
        try:
            resp = self.es.search(index=es_index, body=query, request_timeout=timeout)
        except TransportError as te:
            print("TransportError")
            if te.status_code == 404:
                raise ValueError("not_found")
            else:
                raise ValueError("bad_request")
        except Exception:
            print("Exception")
            raise ValueError("internal_server_error")

        if resp and "hits" in resp:
            return resp["hits"]
        else:
            raise ValueError("internal_server_error")
