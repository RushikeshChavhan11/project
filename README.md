# QuiickTracker

**Face-recognition attendance monitoring prototype**

Python 3.11–3.13 · Flask · OpenCV · YuNet · SFace · SQLAlchemy · SQLite / MySQL

QuiickTracker is a local-first academic prototype for exploring a face-matching workflow for classroom attendance. An administrator registers a student and up to five face images. The application detects and aligns faces with YuNet, extracts feature embeddings with the pre-trained SFace model, builds a per-student embedding gallery, and compares a captured browser-camera frame against that gallery using cosine similarity.

It includes student management, gallery generation, attendance marking, duplicate prevention, searchable attendance history, CSV/PDF exports, and a 14-day trend chart.

## Features

- Administrator login with password hashing and CSRF protection.
- Student profiles with ID, name, course, year/semester, and face-image capture/upload.
- Browser camera support on `localhost` or HTTPS.
- YuNet face detection and SFace 128-dimensional embeddings using OpenCV.
- Normalized per-student embedding gallery and configurable cosine-similarity threshold.
- Multiple detected faces per attendance capture.
- Duplicate attendance protection enforced by a database uniqueness constraint.
- Attendance filtering and CSV/PDF downloads.
- Attendance trend visualization with Matplotlib.
- SQLite for local development; MySQL can be configured through SQLAlchemy.
- Pytest suite 

## The short Windows setup is:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python scripts/download_models.py
python -m flask --app app init-db
python -m flask --app app create-admin
python -m flask --app app run --debug
```
Then open **http://127.0.0.1:5000** and sign in with the administrator credentials created in the terminal.

