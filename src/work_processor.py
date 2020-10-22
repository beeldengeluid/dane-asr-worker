import os
import ntpath
import shutil
from asr import run_asr, process_asr_output, create_word_json
from transcode import transcode_to_mp3

"""
This module contains all the specific processing functions for the DANE-asr-worker. The reason
to separate it from worker.py is so it can also be called via the server.py (debugging UI)

The processing consists of:
- validating the input file (provided by the download worker)
- if it is an audio file: simply run ASR (see module: asr.py)
- if not: first transcode it (see module: transcode.py)
- finally: package the ASR output into a tar.gz (optional)
"""

def process_input_file(input_file_path):
	print('analyzing the input file path')

	if not os.path.isfile(input_file_path):  # check if inputfile exists
		return {'state': 404, 'message': 'No file found at file location'}

	#grab the file_name from the path
	file_name = ntpath.basename(input_file_path)

	#split up the file in asset_id (used for creating a subfolder in the output) and extension
	asset_id, extension = os.path.splitext(file_name)

	#first assume the file is a valid audio file
	asr_input_path = input_file_path

	#check if the input file is a valid audio file, if not: transcode it first
	if not is_audio_file(extension):
		if is_transcodable(extension):
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
			return {
				'state': 406,
				'message': 'Not acceptable: accepted file formats are; mov,mp4,m4a,3gp,3g2,mj2'
			}

	#run the ASR
	try:
		run_asr(asr_input_path, asset_id)
	except Exception as e:
		return {
			'state': 500,
			'message': 'Something went wrong when encoding the file: {0}'.format(e)
		}

	#finally process the ASR results and return the status message
	return process_asr_output(asset_id)

def is_audio_file(extension):
	return extension in ['.mp3', '.wav']

def is_transcodable(extension):
	return extension in [".mov", ".mp4", ".m4a", ".3gp", ".3g2", ".mj2"]

#clean up input files
def remove_files(path):
	for file in os.listdir(path):
		file_path = os.path.join(path, file)
		try:
			if os.path.isfile(file_path) or os.path.islink(file_path):
				os.unlink(file_path)
			elif os.path.isdir(file_path):
				shutil.rmtree(file_path)
		except Exception as e:
			print('Failed to delete {0}. Reason: {1}'.format(file_path, e))