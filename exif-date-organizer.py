import os
import sys
import re
import csv
import logging
from collections import Counter
from datetime import datetime

from PIL import Image

# HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False

from hachoir.parser import createParser
from hachoir.metadata import extractMetadata


# =======================
# KONFIGURASI
# =======================

TARGET_PATH = r"C:\Users\NamaUser\Pictures\Percutian"

IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.tiff', '.heic')
VIDEO_EXT = ('.mp4', '.mov', '.avi', '.mkv')

MIN_CONFIDENCE = 0.6
NON_INTERACTIVE = False

CSV_REPORT = "rename_preview.csv"
LOG_FILE = "rename_media_folder.log"


# =======================
# LOGGING
# =======================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# =======================
# TARIKH UTILITI
# =======================

def normalize_date(date_str):
    return date_str.split(" ")[0].replace(":", "-")


def filesystem_date(filepath):
    ts = os.path.getmtime(filepath)
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


# =======================
# METADATA IMAGE
# =======================

def get_date_from_image(filepath):
    try:
        with Image.open(filepath) as img:
            exif = img.getexif()
            if not exif:
                return None
            if 36867 in exif:
                return normalize_date(exif[36867])
            if 306 in exif:
                return normalize_date(exif[306])
    except Exception:
        return None
    return None


# =======================
# METADATA VIDEO
# =======================

def get_date_from_video(filepath):
    try:
        parser = createParser(filepath)
        if not parser:
            return None
        with parser:
            metadata = extractMetadata(parser)
            if metadata and metadata.has("creation_date"):
                return metadata.get("creation_date").strftime("%Y-%m-%d")
    except Exception:
        return None
    return None


# =======================
# FOLDER UTIL
# =======================

def is_already_renamed(folder):
    return re.match(r"^\d{4}-\d{2}-\d{2}", folder) is not None


def unique_path(path):
    base = path
    counter = 1
    while os.path.exists(path):
        path = f"{base} ({counter})"
        counter += 1
    return path


def handle_missing_metadata(file, folder):
    if NON_INTERACTIVE:
        return "IGNORE", None

    print(f"\n[!] Metadata TIADA: {file}")
    print(f"    Folder: {folder}")

    while True:
        c = input("[S]kip folder | [I]gnore file | [M]anual | [Q]uit >> ").upper()
        if c == "S":
            return "SKIP_FOLDER", None
        if c == "I":
            return "IGNORE", None
        if c == "Q":
            sys.exit("Script dihentikan.")
        if c == "M":
            d = input("Tarikh (YYYY-MM-DD): ").strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                return "MANUAL", d
            print("Format salah.")


# =======================
# SCAN & BUILD REPORT
# =======================

def scan_folders(root_dir):
    report = []

    for dirpath, _, filenames in os.walk(root_dir, topdown=False):
        folder = os.path.basename(dirpath)

        if is_already_renamed(folder):
            continue

        media = [f for f in filenames if f.lower().endswith(IMAGE_EXT + VIDEO_EXT)]
        if not media:
            continue

        print(f"Scanning: {folder}")
        date_counter = Counter()
        skip = False

        for f in media:
            path = os.path.join(dirpath, f)
            date = None

            if f.lower().endswith(IMAGE_EXT):
                date = get_date_from_image(path)
            elif f.lower().endswith(VIDEO_EXT):
                date = get_date_from_video(path)

            if not date:
                action, val = handle_missing_metadata(f, folder)
                if action == "SKIP_FOLDER":
                    skip = True
                    break
                if action == "MANUAL":
                    date = val
                if action == "IGNORE":
                    continue

            if not date:
                date = filesystem_date(path)

            date_counter[date] += 1

        if skip or not date_counter:
            continue

        chosen, count = date_counter.most_common(1)[0]
        total = sum(date_counter.values())
        confidence = count / total

        action = "RENAME" if confidence >= MIN_CONFIDENCE else "SKIP_LOW_CONFIDENCE"

        report.append({
            "folder_path": dirpath,
            "folder_name": folder,
            "proposed_new_name": f"{chosen} {folder}",
            "chosen_date": chosen,
            "confidence": round(confidence, 2),
            "total_files": total,
            "date_distribution": " | ".join(
                f"{d}:{c}" for d, c in date_counter.items()
            ),
            "action": action
        })

    return report


# =======================
# CSV OUTPUT
# =======================

def write_csv(report):
    with open(CSV_REPORT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=report[0].keys())
        writer.writeheader()
        writer.writerows(report)


# =======================
# RENAME EXECUTION
# =======================

def execute_rename(report):
    for row in report:
        if row["action"] != "RENAME":
            continue

        old = row["folder_path"]
        parent = os.path.dirname(old)
        new = unique_path(os.path.join(parent, row["proposed_new_name"]))

        try:
            os.rename(old, new)
            print(f"[OK] {os.path.basename(old)} → {os.path.basename(new)}")
            logging.info(f"Renamed: {old} → {new}")
        except Exception as e:
            print(f"[ERROR] {e}")
            logging.error(str(e))


# =======================
# MAIN
# =======================

if __name__ == "__main__":
    if not os.path.exists(TARGET_PATH):
        sys.exit("Path tidak wujud.")

    print("\n=== SCANNING & DRY RUN ===")
    report = scan_folders(TARGET_PATH)

    if not report:
        sys.exit("Tiada folder sesuai.")

    write_csv(report)
    print(f"\nCSV preview dijana: {CSV_REPORT}")

    confirm = input("\nTeruskan RENAME sebenar berdasarkan CSV? (y/n): ").lower()
    if confirm == "y":
        execute_rename(report)
        print("\nSelesai.")
    else:
        print("\nDibatalkan.")
