import DANE.base_classes
from DANE.config import cfg
from DANE import Result, Task, Document
import json
import os
import subprocess #used for calling cmd line to check if the required docker containers are up
import requests #for communicating with the ASR container's API
from urllib.parse import urlparse, unquote
from time import sleep
import hashlib
import codecs
import ntpath

#from work_processor import process_input_file

"""
This class implements a DANE worker and thus serves as the process receiving tasks from DANE

This particular worker only picks up work from the ASR queue and only will go ahead with (ASR) processing
audiovisual input.

The input file is obtained by requesting the file path from the document index. This file path SHOULD have been
made available by the download worker (before the task was received in this worker)

TODO catch pika.exceptions.ConnectionClosedByBroker in case the rabbitMQ is not available
TODO maybe use https://medium.com/@aliasav/how-follow-a-file-in-python-tail-f-in-python-bca026a901cf
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
		#self.__depends_on = [{ 'key': 'DOWNLOAD', 'some_arg': 'bla' }]

		self.SIMULATE_ASR_SERVICE = config.ASR_API.SIMULATE

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
			self.SIMULATE_ASR_SERVICE = True
			print('ERROR: Could not start speech recognition service, continuing in simulation mode')
			#quit()

		super().__init__(
			self.__queue_name,
			self.__binding_key,
			config,
			self.__depends_on,
			True, #auto_connect
			False #no_api
		)

	"""----------------------------------INIT VALIDATION FUNCTIONS ---------------------------------"""

	#TODO implement actual validation
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

	"""----------------------------------INTERACTION WITH DANE SERVER ---------------------------------"""

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

		# step 3 submit the input file to the ASR service
		asr_result = self.submit_asr_job(input_file, input_hash)
		print(asr_result)

		# step 4 generate a transcript from the ASR service's output
		if asr_result['state'] == 200:
			#TODO change this, harmonize the asset ID with the process ID (pid)
			transcript = self.asr_output_to_transcript(self.get_asr_output_dir(self.get_asset_id(input_file)))
			if transcript:
				self.save_to_dane_index(task, transcript)
				return {'state' : 200, 'message' : 'Successfully generated a transcript file from the ASR service output'}
			else:
				return {'state' : 500, 'message' : 'Failed to generate a transcript file from the ASR service output'}

		#something went wrong inside the ASR service, return that response here
		return asr_result

	#Note: the supplied transcript is EXACTLY the same as what we use in layer__asr in the collection indices,
	#meaning it should be quite trivial to append the DANE output into a collection
	def save_to_dane_index(self, task, transcript):
		print('saving results to DANE, task id={0}'.format(task._id))
		#TODO figure out the multiple lines per transcript (refresh my memory)
		r = Result(self.generator, payload={'transcript' : transcript}, api=self.handler)
		r.save(task._id)

	"""----------------------------------ID MANAGEMENT FUNCTIONS ---------------------------------"""

	#the file name without extension is used as an asset ID by the ASR container to save the results
	def get_asset_id(self, input_file):
		#grab the file_name from the path
		file_name = ntpath.basename(input_file)

		#split up the file in asset_id (used for creating a subfolder in the output) and extension
		asset_id, extension = os.path.splitext(file_name)
		return asset_id

	def get_asr_output_dir(self, asset_id):
		return os.path.join(self.config.ASR_API.OUTPUT_DIR, asset_id)

	def hash_string(self, s):
		return hashlib.sha224("{0}".format(s).encode('utf-8')).hexdigest()

	"""----------------------------------DOWNLOAD FUNCTIONS ---------------------------------"""

	# https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4
	def download_content(self, doc):
		if not doc.target or not 'url' in doc.target or not doc.target['url']:
			print('No url found in DANE doc')
			return None

		print('downloading {}'.format(doc.target['url']))
		fn = os.path.basename(urlparse(doc.target['url']).path)
		fn = unquote(fn)
		#fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
		output_file = os.path.join(self.config.DOWNLOAD.LOCAL_DIR, fn)
		print('saving to file {}'.format(fn))

		# download if the file is not present (preventing unnecessary downloads)
		if not os.path.exists(output_file):
			with open(output_file, "wb") as file:
				response = requests.get(doc.target['url'])
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

	"""----------------------------------INTERACT WITH ASR SERVIVCE (DOCKER CONTAINER) --------------------------"""

	def submit_asr_job(self, input_file, input_hash):
		print('Going to submit {} to the ASR service, using PID={}'.format(input_file, input_hash))
		try:
			dane_asr_api_url = 'http://{}:{}/api/{}/{}?input_file={}&wait_for_completion={}&simulate={}'.format(
				self.config.ASR_API.HOST,
				self.config.ASR_API.PORT,
				'process', #replace with process_debug to debug(?)
				input_hash,
				input_file,
				'1' if self.config.ASR_API.WAIT_FOR_COMPLETION else '0',
				'1' if self.SIMULATE_ASR_SERVICE else '0'
			)
			print(dane_asr_api_url)
			resp = requests.put(dane_asr_api_url)
		except requests.exceptions.ConnectionError as e:
			return {'state': 500, 'message': 'Failure: could not connect to the ASR service'}

		#return the result right away if in synchronous mode
		if self.config.ASR_API.WAIT_FOR_COMPLETION:
			if resp.status_code == 200:
				print('The ASR service is done, returning the results')
				data = json.loads(resp.text)
				return data
			else:
				print('error returned')
				print(resp.text)
				return {'state': 500, 'message': 'Failure: the ASR service returned an error'}

		#else start polling the ASR service, using the input_hash for reference (TODO synch with asset_id)
		print('Polling the ASR service to check when it is finished')
		while(True):
			resp = requests.get('http://{0}:{1}/api/{2}/{3}'.format(
				self.config.ASR_API.HOST,
				self.config.ASR_API.PORT,
				'process', #replace later with process
				input_hash
			))
			process_msg = json.loads(resp.text)

			msg = process_msg['message'] if 'message' in process_msg else 'Error: no valid message received from ASR'
			state = process_msg['state'] if 'state' in process_msg else 500
			finished = process_msg['finished'] if 'finished' in process_msg else False

			if finished:
				return {'state' : 200, 'message' : 'The ASR service generated valid output {}'.format(input_file)}
			elif state == 500:
				return {'state' : 500, 'message' : 'The ASR failed to produce the required output {}'.format(input_file)}
			elif state == 404:
				return {'state' : 404, 'message' : 'The ASR failed to find the required input {}'.format(input_file)}

			#wait for one second before polling again
			sleep(1)

		return {'state' : 500, 'message' : 'The ASR failed to produce the required output {}'.format(input_file)}

	"""----------------------------------PROCESS ASR OUTPUT (DOCKER MOUNT) --------------------------"""

	#mount/asr-output/1272-128104-0000
	def asr_output_to_transcript(self, asr_output_dir):
		print('generating a transcript from the ASR output in: {0}'.format(asr_output_dir))
		transcriptions = None
		if os.path.exists(asr_output_dir):
			try:
				with codecs.open(os.path.join(asr_output_dir, '1Best.ctm'), encoding="utf-8") as times_file:
					times = self.__extractTimeInfo(times_file)

				with codecs.open(os.path.join(asr_output_dir, '1Best.txt'), encoding="utf-8") as asr_file:
					transcriptions = self.__parseASRResults(asr_file, times)
			except EnvironmentError as e:  # OSError or IOError...
				print(os.strerror(e.errno))

			# Clean up the extracted dir
			#shutil.rmtree(asr_output_dir)
			#print("Cleaned up folder {}".format(asr_output_dir))
		else:
			print('Error: cannot generate transcript; ASR output dir does not exist')

		return transcriptions

	def __parseASRResults(self, asr_file, times):
		transcriptions = []
		i = 0
		cur_pos = 0

		for line in asr_file:
			parts = line.replace('\n', '').split("(")

			# extract the text
			words = parts[0].strip()
			num_words = len(words.split(" "))
			word_times = times[cur_pos:cur_pos+num_words]
			cur_pos = cur_pos+num_words

			# Check number of words matches the number of word_times
			if not len(word_times) == num_words:
				print("Number of words does not match word-times for file: {}, "
							   "current position in file: {}".format(asr_file.name, cur_pos))

			# extract the carrier and fragment ID
			carrier_fragid = parts[1].split(" ")[0].split(".")
			carrier = carrier_fragid[0]
			fragid = carrier_fragid[1]

			# extract the starttime
			sTime = parts[1].split(" ")[1].replace(")", "")
			sTime = sTime.split(".")
			starttime = int(sTime[0]) * 1000

			subtitle = {
				'words': words,
				'wordTimes': word_times,
				'start': float(starttime),
				'sequenceNr': i,
				'fragmentId': fragid,
				'carrierId': carrier
			}
			transcriptions.append(subtitle)
			i += 1
		return transcriptions

	def __extractTimeInfo(self, times_file):
		times = []

		for line in times_file:
			time_string = line.split(" ")[2]
			ms_value = int(float(time_string)*1000)
			times.append(ms_value)

		return times


# Start the worker
if __name__ == '__main__':
	w = asr_worker(cfg)
	print(' # Initialising worker. Ctrl+C to exit')
	try:
		w.run()
	except (KeyboardInterrupt, SystemExit):
		w.stop()
