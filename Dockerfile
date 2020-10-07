FROM python:3.7-stretch
MAINTAINER Jaap Blom <jblom@beeldengeluid.nl>

# This Dockerfile is both an extension and a slim-down to Laurens Walbeek's Kaldi_NL Dockerfile:
#   https://github.com/laurensw75/docker-Kaldi-NL/blob/master/Dockerfile
#
# What has been slimmed-down:
#   - Everything related to Gstreamer has been removed
#   - start & stop scripts for Kaldi are not necessary, since only offline transcoding via decode.sh is done
#
# What has been added:
#   - input & output directories for the offline transcoding
#   - DANE ASR worker is now the main process

ARG NUM_BUILD_CORES=2
ENV NUM_BUILD_CORES ${NUM_BUILD_CORES}

RUN apt-get update && apt-get install -y  \
    procps \
    autoconf \
    automake \
    bzip2 \
    g++ \
    git \
    gfortran \
    gstreamer1.0-plugins-good \
    gstreamer1.0-tools \
    gstreamer1.0-pulseaudio \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-ugly  \
    libatlas3-base \
    libgstreamer1.0-dev \
    libtool-bin \
    make \
    perl \
    python2.7 \
    python3 \
    python-pip \
    python-yaml \
    python-simplejson \
    python-gi \
    subversion \
    wget \
    zlib1g-dev && \
    apt-get clean autoclean && \
    apt-get autoremove -y && \
    pip install ws4py==0.3.2 && \
    pip install tornado==4.5.3 --upgrade --force-reinstall && \
    ln -s /usr/bin/python2.7 /usr/bin/python ; ln -s -f bash /bin/sh

WORKDIR /opt

RUN apt-get install -y \
    time \
    sox \
    libsox-fmt-mp3 \
    default-jre \
    unzip

RUN git clone https://github.com/kaldi-asr/kaldi && \
    cd /opt/kaldi/tools && \
    make -j${NUM_BUILD_CORES} -l 2.0 && \
    ./install_portaudio.sh

# required for the latest Kaldi instance (Math Kernel Libraries)
RUN cd /opt/kaldi/tools && \
    extras/install_mkl.sh

RUN cd /opt/kaldi/src && ./configure --shared && \
    sed -i '/-g # -O0 -DKALDI_PARANOID/c\-O3 -DNDEBUG' kaldi.mk && \
    make depend && make

# somehow the models should go in the gstreamer directory, since we did not install that we create it manually
RUN mkdir /opt/kaldi-gstreamer-server

RUN cd /opt/kaldi-gstreamer-server && \
    wget -nv http://nlspraak.ewi.utwente.nl/open-source-spraakherkenning-NL/mod.tar.gz && \
    tar -xvzf mod.tar.gz && rm mod.tar.gz

# extract the prebuilt Kaldi_NL.tar.gz, figure out how this can be generated
COPY Kaldi_NL.tar.gz /opt/
RUN  cd /opt && tar -xvzf Kaldi_NL.tar.gz && rm Kaldi_NL.tar.gz && \
     cd /opt/Kaldi_NL && ln -s /opt/kaldi/egs/wsj/s5/utils utils && ln -s /opt/kaldi/egs/wsj/s5/steps steps

# intall ffmpeg, so the input video files will be transcoded to mp3
RUN apt-get install -y \
    ffmpeg

COPY /src /src

# RUN pip install pipenv
# COPY Pipfile /tmp
# RUN cd /tmp && pipenv lock --requirements > requirements.txt

COPY requirements.txt /src/
RUN pip3 install -r /src/requirements.txt

RUN mkdir /input-files
RUN mkdir /output-files
RUN mkdir /asr-input
RUN mkdir /asr-output

CMD ["python3","-u","/src/worker.py"]