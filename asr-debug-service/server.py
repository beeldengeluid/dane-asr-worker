from flask import Flask
from flask import render_template
from flask import request, Response, url_for
import subprocess
import os

app = Flask(__name__)

#init the config
app.config.from_object('settings.Config')
app.debug = app.config['DEBUG']

"""------------------------------------------------------------------------------
PING / HEARTBEAT ENDPOINT
------------------------------------------------------------------------------"""

@app.route('/ping')
def ping():
	return Response('pong', mimetype='text/plain')

"""------------------------------------------------------------------------------
REGULAR ROUTING (STATIC CONTENT)
------------------------------------------------------------------------------"""
@app.route('/')
def home():
	return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
	input_file = request.form.get('input_file', None)
	print(request.form)
	file_name, extension = os.path.splitext(input_file)
	print(file_name)
	input_path = os.path.join(os.sep, 'input-files', input_file)
	print(input_path)
	print("Starting ASR... (debug)")
	cmd = "cd /opt/Kaldi_NL; ./decode.sh {0} /asr-output/{1}".format(input_path, file_name)
	print(cmd)
	process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
	stdout = process.communicate()[0]
	print(stdout)
	return Response(stdout, mimetype='text/plain')


if __name__ == '__main__':
	app.run(host=app.config['APP_HOST'], port=app.config['APP_PORT'])
