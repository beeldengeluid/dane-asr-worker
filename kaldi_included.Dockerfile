# TODO add container to CLARIAH image registry
FROM public.ecr.aws/a0x3r1t1/kaldi_nl
MAINTAINER Jaap Blom <jblom@beeldengeluid.nl>

# switch to root user, to be able to write to the k8s mount, which is root user by default
USER root

# intall ffmpeg, so the input video files will be transcoded to mp3
RUN apt-get update
RUN apt-get install -y \
    ffmpeg

RUN apt-get install -y python3 \
    python3-pip

# add the Python code & install the required libs
COPY . /src

# make sure the DANE fs mount point exists (Note: not needed if lean-kaldi MODELPATH=/mnt/dane-fs/models)
RUN mkdir /mnt/dane-fs && chmod -R 777 /mnt/dane-fs
RUN mkdir /mnt/dane-fs/models && chmod -R 777 /mnt/dane-fs/models

WORKDIR /src

RUN pip install poetry
RUN poetry install

# ENTRYPOINT ["tail", "-f", "/dev/null"]
ENTRYPOINT ["./docker-entrypoint.sh"]