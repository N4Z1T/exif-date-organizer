#!/usr/bin/env python3
import os
import sys
import re
import logging
import argparse
import json
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime
from PIL import Image, ExifTags

# --- THREADING LOCKS ---
# Lock untuk print supaya text tak bercampur aduk di skrin
PRINT_LOCK = threading.Lock()
# Lock untuk AI supaya kita tak hantar request serentak (Elak 429)
AI_LOCK = threading.Lock()

# --- LIBRARIES ---
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs): return iterable

try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    HACHOIR_AVAILABLE = True
except ImportError:
    HACHOIR_AVAILABLE = False

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

# --- CONFIG ---
LOG_FILENAME = "exif-organizer-parallel.log"
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
    parser = argparse.ArgumentParser(description="EXIF Parallel Organizer V21")
    parser.add_argument("path", help="Target folder path")
    parser.add_argument("--live", action="store_true", help="Execute rename")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel threads (Default: 4)")
    parser.add_argument("--confidence", type=float, default=0.6, help="Min confidence")
    parser.add_argument("--non-interactive", action="store_true", help="Auto-skip missing metadata")
    parser.add_argument("--case", default='title', help="Case format (if AI off)")
    parser.add_argument("--ai-api-key", help="Google AI Studio API Key", default=None)
    return parser.parse_args()

def safe_print(msg, end="\n"):
    """Thread-safe print function"""
    with PRINT_LOCK:
        print(msg, end=end)

def clean_folder_name_regex(foldername, case_type='title'):
    cleaned = re.sub(r"^[\d\.\-\/\s]+", "", foldername).strip()
    if not cleaned: return foldername
    if case_type == 'upper': return cleaned.upper()
    elif case_type == 'lower': return cleaned.lower()
    elif case_type == 'title': return cleaned.title()
    elif case_type == 'sentence': return cleaned.capitalize()
    return cleaned.title()

# --- AI LOGIC ---
SELECTED_MODEL = None

def get_high_quota_model(api_key):
    # Logic sama macam V20
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = [m['name'].replace('models/', '') for m in data.get('models', [])]
            
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
    
    # --- CRITICAL: AI LOCK ---
    # Hanya satu thread boleh guna AI pada satu masa untuk maintain pace
    with AI_LOCK:
        if not api_key: return text

        if SELECTED_MODEL is None:
            safe_print("   [SYSTEM] Selecting Model...", end="\r")
            SELECTED_MODEL = get_high_quota_model(api_key)
            safe_print(f"   [SYSTEM] MODEL: {SELECTED_MODEL}                 ")

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

        # Static Wait Logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, data=json.dumps(data), timeout=20)
                
                if response.status_code == 200:
                    try:
                        res_json = response.json()
                        cleaned = res_json['candidates'][0]['content']['parts'][0]['text']
                        final_text = cleaned.strip().replace('"', '').replace("'", "").replace("\n", "").replace("*", "")
                        
                        # SAFETY PACE: 2.5s sleep INSIDE THE LOCK
                        time.sleep(2.5) 
                        return final_text
                    except:
                        return text
                
                elif response.status_code == 429:
                    wait_time = 10 
                    safe_print(f"   [WAIT] Quota Penuh. Rehat {wait_time}s...", end="\r")
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

def collect_dates(folder_path):
    """Fungsi ini berjalan dalam thread berasingan"""
    date_counter = Counter()
    total_files = 0
    all_files = []
    
    for dirpath, dirnames, filenames in os.walk(folder_path):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for f in filenames:
            if any(j in f for j in IGNORED_FILES): continue
            if f.lower().endswith(IMAGE_EXT + VIDEO_EXT):
                all_files.append(os.path.join(dirpath, f))

    if not all_files: return None, 0

    # Kita tak guna TQDM di sini sebab akan mess up console bila parallel
    for filepath in all_files:
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

