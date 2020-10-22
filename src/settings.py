#debug service settings (settings.py)
APP_HOST = '0.0.0.0'
APP_PORT = 5000 #Note: also change start-container.sh if you change this value!

#asr module settings (asr.py)
ASR_OUTPUT_DIR = 'asr-output'
ASR_PACKAGE_NAME = 'asr-features.tar.gz'
ASR_WORD_JSON_FILE = 'words.json'