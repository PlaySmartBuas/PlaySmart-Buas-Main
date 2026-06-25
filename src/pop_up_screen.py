 
import os
import glob
import datetime
import tkinter as tk
from tkinter import simpledialog, ttk
import json
import sys
import time
import uuid
 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from server.python_app.sftp_upload import upload_file_to_sftp
 
# ------------------ PC CONFIG ------------------
 
PC_NAME = "pc02"
 
# ------------------ Utility Functions ------------------
 
def get_latest_file(path):
 
    files = glob.glob(os.path.join(path, "*.csv"))
 
    return max(files, key=os.path.getmtime) if files else None
 
 
def get_latest_by_extension(path, extension):
 
    files = glob.glob(os.path.join(path, f"*.{extension}"))
 
    return max(files, key=os.path.getmtime) if files else None
 
 
def get_latest_video_any(path):
 
    files = (
        glob.glob(os.path.join(path, "*.mp4")) +
        glob.glob(os.path.join(path, "*.mkv"))
    )
 
    return max(files, key=os.path.getmtime) if files else None
 
 
def get_next_player_id(mapping):
 
    existing_ids = [
        v for v in mapping.values()
        if v.startswith("P")
    ]
 
    nums = [
        int(x[1:])
        for x in existing_ids
        if x[1:].isdigit()
    ]
 
    next_id = max(nums, default=0) + 1
 
    return f"P{next_id:03d}"
 
 
def load_mapping(mapping_file='data/json/ign_mapping.json'):
 
    if os.path.exists(mapping_file):
 
        with open(mapping_file, 'r') as file:
            return json.load(file)
 
    return {}
 
 
def save_mapping(mapping, mapping_file='data/json/ign_mapping.json'):
 
    os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
 
    with open(mapping_file, 'w') as file:
        json.dump(mapping, file, indent=4)
 
 
def upload_ign_mapping():
 
    mapping_file = 'data/json/ign_mapping.json'
 
    if not os.path.exists(mapping_file):
        return
 
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
 
    temp_name = f"ign_mapping_{PC_NAME}_{timestamp}.json"
 
    temp_local = os.path.join(
        "data/json",
        temp_name
    )
 
    try:
 
        # create timestamped copy locally
        with open(mapping_file, 'r') as src:
            data = json.load(src)
 
        with open(temp_local, 'w') as dst:
            json.dump(data, dst, indent=4)
 
        print("Uploading IGN mapping...")
 
        upload_file_to_sftp(
            temp_local,
            "/data/json/"
        )
 
        print("IGN mapping uploaded")
 
        # optional cleanup
        os.remove(temp_local)
 
    except Exception as e:
 
        print(f"IGN mapping upload failed: {e}")
 
 
def load_daily_game_count(count_file='data/json/date_game_count.json'):
 
    if os.path.exists(count_file):
 
        try:
 
            with open(count_file, 'r') as file:
                return json.load(file)
 
        except json.JSONDecodeError:
            return {}
 
    return {}
 
 
def save_daily_game_count(data, count_file='data/json/date_game_count.json'):
 
    os.makedirs(os.path.dirname(count_file), exist_ok=True)
 
    with open(count_file, 'w') as file:
        json.dump(data, file, indent=4)
 
 
def update_daily_game_count(game_name):
 
    today = datetime.datetime.now().strftime("%d-%m-%Y")
 
    data = load_daily_game_count()
 
    data.setdefault(today, {})
 
    data[today][game_name] = data[today].get(game_name, 0) + 1
 
    save_daily_game_count(data)
 
    return get_ordinal(data[today][game_name]), today
 
 
def get_ordinal(n):
 
    return f"{n}{'th' if 4 <= n % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"
 
 
# ------------------ Upload Function ------------------
 
def upload_newest_file(folder_path, dest_directory, extension=None):
 
    if not os.path.exists(folder_path):
        print(f"Missing folder: {folder_path}")
        return
 
    files = []
 
    for f in os.listdir(folder_path):
 
        full_path = os.path.join(folder_path, f)
 
        if not os.path.isfile(full_path):
            continue
 
        if extension and not f.lower().endswith(extension.lower()):
            continue
 
        files.append(full_path)
 
    if not files:
        print(f"No {extension} files in {folder_path}")
        return
 
    newest = max(files, key=os.path.getmtime)
 
    for i in range(3):
 
        try:
 
            print(f"Uploading: {newest}")
 
            upload_file_to_sftp(newest, dest_directory)
 
            print(f"Uploaded: {os.path.basename(newest)}")
 
            return
 
        except Exception as e:
 
            print(f"Retry {i+1} failed: {e}")
 
            time.sleep(2)
 
 
# ------------------ Main ------------------
 
