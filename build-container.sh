#!/bin/bash

IMAGE_NAME=${1:-"dane-la-kaldi"}

echo $IMAGE_NAME

docker build -t $IMAGE_NAME .

if [ $? -eq 0 ]
then
  echo "Success: built the DANE / Lamachine / Kaldi_NL docker image"
  export DANE_ASR_IMAGE=$IMAGE_NAME
  exit 0
else
  echo "Failure: something went wrong while building the docker image" >&2
  exit 1
fi