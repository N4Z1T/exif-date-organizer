import os
import sys
import re
import logging
import argparse
import json
import requests
import time
from collections import Counter
from datetime import datetime
from PIL import Image, ExifTags

# --- 1. TQDM SAFETY ---
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs): return iterable

# --- HACHOIR SUPPORT ---
try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    HACHOIR_AVAILABLE = True
except ImportError:
    HACHOIR_AVAILABLE = False

# --- HEIC SUPPORT ---
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

# --- CONFIG ---
LOG_FILENAME = "renamer_v20.log"
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.tiff', '.heic')
VIDEO_EXT = ('.mp4', '.mov', '.avi', '.mkv', '.3gp', '.m4v')
DATE_OUTPUT_FORMAT = "%Y-%m-%d"
IGNORED_DIRS = {'@eaDir', '#recycle', '.DS_Store', 'Thumbs.db', 'venv'}
IGNORED_FILES = {'SYNOFILE_THUMB', 'desktop.ini', '.DS_Store'}

# --- LOGGING ---
logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# --- UTILS ---
def setup_arguments():
    parser = argparse.ArgumentParser(description="Renamer V20: Final Report Edition.")
    parser.add_argument("path", help="Target folder path")
    parser.add_argument("--live", action="store_true", help="Execute rename")
    parser.add_argument("--confidence", type=float, default=0.6, help="Min confidence (0.0-1.0)")
    parser.add_argument("--non-interactive", action="store_true", help="Auto-skip missing metadata")
    parser.add_argument("--case", default='title', help="Case format (if AI off)")
    parser.add_argument("--ai-api-key", help="Google AI Studio API Key", default=None)
    return parser.parse_args()

def clean_folder_name_regex(foldername, case_type='title'):
    cleaned = re.sub(r"^[\d\.\-\/\s]+", "", foldername).strip()
    if not cleaned: return foldername
    
    if case_type == 'upper': return cleaned.upper()
    elif case_type == 'lower': return cleaned.lower()
    elif case_type == 'title': return cleaned.title()
    elif case_type == 'sentence': return cleaned.capitalize()
    return cleaned.title()

# --- AI LOGIC (GEMMA HUNTER) ---
SELECTED_MODEL = None

def get_high_quota_model(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = [m['name'].replace('models/', '') for m in data.get('models', [])]
            
            # Priority: Gemma 3 (12b/27b) -> Gemma 2 -> Any Gemma -> Gemini 2.0
            gemma_smart = [m for m in models if 'gemma-3' in m and ('12b' in m or '27b' in m)]
            if gemma_smart: return gemma_smart[0]

            any_gemma = [m for m in models if 'gemma' in m]
            if any_gemma: return any_gemma[0]
            
            return "gemini-2.0-flash"
    except Exception as e:
        logging.error(f"Model list failed: {e}")
    return "gemma-3-12b-it"

def ai_fix_spelling(text, api_key):
    global SELECTED_MODEL
    if not api_key: return text

    if SELECTED_MODEL is None:
        print("   [SYSTEM] Selecting Model...", end="\r")
        SELECTED_MODEL = get_high_quota_model(api_key)
        print(f"   [SYSTEM] MODEL: {SELECTED_MODEL}                 ")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{SELECTED_MODEL}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    prompt = (
        f"Tugas: Formatkan tajuk ini. \n"
        f"WAJIB tukar SEMUA HURUF BESAR kepada 'Title Case'.\n"
        f"WAJIB betulkan ejaan Bahasa Melayu.\n"
        f"Kekalkan akronim (KADA, JKR, KPKM) HURUF BESAR.\n"
        f"JANGAN tambah ulasan. HANYA bagi nama akhir.\n\n"
        f"Input: {text}\nOutput:"
    )

    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 60}
    }

    # Static Wait Logic (Tiada Exponential Backoff)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=20)
            
            if response.status_code == 200:
                try:
                    res_json = response.json()
                    cleaned = res_json['candidates'][0]['content']['parts'][0]['text']
                    final_text = cleaned.strip().replace('"', '').replace("'", "").replace("\n", "").replace("*", "")
                    time.sleep(2.5) # Pace 2.5s
                    return final_text
                except:
                    return text
            
            elif response.status_code == 429:
                wait_time = 10 
                print(f"   [WAIT] Quota Penuh. Rehat {wait_time}s...", end="\r")
                time.sleep(wait_time)
                continue
            else:
                return text
        except Exception:
            time.sleep(2)
            continue
        
    return text

# --- METADATA LOGIC ---
def normalize_date(date_str):
    try:
        return datetime.strptime(str(date_str).split(" ")[0], "%Y:%m:%d")
    except: return None

def get_date_from_image(filepath):
    try:
        with Image.open(filepath) as img:
            exif = img.getexif()
            if not exif: return None
            date_str = exif.get(36867) or exif.get(306)
            if date_str: return normalize_date(date_str)
    except: pass
    return None

def get_date_from_video(filepath):
    if not HACHOIR_AVAILABLE: return None
    try:
        parser = createParser(filepath)
        if not parser: return None
        with parser:
            metadata = extractMetadata(parser)
            if metadata and metadata.has("creation_date"):
                return metadata.get("creation_date")
    except: pass
    return None

