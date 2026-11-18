# Installation and local setup

This guide explains how to install and run QuiickTracker from a fresh clone or extracted source folder. The primary instructions are for **Windows 10/11 with VS Code and PowerShell**. macOS/Linux instructions are included at the end.

## 1. Prerequisites

Install the following before starting:

- **Python 3.11, 3.12, or 3.13** (64-bit recommended). Python 3.13 is used in the example commands; Python 3.12 or 3.11 is also supported.
- **Visual Studio Code** and the Microsoft Python extension.
- **Git**, if cloning from GitHub.
- A webcam for live face capture. You can use image upload without a webcam.
- Internet access for downloading the ONNX face models the first time.
- Optional: MySQL Server if you want to use MySQL instead of the default SQLite database.

Download Python from <https://www.python.org/downloads/>. On Windows, enable the Python Launcher option if offered. After installation, open a new terminal and check:

```powershell
py --version
py -0p
```

The launcher should list at least one supported Python version. Replace `py -3.13` in the examples below with `py -3.12` or `py -3.11` if that is the version installed on your computer.

## 2. Get the project and open the correct folder

### Option A — Clone from GitHub

Open PowerShell or the VS Code terminal and run:

```powershell
git clone https://github.com/YOUR_USERNAME/quiicktracker.git
cd quiicktracker
```

Replace the URL with the HTTPS URL of your actual repository.

### Option B — Use the ZIP file

1. Extract the QuiickTracker ZIP file.
2. In VS Code, select **File → Open Folder**.
3. Open the project root folder — the folder that directly contains `app.py`, `requirements.txt`, and `quicktracker/`.

The folder structure should look like this:

```text
QuiickTracker/
├── app.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── quicktracker/
├── models/
├── scripts/
├── tests/
└── docs/
```

Do not run Flask from the parent directory. Verify that the terminal is in the project root:

```powershell
Get-Location
Test-Path .\app.py
```

`Test-Path` should return `True`. If it returns `False`, use `cd` to enter the folder that contains `app.py`.

## 3. Create and activate a virtual environment (Windows)

From the project root, run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

When activation succeeds, PowerShell displays `(.venv)` at the start of the prompt.

### If PowerShell blocks activation

Run this for the current terminal session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

This does not permanently change the machine-wide execution policy.

### If the virtual environment is already present

You do not need to create it again. Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If the environment was copied from another computer or an old folder path, delete and recreate it. Virtual environments are location-specific and should not be copied between machines:

```powershell
Deactivate  # Run only if an environment is currently active.
Remove-Item -Recurse -Force .venv
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 4. Select the Python interpreter in VS Code

1. Press **Ctrl+Shift+P**.
2. Search for **Python: Select Interpreter**.
3. Select the interpreter in the project's `.venv` folder, usually `.venv\Scripts\python.exe`.
4. Open a new VS Code terminal if the old terminal still uses a different interpreter.

Verify the selected interpreter:

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

The printed executable path should point to this project's `.venv` directory.

## 5. Install Python dependencies

Upgrade pip and install the development requirements:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` installs the application dependencies in `requirements.txt` plus pytest for running the test suite.

### OpenCV note

The project uses `opencv-python-headless` in the supported OpenCV 4.x range because of the YuNet `2023mar` ONNX model used by the application. Do not separately install `opencv-python` into the same environment. Having both OpenCV distributions installed can cause import and binary conflicts.

If you previously installed both packages in this virtual environment, remove them and reinstall the project dependencies:

```powershell
python -m pip uninstall -y opencv-python opencv-python-headless
python -m pip install -r requirements-dev.txt
```

## 6. Create the local environment file

Copy the example configuration to `.env`:

```powershell
Copy-Item .env.example .env
```

Open `.env` in VS Code. For a local SQLite setup, the default configuration is sufficient. The application stores its database under `instance/` and uploads under `instance/uploads/`.

Important settings:

```dotenv
SECRET_KEY=
SESSION_COOKIE_SECURE=false
DATABASE_URL=
MODEL_DIR=models
TIMEZONE=Asia/Kolkata
FACE_MATCH_THRESHOLD=0.363
FACE_DETECTION_THRESHOLD=0.90
MAX_CONTENT_LENGTH_MB=30
```

- `SECRET_KEY`: set a long, random value for a persistent deployment. If left blank, a new random value is generated at startup, so existing browser sessions will be invalidated after a restart.
- `SESSION_COOKIE_SECURE`: keep `false` for local HTTP development. Set `true` only when serving the application over HTTPS.
- `DATABASE_URL`: leave blank to use SQLite, or set a SQLAlchemy URL for MySQL.
- `MODEL_DIR`: location of the ONNX files. The default is the project's `models/` folder.
- `TIMEZONE`: timezone used to determine the attendance date.
- `FACE_MATCH_THRESHOLD`: initial cosine-similarity cutoff. It must be calibrated using a properly labelled validation dataset; the default is not a universal safe threshold.
- `FACE_DETECTION_THRESHOLD`: YuNet detection confidence threshold.

