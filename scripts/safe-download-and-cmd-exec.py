import requests
import unicodedata
import string
from urllib.parse import urlparse, unquote
import os
import uuid

HORRIBLE_URL = 'http://videohosting.beng.nl/radio-oranje/Radio%20Oranje%2017-feb.-1941_R.%20H.%20KIEK_%20INTERVIEW%20MET%20DE%20HEREN%20VAS%20NUNEZ%20EN%20VAN%20EENDENBURG%20(TWEE%20NEDERL.mp3'


HORRIBLE_URL_2 = 'http://videohosting.beng.nl/afd/asdfadsf/fake_folder/\[]}{}|~`"\':;,/? abcABC 0123 !@#$%^&*()_+ clᐖﯫⅺຶ 讀ϯՋ㉘ ⅮRㇻᎠ⍩ 𝁱C ℿ؛ἂeuឃC ᅕ ᑉﺜͧ bⓝ s⡽Հᛕ\ue063 牢𐐥er ᐛŴ n წş .ھڱ                                 df                                         df                                  dsfsdfgsg!zip'

HORRIBLE_URL_3 = 'http://videohosting.beng.nl/radio-oranje/Radio%20Oranje%2019-sep.-1944_Opname%20van%20Radio-Oranje-uitzending_%20reportage%20over%20Prins%20Bernhard;%20reportag.mp3'
char_limit = 255
valid_filename_chars = "-_. {}{}".format(string.ascii_letters, string.digits)

def download(url):
    response = requests.get(url)
    file_path = url_to_safe_filename(url)
    if response.ok and file_path:
        with open(file_path, "wb+") as f:
            f.write(response.content)
    else:
        print("Failed to get the file")

def url_to_safe_filename(url, whitelist=valid_filename_chars, replace=' '):
    # ; in the url is terrible, since it cuts off everything after the ; when running urlparse
    url = url.replace(';', '')

    # grab the url path
    url_path = urlparse(url).path

    # get the file/dir name from the URL (if any)
    url_file_name = os.path.basename(url_path)

    # also make sure to get rid of the URL encoding
    filename = unquote(
        url_file_name if url_file_name != '' else url_path
    )

    # if both the url_path and url_file_name are empty the filename will be meaningless, so then assign a random UUID
    filename = str(uuid.uuid4()) if filename in ['', '/'] else filename

    # replace spaces (or anything else passed in the replace param) with underscores
    for r in replace:
        filename = filename.replace(r,'_')

    # keep only valid ascii chars
    cleaned_filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode()

    # keep only whitelisted chars
    cleaned_filename = ''.join(c for c in cleaned_filename if c in whitelist)
    if len(cleaned_filename)>char_limit:
        print("Warning, filename truncated because it was over {}. Filenames may no longer be unique".format(char_limit))
    return cleaned_filename[:char_limit]

if __name__ == '__main__':

    #download(HORRIBLE_URL_3)
    x = url_to_safe_filename(HORRIBLE_URL_3)
    print(x)