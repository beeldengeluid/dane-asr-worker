#!/bin/bash

set -e

#if built using build-container.sh, the docker image name is set to the DANE_ASR_IMAGE env var
#the optional param takes precedence; without env and arg, the default is used
[[ -z "${DANE_ASR_IMAGE}" ]] && IMAGE_NAME=${1:-"dane-la-kaldi"} || IMAGE_NAME="${1:DANE_ASR_IMAGE}"

PWD=`pwd`

docker run --rm -v $PWD/mount/input-files:/input-files \
	-v $PWD/mount/output-files:/output-files \
	-v $PWD/mount/asr-output:/asr-output \
	-p 5000:5000 \
	$IMAGE_NAME