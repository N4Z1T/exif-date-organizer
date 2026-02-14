# Project Context: NAS Media Organizer

## 📌 Project Overview
Satu skrip Python berprestasi tinggi untuk menyusun (rename) folder gambar/video di dalam Synology NAS berdasarkan tarikh metadata (EXIF/Creation Date). Skrip ini direka khas untuk persekitaran NAS yang sensitif terhadap penggunaan CPU dan Disk I/O.

**Current Version:** V35.0 (Final Offline Edition)
**Status:** Production Ready

## 🛠 Tech Stack
- **Language:** Python 3.8+
- **Core Libraries:** `os`, `sys`, `re`, `logging`, `argparse`, `json`, `threading`, `concurrent.futures`
- **External Dependencies:**
  - `Pillow` (Wajib: Image EXIF)
  - `tqdm` (Progress Bar)
  - `hachoir` (Optional: Video Metadata)
  - `pillow-heif` (Optional: HEIC Support)

## 📐 Architecture (OOP)
Kod disusun mengikut prinsip **Single Responsibility Principle (SRP)**:
1.  **MetadataScanner:** Fokus hanya pada imbasan fail dan pengekstrakan tarikh (Read-Only).
2.  **RenameExecutor:** Fokus pada sanitasi nama, penyemakan kekosongan (*uniqueness*), dan operasi fail (Write).
3.  **MediaFolderOrganizer (Orchestrator):** Mengawal aliran kerja, worker threads, dan pelaporan.

## 🔒 Key constraints & Rules (JANGAN UBAH TANPA SEBAB)
1.  **NAS Safety:**
    - Default worker dihadkan kepada `CPU / 2` atau min 4.
    - Menggunakan `SAMPLE_SIZE = 50` untuk mengelakkan bacaan disk berlebihan.
2.  **Offline First:**
    - Tiada pergantungan kepada API luar (AI Removed in V34). Logik bergantung pada Regex, Metadata Dalaman, dan File Creation Date (mtime) sahaja.
3.  **Data Integrity:**
    - `os.rename` atau `shutil.move` mesti diletakkan dalam `threading.Lock()` untuk mengelakkan *Race Condition*.
    - **Date Sanity:** Tarikh mesti antara Tahun 2000 hingga (Tahun Semasa + 1).
4.  **Traceability:**
    - Wajib jana `report.json` (Forensik).
    - Wajib jana `undo.sh` (Bash) dan `undo.ps1` (Windows) untuk pemulihan bencana.
5.  **Dynamic Logging:**
    - Nama fail log mestilah dinamik mengikut path target (elak overwrite log folder lain).

## 📂 Directory Structure Logic
- Input: `/Path/To/Folder_Asal`
- Logic: `2021-01-01 EVENT NAME`
- Regex Cleaning: Membuang tarikh/simbol lama di depan nama folder.
- Case Enforcement: Title/Upper/Lower.