Do not share or commit `.env`. The repository `.gitignore` is configured to exclude it.

## 7. Download and verify face-recognition models

From the project root, run:

```powershell
python scripts/download_models.py
```

The script downloads the OpenCV Zoo ONNX assets into `models/`, verifies their SHA-256 checksums, and checks that OpenCV can load them:

- `face_detection_yunet_2023mar.onnx` — face detector.
- `face_recognition_sface_2021dec.onnx` — face embedding model.

The models are third-party assets with terms separate from the QuiickTracker source code. Read `models/README.md` and `THIRD_PARTY_NOTICES.md`.

If the download fails:

1. Check that the computer has internet access and that a proxy/firewall is not replacing the download with an HTML page or Git LFS pointer.
2. Run the command again; an incomplete or checksum-invalid file is replaced on the next attempt.
3. Check the full error printed by the script. A checksum mismatch should not be bypassed by removing checksum validation.
4. Confirm the Python environment imports the expected OpenCV distribution:

```powershell
python -c "import cv2; print(cv2.__version__); print(cv2.__file__)"
```

Use the OpenCV version constrained by `requirements.txt` (OpenCV 4.x). Do not switch to OpenCV 5.x without also changing and validating the YuNet model/input configuration.

## 8. Initialize the database and create an administrator

Run these commands from the project root with `.venv` activated:

```powershell
python -m flask --app app init-db
python -m flask --app app create-admin
```

The administrator command prompts for:

- Username (at least 3 characters).
- Password (at least 10 characters).
- Password confirmation.

Choose a unique password and do not store it in the repository. The application factory also ensures the database tables exist when the app starts; `init-db` is provided as an explicit setup command.

## 9. Start QuiickTracker

Run:

```powershell
python -m flask --app app run --debug
```

Open this address in a browser:

<http://127.0.0.1:5000>

Sign in with the administrator account created in the previous step. Keep the terminal running while using the application. Stop the development server with **Ctrl+C**.

The Flask debug server is for local development only. Do not expose it to the public internet.

## 10. Run the tests

Install development dependencies using `requirements-dev.txt`, then run:

```powershell
python -m pytest -q
```

For more detail:

```powershell
python -m pytest -v
```

Run Python syntax compilation as an additional check:

```powershell
python -m compileall -q app.py quicktracker scripts tests
```

Automated tests verify selected application logic and routes. They do not measure the real-world accuracy, fairness, spoof resistance, or legal suitability of face recognition.

## 11. Optional: configure MySQL

SQLite is the default and is recommended for first-time local setup. MySQL is optional.

1. Install and start MySQL Server.
2. Create a database and a dedicated database user with access only to that database.
3. Keep the database password private.
4. Set `DATABASE_URL` in `.env` using the SQLAlchemy PyMySQL format:

```dotenv
DATABASE_URL=mysql+pymysql://quicktracker_user:URL_ENCODED_PASSWORD@127.0.0.1:3306/quicktracker?charset=utf8mb4
```

If the password contains reserved URL characters, URL-encode them. Restart the Flask application after changing `.env`. For a new database, run:

```powershell
python -m flask --app app init-db
```

Do not use a root MySQL account for the application.

## 12. Common problems

### `Error: Could not import 'app'`

The terminal is commonly in the wrong folder, or the dependencies have not been installed in the active interpreter.

```powershell
Get-Location
Test-Path .\app.py
python -c "import app; print('App import successful')"
```

The first command should show the project root and `Test-Path` must return `True`. If it returns `False`, `cd` into the directory containing `app.py`. If import still fails, read the Python traceback above the Flask message; it identifies the missing dependency or import error.

### `No module named flask` or another missing package

Activate the project virtual environment and reinstall dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

### `Model file not found` or face model loading error

Run `python scripts/download_models.py` from the project root. Confirm both ONNX files are present in `models/` and the script reports successful checksum and OpenCV validation.

### Camera does not start in the browser

- Allow camera permission for `http://127.0.0.1:5000`.
- Close other applications that may be using the webcam.
- Use `localhost` or `127.0.0.1`; browser camera APIs generally require a secure context (localhost is treated as secure for local development).
- Try a current version of Chrome, Edge, or Firefox.
- Image upload can be used to test the registration and recognition flow if no webcam is available.

### Port 5000 is already in use

Stop the other local server or choose another port:

```powershell
python -m flask --app app run --debug --port 5001
```

Then open <http://127.0.0.1:5001>.

### Database or file permission error

Ensure the application folder is writable. Do not place the project in a protected Windows system directory. Stop Flask before manually moving or backing up the SQLite database.

### `pytest` is not recognised

Run pytest through the active Python interpreter:

```powershell
python -m pytest -q
```

## 13. macOS and Linux

The same Python versions and requirements apply. From the project root:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
python scripts/download_models.py
python -m flask --app app init-db
python -m flask --app app create-admin
python -m flask --app app run --debug
```

Open <http://127.0.0.1:5000>. Replace `python3.13` with `python3.12` or `python3.11` if required. To run tests:

```bash
python -m pytest -q
```