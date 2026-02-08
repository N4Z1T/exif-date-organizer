import os
import sys
import re
import logging
import argparse
import traceback
from collections import Counter
from datetime import datetime
from PIL import Image, ExifTags

# --- HEIC SUPPORT ---
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False

# --- PROGRESS BAR ---
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

# =======================
# CONFIG
# =======================
LOG_FILENAME = "renamer_fix.log"
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.tiff', '.heic')
VIDEO_EXT = ('.mp4', '.mov', '.avi', '.mkv', '.3gp', '.m4v')
DATE_OUTPUT_FORMAT = "%Y-%m-%d"  # ISO Standard

# =======================
# LOGGING
# =======================
logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# =======================
# UTILS
# =======================
def setup_arguments():
    parser = argparse.ArgumentParser(description="Rename ONLY main folders based on recursive media dates.")
    parser.add_argument("path", help="Path induk (cth: /volume1/photo/2026)")
    parser.add_argument("--live", action="store_true", help="Jalankan rename sebenar")
    parser.add_argument("--confidence", type=float, default=0.6, help="Min confidence (0.0 - 1.0)")
    parser.add_argument("--non-interactive", action="store_true", help="Auto-skip jika tiada metadata")
    return parser.parse_args()

def clean_folder_name(foldername):
    """
    Membersihkan nama folder:
    1. Buang tarikh lama di depan.
    2. Tukar format jadi Title Case (Huruf Besar Setiap Perkataan).
    """
    # Buang nombor/tarikh di depan
    cleaned = re.sub(r"^[\d\.\-\/\s]+", "", foldername)
    
    # Kalau nama kosong lepas clean, return asal
    if not cleaned.strip(): return foldername
    
    # .strip() buang space tepi
    # .title() tukar "bacaan yassin" -> "Bacaan Yassin"
    return cleaned.strip().title()

def get_unique_path(path):
    counter = 1
    base = path
    while os.path.exists(path):
        path = f"{base} ({counter})"
        counter += 1
    return path

def normalize_date(date_str):
    try:
        dt_obj = datetime.strptime(str(date_str).split(" ")[0], "%Y:%m:%d")
        return dt_obj
    except (ValueError, TypeError):
        return None

def get_filesystem_date(filepath):
    try:
        ts = os.path.getmtime(filepath)
        return datetime.fromtimestamp(ts)
    except OSError:
        return None

# =======================
# METADATA LOGIC
# =======================
def get_date_from_image(filepath):
    try:
        with Image.open(filepath) as img:
            exif = img.getexif()
            if not exif: return None
            date_str = exif.get(36867) or exif.get(306)
            if date_str: return normalize_date(date_str)
    except Exception:
        pass
    return None

def get_date_from_video(filepath):
    try:
        parser = createParser(filepath)
        if not parser: return None
        with parser:
            metadata = extractMetadata(parser)
            if metadata and metadata.has("creation_date"):
                return metadata.get("creation_date")
    except Exception:
        pass
    return None

