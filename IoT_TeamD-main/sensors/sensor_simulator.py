import time
import random
import sys
import threading
import os
import joblib
import pandas as pd

try:
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion
except ImportError:
    print("paho-mqtt not installed. Install with: pip install paho-mqtt", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
BROKER_HOST = "172.20.10.4"  # Default Broker IP 
BROKER_PORT = 1883

# Load Model
MODEL_PATH = os.path.join(os.path.dirname(__file__), '../machine_learning/leakage_model.pkl')
model = None
if os.path.exists(MODEL_PATH):
    print(f"Loading model from {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
else:
    print(f"Warning: Model not found at {MODEL_PATH}. Simulation will run without ML predictions.")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[{threading.current_thread().name}] Connected to MQTT Broker")
    else:
        print(f"[{threading.current_thread().name}] Failed to connect, return code {rc}")

def simulate_single_sensor(process_id):
    """
    Simulates a single sensor group (Arduino) publishing to:
    sensors/{process_id}/distance
    sensors/{process_id}/temperature
    sensors/{process_id}/humidity
    """
    
    # Setup MQTT Client
    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect

    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
    except Exception as e:
        print(f"[{process_id}] Error connecting to broker: {e}")
        return

    client.loop_start()

    # Topics
    topic_dist = f"sensors/{process_id}/distance"
    topic_temp = f"sensors/{process_id}/temperature"
    topic_hum = f"sensors/{process_id}/humidity"
    topic_leak = f"sensors/{process_id}/leakage_detected"

    # Initial simulated values
    # Bucket is 9.7cm high (Sensor to bottom). 
    # Distance 4.7cm = Full (5cm water).
    # Distance 9.7cm = Empty (0cm water).
    distance = 4.7      # Start full
    temperature = 25.0  # Celsius
    humidity = 60.0     # Percent
    
    # Simulation State
    state = "STABLE" # STABLE, LEAKING, REFILLING
    counter = 0
    leak_rate = 0.0
    prev_distance = distance

    try:
        while True:
            # 1. Simulate Data Variations based on State
            
            if state == "STABLE":
                # Just noise
                distance += random.uniform(-0.05, 0.05)
                counter += 1
                # Chance to start leaking after some time
                if counter > 50 and random.random() < 0.05:
                    state = "LEAKING"
                    leak_rate = random.uniform(0.1, 0.3) # cm per cycle
                    print(f"[{process_id}] STARTED LEAKING!")
                    counter = 0

            elif state == "LEAKING":
                distance += leak_rate + random.uniform(-0.02, 0.02)
                # If empty, stop leaking and start refilling
                if distance >= 9.7:
                    state = "REFILLING"
                    print(f"[{process_id}] EMPTY! REFILLING...")
            
            elif state == "REFILLING":
                distance -= 0.5 # Refill faster than leak
                if distance <= 4.7:
                    distance = 4.7
                    state = "STABLE"
                    print(f"[{process_id}] REFILLED. STABLE.")

            # Clamp values
            if distance < 0: distance = 0
            if distance > 12: distance = 12 # Sensor can read past bucket bottom
            
            temperature += random.uniform(-0.1, 0.1)
            
            humidity += random.uniform(-0.5, 0.5)
            if humidity > 100: humidity = 100
            if humidity < 0: humidity = 0

            # 2. Run ML Prediction
            leakage_detected = False
            if model:
                diff = distance - prev_distance
                input_data = pd.DataFrame([[distance, diff]], columns=['Sensor_Distance', 'Diff'])
                try:
                    prediction = model.predict(input_data)
                    leakage_detected = bool(prediction[0])
                except Exception as e:
                    print(f"[{process_id}] Prediction Error: {e}")
            
            prev_distance = distance

            # 3. Format Messages
            msg_distance = f"{distance:.6f}"
            msg_temp = f"{temperature:.6f}"
            msg_humidity = f"{humidity:.6f}"
            msg_leak = "1" if leakage_detected else "0"
            
            # 4. Publish
            client.publish(topic_dist, msg_distance)
            client.publish(topic_temp, msg_temp)
            client.publish(topic_hum, msg_humidity)
            client.publish(topic_leak, msg_leak)

            print(f"[{process_id}] Sent: Dist={msg_distance}, Leak={msg_leak} (State={state})")

            # 5. Wait
            time.sleep(0.2 + random.uniform(-0.1, 0.1))

    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()

def main():
    # Allow overriding broker IP via command line
    global BROKER_HOST
    if len(sys.argv) > 1:
        BROKER_HOST = sys.argv[1]
        
    print(f"Starting Multi-Sensor Simulation on Broker: {BROKER_HOST}")
    
    processes = ["process_1", "process_2", "process_3", "process_4"]
    
    threads = []
    for pid in processes:
        t = threading.Thread(target=simulate_single_sensor, args=(pid,), name=pid)
        t.start()
        threads.append(t)
        
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\nStopping all simulations...")

if __name__ == "__main__":
    main()