def main():
 
    class DualInputDialog(simpledialog.Dialog):
 
        def body(self, master):
 
            tk.Label(master, text="In-game name:").grid(row=0, column=0)
            tk.Label(master, text="Game:").grid(row=1, column=0)
 
            mapping = load_mapping()
 
            self.player = ttk.Combobox(
                master,
                values=sorted(mapping.keys())
            )
 
            self.player.grid(row=0, column=1)
 
            self.game = ttk.Combobox(
                master,
                values=[
                    "valorant",
                    "league_of_legends",
                    "other"
                ],
                state="readonly"
            )
 
            self.game.set("valorant")
 
            self.game.grid(row=1, column=1)
 
            return self.player
 
        def apply(self):
 
            self.player_name = self.player.get().strip()
 
            self.game_name = self.game.get().strip().lower()
 
    # ---------------- INPUT ----------------
 
    root = tk.Tk()
 
    root.withdraw()
 
    dialog = DualInputDialog(root)
 
    player_name = getattr(dialog, 'player_name', None)
    game_name = getattr(dialog, 'game_name', None)
 
    if not player_name or not game_name:
 
        print("Invalid input")
 
        return
 
    # ---------------- PLAYER ----------------
 
    mapping = load_mapping()
 
    if player_name not in mapping:
 
        mapping[player_name] = get_next_player_id(mapping)
 
        save_mapping(mapping)
 
    player_id = mapping[player_name]
 
    ordinal, today = update_daily_game_count(game_name)
 
    now = datetime.datetime.now().strftime("%H-%M-%S")
 
    base_name = f"{ordinal}_game_{player_id}_{game_name}_{today}_{now}"
 
    def is_already_processed(filepath):
 
        return "_game_" in os.path.basename(filepath)
 
    # ---------------- CSV RENAME ----------------
 
    for folder, tag in {
        "data/input": "input",
        "data/gaze": "gaze",
        "data/emotion": "emotion",
        "data/eda": "eda",
    }.items():
 
        latest = get_latest_file(folder)
 
        if latest and not is_already_processed(latest):
 
            new_path = os.path.join(
                folder,
                f"{base_name}_{tag}.csv"
            )
 
            try:
 
                os.replace(latest, new_path)
 
                print(f"Renamed {tag}")
 
                time.sleep(1)
 
            except Exception as e:
 
                print(f"Rename failed for {tag}: {e}")
 
    # ---------------- AUDIO ----------------
 
    audio_folder = "data/audio"
 
    latest_audio = get_latest_by_extension(audio_folder, "wav")
 
    if latest_audio:
 
        try:
 
            new_audio = os.path.join(
                audio_folder,
                f"{base_name}.wav"
            )
 
            os.replace(latest_audio, new_audio)
 
            txt = latest_audio.replace(".wav", ".txt")
 
            if os.path.exists(txt):
 
                os.replace(
                    txt,
                    os.path.join(audio_folder, f"{base_name}.txt")
                )
 
        except Exception as e:
 
            print(f"Audio rename failed: {e}")
 
    # ---------------- VIDEO ----------------
 
    video_src = os.path.join(
        os.path.expanduser("~"),
        "Videos"
    )
 
    video_dst = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "research_software",
        "data",
        "video"
    )
 
    os.makedirs(video_dst, exist_ok=True)
 
    latest_video = get_latest_video_any(video_src)
 
    if latest_video:
 
        try:
 
            ext = os.path.splitext(latest_video)[1]
 
            os.replace(
                latest_video,
                os.path.join(video_dst, f"{base_name}{ext}")
            )
 
        except Exception as e:
 
            print(f"Video rename failed: {e}")
 
    # ---------------- UPLOAD ----------------
 
    print("Waiting before upload...")
 
    time.sleep(3)
 
    # CSV uploads
    upload_newest_file(
        'data/emotion',
        "/data/emotion/",
        ".csv"
    )
 
    upload_newest_file(
        'data/input',
        "/data/input/",
        ".csv"
    )
 
    upload_newest_file(
        'data/gaze',
        "/data/gaze/",
        ".csv"
    )
 
    upload_newest_file(
        'data/eda',
        "/data/eda/",
        ".csv"
    )
 
    # PNG uploads
    upload_newest_file(
        'data/gaze',
        "/data/gaze/",
        ".png"
    )
 
    # Video upload
    upload_newest_file(
        video_dst,
        "/data/video/",
        ".mp4"
    )
 
    # ---------------- AUDIO UPLOAD ----------------
 
    if os.path.exists(audio_folder):
 
        for f in os.listdir(audio_folder):
 
            full = os.path.join(audio_folder, f)
 
            if os.path.isfile(full):
 
                try:
 
                    print(f"Uploading audio: {full}")
 
                    upload_file_to_sftp(
                        full,
                        "/data/audio/"
                    )
 
                except Exception as e:
 
                    print(f"Audio upload failed: {e}")
 
    # ---------------- IGN MAPPING UPLOAD ----------------
 
    upload_ign_mapping()
 
 
# ------------------ Run ------------------
 
if __name__ == "__main__":
 
    main()