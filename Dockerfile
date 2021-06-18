FROM python:3

COPY ./ /src
COPY requirements.txt /src

WORKDIR /src

RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "/src/worker.py" ]