def collect_dates_recursive(root_folder, non_interactive):
    """
    Fungsi ini masuk ke dalam SEMUA subfolder (CANON, NIKON, etc)
    untuk KUMPUL tarikh sahaja, tapi TIDAK rename folder dalam tu.
    """
    date_counter = Counter()
    files_needing_input = [] # Simpan list untuk tanya user nanti
    
    # Kita guna os.walk di sini untuk scan deep ke dalam
    all_files = []
    for dirpath, _, filenames in os.walk(root_folder):
        for f in filenames:
            if f.lower().endswith(IMAGE_EXT + VIDEO_EXT):
                all_files.append(os.path.join(dirpath, f))

    if not all_files:
        return None, False # Tiada file

    # Progress bar untuk file scanning
    iterator = tqdm(all_files, unit="file", leave=False) if TQDM_AVAILABLE else all_files

    for filepath in iterator:
        date_obj = None
        if filepath.lower().endswith(IMAGE_EXT): date_obj = get_date_from_image(filepath)
        elif filepath.lower().endswith(VIDEO_EXT): date_obj = get_date_from_video(filepath)
        
        if date_obj:
            date_counter[date_obj.strftime("%Y-%m-%d")] += 1
        else:
            # Jika tiada metadata, kita simpan dulu, nanti handle
            files_needing_input.append(filepath)

    # Handle fail tiada metadata (Interaktif)
    for filepath in files_needing_input:
        # Jika dah cukup majoriti, tak payah tanya user pun takpe (Optional logic)
        # Tapi ikut spec asal, kita fallback ke FileSystem atau tanya user
        
        if non_interactive:
            # Auto fallback ke file system date kalau non-interactive
            fs_date = get_filesystem_date(filepath)
            if fs_date: date_counter[fs_date.strftime("%Y-%m-%d")] += 1
            continue

        # Tanya user (Paused)
        fname = os.path.basename(filepath)
        parent = os.path.basename(os.path.dirname(filepath))
        print(f"\n[!] Metadata Missing: {fname} (in /{parent})")
        
        while True:
            c = input("    [S]kip Folder | [I]gnore File | [M]anual Date | [Q]uit >> ").upper()
            if c == 'Q': sys.exit(0)
            if c == 'S': return None, True # Signal untuk skip seluruh folder BAPA
            if c == 'I': break # Ignore file ni
            if c == 'M':
                m = input("    YYYY-MM-DD: ").strip()
                try:
                    d = datetime.strptime(m, "%Y-%m-%d")
                    date_counter[d.strftime("%Y-%m-%d")] += 1
                    break
                except ValueError: print("    Invalid.")
    
    return date_counter, False

# =======================
# MAIN PROCESS (UPDATED)
# =======================
def process_folders(args):
    target_path = os.path.abspath(args.path)
    dry_run = not args.live
    
    print(f"\n{'='*40}")
    print(f" TARGET: {target_path}")
    print(f" MODE  : {'[DRY RUN]' if dry_run else '[LIVE]'}")
    print(f" NOTE  : Only renaming top-level subfolders.")
    print(f"{'='*40}\n")

    if not os.path.exists(target_path):
        print("Path not found.")
        return

    # LIST HANYA FOLDER UTAMA (Level 1)
    # Ini menghalang script masuk rename sub-sub-folder
    try:
        subdirs = [f.path for f in os.scandir(target_path) if f.is_dir()]
    except OSError as e:
        print(f"Error accessing path: {e}")
        return

    subdirs.sort() # Sort supaya kemas masa process

    for folder_path in subdirs:
        folder_name = os.path.basename(folder_path)
        print(f"Processing: {folder_name}...")

        # 1. Deep Scan untuk cari tarikh (Masuk CANON dsb)
        date_stats, should_skip = collect_dates_recursive(folder_path, args.non_interactive)

        if should_skip or not date_stats:
            logging.info(f"Skipped {folder_name} (No valid media/User skipped)")
            continue

        # 2. Kira Majoriti
        most_common_date_str, count = date_stats.most_common(1)[0]
        total_files = sum(date_stats.values())
        confidence = count / total_files

        if confidence < args.confidence:
            print(f"   -> [SKIP] Low Confidence ({confidence:.2f})")
            continue

        # 3. Rename Folder BAPA Sahaja
        clean_name = clean_folder_name(folder_name)
        date_final = datetime.strptime(most_common_date_str, "%Y-%m-%d")
        new_name = f"{date_final.strftime(DATE_OUTPUT_FORMAT)} {clean_name}"

        if new_name == folder_name:
            continue

        new_full_path = get_unique_path(os.path.join(target_path, new_name))

        if dry_run:
            print(f"   -> [DRY] {folder_name} \n            --> {new_name}")
        else:
            try:
                os.rename(folder_path, new_full_path)
                print(f"   -> [OK] Renamed to: {new_name}")
                logging.info(f"RENAMED: {folder_name} -> {new_name}")
            except OSError as e:
                print(f"   -> [ERROR] {e}")

if __name__ == "__main__":
    args = setup_arguments()
    try:
        process_folders(args)
    except KeyboardInterrupt:
        print("\nStopped.")
