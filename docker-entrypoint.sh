#!/bin/bash

input_file=$1
output_dir=$2

if [ -z "$1" ]
  then
    echo "Please supply an input file"
    exit 1
fi

if [ -z "$2" ]
  then
    echo "Please supply an output file"
    exit 1
fi

function errecho() {
  printf "%s\n" "$*" 1>&2
}

###############################################################################
# function download_object_from_bucket
#
# This function downloads an object in a bucket to a file.
#
# Parameters:
#       $1 - The name of the bucket to download the object from.
#       $2 - The path and file name to store the downloaded bucket.
#       $3 - The key (name) of the object in the bucket.
#
# Returns:
#       0 - If successful.
#       1 - If it fails.
###############################################################################
function download_object_from_bucket() {
  local bucket_name=$1
  local destination_file_name=$2
  local object_name=$3
  local response

  response=$(aws s3api get-object \
    --bucket "$bucket_name" \
    --key "$object_name" \
    "$destination_file_name")

  # shellcheck disable=SC2181
  if [[ ${?} -ne 0 ]]; then
    errecho "ERROR: AWS reports put-object operation failed.\n$response"
    return 1
  fi
}

# 1. Parse the input file

# extract the protocol
proto="$(echo $input_file | grep :// | sed -e's,^\(.*://\).*,\1,g')"
# remove the protocol
url="$(echo ${input_file/$proto/})"
# extract the user (if any)
user="$(echo $url | grep @ | cut -d@ -f1)"
# extract the host and port
hostport="$(echo ${url/$user@/} | cut -d/ -f1)"
# by request host without port
host="$(echo $hostport | sed -e 's,:.*,,g')"
# by request - try to extract the port
port="$(echo $hostport | sed -e 's,^.*:,:,g' -e 's,.*:\([0-9]*\).*,\1,g' -e 's,[^0-9],,g')"
# extract the path (if any)
path="$(echo $url | grep / | cut -d/ -f2-)"
# extract the filename
filename=$(echo $input_file | awk -F'/' '{print $NF}')
# filename="audio-file.mp3"

# 2. Check the protocol and download (S3 and HTTP support only for now)
if [ $proto == "s3://" ]; then
    echo Input file is S3 URI: $input_file;

    bucket=`echo $input_file | cut -d'/' -f3`
    key=$path

    echo bucket=$bucket
    echo key=$key
    echo fn=$filename
    download_object_from_bucket "$bucket" "$output_dir/$filename" "$key";
elif [ $proto == "http://" ]; then
    echo Input file is HTTP URI: $input_file;
    wget $input_file --output-document $output_dir/$filename
fi

echo TODO now call Kaldi_NL with the freshly downloaded INPUT

# /opt/Kaldi_NL/decode_OH.sh $output_dir/$filename $output_dir/output

echo done!
