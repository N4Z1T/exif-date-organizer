#!/usr/bin/env python3

import os
import sys
import re
import logging
import argparse
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any, Iterable, Set
import shutil

# --- Library Safety Imports ---
try:
    from PIL import Image, ExifTags
except ImportError:
    sys.exit("CRITICAL ERROR: 'Pillow' library not found.\nPlease run: pip install Pillow")

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable: Iterable, **kwargs: Any) -> Iterable:
        return iterable

# --- Optional Libraries Check ---
try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    HACHOIR_AVAILABLE = True
except ImportError:
    HACHOIR_AVAILABLE = False

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

# --- SYSTEM DEFAULTS ---
DEFAULT_IGNORED_DIRS = {'@eaDir', '#recycle', '.DS_Store', 'venv', '.git', 'lost+found', 'Thumbs.db'}
DEFAULT_IGNORED_FILES = {'SYNOFILE_THUMB', 'desktop.ini', '.DS_Store', 'Thumbs.db'}
DEFAULT_IGNORED_EXT = {'.db', '.tmp', '.ini', '.txt', '.log', '.json', '.sh', '.py', '.ps1'}

INVALID_FILENAME_CHARS = r'[<>:"/\\|?*]'
IMAGE_EXT = frozenset({'.jpg', '.jpeg', '.png', '.tiff', '.heic'})
VIDEO_EXT = frozenset({'.mp4', '.mov', '.avi', '.mkv', '.3gp', '.m4v'})

# --- TUNING KNOBS ---
SAMPLE_SIZE = 50       # Scan max 50 fail per folder
MIN_YEAR = 2000        # Tarikh bawah 2000 dianggap error (Unix epoch/Bad battery)
MAX_YEAR = datetime.now().year + 1 

logger = logging.getLogger(__name__)

# ==========================================
# MODULE 1: METADATA SCANNER
# ==========================================
class MetadataScanner:
    def __init__(self, ignored_dirs: Set[str], ignored_files: Set[str], ignored_ext: Set[str]):
        self.ignored_dirs = ignored_dirs
        self.ignored_files = ignored_files
        self.ignored_ext = ignored_ext

    def scan_folder(self, folder_path: str) -> Tuple[Counter, int]:
        date_counter = Counter()
        
        # Optimization: Use separate lists
        images = []
        videos = []
        
        for dirpath, dirnames, filenames in os.walk(folder_path):
            dirnames[:] = [d for d in dirnames if d not in self.ignored_dirs]
            for f in filenames:
                if any(i in f for i in self.ignored_files): continue
                ext = os.path.splitext(f)[1].lower()
                if ext in self.ignored_ext: continue
                
                if ext in IMAGE_EXT: images.append(os.path.join(dirpath, f))
                elif ext in VIDEO_EXT: videos.append(os.path.join(dirpath, f))

        files_found = images + videos

        if not files_found: return Counter(), 0

        scanned_count = 0
        valid_dates_found = 0
        
        for filepath in files_found:
            if valid_dates_found >= SAMPLE_SIZE: break
                
            date_obj = self._get_date(filepath)
            scanned_count += 1
            if date_obj:
                date_counter[date_obj.strftime("%Y-%m-%d")] += 1
                valid_dates_found += 1
                
        return date_counter, scanned_count

    def _get_date(self, filepath: str) -> Optional[datetime]:
        ext = os.path.splitext(filepath)[1].lower()
        if ext in IMAGE_EXT: return self._get_image_date(filepath)
        elif ext in VIDEO_EXT: return self._get_video_date(filepath)
        return None

    def _get_image_date(self, filepath: str) -> Optional[datetime]:
        try:
            with Image.open(filepath) as img:
                exif = img.getexif()
                if not exif: return None
                date_str = exif.get(36867) or exif.get(306)
                return self._parse_date(date_str)
        except Exception: return None

    def _get_video_date(self, filepath: str) -> Optional[datetime]:
        if not HACHOIR_AVAILABLE: return None
        try:
            parser = createParser(filepath)
            if parser:
                with parser:
                    meta = extractMetadata(parser)
                    if meta and meta.has("creation_date"):
                        return meta.get("creation_date")
        except Exception: pass
        
        # Fallback to mtime if hachoir fails
        try:
            mtime = os.path.getmtime(filepath)
            dt = datetime.fromtimestamp(mtime)
            if MIN_YEAR <= dt.year <= MAX_YEAR:
                return dt
        except Exception: pass
        return None

    @staticmethod
    def _parse_date(date_str: Any) -> Optional[datetime]:
        if not date_str: return None
        try:
            s = str(date_str).strip().split('+')[0].split('Z')[0].replace('T', ' ')
            date_part = s.split(' ')[0].replace('-', ':')
            dt = datetime.strptime(date_part, "%Y:%m:%d")
            
            if MIN_YEAR <= dt.year <= MAX_YEAR:
                return dt
            else:
                return None
                
        except (ValueError, TypeError, IndexError): return None

