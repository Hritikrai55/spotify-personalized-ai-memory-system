"""
Publishes interaction events to Kafka so the user-facing path (chat) never
blocks on graph/embedding writes. A separate worker (worker.py) consumes this
topic and does the actual extraction + graph write, per the spec's
"Interaction capture must be asynchronous" requirement.
"""
import json
from kafka import KafkaProducer
from src.config import settings
from src.models import InteractionEvent

_producer: KafkaProducer | None = None


def get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
    return _producer


def publish_event(event: InteractionEvent) -> None:
    """Fire-and-forget publish, keyed by idempotency_key to dedupe on the consumer side."""
    producer = get_producer()
    producer.send(
        settings.KAFKA_EVENTS_TOPIC,
        key=event.idempotency_key,
        value=event.model_dump(),
    )
    producer.flush(timeout=2)
