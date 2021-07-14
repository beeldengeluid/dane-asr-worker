import os
import ntpath
import shutil
import logging
import json
from time import sleep
from asr import run_asr, process_asr_output, create_word_json
from transcode import transcode_to_mp3
from config.settings import LOG_NAME, PID_CACHE_DIR

"""
This module contains all the specific processing functions for the DANE-asr-worker. The reason
to separate it from worker.py is so it can also be called via the server.py (debugging UI)

The processing consists of:
- validating the input file (provided by the download worker)
- if it is an audio file: simply run ASR (see module: asr.py)
- if not: first transcode it (see module: transcode.py)
- finally: package the ASR output into a tar.gz (optional)
"""

logger = logging.getLogger(LOG_NAME)

#simulates running ASR and/or transcoding, so the API communication can be tested in isolation
def run_simulation(pid, input_file_path, asynchronous=False):
	logger.debug('simlating ASR, but verifying the validity of the request params')
	logger.debug(input_file_path)

	#first write to the PID that the process is busy, then sleep for 5 seconds to simulate ASR/transcoding
	_write_pid_file_json(pid, {
		'state' : 200, 'message' : 'Simulation in progress'
	})
	if not os.path.isfile(input_file_path):  # check if inputfile exists
		return _resp_to_pid_file(pid, asynchronous, {
			'state': 404, 'message': 'No file found at file location {0}'.format(input_file_path)
		})
	else:
		sleep(5)
		return _resp_to_pid_file(pid, asynchronous, {
			'state' : 200, 'message' : 'Succesfully ran ASR on {0}'.format(input_file_path)
		})

#processes the input and keeps a PID file with status information in asynchronous mode
def process_input_file(pid, input_file_path, asynchronous=False):
	logger.debug('processing {} for PID={}'.format(input_file_path, pid))
	if not os.path.isfile(input_file_path):  # check if inputfile exists
		return _resp_to_pid_file(pid, asynchronous, {
			'state': 404, 'message': 'No file found at file location {0}'.format(input_file_path)
		})

	#grab the file_name from the path
	file_name = ntpath.basename(input_file_path)

	#split up the file in asset_id (used for creating a subfolder in the output) and extension
	asset_id, extension = os.path.splitext(file_name)

	#first assume the file is a valid audio file
	asr_input_path = input_file_path

	#check if the input file is a valid audio file, if not: transcode it first
	if not _is_audio_file(extension):
		if _is_transcodable(extension):
			asr_input_path = os.path.join(
				os.sep,
				os.path.dirname(input_file_path), #the dir the input file is in
				asset_id + ".mp3" #same name as input file, but with mp3 extension
			)
			transcode_to_mp3(
				input_file_path,
				asr_input_path #the transcode output is the input for the ASR
			)
		else:
			return _resp_to_pid_file(pid, asynchronous, {
				'state': 406,
				'message': 'Not acceptable: accepted file formats are; mov,mp4,m4a,3gp,3g2,mj2'
			})

	#run the ASR
	try:
		run_asr(asr_input_path, asset_id)
	except Exception as e:
		return _resp_to_pid_file(pid, asynchronous, {
			'state': 500,
			'message': 'Something went wrong when encoding the file: {0}'.format(e)
		})

	#finally process the ASR results and return the status message
	return _resp_to_pid_file(pid, asynchronous, process_asr_output(asset_id))

def poll_pid_status(pid):
	logger.debug('Getting status for pid {}'.format(pid))
	if not _pid_file_exists(pid):
		return {'state' : 404, 'message' : 'Error: PID does not exist (anymore)'}

	status = _read_pid_file(pid)
	try:
		return json.loads(status)
	except Exception as e:
		return {'state' : 500, 'message' : 'PID file was corrupted'}

def _is_audio_file(extension):
	return extension in ['.mp3', '.wav']

def _is_transcodable(extension):
	return extension in [".mov", ".mp4", ".m4a", ".3gp", ".3g2", ".mj2"]

#clean up input files
def _remove_files(path):
	for file in os.listdir(path):
		file_path = os.path.join(path, file)
		try:
			if os.path.isfile(file_path) or os.path.islink(file_path):
				os.unlink(file_path)
			elif os.path.isdir(file_path):
				shutil.rmtree(file_path)
		except Exception as e:
			print('Failed to delete {0}. Reason: {1}'.format(file_path, e))

"""-------------------------------------- PID FILE FUNCTIONS -----------------------------------------------"""

#writes the API response to the PID file, if the "ASR job" is running asynchronously
def _resp_to_pid_file(pid, asynchronous, resp):
	logger.debug(resp)
	if asynchronous:
		_write_pid_file_json(pid, resp)
	return resp

def _get_pid_file_name(pid):
	return '{}/{}'.format(PID_CACHE_DIR, pid)

def _pid_file_exists(pid):
	return os.path.exists(_get_pid_file_name(pid))

def _write_pid_file_json(pid, json_data):
	f  = open(_get_pid_file_name(pid), 'w+')
	f.write(json.dumps(json_data))
	f.close()

def _read_pid_file(pid):
	f  = open(_get_pid_file_name(pid), 'r')
	txt = ''
	for l in f.readlines():
		txt += l
	f.close()
	return txt