import pika
import uuid
import json
import DANE
from DANE.config import cfg

config = cfg.RABBITMQ
ROUTING_KEY = '#.ASR'

def get_rmq_connection():
    credentials = pika.PlainCredentials(
        config.USER,
        config.PASSWORD
    )
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            credentials=credentials,
            host=config.HOST,
            port=config.PORT
            #socket_timeout=5
        )
    )

def simulate_dane_request():
    connection = get_rmq_connection()

    print('got a connection, now going to construct a DANE task')

    task = DANE.Task('ASR')
    document = DANE.Document(
        {
            'id': 'THIS',
            'url': '/input-files/ob-test.mp3',
            'type': 'Video'
        },{
            'id': 'ASRExample',
            'type': 'Software'
        }
    )

    print('now publishing the task on the channel')

    channel = connection.channel()
    corr_id = str(uuid.uuid4())
    channel.basic_publish(
        exchange=config.EXCHANGE,
        routing_key=ROUTING_KEY,
        properties=pika.BasicProperties(
            reply_to=config.RESPONSE_QUEUE,
            correlation_id=corr_id,
        ),
        body=json.dumps({
            # flipflop between json and object is intentional
            # but maybe not most elegant way..
            'task': json.loads(task.to_json())['task'],
            'document': json.loads(document.to_json())
            }))

def simulate_dane_worker():
    connection = get_rmq_connection()
    print('going to consume')
    channel = connection.channel()
    channel.exchange_declare(config.EXCHANGE)
    channel.queue_declare(queue=config.RESPONSE_QUEUE)
    channel.queue_bind(
        exchange=config.EXCHANGE,
        queue=config.RESPONSE_QUEUE,
        routing_key=ROUTING_KEY
    )
    channel.basic_consume(
        queue=config.RESPONSE_QUEUE,
        on_message_callback=on_response,
        auto_ack=True) #set to false if you want to really make sure the job gets done before ACKing

    try:
        channel.start_consuming()
    except KeyboardInterrupt as e:
        channel.stop_consuming()
    print('DONENENEN')

def on_response(ch, method, props, body):
    print('consuming!')
    print('# Response:', body)
    #stop()
    print('## Handled response. Exiting..')


if __name__ == '__main__':
    #https://github.com/dmaze/docker-rabbitmq-example
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", help="use 0 to simulate the producer and 1 to simulate the DANE worker")
    args = parser.parse_args()
    if args.mode == '1':
        simulate_dane_worker()
    elif args.mode == '0':
        simulate_dane_request()
    else:
        print('invalid param, exiting')
