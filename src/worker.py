"""
Standalone worker: consumes interaction events from Kafka and runs the
extraction -> policy filter -> graph write -> embed pipeline. This is the
asynchronous half of ingestion described in the spec; the chat path only
publishes events, it never waits on this.

Run with: python -m src.worker
"""
import json
import logging
from kafka import KafkaConsumer
from src.config import settings
from src.models import InteractionEvent
from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.memory_processor import process_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
log = logging.getLogger(__name__)

# In-memory idempotency guard for this process's lifetime (a durable store,
# e.g. Redis or a DB table, would back this in production).
_seen_keys: set[str] = set()


def run_worker():
    consumer = KafkaConsumer(
        settings.KAFKA_EVENTS_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="memory-processor-workers",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    graph = GraphStore()
    vectors = VectorStore()

    log.info("Worker started, listening on topic '%s'", settings.KAFKA_EVENTS_TOPIC)

    for message in consumer:
        payload = message.value
        idem_key = payload.get("idempotency_key")

        if idem_key in _seen_keys:
            log.info("Skipping duplicate event %s", idem_key)
            continue

        try:
            event = InteractionEvent(**payload)
            written = process_event(event, graph, vectors)
            _seen_keys.add(idem_key)
            log.info(
                "Processed event %s for subject %s -> %d memories written",
                event.event_id,
                event.subject_id,
                len(written),
            )
        except Exception as exc:  # dead-letter in production; log here for the MVP
            log.error("Failed to process event %s: %s", idem_key, exc)


if __name__ == "__main__":
    run_worker()
