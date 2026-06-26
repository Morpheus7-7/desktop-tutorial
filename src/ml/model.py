"""Modello ML per la previsione della direzione (XGBoost).

Espone una probabilità di rialzo in [0, 1]. Se il modello non è ancora stato
addestrato (file mancante) restituisce 0.5 (neutro), così il sistema continua a
funzionare con le sole strategie classiche.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..logging_setup import get_logger
from .features import FEATURE_COLUMNS, latest_feature_row

log = get_logger("ml.model")


class DirectionModel:
    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self._model = None
        self._loaded = False

    # ------------------------------------------------------------------ #
    def load(self) -> bool:
        if not self.model_path.exists():
            log.warning("Modello ML non trovato in %s — segnale ML neutro. "
                        "Allenalo con scripts/train_model.py", self.model_path)
            return False
        try:
            import joblib
            self._model = joblib.load(self.model_path)
            self._loaded = True
            log.info("Modello ML caricato da %s", self.model_path)
            return True
        except Exception as exc:
            log.error("Errore nel caricamento del modello ML: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    def predict_proba_up(self, df: pd.DataFrame) -> float:
        """Probabilità che la prossima candela sia rialzista (0..1)."""
        if not self._loaded or self._model is None:
            return 0.5
        row = latest_feature_row(df)
        if row is None:
            return 0.5
        try:
            proba = self._model.predict_proba(row[FEATURE_COLUMNS])[0][1]
            return float(proba)
        except Exception as exc:
            log.error("Errore in predict_proba: %s", exc)
            return 0.5

    # ------------------------------------------------------------------ #
    @staticmethod
    def train(X: pd.DataFrame, y: pd.Series, model_path: str | Path) -> dict:
        """Allena un classificatore XGBoost e lo salva. Restituisce le metriche."""
        import joblib
        from sklearn.metrics import accuracy_score, roc_auc_score
        from sklearn.model_selection import train_test_split
        from xgboost import XGBClassifier

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False
        )
        model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        proba = model.predict_proba(X_test)[:, 1]
        metrics = {
            "accuracy": float(accuracy_score(y_test, preds)),
            "auc": float(roc_auc_score(y_test, proba)) if y_test.nunique() > 1 else float("nan"),
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
        }

        path = Path(model_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, path)
        log.info("Modello salvato in %s | metriche=%s", path, metrics)
        return metrics
