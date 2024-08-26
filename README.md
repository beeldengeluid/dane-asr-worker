# dane-asr-worker

**Important NOTE**: DANE is currently taken out of the code. If you want to run this worker with the old DANE code intact: use the following image: ghcr.io/beeldengeluid/dane-asr-worker:sha-f9197d8

Once we are sure DANE can be taken out completely, we will also rename this repository and remove all references to dane. For now we still call it the dane-asr-worker.

## Development status

- DANE is currently being taken out of this code base
- the `--input-uri` parameter is fully implemented and supports s3 and http URIs
- the `--output-uri` parameter has **not** yet been implemented, so output is not sent anywhere at the moment

## Configuration

`.env.override` is used to configure the worker and pass the input & output variables. Create this file by copying `.env` and changing the values. Notes on what each value means are also in the `.env` file.

## Docker

```sh
docker build -t dane-asr-worker -f dane-worker.Dockerfile .
```

Run the worker with:

```sh
docker compose -f docker-compose-dane-worker.yml up
```