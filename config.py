import os
import validators

output_base_dir = os.environ.get("OUTPUT_BASE_DIR", "")
s3_endpoint_url = os.environ.get("S3_ENDPOINT_URL", "")
s3_bucket = os.environ.get("S3_BUCKET", "")
s3_folder_in_bucket = os.environ.get("S3_FOLDER_IN_BUCKET", "")

audio_sample_url = os.environ.get("AUDIO_SAMPLE_URL", "")

assert output_base_dir, "Please add OUTPUT_BASE_DIR to your environment"
assert output_base_dir not in [".", "/"]
assert os.path.exists(output_base_dir), "OUTPUT_BASE_DIR does not exist"

if s3_bucket or s3_endpoint_url or s3_folder_in_bucket:
    assert s3_bucket, "Please enter the S3_BUCKET to use"
    assert validators.url(s3_endpoint_url), "Please enter a valid S3_ENDPOINT_URL"
    assert s3_folder_in_bucket, "Please enter a path within the supplied S3 bucket"

if audio_sample_url:
    assert validators.url(audio_sample_url), "Please provide a valid AUDIO_SAMPLE_URL"
