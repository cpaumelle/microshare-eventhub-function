from azure.eventhub import EventHubProducerClient, EventData
import os, json, time

# Get connection string from environment
conn = os.environ.get("EH_CONNSTR")
if not conn:
    raise SystemExit("❌ EH_CONNSTR not set")

producer = EventHubProducerClient.from_connection_string(conn)
with producer:
    for i in range(5):
        data = {"seq": i, "msg": "hello from CT", "ts": time.time()}
        event = EventData(json.dumps(data))
        producer.send_batch([event])
        print("✅ Sent:", data)
        time.sleep(1)
