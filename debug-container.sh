PWD=`pwd`

docker run --rm -ti -v $PWD/mount/input-files:/input-files \
	-v $PWD/mount/output-files:/output-files \
	-v $PWD/mount/asr-output:/asr-output \
	dane-asr-worker-old-kaldi /bin/bash