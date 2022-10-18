# TODO add container to CLARIAH image registry
FROM public.ecr.aws/a0x3r1t1/kaldi_nl
MAINTAINER Jaap Blom <jblom@beeldengeluid.nl>

# switch to root user, to be able to write to the k8s mount, which is root user by default
USER root

# intall ffmpeg, so the input video files will be transcoded to mp3
RUN apt-get update
RUN apt-get install -y \
    ffmpeg

# build python 3.10 from source (since deadsnakes does not seem to work here...)
# https://computingforgeeks.com/how-to-install-python-on-ubuntu-linux-system/
RUN apt update
RUN apt install -y build-essential \
    zlib1g-dev \
    libncurses5-dev \
    libgdbm-dev \
    libnss3-dev \
    libssl-dev \
    libreadline-dev \
    libffi-dev \
    libsqlite3-dev \
    wget \
    libbz2-dev

RUN wget https://www.python.org/ftp/python/3.10.6/Python-3.10.6.tgz
RUN tar -xf Python-3.10.*.tgz
RUN cd Python-3.10.*/ && ./configure --enable-optimizations && make -j $(nproc) && make altinstall

RUN apt install -y python3-pip

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