PWD=`pwd`

docker run --rm -v $PWD/mount/input-files:/input-files \
	-v $PWD/mount/output-files:/output-files \
	-v $PWD/mount/asr-output:/asr-output \
	-p 5000:5000 \
	dane-asr-worker-old-kaldi