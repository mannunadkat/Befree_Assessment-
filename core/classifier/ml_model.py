"""ML model inference module."""

import os
from typing import Tuple, Optional
import joblib
from core.classifier.train import preprocess_text


MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")
_pipeline_cache = None


def get_model():
    global _pipeline_cache
    if _pipeline_cache is None:
        if not os.path.exists(MODEL_PATH):
            from core.classifier.train import train_model
            train_model()
        _pipeline_cache = joblib.load(MODEL_PATH)
    return _pipeline_cache


def classify_by_ml(description: str) -> Tuple[str, float]:
    """
    Predict category and confidence score using trained TF-IDF + LogisticRegression model.
    Returns:
    (category, confidence_probability)
    """
    pipeline = get_model()
    clean = preprocess_text(description)
    if not clean:
        return "Uncategorized", 0.0

    # Get class probabilities
    probs = pipeline.predict_proba([clean])[0]
    classes = pipeline.classes_
    best_idx = probs.argmax()
    best_cat = classes[best_idx]
    best_prob = float(probs[best_idx])

    return best_cat, round(best_prob, 2)
