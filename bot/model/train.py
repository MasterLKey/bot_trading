from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import train_test_split

from bot.logging_setup import get_logger
from bot.model.features_build import FEATURE_NAMES, features_to_vector
from bot.model.label import no_skill_base_rate

log = get_logger("bot.model.train")


@dataclass
class TrainResult:
    model_path: Path
    metrics: dict[str, Any]
    n_samples: int


def train_calibrated_model(
    X: np.ndarray,
    y: np.ndarray,
    *,
    model_path: Path,
    metrics_path: Path,
    target_pct: float,
    stop_pct: float,
) -> TrainResult:
    if len(X) < 50:
        raise ValueError(f"Need at least 50 samples to train, got {len(X)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
    )

    base = HistGradientBoostingClassifier(
        max_depth=5,
        learning_rate=0.08,
        max_iter=150,
        random_state=42,
    )
    # Isotonic calibration on held-out fold inside CV
    clf = CalibratedClassifierCV(base, method="isotonic", cv=3)
    clf.fit(X_train, y_train)

    proba = clf.predict_proba(X_test)[:, 1] if hasattr(clf, "predict_proba") else clf.predict(X_test)
    preds = (proba >= 0.5).astype(int)
    hit_rate = float(np.mean(y_test))
    model_hit = float(np.mean(y_test[proba >= 0.5])) if np.any(proba >= 0.5) else float("nan")
    baseline = no_skill_base_rate(target_pct, stop_pct)
    brier = float(brier_score_loss(y_test, proba))

    # Calibration buckets
    buckets = []
    for lo in np.linspace(0, 0.9, 10):
        hi = lo + 0.1
        mask = (proba >= lo) & (proba < hi)
        if mask.sum() == 0:
            continue
        buckets.append(
            {
                "lo": round(float(lo), 2),
                "hi": round(float(hi), 2),
                "n": int(mask.sum()),
                "avg_p": float(np.mean(proba[mask])),
                "hit_rate": float(np.mean(y_test[mask])),
            }
        )

    # Predicted edge vs realized (approx using target/stop for binary outcomes)
    pred_edge = proba * (target_pct / 100) - (1 - proba) * (stop_pct / 100)
    realized = np.where(y_test == 1, target_pct / 100, -stop_pct / 100)
    metrics = {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "base_rate": hit_rate,
        "no_skill_baseline": baseline,
        "brier": brier,
        "accuracy_at_50": float(np.mean(preds == y_test)),
        "hit_rate_when_p_ge_50": model_hit,
        "beats_baseline": bool(hit_rate > 0 and not np.isnan(model_hit) and model_hit > baseline),
        "mean_predicted_edge": float(np.mean(pred_edge)),
        "mean_realized_edge": float(np.mean(realized)),
        "calibration_buckets": buckets,
        "feature_names": FEATURE_NAMES,
        "target_pct": target_pct,
        "stop_pct": stop_pct,
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "feature_names": FEATURE_NAMES}, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    log.info(
        "Trained model n=%d brier=%.4f baseline=%.3f hit@p>=0.5=%s -> %s",
        len(X),
        brier,
        baseline,
        model_hit,
        model_path,
    )
    return TrainResult(model_path=model_path, metrics=metrics, n_samples=len(X))


def build_xy_from_rows(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    X = np.vstack([features_to_vector(r["features"]) for r in rows])
    y = np.array([int(r["success"]) for r in rows], dtype=int)
    return X, y
