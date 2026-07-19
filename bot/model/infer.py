from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np

from bot.logging_setup import get_logger
from bot.model.features_build import FEATURE_NAMES, features_to_vector

log = get_logger("bot.model.infer")


class ProbabilityModel:
    """Loads calibrated classifier; falls back to no-skill prior when missing."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self._bundle: dict[str, Any] | None = None
        self._mtime: float | None = None
        self.reload()

    def reload(self) -> bool:
        if not self.model_path.exists():
            self._bundle = None
            self._mtime = None
            return False
        mtime = self.model_path.stat().st_mtime
        if self._mtime == mtime and self._bundle is not None:
            return True
        try:
            self._bundle = joblib.load(self.model_path)
            self._mtime = mtime
            log.info("Loaded model from %s", self.model_path)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to load model: %s", exc)
            self._bundle = None
            return False

    @property
    def ready(self) -> bool:
        return self._bundle is not None

    def predict_proba(self, features: dict[str, float], *, target_pct: float, stop_pct: float) -> float:
        self.reload()
        if not self._bundle:
            # No-skill prior
            t, s = abs(target_pct), abs(stop_pct)
            return s / (t + s) if t + s > 0 else 0.5
        model = self._bundle["model"]
        names = self._bundle.get("feature_names", FEATURE_NAMES)
        vec = np.array([float(features.get(n, 0.0)) for n in names], dtype=float).reshape(1, -1)
        try:
            proba = model.predict_proba(vec)[0]
            # class 1 = success
            if len(proba) == 1:
                return float(proba[0])
            return float(proba[1])
        except Exception as exc:  # noqa: BLE001
            log.debug("predict failed: %s", exc)
            t, s = abs(target_pct), abs(stop_pct)
            return s / (t + s) if t + s > 0 else 0.5


def expected_edge(p: float, target_pct: float, stop_pct: float, fee_buffer_pct: float = 0.0) -> float:
    """Edge as fraction of price (not percent points)."""
    return p * (target_pct / 100.0) - (1 - p) * (stop_pct / 100.0) - (fee_buffer_pct / 100.0)