# --- WORKER FUNCTION ---
def process_single_folder(folder_path, args):
    """
    Ini adalah 'Pekerja' yang akan dijalankan oleh ThreadPool
    Mengembalikan status (result) untuk summary
    """
    folder_name = os.path.basename(folder_path)
    result = {'status': 'skipped', 'name': folder_name, 'reason': '', 'new_name': ''}

    # 1. SCANNING (PARALLEL)
    date_stats, total_files = collect_dates(folder_path)

    if not date_stats:
        result['reason'] = 'Tiada metadata'
        return result

    most_common_date_str, count = date_stats.most_common(1)[0]
    confidence = count / total_files if total_files > 0 else 0

    if confidence < args.confidence:
        result['reason'] = f'Low Confidence ({confidence:.2f})'
        return result

    # 2. AI PROCESSING (SERIALIZED VIA LOCK)
    clean_base = clean_folder_name_regex(folder_name, args.case)
    
    # Bahagian ini akan tunggu giliran (AI_LOCK)
    if args.ai_api_key:
        final_name = ai_fix_spelling(clean_base, args.ai_api_key)
    else:
        final_name = clean_base

    new_name = f"{most_common_date_str} {final_name}"
    
    if new_name == folder_name:
        result['status'] = 'unchanged'
        return result

    # 3. RENAMING
    # Kita perlu lock juga masa rename file path supaya tak conflict (jarang berlaku tapi selamat)
    # Tapi get_unique_path check file system, jadi ia OK run parallel asalkan parent dir berbeza
    
    parent_dir = os.path.dirname(folder_path)
    new_full_path = get_unique_path(os.path.join(parent_dir, new_name))
    
    if args.live:
        try:
            os.rename(folder_path, new_full_path)
            result['status'] = 'renamed'
            result['new_name'] = new_name
            safe_print(f"[OK] {folder_name} -> {new_name}")
            logging.info(f"Renamed: {folder_name} -> {new_name}")
        except OSError as e:
            result['status'] = 'error'
            result['reason'] = str(e)
            safe_print(f"[ERR] {folder_name}: {e}")
            logging.error(f"Error {folder_name}: {e}")
    else:
        result['status'] = 'renamed' # Dry run success
        result['new_name'] = new_name
        safe_print(f"[DRY] {folder_name} -> {new_name}")
        logging.info(f"[DRY] {folder_name} -> {new_name}")

    return result

# --- MAIN PROCESS ---
def process_folders(args):
    target_path = os.path.abspath(args.path)
    
    print(f"\n{'='*40}")
    print(f" TARGET: {target_path}")
    print(f" MODE  : {'[LIVE RENAME]' if args.live else '[DRY RUN]'}")
    print(f" WORKER: {args.workers} Threads")
    print(f"{'='*40}\n")

    if not os.path.exists(target_path): 
        print("Path not found!")
        return

    subdirs = sorted([f.path for f in os.scandir(target_path) if f.is_dir()])
    subdirs = [d for d in subdirs if os.path.basename(d) not in IGNORED_DIRS]
    total_folders = len(subdirs)

    results_summary = {
        'renamed': [],
        'skipped': [],
        'error': [],
        'unchanged': []
    }

    print(f"🚀 Memulakan {args.workers} worker parallel...\n")

    # --- PARALLEL EXECUTION BLOCK ---
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Hantar semua kerja kepada workers
        future_to_folder = {executor.submit(process_single_folder, folder, args): folder for folder in subdirs}
        
        # Monitor progress menggunakan TQDM
        for future in tqdm(as_completed(future_to_folder), total=total_folders, unit="folder"):
            try:
                data = future.result()
                status = data['status']
                
                if status == 'renamed':
                    results_summary['renamed'].append((data['name'], data['new_name']))
                elif status == 'skipped':
                    results_summary['skipped'].append((data['name'], data['reason']))
                elif status == 'error':
                    results_summary['error'].append((data['name'], data['reason']))
                elif status == 'unchanged':
                    results_summary['unchanged'].append(data['name'])
                    
            except Exception as exc:
                safe_print(f"\n[CRITICAL ERROR] Worker crashed: {exc}")

    # --- FINAL REPORT ---
    print(f"\n{'='*50}")
    print(f"              LAPORAN AKHIR (PARALLEL)")
    print(f"{'='*50}")
    
    print(f"📂 Total Folder     : {total_folders}")
    print(f"✅ Berjaya Rename   : {len(results_summary['renamed'])}")
    print(f"⏭️  Skipped          : {len(results_summary['skipped'])}")
    print(f"💤 Tiada Perubahan  : {len(results_summary['unchanged'])}")
    print(f"❌ Error            : {len(results_summary['error'])}")
    
    if results_summary['skipped']:
        print(f"\n{'='*50}")
        print(f"⚠️  DETAIL SKIP (SAMPEL):")
        print(f"{'-'*50}")
        for name, reason in results_summary['skipped'][:10]: # Tunjuk 10 pertama je
            display = (name[:40] + '..') if len(name) > 40 else name
            print(f" • {display:<45} -> {reason}")
        if len(results_summary['skipped']) > 10:
            print(f"   ... dan {len(results_summary['skipped'])-10} lagi.")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    args = setup_arguments()
    try:
        process_folders(args)
    except KeyboardInterrupt:
        print("\nStopped.")