def collect_dates_recursive(root_folder, non_interactive):
    date_counter = Counter()
    total_files = 0
    all_files = []
    
    for dirpath, dirnames, filenames in os.walk(root_folder):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for f in filenames:
            if any(j in f for j in IGNORED_FILES): continue
            if f.lower().endswith(IMAGE_EXT + VIDEO_EXT):
                all_files.append(os.path.join(dirpath, f))

    if not all_files: return None, 0

    for filepath in tqdm(all_files, unit="file", leave=False):
        total_files += 1
        date_obj = None
        if filepath.lower().endswith(IMAGE_EXT):
            date_obj = get_date_from_image(filepath)
        elif filepath.lower().endswith(VIDEO_EXT):
            date_obj = get_date_from_video(filepath)
        
        if date_obj:
            date_counter[date_obj.strftime("%Y-%m-%d")] += 1
            
    return date_counter, total_files

def get_unique_path(base_path):
    if not os.path.exists(base_path): return base_path
    counter = 1
    while True:
        new_path = f"{base_path} ({counter})"
        if not os.path.exists(new_path): return new_path
        counter += 1

# --- MAIN PROCESS ---
def process_folders(args):
    target_path = os.path.abspath(args.path)
    use_ai = args.ai_api_key is not None
    
    # LIST UNTUK SUMMARY
    renamed_list = []
    skipped_list = []
    error_list = []
    
    print(f"\n{'='*40}")
    print(f" TARGET: {target_path}")
    print(f" MODE  : {'[LIVE RENAME]' if args.live else '[DRY RUN]'}")
    print(f" AI    : {'ENABLED' if use_ai else 'OFF'}")
    print(f"{'='*40}\n")

    if not os.path.exists(target_path): 
        print("Path not found!")
        return

    subdirs = sorted([f.path for f in os.scandir(target_path) if f.is_dir()])
    total_folders = len(subdirs)

    for folder_path in subdirs:
        folder_name = os.path.basename(folder_path)
        if folder_name in IGNORED_DIRS: 
            continue # System folders tak payah masuk report

        print(f"Processing: {folder_name}...")
        
        date_stats, total_files = collect_dates_recursive(folder_path, args.non_interactive)

        # CASE 1: Tiada Metadata
        if not date_stats:
            msg = "Tiada metadata/tarikh dijumpai"
            logging.info(f"Skipped {folder_name}: {msg}")
            skipped_list.append((folder_name, msg))
            continue

        most_common_date_str, count = date_stats.most_common(1)[0]
        confidence = count / total_files if total_files > 0 else 0

        # CASE 2: Low Confidence
        if confidence < args.confidence:
            msg = f"Low Confidence ({confidence:.2f})"
            print(f"   -> [SKIP] {msg}")
            logging.info(f"Skipped {folder_name}: {msg}")
            skipped_list.append((folder_name, msg))
            continue

        # PREPARE NEW NAME
        clean_base = clean_folder_name_regex(folder_name, args.case)
        if use_ai:
            print("   -> [AI] Fixing...", end="\r")
            final_name = ai_fix_spelling(clean_base, args.ai_api_key)
            print(f"   -> [AI] Result: {final_name}          ")
        else:
            final_name = clean_base

        new_name = f"{most_common_date_str} {final_name}"
        
        # CASE 3: Nama Dah Betul (Unchanged)
        if new_name == folder_name: 
            # Kita tak anggap ini 'Skip', tapi 'No Action Needed'
            # Tak perlu masuk list 'renamed' sebab tak ubah apa-apa
            continue

        new_full_path = get_unique_path(os.path.join(target_path, new_name))
        
        # EXECUTE RENAME
        if args.live:
            try:
                os.rename(folder_path, new_full_path)
                print(f"   -> [OK] {new_name}")
                logging.info(f"Renamed: {folder_name} -> {new_name}")
                renamed_list.append((folder_name, new_name))
            except OSError as e:
                print(f"   -> [ERR] {e}")
                logging.error(f"Error {folder_name}: {e}")
                error_list.append((folder_name, str(e)))
        else:
            print(f"   -> [DRY] {new_name}")
            logging.info(f"[DRY] {folder_name} -> {new_name}")
            renamed_list.append((folder_name, new_name))

    # --- FINAL REPORT ---
    print(f"\n{'='*50}")
    print(f"              LAPORAN AKHIR")
    print(f"{'='*50}")
    
    print(f"📂 Jumlah Folder Diimbas : {total_folders}")
    print(f"✅ Berjaya Rename        : {len(renamed_list)}")
    print(f"⏭️  Skipped               : {len(skipped_list)}")
    print(f"❌ Error                 : {len(error_list)}")
    
    # Tunjuk detail folder yang diskip (Jika ada)
    if skipped_list:
        print(f"\n{'='*50}")
        print(f"⚠️  SENARAI FOLDER YANG DISKIP:")
        print(f"{'-'*50}")
        for name, reason in skipped_list:
            # Potong nama folder kalau panjang sangat supaya kemas
            display_name = (name[:45] + '..') if len(name) > 45 else name
            print(f" • {display_name:<50} -> {reason}")
    
    # Tunjuk error (Jika ada)
    if error_list:
        print(f"\n{'='*50}")
        print(f"❌ SENARAI ERROR:")
        print(f"{'-'*50}")
        for name, err in error_list:
             print(f" • {name} -> {err}")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    args = setup_arguments()
    try:
        process_folders(args)
    except KeyboardInterrupt:
        print("\nStopped.")
