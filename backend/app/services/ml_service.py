import json
from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)


MODEL_PATH = Path(__file__).parent.parent.parent / "models"
MODEL_PATH.mkdir(parents=True, exist_ok=True)

MODEL_FILE = MODEL_PATH / "rf_model.joblib"
METRICS_FILE = MODEL_PATH / "rf_model_metrics.json"


def build_preprocessor(categorical_features, numeric_features):
    cat_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    num_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", num_pipeline, numeric_features),
            ("cat", cat_pipeline, categorical_features),
        ],
        remainder="drop",
    )


def _can_stratify(y: pd.Series) -> bool:
    """
    Stratify requires at least 2 classes and at least 2 samples per class.
    """
    counts = y.value_counts()
    return len(counts) >= 2 and counts.min() >= 2


def _safe_cv_folds(y_train: pd.Series, requested_cv: int = 5) -> int:
    """
    GridSearchCV cannot use more folds than the smallest class count.
    """
    counts = y_train.value_counts()

    if len(counts) < 2:
        return 0

    min_class_count = int(counts.min())

    if min_class_count < 2:
        return 0

    return min(requested_cv, min_class_count)


def train_from_dataframe(
    df: pd.DataFrame,
    target_col: str = "flux",
    do_cv: bool = True,
) -> dict:
    required = [
        "protocol",
        "port",
        "src_ip",
        "dst_ip",
        "flowMainSG",
        "flowGrefSG",
        target_col,
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    df = df.copy()
    df = df.fillna("")

    for col in required:
        df[col] = df[col].astype(str).fillna("").str.strip()

    df = df[df[target_col] != ""].copy()

    if df.empty:
        raise ValueError(f"No usable rows found for target column: {target_col}")

    class_count = df[target_col].nunique()

    if class_count < 2:
        raise ValueError(
            f"Cannot train model: target '{target_col}' has only one class."
        )

    df["port"] = pd.to_numeric(df["port"], errors="coerce")

    numeric_features = ["port"]
    categorical_features = [
        "protocol",
        "src_ip",
        "dst_ip",
        "flowMainSG",
        "flowGrefSG",
    ]

    X = df[numeric_features + categorical_features]
    y = df[target_col].astype(str)

    preprocessor = build_preprocessor(
        categorical_features=categorical_features,
        numeric_features=numeric_features,
    )

    base_model = RandomForestClassifier(
        random_state=42,
        class_weight="balanced",
    )

    pipe = Pipeline(
        steps=[
            ("pre", preprocessor),
            ("model", base_model),
        ]
    )

    stratify_value = y if _can_stratify(y) else None

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=stratify_value,
    )

    cv_folds = _safe_cv_folds(y_train, requested_cv=5)

    best_params = None

    if do_cv and cv_folds >= 2:
        param_grid = {
            "model__n_estimators": [100, 200],
            "model__max_depth": [None, 10, 20],
            "model__min_samples_split": [2, 5],
        }

        grid_search = GridSearchCV(
            pipe,
            param_grid,
            cv=cv_folds,
            scoring="f1_macro",
            n_jobs=-1,
        )

        grid_search.fit(X_train, y_train)
        best_model = grid_search.best_estimator_
        best_params = grid_search.best_params_

    else:
        pipe.fit(X_train, y_train)
        best_model = pipe

    y_pred = best_model.predict(X_test)

    accuracy = float(accuracy_score(y_test, y_pred))
    precision = float(
        precision_score(y_test, y_pred, average="macro", zero_division=0)
    )
    recall = float(
        recall_score(y_test, y_pred, average="macro", zero_division=0)
    )
    f1 = float(
        f1_score(y_test, y_pred, average="macro", zero_division=0)
    )

    report = classification_report(
        y_test,
        y_pred,
        output_dict=True,
        zero_division=0,
    )

    cm = confusion_matrix(y_test, y_pred).tolist()

    joblib.dump(best_model, MODEL_FILE)

    metrics = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "classification_report": report,
        "confusion_matrix": cm,
        "best_params": best_params,
        "target_col": target_col,
        "n_classes": int(class_count),
        "n_rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
    }

    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    return {
        "model_path": str(MODEL_FILE),
        "metrics_path": str(METRICS_FILE),
        "n_classes": int(class_count),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "metrics": metrics,
    }


def load_model():
    if MODEL_FILE.exists():
        return joblib.load(MODEL_FILE)

    return None


def predict(df: pd.DataFrame, return_proba: bool = False):
    """
    Predict and return a list of dicts containing prediction, probability
    optionally, and context fields.
    """
    model = load_model()

    if model is None:
        raise RuntimeError("No trained model found. Call train first.")

    required_cols = [
        "protocol",
        "port",
        "src_ip",
        "dst_ip",
        "flowMainSG",
        "flowGrefSG",
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing column for prediction: {col}")

    df_local = df.copy()
    df_local = df_local.fillna("")

    for col in required_cols:
        df_local[col] = df_local[col].astype(str).fillna("").str.strip()

    df_local["port"] = pd.to_numeric(df_local["port"], errors="coerce")

    X = df_local[
        [
            "port",
            "protocol",
            "src_ip",
            "dst_ip",
            "flowMainSG",
            "flowGrefSG",
        ]
    ]

    preds = model.predict(X)

    results = []
    proba_matrix = None
    classes = []

    if return_proba and hasattr(model, "predict_proba"):
        try:
            proba_matrix = model.predict_proba(X)
            classes = model.classes_
        except Exception:
            proba_matrix = None
            classes = []

    for i, pred in enumerate(preds):
        row = df_local.iloc[i]

        item = {
            "prediction": str(pred),
            "src_ip": row.get("src_ip"),
            "dst_ip": row.get("dst_ip"),
            "port": row.get("port"),
            "flowMainSG": row.get("flowMainSG"),
            "flowGrefSG": row.get("flowGrefSG"),
        }

        if proba_matrix is not None:
            probs = {
                str(cls): float(proba_matrix[i, j])
                for j, cls in enumerate(classes)
            }

            item["proba"] = probs
            item["confidence"] = max(probs.values()) if probs else None

        results.append(item)

    return results