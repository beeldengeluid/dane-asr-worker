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

"""
TODO: I do not like the response format too much. Why make the status code part of the resonse object if HTTP supports
status code natively...
"""

@api.route('/process/<string:pid>',	endpoint='process')
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

	#run ASR in a different thread, so the client immediately gets a response and can start polling progress via GET
	def run_asr_async(self, pid, input_file, simulate=True):
		print('starting ASR in different thread...')
		t = threading.Thread(target=self.run_asr, args=(
			pid,
			input_file,
			simulate,
			self.get_pid_file_name(pid),
			True,
		))
		t.daemon = True
		t.start()

	def run_asr(self, pid, input_file, simulate=True, pid_file=None, asynchronous=False):
		print('running asr for PID={0}'.format(pid))
		resp = {'state' : 200, 'message' : 'Succesfully ran ASR on {0}'.format(input_file)} # assume the best
		if simulate:
			sleep(5)
		else:
			resp = process_input_file(os.path.join(os.sep, 'input-files', input_file))

		#if in async mode make sure to set the status file to "done"/"failed", so the client poller knows
		if asynchronous:
			success = 'state' in resp and resp['state'] == 200
			print('updating pid file {0}'.format(pid))
			f  = open(pid_file, 'w')
			f.write('done' if success else 'failed')
			f.close()

		return resp

	#@api.response(200, 'Success', processResponse)
	def put(self, pid):
		input_file = request.args.get('input_file', None)
		wait = request.args.get('wait_for_completion', '1') == '1'
		simulate = request.args.get('simulate', '1') == '1'

		if input_file:
			if wait:
				print('Starting ASR in same thread...')
				resp = self.run_asr(pid, input_file, simulate)
				print('ASR done, returning response to client')
				print(resp)
				return json.dumps(resp), resp['state'], {}
			else:
				print('saving the pid to this file')
				self.create_pid_file(pid)
				self.run_asr_async(pid, input_file, simulate)
				return {
					'state' : 200,
					'message' : 'submitted the ASR work; status can be retrieved via PID={0}'.format(pid),
					'pid' : pid
				}, 200, {}
		else:
			return {'state' : 400, 'message' : 'error: bad params'}, 400, {}
		return {'state' : 500, 'message' : 'error: internal server error'}, 500, {}

	#fetch the status of the pid
	def get(self, pid):
		if not self.pid_file_exists(pid):
			return {'state' : 404, 'message' : 'Error: PID does not exist (anymore)'}, 404, {}

		status = self.read_pid_file(pid)
		if status == 'done':
			return {'state' : 200, 'message' : 'finished'}, 200, {}
		else:
			return {'state' : 200, 'message' : 'in progress'}, 200, {}
