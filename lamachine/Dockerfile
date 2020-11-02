FROM proycon/lamachine:core
MAINTAINER Maarten van Gompel <proycon@anaproy.nl>
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
RUN apt-get update

RUN apt-get install -y python3 \
	python3-pip

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

#CMD /bin/bash -l