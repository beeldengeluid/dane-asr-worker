import requests
import json
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
