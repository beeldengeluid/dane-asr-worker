#docker images -a | grep "<none>" | awk '{print $3}' | xargs docker rmi
#docker rm $(docker ps -a -f status=exited -q)


#FROM python:3.7-stretch
FROM debian:latest
MAINTAINER Jaap Blom <jblom@beeldengeluid.nl>

# This Dockerfile is both an extension and a slim-down to Laurens van der Werff's Kaldi_NL Dockerfile:
#   https://github.com/laurensw75/docker-Kaldi-NL/blob/master/Dockerfile
#
# What has been slimmed-down:
#   - Everything related to Gstreamer has been removed
#   - start & stop scripts for Kaldi are not necessary, since only offline transcoding via decode.sh is done
#
# What has been added:
#   - input & output directories for the offline transcoding
#   - DANE ASR worker is now the main process

ARG NUM_BUILD_CORES=1
ENV NUM_BUILD_CORES ${NUM_BUILD_CORES}

#split up in different layers, so the image building does not take so long after a small change

#first make sure the apt-get repo's are up to date
RUN apt-get update

#basic make stuff
RUN apt-get install -y procps \
    autoconf \
    automake

#g++, fortran, git & bzip2
RUN apt-get install -y bzip2 \
    g++ \
    git \
    gfortran

#all gstreamer stuff
RUN apt-get install -y gstreamer1.0-plugins-good \
    gstreamer1.0-tools \
    gstreamer1.0-pulseaudio \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-ugly

#libtool and make
RUN apt-get install -y libatlas3-base \
    libgstreamer1.0-dev \
    libtool-bin \
    make

#perl and python libs
RUN apt-get install -y perl \
    python2.7 \
    python3 \
    python-pip \
    python3-pip \
    python-yaml \
    python-simplejson \
    python-gi

#subversion, wget and zlib1g-dev
RUN apt-get install -y subversion wget zlib1g-dev

#clean all crap
RUN apt-get clean autoclean && \
    apt-get autoremove -y

#pip install some python2.7 shit for Kaldi
RUN pip install ws4py==0.3.2 && \
    pip install tornado==4.5.3 --upgrade --force-reinstall && \
    ln -s /usr/bin/python2.7 /usr/bin/python ; ln -s -f bash /bin/sh
#5e6f08c13efc8ab425b77debcb33bae13dc6b31e
#ln: failed to create symbolic link '/usr/bin/python': File exists
#debconf: delaying package configuration, since apt-utils is not installed

WORKDIR /opt

#install Kaldi third party tools
RUN apt-get install -y \
    time \
    sox \
    libsox-fmt-mp3 \
    default-jre \
    unzip

#get kaldi
RUN git clone https://github.com/kaldi-asr/kaldi

# checkout an OLD version that JW was using at the time. This should work. TODO build Kaldi_NL from scratch
RUN cd kaldi && git checkout bf0ee72db10155348ef9150b0cb755c0afe16a26

#the tools dir of Kaldi contains the main INSTALL & make file
WORKDIR /opt/kaldi/tools

#-l 2.0
RUN make -j${NUM_BUILD_CORES}
RUN ./install_portaudio.sh

# required for the latest Kaldi instance (Math Kernel Libraries)
RUN extras/install_mkl.sh

#configure, make install of Kaldi
RUN cd /opt/kaldi/src && ./configure --shared && \
    sed -i '/-g # -O0 -DKALDI_PARANOID/c\-O3 -DNDEBUG' kaldi.mk && \
    make depend && make

# because we use the prebuilt Kaldi_NL, we need to create the dir that this prebuilt instance expects
# to contain the language model
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

# add the Python code & install the required libs
COPY ./src /src
COPY requirements.txt /src/
RUN pip3 install -r /src/requirements.txt

# create the input and output folders, which should match your local folders in [THIS REPO BASE]/mount/*
# see start-container.sh how these folders are mounted on container creation
RUN mkdir /input-files
RUN mkdir /output-files
RUN mkdir /asr-output

#start the dane worker
CMD ["python3","-u","/src/worker.py"]

#start the debug service
#CMD ["python3","-u","/src/server.py"]