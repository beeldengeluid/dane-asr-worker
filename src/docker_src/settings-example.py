#debug service settings (settings.py)
APP_HOST = '0.0.0.0'
APP_PORT = 3023 #Note: also change start-container.sh if you change this value!

#MAIN_INPUT_DIR = '../../mount/input-files' when testing the process_api seperately
MAIN_INPUT_DIR = '/input-files' #when running the docker container

#asr module settings (asr.py)
ASR_OUTPUT_DIR = '/asr-output'
ASR_PACKAGE_NAME = 'asr-features.tar.gz'
ASR_WORD_JSON_FILE = 'words.json'

#(as module) kaldi NL base dir and the decoder script therein
KALDI_NL_DIR = '/usr/local/opt/kaldi_nl' #'/opt/Kaldi_NL'
KALDI_NL_DECODER = 'decode_OH.sh' #'decode.sh'

PID_CACHE_DIR = 'pid-cache' # relative from the server.py dir

LOG_DIR = "log" # relative from the server.py dir
LOG_NAME = "asr-service.log"
LOG_LEVEL_CONSOLE = "DEBUG" # Levels: NOTSET - DEBUG - INFO - WARNING - ERROR - CRITICAL
LOG_LEVEL_FILE = "DEBUG" # Levels: NOTSET - DEBUG - INFO - WARNING - ERROR - CRITICAL

#https://github.com/CLARIAH/DANE-server/blob/master/test/test_server.py
#https://github.com/CLARIAH/DANE/blob/master/examples/dane_example.ipynb
#https://github.com/CLARIAH/DANE/blob/master/examples/HTTP%20request%20example.ipynb