# ==========================================
# MODULE 2: RENAME EXECUTOR
# ==========================================
class RenameExecutor:
    def __init__(self):
        self._rename_lock = threading.Lock()

    def sanitize_name(self, name: str) -> str:
        return re.sub(INVALID_FILENAME_CHARS, '', name).strip()

    def get_unique_path(self, base_path: str) -> str:
        if not os.path.exists(base_path): return base_path
        counter = 1
        while counter < 1000:
            new_path = f"{base_path} ({counter})"
            if not os.path.exists(new_path): return new_path
            counter += 1
        return base_path

    def execute(self, old_path: str, new_name: str, live_mode: bool) -> Tuple[str, str]:
        parent_dir = os.path.dirname(old_path)
        safe_name = self.sanitize_name(new_name)
        target_base_path = os.path.join(parent_dir, safe_name)

        if os.path.basename(old_path) == safe_name:
            return 'unchanged', safe_name

        if live_mode:
            with self._rename_lock:
                final_path = self.get_unique_path(target_base_path)
                try:
                    if not os.path.exists(old_path): return 'error', "Source missing"
                    
                    # Use shutil.move for robustness (handles cross-device moves if needed)
                    shutil.move(old_path, final_path)
                    return 'renamed', os.path.basename(final_path)
                except OSError as e:
                    return 'error', str(e)
        else:
            final_path = self.get_unique_path(target_base_path)
            return 'dry_run', os.path.basename(final_path)

# ==========================================
# MODULE 3: ORCHESTRATOR
# ==========================================
class MediaFolderOrganizer:
    def __init__(self, args, file_prefix: str):
        self.target_path = os.path.abspath(args.path)
        self.live_run = args.live
        self.workers = args.workers
        self.confidence = args.confidence
        self.case = args.case
        self.file_prefix = file_prefix
        
        self.ignored_dirs = DEFAULT_IGNORED_DIRS.union(set(args.ignore_dirs))
        self.ignored_ext = DEFAULT_IGNORED_EXT.union(set(args.ignore_ext))
        
        self.scanner = MetadataScanner(self.ignored_dirs, DEFAULT_IGNORED_FILES, self.ignored_ext)
        self.executor = RenameExecutor()

    def _clean_base_name(self, name: str) -> str:
        clean = re.sub(r"^[\d\.\-\/\s]+", "", name).strip()
        if not clean: return ""
        
        if self.case == 'upper': return clean.upper()
        if self.case == 'lower': return clean.lower()
        return clean.title()

    def _process_folder(self, folder_path: str) -> Dict[str, Any]:
        folder_name = os.path.basename(folder_path)
        result = {'status': 'skipped', 'name': folder_name, 'reason': '', 'new_name': '', 'original_path': folder_path}

        # 1. SCAN
        dates, total = self.scanner.scan_folder(folder_path)
        if not dates:
            result['reason'] = "No valid dates found (Empty)"
            return result
            
        # 2. DECIDE
        try:
            top_date_info = dates.most_common(1)
            if not top_date_info:
                result['reason'] = "Date list empty"
                return result
            top_date, count = top_date_info[0]
            if not top_date: 
                result['reason'] = "Top date None"
                return result
        except IndexError:
            result['reason'] = "Index Error"
            return result

        conf = count / total if total > 0 else 0
        if conf < self.confidence:
            result['reason'] = f"Low confidence ({conf:.2f})"
            return result

        # 3. PLAN
        base_name = self._clean_base_name(folder_name)
        new_name_candidate = f"{top_date} {base_name}".strip()

        # 4. EXECUTE
        status, final_name = self.executor.execute(folder_path, new_name_candidate, self.live_run)
        
        result['status'] = status
        result['new_name'] = final_name
        result['full_new_path'] = os.path.join(os.path.dirname(folder_path), final_name)
        if status == 'error': result['reason'] = final_name
        
        return result

    def generate_reports(self, results: List[Dict]):
        """Generates JSON Report and Bash/PS1 Undo Scripts"""
        
        # 1. JSON Report
        json_path = f"{self.file_prefix}_report.json"
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            logger.info(f"📄 Forensic Report saved to: {json_path}")
        except Exception as e:
            logger.error(f"Failed to save JSON report: {e}")

        renamed_items = [r for r in results if r['status'] == 'renamed']
        if not renamed_items: return

        # 2. Bash Undo Script
        undo_path = f"{self.file_prefix}_undo.sh"
        try:
            with open(undo_path, 'w', encoding='utf-8') as f:
                f.write("#!/bin/bash\n")
                f.write(f"# Undo Script for target: {self.target_path}\n\n")
                for item in renamed_items:
                    old = item['original_path'].replace('"', '\\"')
                    new = item['full_new_path'].replace('"', '\\"')
                    f.write(f'mv "{new}" "{old}"\n')
            
            os.chmod(undo_path, 0o755)
            logger.info(f"↩️  Undo Script saved to: {undo_path}")
        except Exception as e:
            logger.error(f"Failed to save Undo script: {e}")

        # 3. PowerShell Undo Script
        undo_ps1 = f"{self.file_prefix}_undo.ps1"
        try:
            with open(undo_ps1, 'w', encoding='utf-8') as f:
                f.write("# PowerShell Undo Script\n\n")
                for item in renamed_items:
                    old = item['original_path'].replace("'", "''")
                    new = item['full_new_path'].replace("'", "''")
                    f.write(f"Move-Item -Path '{new}' -Destination '{old}' -Force\n")
            logger.info(f"↩️  PowerShell Undo saved to: {undo_ps1}")
        except Exception as e:
            logger.error(f"Failed to save PS1 Undo: {e}")

    def run(self):
        print("\n" + "="*40)
        print("SYSTEM CHECK (V35 Final)")
        print("="*40)
        if HACHOIR_AVAILABLE: print("✅ [OK] hachoir (Video)")
        else: print("⚠️  [WARNING] 'hachoir' missing. Videos skipped.")
        if HEIF_AVAILABLE: print("✅ [OK] pillow-heif (HEIC)")
        else: print("⚠️  [WARNING] 'pillow-heif' missing. HEIC skipped.")
        print("="*40 + "\n")

        logger.info(f"🚀 Starting NAS Organizer V35")
        logger.info(f"📂 Target: {self.target_path}")
        
        subdirs = sorted([f.path for f in os.scandir(self.target_path) if f.is_dir() 
                         and os.path.basename(f.path) not in self.ignored_dirs])
        
        stats = Counter()
        skipped_details = []
        all_results = []

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self._process_folder, f): f for f in subdirs}
            
            for fut in tqdm(as_completed(futures), total=len(subdirs), unit="dir"):
                try:
                    res = fut.result()
                    all_results.append(res)
                    stats[res['status']] += 1
                    
                    if res['status'] == 'renamed':
                        logger.info(f"✅ {res['name']} -> {res['new_name']}")
                    elif res['status'] == 'dry_run':
                        logger.info(f"🔮 {res['name']} -> {res['new_name']}")
                    elif res['status'] == 'error':
                        logger.error(f"❌ {res['name']}: {res['reason']}")
                    elif res['status'] == 'skipped':
                        skipped_details.append(f"{res['name']} ({res['reason']})")
                        
                except Exception as e:
                    logger.critical(f"Worker Crash: {e}")
                    stats['crash'] += 1

        self.generate_reports(all_results)

        print("\n" + "="*40)
        print("          FINAL REPORT")
        print("="*40)
        print(f"📂 Total Scanned : {len(subdirs)}")
        print(f"✅ Renamed       : {stats['renamed']}")
        print(f"🔮 Dry Run       : {stats['dry_run']}")
        print(f"💤 Unchanged     : {stats['unchanged']}")
        print(f"⏭️  Skipped       : {stats['skipped']}")
        print(f"❌ Errors        : {stats['error']}")
        print("-" * 40)
        print(f"📄 Full Report   : {self.file_prefix}_report.json")
        if stats['renamed'] > 0:
            print(f"↩️  Undo Script   : {self.file_prefix}_undo.sh / .ps1")
        
        if skipped_details:
            print("-" * 40)
            print("⚠️  Skipped Samples:")
            for s in skipped_details[:5]: print(f" • {s}")
            if len(skipped_details) > 5: print(f"   ... and {len(skipped_details)-5} more (see json).")
        print("="*40 + "\n")

