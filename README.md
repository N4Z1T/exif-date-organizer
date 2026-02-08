# Media Folder Renamer CLI 📂

A robust, production-ready Python tool designed to organize media folders by renaming them based on the **majority execution date (EXIF/Metadata)** of the files inside.

Ideal for photographers, data hoarders, and Synology NAS users who want to standardize their directory structure to the **ISO Format (`YYYY-MM-DD`)** without losing original folder context.

##  Key Features

* **Smart Renaming:** Automatically detects the most common date in a folder and renames the folder to `YYYY-MM-DD [Cleaned Name]`.
* **Name Cleaning:** Intelligently removes old, messy dates from folder names (e.g., `2.8.2026 Ngatik` → `2026-02-08 Ngatik`).
* **Recursive Scanning:** Processes folders bottom-up to ensure nested structures are handled correctly.
* **Broad Format Support:**
    * **Images:** `.jpg`, `.png`, `.tiff`
    * **HEIC:** Native support for Apple High Efficiency Image Container.
    * **Video:** Extracts metadata from `.mp4`, `.mov`, `.mkv`, `.avi` (via Hachoir).
* **Safety First:**
    * **Dry Run by Default:** Never modifies files unless `--live` flag is used.
    * **Confidence Threshold:** Only renames if a specified percentage (default 60%) of files share the same date.
    * **Conflict Resolution:** Auto-increments names if the target folder already exists.
* **Interactive Mode:** Pauses and asks for user input if metadata is missing (Skip, Ignore, Manual Entry).
* **Detailed Logging:** Generates a full `.log` file with error tracebacks and audit trails.

## 🛠️ Prerequisites

* **Python 3.7+**
* **Required Libraries:**
    * `Pillow` (Image processing)
    * `hachoir` (Video metadata)
    * `pillow-heif` (HEIC support)
    * `tqdm` (Progress bar - Optional but recommended)

##  Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/yourusername/media-folder-renamer.git](https://github.com/yourusername/media-folder-renamer.git)
    cd media-folder-renamer
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install Pillow hachoir pillow-heif tqdm
    ```

##  Usage

This tool uses Command Line Arguments. You do not need to edit the script to change target folders.

### Basic Syntax
```bash
python renamer_pro.py [TARGET_PATH] [OPTIONS]
```

### Examples
1. Dry Run (Simulation - Safe to run anytime) Shows what would happen without changing anything.
```bash
python renamer_pro.py "/Users/Admin/Pictures/2026"
```
2. Live Rename (Apply Changes) Actually renames the folders.
   ```bash
   python renamer_pro.py "/Users/Admin/Pictures/2026" --live
   ```
3. Strict Mode (High Confidence) Only rename if 80% of files match the date.
   ```bash
   python renamer_pro.py "/Users/Admin/Pictures/2026" --confidence 0.8 --live
   ```
4. Non-Interactive (Silent Mode) Great for running in the background. Automatically skips folders with missing metadata.
   ```bash
   python renamer_pro.py "/Users/Admin/Pictures/2026" --live --non-interactive
   ```

##  How It Works
1. Scan: The script enters a folder and reads the EXIF/Metadata of all supported media files.
2. Vote: It counts the dates found.
3. Example: 45 files are from 2026-02-08, 5 files are from 2026-02-09.
4. Decision: Since 2026-02-08 is the majority (>60%), it is chosen.
5. Clean: It takes the original folder name (e.g., 2.8.26 Trip) and uses Regex to strip the old date.
   ** Result: Trip
6. Rename: Combines the new date + cleaned name.
   ** Final: 2026-02-08 Trip

## Logging
A log file named renamer_pro.log is automatically created in the script's directory. It records:
* Renamed folders.
* Skipped folders (and reasons).
* User decisions (manual inputs).
* Error tracebacks (corrupt files).

### ⚠️ Disclaimer
Always backup your data. While this script is designed with safety features (Dry Run, Conflict Handling), the author is not responsible for any data loss.
