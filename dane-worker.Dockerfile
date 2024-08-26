# FROM public.ecr.aws/a0x3r1t1/kaldi_nl
FROM 917951871879.dkr.ecr.eu-west-1.amazonaws.com/kaldi_nl:v1.2
LABEL org.opencontainers.image.authors="jblom@beeldengeluid.nl"

# switch to root user, to be able to write to the k8s mount, which is root user by default
USER root

# intall ffmpeg, so the input video files will be transcoded to mp3
RUN apt-get update
RUN apt-get install -y \
    ffmpeg

# build python 3.11 from source (since deadsnakes does not seem to work here...)
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

RUN wget https://www.python.org/ftp/python/3.11.0/Python-3.11.0.tgz
RUN tar -xf Python-3.11.*.tgz
RUN cd Python-3.11.*/ && ./configure --enable-optimizations && make -j $(nproc) && make install

RUN echo "reinstall pip" && apt install -y python3-pip

# add the Python code & install the required libs
COPY . /src

# make sure the DANE fs mount point exists (Note: not needed if lean-kaldi MODELPATH=/mnt/dane-fs/models)
RUN mkdir /mnt/dane-fs && chmod -R 777 /mnt/dane-fs
RUN mkdir /mnt/dane-fs/models && chmod -R 777 /mnt/dane-fs/models

# create a dir for the poetry cache (for env variable POETRY_CACHE_DIR)
RUN mkdir /poetry-cache && chmod -R 777 /poetry-cache

WORKDIR /src

# IMPORTANT READ FOR OPENSHIFT https://cloud.redhat.com/blog/a-guide-to-openshift-and-uids

RUN pip install poetry
ENV POETRY_CACHE_DIR=/poetry-cache
RUN poetry env use python3.11
RUN poetry install --without dev

ENTRYPOINT ["./dane-worker-entrypoint.sh"]