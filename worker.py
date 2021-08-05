import DANE.base_classes
from DANE.config import cfg
from DANE import Result, Task, Document

import os
import codecs
import ntpath
from pathlib import Path
import json
import requests #for communicating with the ASR container's API
from urllib.parse import urlparse, unquote, quote
from time import sleep
import hashlib
import logging
from logging.handlers import TimedRotatingFileHandler

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
		self.logger = self.init_logger(config)
		self.logger.debug(config)

		# first make sure the config has everything we need
		# Note: base_config is loaded first by DANE, so make sure you overwrite everything in your config.yml!
		try:
			# put all of the relevant settings in a variable
			self.USE_DANE_DOWNLOADER: bool = config.FILE_SYSTEM.USE_DANE_DOWNLOADER
			self.BASE_MOUNT: str = config.FILE_SYSTEM.BASE_MOUNT

			# construct the input & output paths using the base mount as a parent dir
			self.ASR_INPUT_DIR: str = os.path.join(self.BASE_MOUNT, config.FILE_SYSTEM.INPUT_DIR)
			self.ASR_OUTPUT_DIR: str = os.path.join(self.BASE_MOUNT, config.FILE_SYSTEM.OUTPUT_DIR)

			# ASR API settings
			self.ASR_API_HOST: str = config.ASR_API.HOST
			self.ASR_API_PORT: int = config.ASR_API.PORT
			self.ASR_API_WAIT_FOR_COMPLETION: bool = config.ASR_API.WAIT_FOR_COMPLETION
			self.ASR_API_SIMULATE: bool = config.ASR_API.SIMULATE
		except AttributeError as e:
			self.logger.error('Missing configuration setting')
			quit()

		# check if the main
		if not self.validate_data_dirs(self.ASR_INPUT_DIR, self.ASR_OUTPUT_DIR):
			self.logger.debug('ERROR: data dirs not configured properly')
			quit()

		# we specify a queue name because every worker of this type should
		# listen to the same queue
		self.__queue_name = 'ASR' #this is the queue that receives the work and NOT the reply queue
		self.__binding_key = "#.ASR" #['Video.ASR', 'Sound.ASR']#'#.ASR'
		self.__depends_on = ['DOWNLOAD']
		#['DOWNLOAD'] TODO Nanne will support adding params to this, so it's possible to override the default Task being generated for the downloader
		#self.__depends_on = [{ 'key': 'DOWNLOAD', 'some_arg': 'bla' }]

		#TODO check if the ASR service is available

		super().__init__(
			self.__queue_name,
			self.__binding_key,
			config,
			self.__depends_on,
			True, #auto_connect
			False #no_api
		)

	def init_logger(self, config):
		logger = logging.getLogger('DANE-ASR')
		logger.setLevel(config.LOGGING.LEVEL)
		# create file handler which logs to file
		if not os.path.exists(os.path.realpath(config.LOGGING.DIR)):
			os.makedirs(os.path.realpath(config.LOGGING.DIR), exist_ok=True)

		fh = TimedRotatingFileHandler(os.path.join(
			os.path.realpath(config.LOGGING.DIR), "DANE-ASR-worker.log"),
			when='W6', # start new log on sunday
			backupCount=3)
		fh.setLevel(config.LOGGING.LEVEL)
		# create console handler
		ch = logging.StreamHandler()
		ch.setLevel(config.LOGGING.LEVEL)
		# create formatter and add it to the handlers
		formatter = logging.Formatter(
				'%(asctime)s - %(levelname)s - %(message)s',
				"%Y-%m-%d %H:%M:%S")
		fh.setFormatter(formatter)
		ch.setFormatter(formatter)
		# add the handlers to the logger
		logger.addHandler(fh)
		logger.addHandler(ch)
		return logger

	"""----------------------------------INIT VALIDATION FUNCTIONS ---------------------------------"""

	def validate_data_dirs(self, asr_input_dir: str, asr_output_dir: str):
	    i_dir = Path(asr_input_dir)
	    o_dir = Path(asr_output_dir)

	    if not os.path.exists(i_dir.parent.absolute()):
	        self.logger.debug('{} does not exist. Make sure BASE_MOUNT_DIR exists before retrying'.format(
	            i_dir.parent.absolute())
	        )
	        return False

	    #make sure the input and output dirs are there
	    try:
	        os.makedirs(i_dir, 0o755)
	        self.logger.debug('created ASR input dir: {}'.format(i_dir))
	    except FileExistsError as e:
	        self.logger.debug(e)

	    try:
	        os.makedirs(o_dir, 0o755)
	        self.logger.debug('created ASR output dir: {}'.format(o_dir))
	    except FileExistsError as e:
	        self.logger.debug(e)

	    return True

	"""----------------------------------INTERACTION WITH DANE SERVER ---------------------------------"""

	#DANE callback function, called whenever there is a job for this worker
	def callback(self, task, doc):
		self.logger.debug('receiving a task from the DANE (mock) server!')
		self.logger.debug(task)
		self.logger.debug(doc)

		# step 1 (temporary, until DOWNLOAD depency accepts params to override download dir)
		input_file = self.fetch_downloaded_content(doc) if self.USE_DANE_DOWNLOADER else None

		if input_file == None:
			self.logger.debug('The file was not downloaded by the DANE worker, downloading it myself...')
			input_file = self.download_content(doc)
			if input_file == None:
				return {'state' : 500, 'message' : 'Could not download the document content'}

		# step 2 create hash of input file to use for progress tracking
		input_hash = self.hash_string(input_file)

		# step 3 submit the input file to the ASR service
		asr_result = self.submit_asr_job(input_file, input_hash)
		self.logger.debug(asr_result)

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
		self.logger.debug('saving results to DANE, task id={0}'.format(task._id))
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
		self.logger.debug('working with this asset ID {}'.format(asset_id))
		return asset_id

	def get_asr_output_dir(self, asset_id):
		return os.path.join(self.ASR_OUTPUT_DIR, asset_id)

	def hash_string(self, s):
		return hashlib.sha224("{0}".format(s).encode('utf-8')).hexdigest()

	"""----------------------------------DOWNLOAD FUNCTIONS ---------------------------------"""

	# https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4
	def download_content(self, doc):
		if not doc.target or not 'url' in doc.target or not doc.target['url']:
			self.logger.debug('No url found in DANE doc')
			return None

		self.logger.debug('downloading {}'.format(doc.target['url']))
		fn = os.path.basename(urlparse(doc.target['url']).path)
		#fn = unquote(fn)
		#fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
		output_file = os.path.join(self.ASR_INPUT_DIR, fn)
		self.logger.debug('saving to file {}'.format(fn))

		# download if the file is not present (preventing unnecessary downloads)
		if not os.path.exists(output_file):
			with open(output_file, "wb") as file:
				response = requests.get(doc.target['url'])
				file.write(response.content)
				file.close()
		return fn

	#TODO make sure this works
	def fetch_downloaded_content(self, doc):
		self.logger.debug('checking download worker output')
		try:
			possibles = self.handler.searchResult(doc._id, 'DOWNLOAD')
			self.logger.debug(possibles)
			return possibles[0].payload['file_path']
		except KeyError as e:
			self.logger.debug(e)

		return None

	"""----------------------------------INTERACT WITH ASR SERVIVCE (DOCKER CONTAINER) --------------------------"""

	def submit_asr_job(self, input_file, input_hash):
		self.logger.debug('Going to submit {} to the ASR service, using PID={}'.format(input_file, input_hash))
		try:
			dane_asr_api_url = 'http://{}:{}/api/{}/{}?input_file={}&wait_for_completion={}&simulate={}'.format(
				self.ASR_API_HOST,
				self.ASR_API_PORT,
				'process', #replace with process_debug to debug(?)
				input_hash,
				input_file,
				'1' if self.ASR_API_WAIT_FOR_COMPLETION else '0',
				'1' if self.ASR_API_SIMULATE else '0'
			)
			self.logger.debug(dane_asr_api_url)
			resp = requests.put(dane_asr_api_url)
		except requests.exceptions.ConnectionError as e:
			self.logger.error(e)
			return {'state': 500, 'message': 'Failure: could not connect to the ASR service'}

		#return the result right away if in synchronous mode
		if self.ASR_API_WAIT_FOR_COMPLETION:
			if resp.status_code == 200:
				self.logger.debug('The ASR service is done, returning the results')
				data = json.loads(resp.text)
				return data
			else:
				self.logger.debug('error returned')
				self.logger.debug(resp.text)
				return {'state': 500, 'message': 'Failure: the ASR service returned an error'}

		#else start polling the ASR service, using the input_hash for reference (TODO synch with asset_id)
		self.logger.debug('Polling the ASR service to check when it is finished')
		while(True):
			resp = requests.get('http://{0}:{1}/api/{2}/{3}'.format(
				self.ASR_API_HOST,
				self.ASR_API_PORT,
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
		self.logger.debug('generating a transcript from the ASR output in: {0}'.format(asr_output_dir))
		transcriptions = None
		if os.path.exists(asr_output_dir):
			try:
				with codecs.open(os.path.join(asr_output_dir, '1Best.ctm'), encoding="utf-8") as times_file:
					times = self.__extractTimeInfo(times_file)

				with codecs.open(os.path.join(asr_output_dir, '1Best.txt'), encoding="utf-8") as asr_file:
					transcriptions = self.__parseASRResults(asr_file, times)
			except EnvironmentError as e:  # OSError or IOError...
				self.logger.debug(os.strerror(e.errno))

			# Clean up the extracted dir
			#shutil.rmtree(asr_output_dir)
			#self.logger.debug("Cleaned up folder {}".format(asr_output_dir))
		else:
			self.logger.debug('Error: cannot generate transcript; ASR output dir does not exist')

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
				self.logger.debug("Number of words does not match word-times for file: {}, "
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
	try:
		w.run()
	except (KeyboardInterrupt, SystemExit):
		w.stop()
