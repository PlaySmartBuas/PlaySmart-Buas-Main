import os
import glob
import re
import argparse
import pandas as pd
 
 
# ------------------ BASE PATH ------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
 
 
# ------------------ HELPERS ------------------
 
def extract_session_id(path):
    name = os.path.basename(path)
    parts = name.split("_")
    return "_".join(parts[:-1])  # remove _tag
 
 
def session_time(session):
    """
    Extract datetime from session ID using regex.
    """
    match = re.search(r"(\d{2}-\d{2}-\d{4})_(\d{2}-\d{2}-\d{2})", session)
 
    if not match:
        raise ValueError(f"Cannot parse session time from: {session}")
 
    return pd.to_datetime(
        f"{match.group(1)} {match.group(2)}",
        format="%d-%m-%Y %H-%M-%S"
    )
 
 
def get_sessions(folder, tag):
    files = glob.glob(os.path.join(folder, f"*_{tag}.csv"))
 
    sessions = {}
    for f in files:
        session = extract_session_id(f)
        sessions.setdefault(session, []).append(f)
 
    return sessions
 
 
# ------------------ LOADER ------------------
 
def load_csv_clean_time(path, label):
    df = pd.read_csv(path)
 
    if 'unix_time' not in df.columns:
        raise ValueError(f"{label}: missing 'unix_time' column")
 
    before = len(df)
 
    df['unix_time'] = pd.to_numeric(df['unix_time'], errors='coerce')
 
    # seconds → ms
    if df['unix_time'].max() < 1e12:
        print(f"[WARNING] {label} in seconds → converting to ms")
        df['unix_time'] *= 1000
 
    df['unix_time'] = df['unix_time'].round()
    df.dropna(subset=['unix_time'], inplace=True)
 
    if df.empty:
        raise ValueError(f"{label} empty after cleaning")
 
    df['unix_time'] = df['unix_time'].astype('int64')
    df = df.sort_values('unix_time')
 
    print(f"{label}: {df['unix_time'].min()} → {df['unix_time'].max()} ({len(df)}/{before})")
 
    return df
 
 
# ------------------ MAIN ------------------
 
def main():
    ap = argparse.ArgumentParser(description="Merge gaze, KBM, emotion, and EDA")
 
    ap.add_argument("--gaze")
    ap.add_argument("--kbm")
    ap.add_argument("--emotion")
    ap.add_argument("--eda", required=False)
    ap.add_argument("--outdir", required=True)
 
    ap.add_argument("--tolerance", type=int, default=500)
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--no_auto_align", action="store_true")
 
    args = ap.parse_args()
 
 
    # ---------------- AUTO MODE ----------------
    if args.auto:
        print("[AUTO] Searching for complete session...")
 
        gaze_sessions = get_sessions(os.path.join(BASE_DIR, "data/gaze"), "gaze")
        kbm_sessions  = get_sessions(os.path.join(BASE_DIR, "data/input"), "input")
        emo_sessions  = get_sessions(os.path.join(BASE_DIR, "data/emotion"), "emotion")
        eda_sessions  = get_sessions(os.path.join(BASE_DIR, "data/eda"), "eda")
 
        common = (
            set(gaze_sessions.keys())
            & set(kbm_sessions.keys())
            & set(emo_sessions.keys())
        )
 
        if not common:
            raise ValueError("❌ No complete session found")
 
        best_session = max(common, key=session_time)
 
        args.gaze = gaze_sessions[best_session][0]
        args.kbm = kbm_sessions[best_session][0]
        args.emotion = emo_sessions[best_session][0]
        args.eda = eda_sessions.get(best_session, [None])[0]
 
        print("\n✅ Selected session:", best_session)
        print("gaze:", args.gaze)
        print("kbm:", args.kbm)
        print("emotion:", args.emotion)
        print("eda:", args.eda)
 
 
    # ---------------- LOAD DATA ----------------
    print("\nLoading datasets...")
 
    df_gaze = load_csv_clean_time(args.gaze, "Gaze")
    df_kbm  = load_csv_clean_time(args.kbm, "KBM")
    df_emo  = load_csv_clean_time(args.emotion, "Emotion")
 
    df_eda = None
    if args.eda:
        df_eda = load_csv_clean_time(args.eda, "EDA")
 
 
    # ---------------- ALIGN ----------------
    if not args.no_auto_align:
        earliest = min(df_gaze['unix_time'].min(), df_kbm['unix_time'].min())
 
        emo_offset = int(earliest - df_emo['unix_time'].min())
        df_emo['unix_time'] += emo_offset
 
        if df_eda is not None:
            eda_offset = int(earliest - df_eda['unix_time'].min())
            df_eda['unix_time'] += eda_offset
 
 
    # ---------------- MERGE ----------------
    print("\nMerging gaze + KBM...")
 
    df_merge = pd.merge_asof(
        df_gaze,
        df_kbm,
        on='unix_time',
        direction='nearest',
        tolerance=args.tolerance
    )
 
    print("Merging emotion...")
 
    df_merge = pd.merge_asof(
        df_merge,
        df_emo,
        on='unix_time',
        direction='nearest',
        tolerance=args.tolerance
    )
 
    if df_eda is not None:
        print("Merging EDA...")
 
        df_merge = pd.merge_asof(
            df_merge,
            df_eda,
            on='unix_time',
            direction='nearest',
            tolerance=args.tolerance
        )
    else:
        print("[EDA] Skipped")
 
 
    # ---------------- SAVE ----------------
    df_merge['datetime'] = pd.to_datetime(df_merge['unix_time'], unit='ms')
 
    prefix = extract_session_id(args.gaze) + "_"
 
    os.makedirs(args.outdir, exist_ok=True)
 
    out_path = os.path.join(args.outdir, f"{prefix}merged.csv")
    df_merge.to_csv(out_path, index=False)
 
    print(f"\nSaved → {out_path}")
 
 
if __name__ == "__main__":
    main()