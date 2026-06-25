import time
import os
import random
from datetime import datetime
import pandas as pd
import screeninfo
import tobii_research as tr
import keyboard
import matplotlib.pyplot as plt

# ---------------------------
# SCREEN SETUP
# ---------------------------
screen = screeninfo.get_monitors()[0]
screen_width, screen_height = screen.width, screen.height
screen_resolution = f"{screen_width}x{screen_height}p"

# ---------------------------
# FOLDER SETUP
# ---------------------------
data_folder = 'data/gaze'
os.makedirs(data_folder, exist_ok=True)

gaze_data_list = []

# ---------------------------
# EYE TRACKER SETUP
# ---------------------------
eyetrackers = tr.find_all_eyetrackers()
my_eyetracker = eyetrackers[0] if eyetrackers else None
use_mock_data = len(eyetrackers) == 0

if use_mock_data:
    print("No eye tracker found. Using mock data...")
else:
    print(f"Connected to: {my_eyetracker.model}")

# ---------------------------
# SMOOTHED GAZE
# ---------------------------
smoothed_x, smoothed_y = screen_width // 2, screen_height // 2

# ---------------------------
# BASELINE SETTINGS
# ---------------------------
baseline_samples = 60
baseline_pupil_values = []
baseline_pupil = None

# ---------------------------
# DELTA TRACKING (NEW)
# ---------------------------
previous_avg_pupil = None

# ---------------------------
# MOCK DATA
# ---------------------------
def generate_mock_gaze():
    return random.uniform(0.1, 0.8), random.uniform(0.1, 0.8)

def generate_mock_pupil():
    return random.uniform(2.5, 4.5)

# ---------------------------
# CALLBACK
# ---------------------------
def gaze_data_callback(gaze_data):
    global smoothed_x, smoothed_y
    global baseline_pupil, baseline_pupil_values
    global previous_avg_pupil

    unix_time = int(time.time() * 1000)

    # Gaze + pupil
    if use_mock_data:
        left_gaze_x, left_gaze_y = generate_mock_gaze()
        right_gaze_x, right_gaze_y = generate_mock_gaze()
        left_pupil = generate_mock_pupil()
        right_pupil = generate_mock_pupil()
    else:
        left_gaze_x, left_gaze_y = gaze_data.get('left_gaze_point_on_display_area', (None, None))
        right_gaze_x, right_gaze_y = gaze_data.get('right_gaze_point_on_display_area', (None, None))
        left_pupil = gaze_data.get('left_pupil_diameter', None)
        right_pupil = gaze_data.get('right_pupil_diameter', None)

    # Average gaze
    if None not in (left_gaze_x, left_gaze_y, right_gaze_x, right_gaze_y):
        avg_x = (left_gaze_x + right_gaze_x) / 2
        avg_y = (left_gaze_y + right_gaze_y) / 2
    else:
        avg_x, avg_y = generate_mock_gaze()

    smoothed_x = int(avg_x * screen_width)
    smoothed_y = int(avg_y * screen_height)

    # Average pupil
    if left_pupil is not None and right_pupil is not None:
        avg_pupil = (left_pupil + right_pupil) / 2
    else:
        avg_pupil = left_pupil or right_pupil

    pupil_dilation = None
    pupil_delta_change = None

    if avg_pupil is not None:
        # ---------------------------
        # BASELINE BUILDING
        # ---------------------------
        if len(baseline_pupil_values) < baseline_samples:
            baseline_pupil_values.append(avg_pupil)

        elif baseline_pupil is None:
            baseline_pupil = sum(baseline_pupil_values) / len(baseline_pupil_values)
            print(f"Baseline established: {baseline_pupil:.2f} mm")

        # ---------------------------
        # BASELINE DILATION
        # ---------------------------
        if baseline_pupil is not None:
            pupil_dilation = avg_pupil - baseline_pupil

        # ---------------------------
        # DELTA CHANGE (NEW)
        # ---------------------------
        if previous_avg_pupil is not None:
            pupil_delta_change = avg_pupil - previous_avg_pupil

        previous_avg_pupil = avg_pupil

    # ---------------------------
    # STORE DATA
    # ---------------------------
    gaze_data_list.append({
        "unix_time": unix_time,
        "left_gaze_x": left_gaze_x,
        "left_gaze_y": left_gaze_y,
        "right_gaze_x": right_gaze_x,
        "right_gaze_y": right_gaze_y,
        "screen_x": smoothed_x,
        "screen_y": smoothed_y,
        "left_pupil_diameter": left_pupil,
        "right_pupil_diameter": right_pupil,
        "avg_pupil_diameter": avg_pupil,        # absolute
        "baseline_pupil": baseline_pupil,
        "pupil_dilation": pupil_dilation,       # vs baseline
        "pupil_delta_change": pupil_delta_change,  # NEW
        "screen_resolution": screen_resolution
    })

# Subscribe
if not use_mock_data:
    my_eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback, as_dictionary=True)

# ---------------------------
# MAIN LOOP
# ---------------------------
print("Recording... Press F12 to stop.")

try:
    while not keyboard.is_pressed("f12"):
        if use_mock_data:
            gaze_data_callback({})
        time.sleep(1/60)

# ---------------------------
# SAVE + PLOT
# ---------------------------
finally:
    if not use_mock_data:
        my_eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)

    if not gaze_data_list:
        print("No data recorded.")
    else:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        # Save CSV
        csv_path = os.path.join(data_folder, f'gaze_data_{timestamp}.csv')
        df = pd.DataFrame(gaze_data_list)
        df.to_csv(csv_path, index=False)

        print(f"CSV saved: {csv_path}")

        # ---------------------------
        # SAVE GRAPH (DILATION)
        # ---------------------------
        df_dilation = df.dropna(subset=["pupil_dilation"])

        if not df_dilation.empty:
            time_sec = (df_dilation["unix_time"] - df_dilation["unix_time"].iloc[0]) / 1000

            plt.figure()
            plt.plot(time_sec, df_dilation["pupil_dilation"])
            plt.xlabel("Time (seconds)")
            plt.ylabel("Pupil Dilation (mm)")
            plt.title("Pupil Dilation Over Time")
            plt.grid()

            image_path = os.path.join(data_folder, f'pupil_dilation_{timestamp}.png')
            plt.savefig(image_path)
            plt.close()

            print(f"Dilation graph saved: {image_path}")
        else:
            print("No dilation data (record longer or reduce baseline_samples).")

        # ---------------------------
        # SAVE GRAPH (ABSOLUTE SIZE)
        # ---------------------------
        df_abs = df.dropna(subset=["avg_pupil_diameter"])

        if not df_abs.empty:
            time_sec = (df_abs["unix_time"] - df_abs["unix_time"].iloc[0]) / 1000

            plt.figure()
            plt.plot(time_sec, df_abs["avg_pupil_diameter"])
            plt.xlabel("Time (seconds)")
            plt.ylabel("Pupil Diameter (mm)")
            plt.title("Absolute Pupil Diameter Over Time")
            plt.grid()

            image_path = os.path.join(data_folder, f'pupil_absolute_{timestamp}.png')
            plt.savefig(image_path)
            plt.close()

            print(f"Absolute graph saved: {image_path}")
        else:
            print("No absolute pupil data.")