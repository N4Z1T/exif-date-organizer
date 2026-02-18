# Changelog

## [V35.1] - 2026-02-19 (Current)
### Changed
- **Type Safety:** Annotated `scanned_count` dan `valid_dates_found` secara eksplisit sebagai `int`. Tukar `+=` kepada `= x + 1` untuk elak Pyre2 type inference bug.
- **`os.walk` Pruning:** Ganti `dirnames[:] = [...]` dengan `.clear()` + `.extend()` untuk keserasian linter yang lebih baik.
- **`Executor.submit` Wrapper:** Ekstrak `_submit_folder(path: str)` sebagai fungsi dalaman bertaip untuk elak Pyre2 false positive pada bound method signature.
- **`# type: ignore` Suppression:** Tambah `# type: ignore[operator]` (line 103) dan `# type: ignore[arg-type]` (line 336) pada 2 baris yang Pyre2 salah flag — confirmed linter bugs, bukan logic error.

### Fixed
- **`requirements.txt`:** Buang `requests` yang tidak digunakan.

### Added
- **`test_verify.py`:** Unit test untuk `MetadataScanner._parse_date` dan `RenameExecutor.sanitize_name`. Guna `importlib.util` untuk load modul dengan nama fail berhyphen (`exif-parallel-organizer.py`).

### Known Issues (Tidak Perlu Dibaiki)
- Pyre2 masih report `Could not find import of PIL/tqdm/hachoir/pillow_heif` — ini **environment issue** (packages belum `pip install` dalam venv yang IDE guna), bukan bug dalam kod. Kod sudah ada `try/except ImportError` guard yang betul.

## [V35.0] - 2026-02-13
### Added
- **Dynamic Logging:** Nama fail log, report, dan undo script kini mengikut nama folder target (cth: `volume1_Gambar_2025.log`).
- **PowerShell Support:** Menjana `undo.ps1` untuk pengguna Windows yang akses NAS via SMB.
- **Smart Worker:** Auto-detect CPU threads dan guna separuh sahaja untuk keselamatan NAS.

### Fixed
- **Logic Bug:** Membuang kod `shutil.move` yang tidak perlu dalam blok Dry Run.
- **Redundancy:** Membersihkan kod semakan `os.path.exists` yang berulang.

## [V34.0] - Offline Edition
### Removed
- **AI Modules:** Membuang sepenuhnya `AIService`, `requests`, dan logik Google Gemini API. Skrip kini 100% offline dan pantas.

## [V33.0] - Safety & Forensics
### Added
- **Date Sanity Check:** Menolak tarikh < 2000 (Unix Epoch error) atau > Current Year + 1.
- **Forensic Report:** Output `report.json` untuk analisis mendalam.
- **Bash Undo Script:** Auto-generate script untuk *revert* perubahan.
- **Env Var:** Sokongan `GEMINI_API_KEY` (sebelum dimansuhkan di V34).

## [V30.0 - V32.0] - Robustness
### Changed
- **Date Parsing:** Logik `_parse_date` yang lebih agresif (handle Timezone, ISO format, dash/colon separator).
- **Flexible Ignores:** Menambah flag `--ignore-dirs` dan `--ignore-ext`.
- **Dependency Check:** Amaran jelas jika `hachoir` atau `pillow-heif` tiada, tanpa mematikan skrip.

## [V24.0 - V29.0] - Architecture Refactor
### Changed
- **OOP Rewrite:** Memecahkan kod procedural kepada kelas (`Scanner`, `Executor`).
- **Atomic Locking:** Menambah `threading.Lock` pada operasi rename.
- **Strict Logic:** Membuang tekaan tarikh dari nama fail (filename parsing). Fallback kepada *file mtime* hanya untuk video jika metadata gagal.
- **Fix:** Masalah trailing space pada nama folder jika nama asal kosong.