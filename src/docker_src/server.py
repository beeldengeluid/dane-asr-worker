from flask import Flask
from flask import render_template
from flask import request, Response

import os
import json
from settings import APP_HOST, APP_PORT, PID_CACHE_DIR
from work_processor import process_input_file
from apis import api

app = Flask(__name__)
app.config['PID_CACHE_DIR'] = PID_CACHE_DIR

api.init_app(
	app,
	title='Beeld en Geluid ASR container',
    description='Access the speech transcription service within this docker container'
)

#decided to stick to OAS 2.0 after looking for good tools for supporting OAS 3.0. It
#seems it is smart to wait a bit for better support: https://developer.acronis.com/blog/posts/raml-vs-swagger/
#Note: you can check support pretty well with https://editor.swagger.io/

"""------------------------------------------------------------------------------
PING / HEARTBEAT ENDPOINT
------------------------------------------------------------------------------"""

@app.route('/ping')
def ping():
	return Response('pong', mimetype='text/plain')

"""------------------------------------------------------------------------------
REGULAR ROUTING (STATIC CONTENT)
------------------------------------------------------------------------------"""
@app.route('/debug')
def home():
	return render_template('index.html')

@app.route('/process-debug', methods=['POST'])
def debug():
	input_file = request.form.get('input_file', None)
	resp = process_input_file(os.path.join(os.sep, 'input-files', input_file))
	return Response(json.dumps(resp), mimetype='application/json')

if __name__ == '__main__':
	app.run(host=APP_HOST, port=APP_PORT)
