import DANE.base_classes
from DANE.config import cfg
from DANE import Result, Task, Document
import json
import os

from work_processor import process_input_file

"""
This class implements a DANE worker and thus serves as the process receiving tasks from DANE

This particular worker only picks up work from the ASR queue and only will go ahead with (ASR) processing
audiovisual input.

The input file is obtained by requesting the file path from the document index. This file path SHOULD have been
made available by the download worker (before the task was received in this worker)
"""

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

		self.config = config
		self.test_run()

	def test_run(self):
		print('DOING A TEST RUN')
		resp = process_input_file(os.path.join(os.sep, 'input-files', self.config.ASR.VIDEO_TEST_FILE))
		print(json.dumps(resp, indent=4, sort_keys=True))

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
		return process_input_file(vid_file)

if __name__ == '__main__':
	w = asr_worker(cfg)

	"""
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
	"""