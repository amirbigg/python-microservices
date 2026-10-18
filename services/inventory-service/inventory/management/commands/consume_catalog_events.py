import json
import logging
import os
import time

import pika

from django.core.management.base import BaseCommand
from django.db import DatabaseError

from inventory.messaging.catalog_event import InvalidCatalogEvent, process_catalog_event


logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))

EXCHANGE_NAME = "catalog.events"
QUEUE_NAME = "inventory.product-created"
ROUTING_KEY = "product.created"

DEAD_LETTER_EXCHANGE = "inventory.events.dlx"
DEAD_LETTER_QUEUE = "inventory.product-created.dlq"
DEAD_LETTER_ROUTING_KEY = "product-created.invalid"


class Command(BaseCommand):
    help = "Consume product.created events and initialize Inventory records."

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting the Catalog event consumer...")

        while True:
            connection = None

            try:
                connection = pika.BlockingConnection(pika.ConnectionParameters(
                    host=RABBITMQ_HOST, port=RABBITMQ_PORT, heartbeat=60, blocked_connection_timeout=30
                ))
                channel = connection.channel()
                self._declare_topology(channel)
                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_NAME, on_message_callback=self._on_message, auto_ack=False)

                self.stdout.write(self.style.SUCCESS(f"Waiting for `{ROUTING_KEY}` events on queue `{QUEUE_NAME}`."))
                channel.start_consuming()

            except KeyboardInterrupt:
                self.stdout.write("Stopping the Catalog event consumer...")
                break
            except (pika.exceptions.AMQPError, OSError):
                logger.exception("Rabbitmq connection or consumer error.")
                self.stderr.write("Rabbitmq unavailable; retrying in 5 seconds...")
                time.sleep(5)
            finally:
                if connection is not None and connection.is_open:
                    try:
                        connection.close()
                    except pika.exceptions.AMQPError:
                        logger.exception("Error closing Rabbitmq connection.")

    @staticmethod
    def _declare_topology(channel):
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type="direct", durable=True)
        channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
        channel.queue_bind(exchange=DEAD_LETTER_EXCHANGE, queue=DEAD_LETTER_QUEUE, routing_key=DEAD_LETTER_ROUTING_KEY)
        channel.queue_declare(queue=QUEUE_NAME, durable=True,
                              arguments={
                                  "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
                                  "x-dead-letter-routing-key": DEAD_LETTER_ROUTING_KEY
                              })

        channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=ROUTING_KEY)

    @staticmethod
    def _on_message(channel, method, properties, body):
        try:
            message = json.loads(body.decode("utf-8"))
            item, created = process_catalog_event(message)
        except (UnicodeDecodeError, json.JSONDecodeError, InvalidCatalogEvent) as exc:
            logger.warning(f"Rejecting invalid catalog event: {exc}")
            channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return
        except DatabaseError:
            logger.exception("Database error while processing Catalog event.")
            time.sleep(2)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return
        except Exception:
            logger.exception("Unexpected error while processing Catalog event.")
            channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return

        channel.basic_ack(delivery_tag=method.delivery_tag)

        if created:
            logger.info("Created inventory for product_id=%s, quality=%s", item.product_id, item.quantity)
        else:
            logger.info("Duplicate product.created event ignored for product_id=%s", item.product_id)