def main():
    parser = argparse.ArgumentParser(description="NAS Photo Organizer V35 (Dynamic Log)")
    parser.add_argument("path", help="Folder path")
    parser.add_argument("--live", action="store_true", help="Enable renaming")
    
    # Auto-detect CPU threads (Conservative: CPU / 2)
    default_workers = max(1, (os.cpu_count() or 4) // 2)
    parser.add_argument("--workers", type=int, default=default_workers, help=f"Default: {default_workers} (Auto: CPU/2)")
    
    parser.add_argument("--confidence", type=float, default=0.6)
    parser.add_argument("--case", default='upper', choices=['title', 'upper', 'lower'])
    parser.add_argument("--debug", action="store_true", help="Enable verbose logs")
    parser.add_argument("--ignore-dirs", nargs='+', default=[], help="Add dirs to ignore")
    parser.add_argument("--ignore-ext", nargs='+', default=[], help="Add extensions to ignore")

    args = parser.parse_args()

    if not os.path.exists(args.path):
        print("Error: Path not found.")
        return

    # --- DYNAMIC FILENAME GENERATION ---
    # Convert path to filename safe string: "volume1_Gambar_2025"
    safe_path_name = re.sub(r'[^a-zA-Z0-9]', '_', args.path.strip()).strip('_')
    if not safe_path_name: safe_path_name = "nas_organizer_root"
    
    log_filename = f"{safe_path_name}.log"

    # Setup Logging
    lvl = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(filename=log_filename, filemode='w', level=lvl,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING) 
    logging.getLogger('').addHandler(console)

    # Pass the filename prefix to class so it can name report/undo similarly
    MediaFolderOrganizer(args, file_prefix=safe_path_name).run()

if __name__ == "__main__":
    main()
