import pika
import uuid
import json
from dane import Document, Task
from dane.config import cfg


config = cfg.RABBITMQ
ROUTING_KEY = "#.ASR"
ASR_QUEUE = "ASR"


def get_rmq_connection():
    credentials = pika.PlainCredentials(config.USER, config.PASSWORD)
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            credentials=credentials,
            host=config.HOST,
            port=config.PORT
            # socket_timeout=5
        )
    )


def simulate_dane_request():
    connection = get_rmq_connection()

    print("got a connection, now going to construct a DANE task")

    task = Task("ASR")
    document = Document(
        {
            "id": "oai:openimages.eu:29452",
            "url": "https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4",
            "type": "Video",
        },
        {"id": "openbeelden", "type": "Organization"},
        api=None,
        _id="14cead6ceb9e887bdb3ca1ef0b9cefd84416a8e9",
    )

    print("now publishing the task on the channel")
    print(task.to_json())
    channel = connection.channel()
    corr_id = str(uuid.uuid4())
    channel.basic_publish(
        exchange=config.EXCHANGE,
        routing_key=ROUTING_KEY,
        properties=pika.BasicProperties(
            reply_to=config.RESPONSE_QUEUE,
            correlation_id=corr_id,
        ),
        body=json.dumps(
            {
                # flipflop between json and object is intentional
                # but maybe not most elegant way..
                "task": json.loads(task.to_json()),
                "document": json.loads(document.to_json()),
            }
        ),
    )


def simulate_dane_worker():
    connection = get_rmq_connection()
    print("going to consume")
    channel = connection.channel()
    channel.exchange_declare(config.EXCHANGE, exchange_type="topic")
    channel.queue_declare(
        queue=ASR_QUEUE, durable=True, arguments={"x-max-priority": 10}
    )
    channel.queue_bind(
        exchange=config.EXCHANGE, queue=ASR_QUEUE, routing_key=ROUTING_KEY
    )
    channel.basic_consume(
        queue=ASR_QUEUE, on_message_callback=on_response, auto_ack=False
    )  # set to false if you want to really make sure the job gets done before ACKing

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    print("DONENENEN")


def simulate_dane_msg_queue():
    connection = get_rmq_connection()
    print("going to consume")
    channel = connection.channel()
    channel.exchange_declare(config.EXCHANGE, exchange_type="topic")
    channel.queue_declare(
        queue=config.RESPONSE_QUEUE, durable=True, arguments={"x-max-priority": 10}
    )
    channel.queue_bind(
        exchange=config.EXCHANGE, queue=config.RESPONSE_QUEUE, routing_key=ROUTING_KEY
    )
    channel.basic_consume(
        queue=config.RESPONSE_QUEUE, on_message_callback=on_response, auto_ack=False
    )  # set to false if you want to really make sure the job gets done before ACKing

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    print("DONENENEN")


def on_response(ch, method, props, body):
    print("consuming!")
    print("# Response:", body)
    # stop()
    print("## Handled response. Exiting..")


if __name__ == "__main__":
    # https://github.com/dmaze/docker-rabbitmq-example
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", help="use 0 to simulate the producer and 1 to simulate the DANE worker"
    )
    args = parser.parse_args()
    if args.mode == "1":
        simulate_dane_msg_queue()
    elif args.mode == "0":
        simulate_dane_request()
    elif args.mode == "2    ":
        simulate_dane_worker()
    else:
        print("invalid param, exiting")
