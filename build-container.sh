#!/bin/bash

DANE_DOCKER_IMAGE=${1:-"dane-la-kaldi"}

echo $DANE_DOCKER_IMAGE

docker build -t $DANE_DOCKER_IMAGE .

if [ $? -eq 0 ]
then
  echo "Success: built the DANE / Lamachine / Kaldi_NL docker image"
  export DANE_DOCKER_IMAGE=$DANE_DOCKER_IMAGE
  echo "Your docker image name is now stored in your environment in DANE_ASR_IMAGE"
  exit 0
else
  echo "Failure: something went wrong while building the docker image" >&2
  exit 1
fi