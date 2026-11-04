"""Classical ML training script: Multi-ngram FeatureUnion (Word + Char) + Logistic Regression."""

import os
import re
import joblib


def preprocess_text(text: str) -> str:
    """Normalize text while preserving subwords, handles OCR noise cleanly."""
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    return s


BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "training_data.csv")
TEST_CASES_DATA_PATH = os.path.join(BASE_DIR, "..", "..", "test cases", "classification_data", "classification_train_labeled.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model.joblib")
OVERRIDES_PATH = os.path.join(BASE_DIR, "..", "..", "data", "user_overrides.csv")


def train_model():
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline, FeatureUnion
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    print("Loading training datasets...")
    dfs = []
    if os.path.exists(DATA_PATH):
        dfs.append(pd.read_csv(DATA_PATH))
    if os.path.exists(TEST_CASES_DATA_PATH):
        dfs.append(pd.read_csv(TEST_CASES_DATA_PATH))

    # If user overrides exist, append them to training set
    if os.path.exists(OVERRIDES_PATH):
        try:
            df_overrides = pd.read_csv(OVERRIDES_PATH)
            if not df_overrides.empty and "description" in df_overrides.columns and "category" in df_overrides.columns:
                print(f"Incorporating {len(df_overrides)} user overrides into training data...")
                dfs.append(df_overrides[["description", "category"]])
        except Exception as e:
            print(f"Warning: could not load overrides: {e}")

    df = pd.concat(dfs, ignore_index=True)[["description", "category"]].dropna().drop_duplicates()
    df["clean_text"] = df["description"].apply(preprocess_text)
    X = df["clean_text"]
    y = df["category"]

    class_counts = y.value_counts()
    can_stratify = (class_counts.min() >= 2)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y if can_stratify else None
    )

    print("Fitting Word + Char_wb TF-IDF + Logistic Regression pipeline...")
    pipeline = Pipeline([
        ('features', FeatureUnion([
            ('word', TfidfVectorizer(
                ngram_range=(1, 3),
                min_df=2,
                sublinear_tf=True
            )),
            ('char', TfidfVectorizer(
                analyzer='char_wb',
                ngram_range=(3, 5),
                min_df=2,
                sublinear_tf=True
            ))
        ])),
        ('clf', LogisticRegression(
            C=10.0,
            max_iter=1000,
            class_weight='balanced',
            random_state=42
        ))
    ])

    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n==========================================")
    print(f"Model Validation Accuracy: {acc * 100:.2f}%")
    print(f"==========================================")

    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model successfully saved to {MODEL_PATH}")
    return acc


if __name__ == "__main__":
    train_model()
