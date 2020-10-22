from flask import Flask
from flask import render_template
from flask import request, Response

import os
import json
from settings import APP_HOST, APP_PORT
from work_processor import process_input_file

app = Flask(__name__)

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
	resp = process_input_file(os.path.join(os.sep, 'input-files', input_file))
	return Response(json.dumps(resp), mimetype='application/json')

if __name__ == '__main__':
	app.run(host=APP_HOST, port=APP_PORT)
