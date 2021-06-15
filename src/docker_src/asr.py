import subprocess
import os
import tarfile
import glob
import json

from settings import ASR_OUTPUT_DIR, ASR_PACKAGE_NAME, ASR_WORD_JSON_FILE, KALDI_NL_DIR, KALDI_NL_DECODER

"""
This module contains functions for running audio files through Kaldi_NL to generate a speech transcript.

Moreover this module has functions for:
- validating the ASR output
- generating a JSON file (based on the 1Best.ctm transcript file)
- packaging the ASR output (as a tar)

"""
ASR_TRANSCRIPT_FILE = '1Best.ctm'

#runs the asr on the input path and puts the results in the ASR_OUTPUT_DIR dir
def run_asr(input_path, asset_id):
	print("Starting ASR")
	cmd = "cd {0}; ./{1} {2} /{3}/{4}".format(
		KALDI_NL_DIR,
		KALDI_NL_DECODER,
		input_path,
		ASR_OUTPUT_DIR,
		asset_id
	)
	print(cmd)
	process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
	stdout = process.communicate()[0]  # wait until finished. Remove stdout stuff if letting run in background and continue.
	print(stdout)
	return stdout


def process_asr_output(asset_id):
	print('processing the output of {}'.format(asset_id))

	if validate_asr_output(asset_id) == False:
		return {'state': 500, 'message': 'error: ASR output did not yield a transcript file'}

	#create a word.json file
	create_word_json(asset_id, True)

	#package the output
	package_output(asset_id)

	#package the features and json file, so it can be used for indexing or something else
	return {'state': 200, 'message': 'Successfully processed {}'.format(asset_id), 'finished' : True}

#if there is no 1Best.ctm there is something wrong with the input file or Kaldi...
#TODO also check if the files and dir for package_output are there
def validate_asr_output(asset_id):
	return os.path.isfile(__get_transcript_file_path(asset_id))

#packages the features and the human readable output (1Best.*)
def package_output(asset_id):
	output_dir = get_output_dir(asset_id)
	files_to_be_added = [
		'/{0}/liumlog/*.seg'.format(output_dir),
		'/{0}/1Best.*'.format(output_dir),
		'/{0}/intermediate/decode/*'.format(output_dir)
	]

	#also add the words json file if it was generated
	if os.path.exists(__get_words_file_path(asset_id)):
		files_to_be_added.append(__get_words_file_path(asset_id))

	tar_path = os.path.join(os.sep, output_dir, ASR_PACKAGE_NAME)
	tar = tarfile.open(tar_path, "w:gz")

	for pattern in files_to_be_added:
		for file_path in glob.glob(pattern):
			path, asset_id = os.path.split(file_path)
			tar.add(file_path, arcname=asset_id)

	tar.close()

def create_word_json(asset_id, save_in_asr_output=False):
	transcript = __get_transcript_file_path(asset_id)
	word_json = []
	with open(transcript, encoding='utf-8', mode='r') as file:
		for line in file.readlines():
			print(line)
			data = line.split(' ')

			start_time = float(data[2]) * 1000  # in millisec
			mark = data[4]
			json_entry = {
				"start": start_time,
				"words": mark
			}
			word_json.append(json_entry)

	if save_in_asr_output:
		with open(__get_words_file_path(asset_id), 'w+') as outfile:
			json.dump(word_json, outfile, indent=4)

	print(json.dumps(word_json, indent=4, sort_keys=True))
	return word_json

def get_output_dir(asset_id):
	return os.path.join(os.sep, ASR_OUTPUT_DIR, asset_id)

def __get_transcript_file_path(asset_id):
	return os.path.join(os.sep, get_output_dir(asset_id), ASR_TRANSCRIPT_FILE)

def __get_words_file_path(asset_id):
	return os.path.join(os.sep, get_output_dir(asset_id), ASR_WORD_JSON_FILE)
