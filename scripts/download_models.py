#!/usr/bin/env python3
"""Download and validate the official OpenCV Zoo YuNet and SFace ONNX models.

Run from the project root:
    python scripts/download_models.py

Model weights are downloaded separately and are intentionally not committed to Git.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"

# These SHA-256 values are published by the official OpenCV model files on
# Hugging Face (OpenCV's mirror of OpenCV Zoo). The YuNet model is approximately
# 233 kB; a 500 kB minimum-size check incorrectly rejects this valid model.
MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "url": (
            "https://huggingface.co/opencv/opencv_zoo/resolve/main/"
            "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
        ),
        "minimum_size": 200_000,
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    },
    "face_recognition_sface_2021dec.onnx": {
        "url": (
            "https://huggingface.co/opencv/opencv_zoo/resolve/main/"
            "models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
        ),
        "minimum_size": 30_000_000,
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    },
}


def is_git_lfs_pointer(path: Path) -> bool:
    """Return True if the downloaded content is a Git LFS pointer text file."""
    try:
        with path.open("rb") as model_file:
            prefix = model_file.read(200)
    except OSError:
        return False
    return prefix.startswith(b"version https://git-lfs.github.com/spec/v1")


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 in chunks to avoid loading a large model into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid_model(path: Path, details: dict[str, object]) -> bool:
    if not path.is_file():
        return False
    if path.stat().st_size < int(details["minimum_size"]):
        return False
    if is_git_lfs_pointer(path):
        return False
    return sha256_file(path) == str(details["sha256"])


def download(url: str, target: Path, details: dict[str, object]) -> None:
    """Download one model and verify its expected size and SHA-256 checksum."""
    if target.exists() and is_valid_model(target, details):
        print(f"Already downloaded and verified: {target.name}")
        return

    if target.exists():
        print(f"Existing {target.name} is incomplete or has an invalid checksum; replacing it.")

    temporary = target.with_suffix(target.suffix + ".download")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "QuiickTracker-model-setup/1.0"},
    )

    print(f"Downloading {target.name} ...")
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError(f"Model server returned HTTP {status}.")
            with temporary.open("wb") as output:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    output.write(block)

        size = temporary.stat().st_size
        if size < int(details["minimum_size"]):
            raise RuntimeError(
                f"Downloaded file is too small ({size:,} bytes); expected at least "
                f"{int(details['minimum_size']):,} bytes."
            )
        if is_git_lfs_pointer(temporary):
            raise RuntimeError("The server returned a Git LFS pointer instead of ONNX weights.")

        actual_hash = sha256_file(temporary)
        expected_hash = str(details["sha256"])
        if actual_hash.lower() != expected_hash.lower():
            raise RuntimeError(
                "Model SHA-256 verification failed. "
                f"Expected {expected_hash}, received {actual_hash}."
            )

        temporary.replace(target)
        print(f"Saved and verified {target.name} ({size:,} bytes).")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate_models() -> None:
    """Ask OpenCV to load both ONNX files so invalid downloads fail early."""
    detector_path = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
    recognizer_path = MODEL_DIR / "face_recognition_sface_2021dec.onnx"
    try:
        detector = cv2.FaceDetectorYN_create(str(detector_path), "", (320, 320))
        recognizer = cv2.FaceRecognizerSF_create(str(recognizer_path), "")
        if detector is None or recognizer is None:
            raise RuntimeError("OpenCV returned an empty face model instance.")
    except Exception as exc:
        raise RuntimeError(
            "OpenCV could not load one or both ONNX files. Check that the installed "
            "opencv-python-headless version supports FaceDetectorYN and FaceRecognizerSF."
        ) from exc


def main() -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        for filename, details in MODELS.items():
            download(str(details["url"]), MODEL_DIR / filename, details)
        validate_models()
    except Exception as exc:
        print(f"Model setup failed: {exc}", file=sys.stderr)
        print(
            "Check the internet connection and retry: python scripts/download_models.py",
            file=sys.stderr,
        )
        return 1

    print("\nBoth YuNet and SFace ONNX models passed checksum verification and loaded in OpenCV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
