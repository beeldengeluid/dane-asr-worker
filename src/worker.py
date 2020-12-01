import DANE.base_classes
from DANE.config import cfg
from DANE import Result, Task, Document
import json
import os
import subprocess #used for calling cmd line to check if the required docker containers are up
import requests #for communicating with the ASR container's API
from urllib.parse import urlparse
from time import sleep
import hashlib

#from work_processor import process_input_file

"""
This class implements a DANE worker and thus serves as the process receiving tasks from DANE

This particular worker only picks up work from the ASR queue and only will go ahead with (ASR) processing
audiovisual input.

The input file is obtained by requesting the file path from the document index. This file path SHOULD have been
made available by the download worker (before the task was received in this worker)

TODO catch pika.exceptions.ConnectionClosedByBroker in case the rabbitMQ is not available
"""

class asr_worker(DANE.base_classes.base_worker):

	def __init__(self, config):
		self.config = config
		 # we specify a queue name because every worker of this type should
		# listen to the same queue
		self.__queue_name = 'ASR' #this is the queue that receives the work and NOT the reply queue
		self.__binding_key = "#.ASR" #['Video.ASR', 'Sound.ASR']#'#.ASR'
		#['DOWNLOAD'] TODO Nanne will support adding params to this, so it's possible to override the default Task being generated for the downloader
		self.__depends_on = []

		if not self.validate_config():
			print('ERROR: Invalid config, aborting')
			quit()

		if config.DEBUG:
			if not self.init_rabbitmq_container():
				print('ERROR: Could not start in debug mode, RabbitMQ container could not be started, aborting...')
				quit()
			else:
				print('great!')

		if not self.init_asr_container():
			#print('ERROR: Could not start speech recognition service, aborting')
			print('ERROR: Could not start speech recognition service, but continuing anyway')
			#quit()

		super().__init__(
			self.__queue_name,
			self.__binding_key,
			config,
			self.__depends_on,
			True, #auto_connect
			False #no_api
		)
		#self.test_run()

	def validate_config(self):
		return True

	def __docker_container_runs(self, container_name):
		cmd = ['docker', 'container', 'inspect', '-f', "'{{.State.Status}}'", container_name]
		print(' '.join(cmd))
		process = subprocess.Popen(' '.join(cmd), stdout=subprocess.PIPE, shell=True)
		stdout = process.communicate()[0]  # wait until finished. Remove stdout stuff if letting run in background and continue.
		return str(stdout).find('running') != -1

	def init_rabbitmq_container(self):
		print('Checking if the RabbitMQ container (named {0}) is running'.format(self.config.DOCKER.RABBITMQ_CONTAINER))
		return self.__docker_container_runs(self.config.DOCKER.RABBITMQ_CONTAINER)

	def init_asr_container(self):
		print('Checking if the ASR container (named {0}) is running'.format(self.config.DOCKER.ASR_CONTAINER))
		return self.__docker_container_runs(self.config.DOCKER.ASR_CONTAINER)

	def test_run(self):
		print('DOING A TEST RUN')
		resp = process_input_file(os.path.join(os.sep, 'input-files', self.config.ASR.VIDEO_TEST_FILE))
		print(json.dumps(resp, indent=4, sort_keys=True))

	# https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4
	def download_content(self, doc):
		if not doc.target or not 'url' in doc.target or not doc.target['url']:
			print('No url found in doc')
			return None

		print('downloading {0}'.format(doc.target['url']))
		fn = os.path.basename(urlparse(doc.target['url']).path)
		print('saving to file {0}'.format(fn))
		# open in binary mode
		with open(os.path.join(self.config.DOWNLOAD.LOCAL_DIR, fn), "wb") as file:
			# get request
			response = requests.get(doc.target['url'])
			# write to file
			file.write(response.content)
			file.close()
		return fn

	def fetch_downloaded_content(self, doc):
		print('checking download worker output')
		try:
			possibles = self.handler.searchResult(doc._id, 'DOWNLOAD')
			print(possibles)
			return possibles[0].payload['file_path']
		except KeyError as e:
			print(e)

		return None

	def hash_string(self, s):
		return hashlib.sha224("{0}".format(s).encode('utf-8')).hexdigest()

	def submit_asr_job(self, input_file, input_hash):
		print('Going to submit {0} to the ASR service'.format(input_file))
		try:
			resp = requests.put('http://{0}:{1}/api/{2}/{3}?input_file={4}&wait_for_completion=0'.format(
				self.config.ASR_API.HOST,
				self.config.ASR_API.PORT,
				'process-simulation', #replace later with process
				input_hash,
				input_file
			))
		except requests.exceptions.ConnectionError as e:
			#print('Could not connect to the ASR container. Damn shame kid, but now we are going to fake it')
			#self.save_dummy_result(task)
			return {'state': 500, 'message': 'Failure: the ASR service failed to process your request'}

		print(resp.text)

		print('now waiting for the ASR job to finish')

		while(True):
			resp = requests.get('http://{0}:{1}/api/{2}/{3}'.format(
				self.config.ASR_API.HOST,
				self.config.ASR_API.PORT,
				'process-simulation', #replace later with process
				input_hash
			))
			status = json.loads(resp.text)['status']
			print(status)
			if status == 'finished':
				print('yay the job is done!')
				return {'state' : 200, 'message' : 'Successfully yielded a speech transcript for {0}'.format(input_file)}
			sleep(1)
		return {'state' : 500, 'message' : 'Failed to generate a speech transcript for {0}'.format(input_file)}

	#DANE callback function, called whenever there is a job for this worker
	def callback(self, task, doc):
		print('receiving a task from the DANE (mock) server!')
		print(task)
		print(doc)

		# step 1 (temporary, until DOWNLOAD depency accepts params to override download dir)
		input_file = self.fetch_downloaded_content(doc) if self.config.DOWNLOAD.USE_DANE_DOWNLOADER else None

		if input_file == None:
			print('The file was not downloaded by the DANE worker, downloading it myself...')
			input_file = self.download_content(doc)
			if input_file == None:
				return {'state' : 500, 'message' : 'Could not download the document content'}

		# step 2 create hash of input file to use for progress tracking
		input_hash = self.hash_string(input_file)

		# step 3
		result = self.submit_asr_job(input_file, input_hash)

		print(result)

		return result


		#print('PROCESSING TASK ON DOC')
		"""------------------------------------------------
		TO IMPLEMENT:
		- call the ASR via a GET. Get a file name back
		- keep checking the file for status update
		- (use https://medium.com/@aliasav/how-follow-a-file-in-python-tail-f-in-python-bca026a901cf)
		------------------------------------------------"""

	#mount/asr-output/1272-128104-0000
	def parse_asr_output(self):
		'mount/asr-output/1272-128104-0000'

	#TODO check how to generate the index document right here, so indexing it within the actual catalogue is much easier
	#NOTE for openbeelden, it should be indexed in the ODL on ES7 in the amazon cluster
	#NOTE for DAAN, it should be indexed within the ES5 cluster (for now)
	def save_dummy_result(self, task):
		r = Result(
			self.generator,
			payload={
				"wordTimes": [ 300,1710,1920,2100,2580,3390,3660,4260,5550,5880,6360,7200,7770,8220,8400,8490],
				"sequenceNr": 0,
				"start": 0,
				"fragmentId": "0001",
				"words": "Zojuist op haar laatste verjaardag als regerend vorstin heeft koningin juliana afstand gedaan van de troon.",
				"carrierId": "NIET_BEKEND__-AEN557540L7"
			},
			api=self.handler
		)
		# Now save the result
		r.save(task._id)

if __name__ == '__main__':
	w = asr_worker(cfg)

	print(' # Initialising worker. Ctrl+C to exit')
	try:
		w.run()
	except (KeyboardInterrupt, SystemExit):
		w.stop()

	"""
	#create some dummy task & document
	t = Task('ASR', priority=1, _id = None, api = None, state=None, msg=None)
	d = Document({
			'id' : '',
			'url' : '',
			'type' : 'Video'
		}, {
			'id' : '',
			'type' : 'Human'
		}, api=None, _id=None)

	#directly do the callback to test ASR without the DANE server
	w.callback(t, d)
	"""
