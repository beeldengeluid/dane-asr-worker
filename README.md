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

**Note** You can download sample data [here](s3://x-omg-daan-av/dane-asr-worker-sample-data.tar.gz)


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


## Python (run with sample data)

Install the Python virtual env with all required packages:

```sh
poetry install
```

Enter the virtual env:

```sh
poetry shell
```

Test the worker code:

```sh
./scripts/check-project.sh
```

Run the worker:

```sh
./scripts/run.sh
```

CLI arguments:
* `--input-uri`: S3 or HTTP URI
* `--output-uri`: S3 URI (not implemented yet)


### Run with sample data

You can download sample data [here](s3://x-omg-daan-av/dane-asr-worker-sample-data.tar.gz). Make sure to put it in the `data` directory within your local copy of this repo.

Make sure to configure your `.env.override` with:

`AUDIO_SAMPLE_URL`=http://fake-hosting.beng.nl/2101608150135908031__NOS_JOURNAAL_-WON01207359.mp4

Since `./data/2101608150135908031__NOS_JOURNAAL_-WON01207359.mp4` already exists, you can test that the worker will skip trying to download the data from that `--input-uri`

Also the worker should see that also the Kald_NL output already exists and will skip calling Kaldi_NL as well (see the `run` function in `simple_asr.py` to follow the workers current processing logic)
