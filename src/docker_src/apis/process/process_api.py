import requests
import json
from time import sleep
import os
from flask import current_app, request, Response
from flask_restx import Api, Namespace, Resource, fields

from work_processor import process_input_file

api = Namespace('ASR Processing API', description='Process mp3 & wav into text')

_anyField = api.model('AnyField', {})

#See src/tests/unit_tests/apis/basic_search/output_search.json
processResponse = api.model('ProcessResponse', {
	'status' : fields.String(description='whether the ', example="success"),
})

@api.route('/process',	endpoint='process')
@api.doc(params={
	'input_file': {
		'in': 'query',
		'description': 'path to input file starting from the mounted folder "/input-files"',
		'default': ''
	}
})
class ProcessEndpoint(Resource):

	#@api.response(200, 'Success', processResponse)
	def get(self):
		#TODO build in arg: wait_for_completion
		input_file = request.args.get('input_file', None)
		if input_file:
			resp = process_input_file(os.path.join(os.sep, 'input-files', input_file))
			return Response(json.dumps(resp), mimetype='application/json')
			#return {'status' : 'success'}, 200, {}
		return {'status' : 'error'}, 500, {}

@api.route('/process-simulation',	endpoint='process-simulation')
@api.doc(params={
	'input_file': {
		'in': 'query',
		'description': 'path to input file starting from the mounted folder "/input-files"',
		'default': ''
	},
	'wait_for_completion' : {
		'in' : 'query',
		'description' : 'wait for the completion of the ASR or not',
		'default' : '1'
	}
})
class ProcessEndpoint(Resource):

	#@api.response(200, 'Success', processResponse)
	def get(self):
		#TODO build in arg: wait_for_completion
		input_file = request.args.get('input_file', None)
		wait = request.args.get('wait_for_completion', '1')
		if input_file:
			#resp = process_input_file(os.path.join(os.sep, 'input-files', input_file))
			#return Response(json.dumps(resp), mimetype='application/json')
			if wait == '1':
				print('waiting for a bit')
				sleep(20) # wait for 20 seconds (* sound of fake asr running *)
				print('I have awakened')
			return {'status' : 'success'}, 200, {}
		else:
			return {'status' : 'error: bad params'}, 400, {}
		return {'status' : 'error'}, 500, {}
