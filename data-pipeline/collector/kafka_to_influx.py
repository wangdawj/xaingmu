"""Kafka -> InfluxDB 消费写入"""
import json
import os
from datetime import datetime

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import ASYNCHRONOUS
from kafka import KafkaConsumer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = "energy.raw"
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN", "campus-energy-token")
INFLUX_ORG = os.getenv("INFLUXDB_ORG", "campus")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "energy")


def to_point(record: dict) -> Point:
    ts = datetime.fromisoformat(record["event_time"].replace("Z", "+00:00"))
    return (
        Point("electricity_data")
        .tag("building_id", record["building_id"])
        .tag("region_id", record["region_id"])
        .tag("meter_id", record["meter_id"])
        .tag("data_type", record.get("data_type", "realtime"))
        .field("value", float(record["value"]))
        .field("voltage", float(record.get("voltage", 0)))
        .field("current", float(record.get("current", 0)))
        .time(ts, WritePrecision.NS)
    )


def main():
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        group_id="influx-writer",
    )
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=ASYNCHRONOUS)
    print(f"消费 Kafka [{TOPIC}] 并写入 InfluxDB...")
    count = 0
    try:
        for msg in consumer:
            point = to_point(msg.value)
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            count += 1
            if count % 500 == 0:
                print(f"已写入 {count} 条")
    except KeyboardInterrupt:
        print(f"\n停止消费，共写入 {count} 条")
    finally:
        write_api.close()
        client.close()
        consumer.close()


if __name__ == "__main__":
    main()
