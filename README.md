# exif-date-organizer
A robust Python script to recursively organize and rename media folders based on the **majority execution date (EXIF/Metadata)** of the images and videos contained within.

Designed for photographers and data hoarders, this script ensures your folder structure is chronological (`YYYY-MM-DD [Original Name]`) without losing the original folder context.

##  Features

* **Recursive Scanning:** Processes folders bottom-up (sub-folders first) to maintain structure integrity.
* **Format Support:** Handles Images (`.jpg`, `.png`, `.heic`) and Videos (`.mp4`, `.mov`, `.avi`, `.mkv`).
* **HEIC Support:** Native support for Apple High Efficiency Image Container files.
* **Smart Date Detection:**
    * Extracts `DateTimeOriginal` from EXIF (Images).
    * Extracts `creation_date` from Metadata (Videos via Hachoir).
    * Fallback to Filesystem date (optional/interactive).
* **Majority Rule Logic:** Renames the folder based on the most frequent date found (Mode), with a configurable **Confidence Level** threshold (default 60%).
* **Interactive Safety:** Pauses and asks for user input if metadata is missing (Skip, Ignore, Manual Entry).
* **Conflict Handling:** Auto-increments folder names if the target name already exists (e.g., `2023-12-25 Event (1)`).
* **Dry Run:** Always runs a simulation first before applying changes.
* **Logging:** Saves a detailed `.log` file of all operations.

##  Prerequisites

* Python 3.7+
* **Libraries:** `Pillow`, `hachoir`, `pillow-heif`

##  Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/N4Z1T/exif-date-organizer.git
    cd exif-date-organizer
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

Open the script (`exif-date-organizer.py`) and modify the `TARGET_PATH` variable to point to your media folder:

```python
# Windows Example
TARGET_PATH = r"C:\Users\Admin\Pictures\Holiday"

# Synology NAS / Linux Example
TARGET_PATH = r"/volume1/homes/user/Photos"

⚠️ Disclaimer
Always backup your data before running batch renaming scripts. While this script includes a "Dry Run" mode and safety checks (unique paths, confidence levels), the author is not responsible for any data loss or corruption.
