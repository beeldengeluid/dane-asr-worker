import subprocess

"""
This module supplies the function for transcoding valid video files into mp3 format (i.e. valid input for Kaldi)
"""

def transcode_to_mp3(path, asr_path):
	print("Encoding file")
	cmd = "ffmpeg -i {0} {1}".format(path, asr_path)
	print(cmd)
	process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
	stdout = process.communicate()[0] # wait until finished. Remove stdout stuff if letting run in background and continue.
