# dane-asr-worker

**Important NOTE**: DANE is currently taken out of the code. If you want to run this worker with the old DANE code intact: use the following image: ghcr.io/beeldengeluid/dane-asr-worker:sha-f9197d8

Once we are sure DANE can be taken out completely, we will also rename this repository and remove all references to dane. For now we still call it the dane-asr-worker.

## Development status

- DANE is currently being taken out of this code base
- the `--input-uri` parameter is fully implemented and supports s3 and http URIs
- the `--output-uri` parameter has **not** yet been implemented, so output is not sent anywhere at the moment
- try out this new image in OpenShift and call it from Airflow
- make sure [the whispeer worker](https://github.com/beeldengeluid/dane-whisper-asr-worker) can also be wired up in the same manner

## Configuration

`.env.override` is used to configure the worker and pass the input & output variables. Create this file by copying `.env` and changing the values. Notes on what each value means are also in the `.env` file.

Besides the environment, it's required to make sure the following 2 directories are available:

* `data` (see `OUTPUT_BASE_DIR` in `.env`)
* `models` (Kaldi_NL looks for the models in the `/models` dir)

### Data dir
The data dir is structured as follows:

* `data`: place where the `--input-uri` is downloaded into
* `data/output/{FILE_ID}`: folder where the output of Kaldi_NL is stored
* `data/output/{FILE_ID.tar.gz}`: tarball containing part of the Kaldi_NL output that will be transferred back to `--output-uri` (in S3)

**Note** that the last bit will probably be changed later on. Most likely `data/ouput/{FILE_ID}/1Best.ctm|1Best.txt|transcript.json` will be uploaded uncompressed.


**TODO** put a sample data dir in S3 to test out this worker more easily

### Model dir

Kaldi_NL will check the `models` dir on startup to see if the (Utwente + Radbout) models were already downloaded. If not these models will be downloaded.

Note that Kaldi_NL also will try to create symlinks in the `models` dir, which **will fail** (most definitely in OpenShift) if the process does not have the right permissions. For this reason the docker-compose files in this repo are set to run as **root**.

Also note that the Kaldi_NL model download will run on an average laptop, but the speech recognition process will not work with less than 16Gb of RAM.


## Docker

```sh
docker build -t dane-asr-worker -f dane-worker.Dockerfile .
```

Run the worker with:

```sh
docker compose -f docker-compose-dane-worker.yml up
```