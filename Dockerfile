FROM proycon/lamachine:core
MAINTAINER Maarten van Gompel <proycon@anaproy.nl>
MAINTAINER Jaap Blom <jblom@beeldengeluid.nl>
LABEL description="A LaMachine installation with Kaldi NL and Oral History (CLST)"
#RUN lamachine-config lm_base_url https://your.domain.here
#RUN lamachine-config force_https yes
#RUN lamachine-config private true
#RUN lamachine-config maintainer_name "Your name here"
#RUN lamachine-config maintainer_mail "your@mail.here"
RUN lamachine-add kaldi_nl
RUN lamachine-add oralhistory
RUN lamachine-update

#install DANE worker dependencies
RUN sudo apt-get update

# intall ffmpeg, so the input video files will be transcoded to mp3
RUN sudo apt-get install -y \
    ffmpeg

# add the Python code & install the required libs
COPY ./src/docker_src /src
COPY requirements.txt /src/
RUN pip3 install -r /src/requirements.txt

# create the input and output folders, which should match your local folders in [THIS REPO BASE]/mount/*
# see start-container.sh how these folders are mounted on container creation
RUN sudo mkdir /input-files
RUN sudo mkdir /output-files
RUN sudo mkdir /asr-output

#make sure to set the KALDI_ROOT or kaldi_NL won't be able to locate it
ENV KALDI_ROOT=/usr/local/opt/kaldi

#start the dane worker
#CMD ["python3","-u","/src/worker.py"]
CMD ["python3","-u","/src/server.py"]