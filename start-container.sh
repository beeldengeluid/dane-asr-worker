#!/bin/bash

set -e

#if built using build-container.sh, the docker image name is set to the DANE_DOCKER_IMAGE env var
#the optional param takes precedence; without env and arg, the default is used
[[ -z "${DANE_DOCKER_IMAGE}" ]] && DANE_DOCKER_IMAGE=${1:-"dane-la-kaldi"} || DANE_DOCKER_IMAGE="${1:DANE_DOCKER_IMAGE}"
[[ -z "${DANE_DOCKER_PORT}" ]] && DANE_DOCKER_PORT=${1:-3023} || DANE_DOCKER_PORT="${1:DANE_DOCKER_PORT}"

PWD=`pwd`

docker run --rm -v $PWD/mount/input-files:/input-files \
	-v $PWD/mount/output-files:/output-files \
	-v $PWD/mount/asr-output:/asr-output \
	-p $DANE_DOCKER_PORT:$DANE_DOCKER_PORT \
	$DANE_DOCKER_IMAGE