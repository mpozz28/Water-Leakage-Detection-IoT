import paho.mqtt.client as mqtt
import joblib
import pandas as pd
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import sys
import time

# MQTT Settings
MQTT_BROKER = "localhost" # Raspberry Pi is the broker
MQTT_PORT = 1883
# Wildcard topics to catch all processes (e.g., sensors/process_1/distance)
MQTT_TOPIC_DISTANCE = "sensors/+/distance"
MQTT_TOPIC_TEMP = "sensors/+/temperature"
MQTT_TOPIC_HUMIDITY = "sensors/+/humidity"

# InfluxDB Settings 
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "HxrnQS55ysQFXqd1xW3UervIKtT8H3F2i0KMqup_IR0KujWyWoqulf0WukMI7DTrp3rpeeovqR33rqqnzrRj2Q=="
INFLUXDB_ORG = "IOT"
INFLUXDB_BUCKET = "sensors"
BUCKET_HEIGHT_CM = 9.0 # Total height of the bucket in cm

# Model Path
MODEL_PATH = os.path.join(os.path.dirname(__file__), '../machine_learning/leakage_model.pkl')

# Global State: Dictionary to hold state for each process ID
# Structure: { "process_id": { "distance": None, "temp": None, "humidity": None } }
sensor_states = {} 

model = None
write_api = None

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe([(MQTT_TOPIC_DISTANCE, 0), (MQTT_TOPIC_TEMP, 0), (MQTT_TOPIC_HUMIDITY, 0)])

def on_message(client, userdata, msg):
    global sensor_states
    
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    
    # Parse Topic: sensors/{process_id}/{measurement}
    try:
        parts = topic.split('/')
        if len(parts) != 3:
            return # Unexpected topic format
            
        process_id = parts[1]
        measurement = parts[2]
        
        # Initialize state for this process if new
        if process_id not in sensor_states:
            sensor_states[process_id] = {"distance": None, "prev_distance": None, "temp": None, "humidity": None}
            
        value = float(payload)
        
        if measurement == "distance":
            # Value is in cm
            sensor_states[process_id]["distance"] = value
            process_data(process_id)
        elif measurement == "temperature":
            sensor_states[process_id]["temp"] = value
        elif measurement == "humidity":
            sensor_states[process_id]["humidity"] = value
            
    except ValueError:
        print(f"Error parsing payload: {payload}")
    except Exception as e:
        print(f"Error processing message: {e}")

def process_data(process_id):
    """
    Called when new distance data arrives for a specific process.
    Runs inference and writes to InfluxDB with the process_id tag.
    """
    global model, write_api, sensor_states
    
    state = sensor_states.get(process_id)
    if not state or state["distance"] is None:
        return

    dist = state["distance"]
    temp = state["temp"]
    hum = state["humidity"]

    # Calculate Diff for model
    prev_dist = state.get("prev_distance")
    if prev_dist is None:
        prev_dist = dist # First reading, diff is 0
    
    diff = dist - prev_dist
    
    # Update prev_distance for NEXT time
    state["prev_distance"] = dist

    # 1. Prepare data for model
    input_data = pd.DataFrame([[dist, diff]], columns=['Sensor_Distance', 'Diff'])
    
    # 2. Run Inference
    leakage_prediction = False
    if model:
        try:
            prediction = model.predict(input_data)
            leakage_prediction = bool(prediction[0])
        except Exception as e:
            print(f"Inference error: {e}")

    # Calculate Water Level (Depth)
    # If sensor reads 5cm and bucket is 20cm, water level is 15cm.
    water_level = BUCKET_HEIGHT_CM - dist
    water_level_percentage = (water_level / BUCKET_HEIGHT_CM) * 100
    
    print(f"[{process_id}] Dist: {dist:.2f} cm, Water Level: {water_level:.2f} cm ({water_level_percentage:.1f}%), Leakage: {leakage_prediction}")

    # 3. Write to InfluxDB
    if write_api:
        point = Point("sensor_readings") \
            .tag("process_id", process_id) \
            .field("distance_cm", dist) \
            .field("water_level_percentage", water_level_percentage) \
            .field("leakage_detected", leakage_prediction)
        
        if temp is not None:
            point.field("temperature", temp)
        if hum is not None:
            point.field("humidity", hum)
            
        try:
            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        except Exception as e:
            print(f"InfluxDB Write Error: {e}")

# --- Main Execution ---
def main():
    global model, write_api
    
    # Load Model
    if os.path.exists(MODEL_PATH):
        print(f"Loading model from {MODEL_PATH}")
        model = joblib.load(MODEL_PATH)
    else:
        print(f"Warning: Model not found at {MODEL_PATH}. Inference will be skipped.")

    # Setup InfluxDB
    try:
        client_influx = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        write_api = client_influx.write_api(write_options=SYNCHRONOUS)
        print("InfluxDB Client initialized.")
    except Exception as e:
        print(f"Failed to initialize InfluxDB: {e}")

    # Setup MQTT
    client_mqtt = mqtt.Client()
    client_mqtt.on_connect = on_connect
    client_mqtt.on_message = on_message

    print(f"Connecting to MQTT Broker at {MQTT_BROKER}...")
    try:
        client_mqtt.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Failed to connect to MQTT Broker: {e}")
        return

    # Loop
    try:
        client_mqtt.loop_forever()
    except KeyboardInterrupt:
        print("Stopping...")
        client_mqtt.disconnect()

if __name__ == "__main__":
    main()
