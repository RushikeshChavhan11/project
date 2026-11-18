import numpy as np
import pytest

from quicktracker.face_engine import FaceEngine, FaceEngineError, cosine_similarity


def test_cosine_similarity_for_identical_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_for_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_rejects_different_dimensions():
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_cosine_similarity_handles_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == -1.0


def test_missing_models_are_reported(tmp_path):
    engine = FaceEngine(tmp_path)
    assert not engine.ready
    assert len(engine.missing_models) == 2



def test_decode_image_rejects_invalid_bytes():
    with pytest.raises(FaceEngineError):
        FaceEngine.decode_image(b"not an image")
