from flask_restx import Api

from .process.process_api import api as processAPI

api = Api(version='v0.1')
api.add_namespace(processAPI, path='/api')