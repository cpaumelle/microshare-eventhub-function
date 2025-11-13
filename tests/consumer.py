from azure.eventhub import EventHubConsumerClient
import os

conn = os.environ.get("EH_CONNSTR")
if not conn:
    raise SystemExit("❌ EH_CONNSTR not set")

client = EventHubConsumerClient.from_connection_string(
    conn, consumer_group="$Default"
)

def on_event(partition_context, event):
    print(f"[{partition_context.partition_id}] {event.body_as_str()}")
    partition_context.update_checkpoint(event)

print("👂 Listening for events ... Ctrl+C to stop")
with client:
    client.receive(on_event=on_event, starting_position="-1")
