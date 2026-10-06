import json
import pika
from django.core.management.base import BaseCommand


RABBITMQ_HOST = "rabbitmq"
EXCHANGE_NAME = "catalog.events"
QUEUE_NAME = "catalog.events.consumer"

class Command(BaseCommand):
    help = "Consume catalog events from Rabbitmq"

    def handle(self, *args, **options):
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.queue_declare(queue=QUEUE_NAME, durable=True)

        channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="product.*")
        self.stdout.write(self.style.SUCCESS("Waiting for events..."))

        def callback(ch, method, properties, body):
            message = json.loads(body)
            self.stdout.write(self.style.SUCCESS(f"Received event: {message}"))
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
        channel.start_consuming()
