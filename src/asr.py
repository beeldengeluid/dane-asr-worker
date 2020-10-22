import subprocess
import os
import tarfile
import glob
import json

ASR_INPUT = 'asr-input'
ASR_OUTPUT = 'asr-output'
ASR_PACKAGE_NAME = 'asr-features.tar.gz'

#runs the asr on the input path and puts the results in the ASR_OUTPUT dir
def run_asr(input_path, asset_id):
	print("Starting ASR")
	cmd = "cd /opt/Kaldi_NL; ./decode.sh {0} /{1}/{2}".format(input_path, ASR_OUTPUT, asset_id)
	print(cmd)
	process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
	stdout = process.communicate()[0]  # wait until finished. Remove stdout stuff if letting run in background and continue.
	print(stdout)
	return stdout


def process_asr_output(asset_id):
	print('processing the output of {0}'.format(asset_id))

	if validate_asr_output(asset_id) == False:
		return {'state': 500, 'message': 'error: ASR output did not contain a 1Best.ctm file'}

	#create a word.json file
	create_word_json(asset_id, True)

	#package the features and json file, so it can be used for indexing or something else
	return {'state': 200, 'message': 'Successfully processed {0}'.format(asset_id)}

#if there is no 1Best.ctm there is something wrong with the input file or Kaldi...
#TODO also check if the files and dir for package_output are there
def validate_asr_output(asset_id):
	return os.path.isfile(__to_transcript_path(asset_id))

#packages the features and the human readable output (1Best.*)
def package_output(asset_id):
	files_to_be_added = [
		'/{0}/{1}/liumlog/*.seg'.format(ASR_OUTPUT, asset_id),
		'/{0}/{1}/1Best.*'.format(ASR_OUTPUT, asset_id),
		'/{0}/{1}/intermediate/decode/*'.format(ASR_OUTPUT, asset_id)
	]

	tar_path = os.path.join(os.sep, ASR_OUTPUT, asset_id + ASR_PACKAGE_NAME)
	tar = tarfile.open(tar_path, "w:gz")

	for pattern in files_to_be_added:
		for file_path in glob.glob(pattern):
			path, asset_id = os.path.split(file_path)
			tar.add(file_path, arcname=asset_id)

	tar.close()

def create_word_json(asset_id, save_in_asr_output=False):
	transcript = __to_transcript_path(asset_id)
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
		with open(os.path.join(os.sep, ASR_OUTPUT, asset_id, asset_id + "_asr.json"), 'w+') as outfile:
			json.dump(word_json, outfile, indent=4)

	print(json.dumps(word_json, indent=4, sort_keys=True))
	return word_json

def __to_transcript_path(asset_id):
	return os.path.join(os.sep, ASR_OUTPUT, asset_id, '1Best.ctm')