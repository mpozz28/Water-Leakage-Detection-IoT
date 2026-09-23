import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

def generate_sensor_data(bucket_height=9.0, duration_per_phase=100, freq=1):
    """
    bucket_height: Height of bucket in cm.
    Generates data with stable phases and leaking phases to train a robust model.
    """
    data_rows = []
    
    # --- Simulation Parameters ---
    # Distance from sensor to water (cm). 
    # 0 = Full to brim (theoretically), 9 = Empty.
    
    current_dist = 2.0 # Start with water near top (7cm water in 9cm bucket)
    
    # Phase 1: Stable Full (No Leak)
    for _ in range(duration_per_phase):
        noise = np.random.uniform(-0.5, 0.5) # +/- 5mm noise
        reading = current_dist + noise
        reading = max(0, min(reading, bucket_height))
        data_rows.append({'Sensor_Distance': reading, 'Leakage': False})
        
    # Phase 2: Leaking (Water level drops -> Distance increases)
    # We pick a RANDOM leak rate for this phase to make the model robust to different leak sizes
    base_leak_rate = np.random.uniform(0.05, 0.5) # Random rate between 0.05cm and 0.5cm per sample
    print("Simulating leak with base rate: {:.3f} cm/sample".format(base_leak_rate))
    for _ in range(duration_per_phase):
        current_dist += base_leak_rate
        # Add some randomness to the flow itself
        current_dist += np.random.uniform(-0.02, 0.02)
        
        noise = np.random.uniform(-0.1, 0.1)
        reading = current_dist + noise
        reading = max(0, min(reading, bucket_height))
        
        # If we hit bottom, stop leaking
        if current_dist >= bucket_height:
            current_dist = bucket_height
            data_rows.append({'Sensor_Distance': reading, 'Leakage': False})
        else:
            data_rows.append({'Sensor_Distance': reading, 'Leakage': True})

    # Phase 3: Stable Empty/Low (No Leak)
    # This is crucial so the model doesn't learn "High Distance = Leak"
    for _ in range(duration_per_phase):
        noise = np.random.uniform(-0.1, 0.1)
        reading = current_dist + noise
        reading = max(0, min(reading, bucket_height))
        data_rows.append({'Sensor_Distance': reading, 'Leakage': False})

    df = pd.DataFrame(data_rows)
    df['Time'] = df.index  # Add Time column for plotting
    
    # --- Feature Engineering ---
    # The model needs to know the RATE of change, not just absolute distance.
    df['Prev_Sensor_Distance'] = df['Sensor_Distance'].shift(1)
    df['Diff'] = df['Sensor_Distance'] - df['Prev_Sensor_Distance']
    
    # Fill NaN for the first row
    df = df.fillna(0)
    
    return df

def generate_large_dataset(num_episodes=50):
    all_data = []
    print(f"Generating {num_episodes} episodes with different leak rates...")
    
    for i in range(num_episodes):
        # Each call picks a new random leak rate internally
        df = generate_sensor_data(bucket_height=9.0, duration_per_phase=100)
        # Add an episode ID just in case we need to distinguish later (optional)
        df['Episode'] = i
        all_data.append(df)
        
    final_df = pd.concat(all_data, ignore_index=True)
    if not os.path.exists('sensor_data.csv'):
        final_df.to_csv('sensor_data.csv', index=False)
    else:
        # remove existing file to avoid appending duplicates
        os.remove('sensor_data.csv')
        final_df.to_csv('sensor_data.csv', index=False)
    print(f"Total data generated: {len(final_df)} samples. Saved to sensor_data.csv")
    return final_df

def plot_sensor_data(data):
    plt.figure(figsize=(12, 6))
    
    # Plotting Distance
    plt.plot(data['Time'], data['Sensor_Distance'], label='Sensor Distance (Air Gap)', color='purple')
    
    plt.title('Sonar Sensor Reading (Top-Mounted)')
    plt.xlabel('Time (s)')
    plt.ylabel('Distance from Sensor (cm)')

    
    plt.legend()
    plt.grid()
    plt.show()

if __name__ == "__main__":
    # Generate a large, diverse dataset for training
    data = generate_large_dataset(num_episodes=50)
    
    # Plot just the first episode to verify it looks correct
    first_episode = data[data['Episode'] == 0]
    second_episode = data[data['Episode'] == 1]
    third_episode = data[data['Episode'] == 2]
    plot_sensor_data(first_episode) # Commented out to avoid blocking execution
    plot_sensor_data(second_episode)
    plot_sensor_data(third_episode)

