"""OpenCV YuNet + SFace inference adapter.

This uses the pre-trained OpenCV Zoo models. It does not train a CNN/GNN/Transformer
network; the training step in this application builds a per-student embedding gallery.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class FaceEngineError(RuntimeError):
    pass


class FaceEngine:
    DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
    RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"

    def __init__(self, model_dir: str | Path, detection_threshold: float = 0.90):
        self.model_dir = Path(model_dir)
        self.detector_path = self.model_dir / self.DETECTOR_FILE
        self.recognizer_path = self.model_dir / self.RECOGNIZER_FILE
        self.detection_threshold = detection_threshold
        self._lock = threading.RLock()
        self.detector = None
        self.recognizer = None

    @property
    def missing_models(self) -> list[str]:
        return [
            str(path)
            for path in (self.detector_path, self.recognizer_path)
            if not path.is_file()
        ]

    @property
    def ready(self) -> bool:
        return not self.missing_models

    def _load(self) -> None:
        missing = self.missing_models
        if missing:
            raise FaceEngineError(
                "Face model files are missing. Run `python scripts/download_models.py`. "
                + "Missing: "
                + ", ".join(missing)
            )
        if self.detector is None:
            try:
                self.detector = cv2.FaceDetectorYN_create(
                    str(self.detector_path), "", (320, 320),
                    float(self.detection_threshold), 0.30, 5000
                )
                self.recognizer = cv2.FaceRecognizerSF_create(
                    str(self.recognizer_path), ""
                )
            except Exception as exc:  # OpenCV may fail on incompatible ONNX builds.
                self.detector = None
                self.recognizer = None
                raise FaceEngineError(f"Could not load OpenCV face models: {exc}") from exc

    @staticmethod
    def decode_image(image_bytes: bytes) -> np.ndarray:
        if not image_bytes:
            raise FaceEngineError("No image data was received.")
        try:
            image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        except cv2.error as exc:
            raise FaceEngineError("The uploaded file could not be decoded as an image.") from exc
        if image is None or image.size == 0:
            raise FaceEngineError("The uploaded file is not a valid image.")
        return image

    def extract_all(self, image_bytes: bytes) -> list[dict[str, Any]]:
        """Return one normalized 128-D embedding per detected face in the image."""
        image = self.decode_image(image_bytes)
        height, width = image.shape[:2]
        if width < 80 or height < 80:
            raise FaceEngineError("Image is too small. Use a clear image at least 80x80 pixels.")

        with self._lock:
            self._load()
            self.detector.setInputSize((width, height))
            _, faces = self.detector.detect(image)
            if faces is None or len(faces) == 0:
                raise FaceEngineError("No face was detected. Improve lighting and face the camera.")

            results: list[dict[str, Any]] = []
            for face in faces:
                aligned = self.recognizer.alignCrop(image, face)
                feature = self.recognizer.feature(aligned).astype(np.float32).reshape(-1)
                norm = float(np.linalg.norm(feature))
                if norm <= 1e-12:
                    continue
                vector = (feature / norm).astype(float).tolist()
                results.append(
                    {
                        "embedding": vector,
                        "confidence": float(face[-1]),
                        "box": [int(v) for v in face[:4]],
                        "area": float(max(face[2], 0) * max(face[3], 0)),
                    }
                )

        if not results:
            raise FaceEngineError("A face was detected, but its embedding could not be generated.")
        return results

    def extract_largest(self, image_bytes: bytes) -> list[float]:
        faces = self.extract_all(image_bytes)
        return max(faces, key=lambda item: item["area"])["embedding"]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    a = np.asarray(left, dtype=np.float32).reshape(-1)
    b = np.asarray(right, dtype=np.float32).reshape(-1)
    if a.shape != b.shape:
        raise ValueError("Embedding dimensions do not match.")
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= 1e-12:
        return -1.0
    return float(np.dot(a, b) / denominator)
