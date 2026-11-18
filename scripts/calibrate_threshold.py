#!/usr/bin/env python3
"""Evaluate a cosine-similarity threshold from a labeled image-pair CSV.

CSV columns: image_a,image_b,same_person
Paths may be absolute or relative to the project root. same_person accepts
true/false, 1/0, yes/no. Keep a separate validation set for final reporting.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from quicktracker.face_engine import FaceEngine, cosine_similarity

ROOT = Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else ROOT / candidate


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "same"}:
        return True
    if normalized in {"false", "0", "no", "different"}:
        return False
    raise ValueError(f"Unsupported same_person value: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pairs_csv", help="CSV containing image_a,image_b,same_person")
    parser.add_argument("--steps", type=int, default=201, help="Number of thresholds to evaluate")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    model_dir = Path(os.getenv("MODEL_DIR", "models")).expanduser()
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    detection_threshold = float(os.getenv("FACE_DETECTION_THRESHOLD", "0.90"))
    engine = FaceEngine(model_dir, detection_threshold=detection_threshold)
    if not engine.ready:
        parser.error("Face model files are missing. Run `python scripts/download_models.py` first.")

    pairs = []
    with resolve_path(args.pairs_csv).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"image_a", "image_b", "same_person"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            parser.error("CSV must contain image_a,image_b,same_person columns.")
        for row_number, row in enumerate(reader, start=2):
            left_path = resolve_path(row["image_a"])
            right_path = resolve_path(row["image_b"])
            try:
                left = engine.extract_largest(left_path.read_bytes())
                right = engine.extract_largest(right_path.read_bytes())
                same = parse_bool(row["same_person"])
            except Exception as exc:
                parser.error(f"Could not process CSV row {row_number}: {exc}")
            pairs.append((cosine_similarity(left, right), same))

    if len(pairs) < 10:
        parser.error("Provide at least 10 labeled image pairs; a larger balanced dataset is strongly recommended.")
    scores = np.asarray([item[0] for item in pairs], dtype=np.float32)
    labels = np.asarray([item[1] for item in pairs], dtype=bool)
    if labels.all() or (~labels).all():
        parser.error("The validation CSV must include both same-person and different-person pairs.")

    thresholds = np.linspace(-1.0, 1.0, max(3, args.steps))
    best = None
    for threshold in thresholds:
        predicted_same = scores >= threshold
        false_accept = np.mean(predicted_same[~labels])
        false_reject = np.mean(~predicted_same[labels])
        balanced_accuracy = 1.0 - (false_accept + false_reject) / 2.0
        candidate = (balanced_accuracy, -abs(false_accept - false_reject), threshold, false_accept, false_reject)
        if best is None or candidate[:2] > best[:2]:
            best = candidate

    assert best is not None
    print(f"Pairs evaluated: {len(pairs)} (same={int(labels.sum())}, different={int((~labels).sum())})")
    print(f"Suggested threshold: {best[2]:.3f}")
    print(f"Balanced accuracy: {best[0] * 100:.2f}%")
    print(f"False accept rate: {best[3] * 100:.2f}%")
    print(f"False reject rate: {best[4] * 100:.2f}%")
    print("Set FACE_MATCH_THRESHOLD in .env only after reviewing these errors and testing on a separate hold-out set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
