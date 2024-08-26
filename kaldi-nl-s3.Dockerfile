FROM 917951871879.dkr.ecr.eu-west-1.amazonaws.com/kaldi_nl:v1.2
LABEL org.opencontainers.image.authors="jblom@beeldengeluid.nl"

RUN apt-get update
RUN apt-get install -y \
    curl

WORKDIR /opt

# install the AWS CLI (later install Minio CLI "mc")
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install

COPY docker-entrypoint.sh /docker/docker-entrypoint.sh

CMD ["tail", "-f", "/dev/null"]
# ENTRYPOINT [ "/docker/docker-entrypoint.sh" ]