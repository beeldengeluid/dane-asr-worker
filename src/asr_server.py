import pika
import uuid
import json
import DANE
from DANE.config import cfg

class asr_server():

    def __init__(self, config):
        self.config = config.RABBITMQ
        credentials = pika.PlainCredentials(self.config.USER,
                self.config.PASSWORD)
        self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        credentials=credentials,
                        host=self.config.HOST, port=self.config.PORT))

        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='response_queue', exclusive=True)

        self.channel.basic_consume(
            queue='response_queue',
            on_message_callback=self.on_response,
            auto_ack=True)

    def on_response(self, ch, method, props, body):
        print('# Response:', json.loads(body))
        self.stop()
        print('## Handled response. Exiting..')

    def run(self):
        self.channel.start_consuming()

    def stop(self):
        self.channel.stop_consuming()

    def simulate_request(self):
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

        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange=self.config.EXCHANGE,
            routing_key='#.ASR',
            properties=pika.BasicProperties(
                reply_to='response_queue',
                correlation_id=self.corr_id,
            ),
            body=json.dumps({
                # flipflop between json and object is intentional
                # but maybe not most elegant way..
                'task': json.loads(task.to_json())['task'],
                'document': json.loads(document.to_json())
                }))

    def test_produce(self):
        connection = pika.BlockingConnection()
        channel = connection.channel()
        channel.basic_publish(exchange='test', routing_key='test',
                              body=b'Test message.')
        connection.close()

    def test_consume(self):
        connection = pika.BlockingConnection()
        channel = connection.channel()

        for method_frame, properties, body in channel.consume('test'):
            # Display the message parts and acknowledge the message
            print(method_frame, properties, body)
            channel.basic_ack(method_frame.delivery_tag)

            # Escape out of the loop after 10 messages
            if method_frame.delivery_tag == 10:
                break

        # Cancel the consumer and return any pending messages
        requeued_messages = channel.cancel()
        print('Requeued %i messages' % requeued_messages)
        connection.close()

if __name__ == '__main__':

    asr = asr_server(cfg)

    print('## Simulating request for size of this file')
    #asr.simulate_request()
    asr.test_produce()
    asr.test_consume()
    """
    print('## Waiting for response. Ctrl+C to exit.')
    try:
        asr.run()
    except KeyboardInterrupt:
        asr.stop()
    """