#debug service settings (settings.py)
APP_HOST = '0.0.0.0'
APP_PORT = 3023 #Note: also change start-container.sh if you change this value!

#asr module settings (asr.py)
ASR_OUTPUT_DIR = 'asr-output'
ASR_PACKAGE_NAME = 'asr-features.tar.gz'
ASR_WORD_JSON_FILE = 'words.json'

#(as module) kaldi NL base dir and the decoder script therein
KALDI_NL_DIR = '/usr/local/opt/kaldi_nl' #'/opt/Kaldi_NL'
KALDI_NL_DECODER = 'decode_OH.sh' #'decode.sh'

#https://github.com/CLARIAH/DANE-server/blob/master/test/test_server.py
#https://github.com/CLARIAH/DANE/blob/master/examples/dane_example.ipynb
#https://github.com/CLARIAH/DANE/blob/master/examples/HTTP%20request%20example.ipynb