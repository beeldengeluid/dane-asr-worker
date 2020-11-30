import requests
import json
import threading
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

@api.route('/process-simulation/<string:pid>',	endpoint='process-simulation')
@api.doc(params={
	'input_file': {
		'in': 'query',
		'description': 'path to input file starting from the mounted folder "/input-files"',
		'default': ''
	},
	'pid': {
		'in': 'path',
		'description': 'process code you want to use to track progress (e.g. hash of input_file)',
		'default': ''
	},
	'wait_for_completion' : {
		'in' : 'query',
		'description' : 'wait for the completion of the ASR or not',
		'default' : '1'
	}
})
class ProcessEndpoint(Resource):

	def get_pid_file_name(self, pid):
		return '{0}/{1}'.format(current_app.config['PID_CACHE_DIR'], pid)

	def pid_file_exists(self, pid):
		return os.path.exists(self.get_pid_file_name(pid))

	def create_pid_file(self, pid):
		f  = open(self.get_pid_file_name(pid), 'w+')
		f.close()

	def write_pid_file(self, pid, txt):
		f  = open(self.get_pid_file_name(pid), 'w')
		f.write(txt)
		f.close()

	def read_pid_file(self, pid):
		f  = open(self.get_pid_file_name(pid), 'r')
		txt = ''
		for l in f.readlines():
			txt += l
		f.close()
		return txt

	# wait for 20 seconds (* sound of fake asr running *)
	# run tasks from thread, so it doesnt block API response
	def async_asr(self, pid):
		print('starting ASR in different thread...')
		t = threading.Thread(target=self.simulate_asr, args=(pid, self.get_pid_file_name(pid), True,))
		t.daemon = True
		t.start()

	def simulate_asr(self, pid, pid_file, asynchronous=False):
		print('running asr for PID={0}'.format(pid))
		sleep(5)
		if asynchronous:
			print('updating pid file {0}'.format(pid))
			f  = open(pid_file, 'w')
			f.write('done')
			f.close()

	#@api.response(200, 'Success', processResponse)
	def put(self, pid):
		#TODO build in arg: wait_for_completion
		input_file = request.args.get('input_file', None)
		wait = request.args.get('wait_for_completion', '1')

		if input_file:
			#resp = process_input_file(os.path.join(os.sep, 'input-files', input_file))
			#return Response(json.dumps(resp), mimetype='application/json')
			if wait == '1':
				print('Starting ASR in same thread...')
				self.simulate_asr(pid)
				return {'status' : 'success'}, 200, {}
			else:
				print('saving the pid to this file')
				self.create_pid_file(pid)
				self.async_asr(pid)
				return {
					'status' : 'success',
					'message' : 'submitted the ASR work; status can be retrieved via PID={0}'.format(pid),
					'pid' : pid
				}, 200, {}
		else:
			return {'status' : 'error: bad params'}, 400, {}
		return {'status' : 'error'}, 500, {}

	#fetch the status of the pid
	def get(self, pid):
		if not self.pid_file_exists(pid):
			return {'status' : 'Error: PID does not exist (anymore)'}, 404, {}

		status = self.read_pid_file(pid)
		if status == 'done':
			return {'status' : 'finished'}, 200, {}
		else:
			return {'status' : 'in progress'}, 200, {}
