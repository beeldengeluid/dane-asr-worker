import DANE.base_classes
from DANE.config import cfg
from DANE import Result, Task, Document
import json
import os
import tarfile
import subprocess
import shutil
import glob

class asr_worker(DANE.base_classes.base_worker):

	def __init__(self, config):
		 # we specify a queue name because every worker of this type should
		# listen to the same queue
		self.__queue_name = 'ASR'
		self.__binding_key = '#.ASR'#['Video.ASR', 'Sound.ASR']
		self.__depends_on = ['DOWNLOAD']

		"""
		super().__init__(
			queue=self.__queue_name,
			binding_key=self.__binding_key,
			depends_on=self.__depends_on,
			config=config
		)
		"""

		#self.vid_file = '/Users/jblom/temp/asr_test.mp4'
		self.config = config
		self.test_run()

	def test_run(self):
		print('Going to try things out on the video test file')
		file = self.config.ASR.VIDEO_TEST_FILE

		file_name, extension = os.path.splitext(file)


		# input folder
		file_path = os.path.join(os.sep, 'input-files', file)

		if not os.path.isfile(file_path):  # check if inputfile exists
			return json.dumps({'state': 404,
							   'message': 'No file found at file location'})

		if extension in ['.mp3', '.wav']:
			# continue if its already a audio file
			asr_input = file_path

		else:
			# encode video to audio
			asr_input = os.path.join(os.sep, 'asr-input', file_name + ".mp3")

			if extension not in [".mov", ".mp4", ".m4a", ".3gp", ".3g2", ".mj2"]:
				print(json.dumps({
					'state': 406,
					'message': 'Not acceptable: accepted file formats are; mov,mp4,m4a,3gp,3g2,mj2'
				}))
			try:
				self.prepare_file(file_path, asr_input)
				print("Encoding Done")
			except Exception as e:
				print(json.dumps({
					'state': 500,
					'message': 'Something went wrong when encoding the file: {0}'.format(e)
				}))

		# Do ASR
		try:
			self.asr(asr_input)
			print("Asr Done")
		except Exception as e:
			print(json.dumps({
				'state': 500,
				'message': 'Something went wrong during the ASR: {0}'.format(e)
			}))

		# Process ASR results
		if self.process_results(file_name):
			print(json.dumps({'state': 200, 'message': 'Success'}))


	#DANE callback function, called whenever there is a job for this worker
	def callback(self, task, doc):
		"""
		try:
			possibles = self.handler.searchResult(doc._id, 'DOWNLOAD')
			vid_file = possibles[0].payload['file_path']
		except KeyError as e:
			return {'state': 500,
				'message': "No DOWNLOAD result found"}
		"""
		#print('processing video file %s' % self.config.ASR.VIDEO_TEST_FILE)
		print('calling back')
		print(self.config.ASR.VIDEO_TEST_FILE)

	def asr(self, input_path):
		print("Starting asr")
		cmd = "cd /opt/Kaldi_NL; ./decode.sh {0} /asr-output/".format(input_path)
		print(cmd)
		process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
		stdout = process.communicate()[0]  # wait until finished. Remove stdout stuff if letting run in background and continue.

	def process_results(self, original_file):
		if not os.path.isfile(os.path.join(os.sep, 'asr-output', '1Best.ctm')):

			self.remove_files(os.path.join(os.sep, 'asr-output'))
			self.remove_files(os.path.join(os.sep, 'asr-input'))

			print(json.dumps({
				'state': 501,
				'message': 'Fail - decoded without 1best'
			}))
			return False

		files_to_be_added = [
			'/asr-output/liumlog/*.seg',
			'/asr-output/1Best.*',
			'/asr-output/intermediate/decode/*'
		]

		tar_path = os.path.join(os.sep, 'asr-output', original_file + "asr_features.tar.gz")
		tar = tarfile.open(tar_path, "w:gz")

		for pattern in files_to_be_added:
			for file_path in glob.glob(pattern):
				path, file_name = os.path.split(file_path)
				tar.add(file_path, arcname=file_name)

		tar.close()

		# TODO Send tar with features somewhere
		### TEMP FOR RESEARCH
		word_json = self.create_word_json(os.path.join(os.sep, 'asr-output', '1Best.ctm'))
		file_destination = os.path.join(os.sep, 'input-files', 'Videos', original_file, original_file + "_asr.json")

		with open(file_destination, 'w') as outfile:
			json.dump(word_json, outfile, indent=4)


		self.remove_files(os.path.join(os.sep, 'asr-output'))
		self.remove_files(os.path.join(os.sep, 'asr-input'))
		return True

	def create_word_json(self, transcript):
		word_json = []
		with open(transcript, encoding='utf-8', mode='r') as file:
			for line in file.readlines():
				data = line.split(' ')

				start_time = float(data[2]) * 1000  # in millisec
				mark = data[4]
				json_entry = {
					"start": start_time,
					"words": mark
				}
				word_json.append(json_entry)

		return word_json

	#clean up input files
	def remove_files(self, path):
		for file in os.listdir(path):
			file_path = os.path.join(path, file)
			try:
				if os.path.isfile(file_path) or os.path.islink(file_path):
					os.unlink(file_path)
				elif os.path.isdir(file_path):
					shutil.rmtree(file_path)
			except Exception as e:
				print('Failed to delete {0}. Reason: {1}'.format(file_path, e))

	#TRANSOCDE VIDEO FILE INTO MP3
	def prepare_file(self, path, asr_path):
		print("Encoding file")
		cmd = "ffmpeg -i {0} {1}".format(path, asr_path)
		print(cmd)
		process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
		stdout = process.communicate()[0] # wait until finished. Remove stdout stuff if letting run in background and continue.

if __name__ == '__main__':
	w = asr_worker(cfg)

	#create some dummy task & document
	t = Task('Video.ASR', priority=1, _id = None, api = None, state=None, msg=None)
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

