"""
Train XGBoost regressor on synthetic data for weekly premium risk adjustment.
Run: python -m app.ml.train_premium_model (from backend/)
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.services.features import FEATURE_ORDER

OUT = Path(__file__).resolve().parent / "premium_xgb.pkl"
FEATURES = list(FEATURE_ORDER)


def synth_dataset(n: int = 2000) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(42)
    flood = rng.uniform(0.05, 0.98, n)
    heat = rng.uniform(30.0, 44.0, n)
    aqi_pct = rng.uniform(35.0, 98.0, n)
    cv = rng.uniform(0.02, 0.35, n)
    consistency = rng.uniform(0.4, 1.0, n)
    disrupt = rng.uniform(0.0, 10.0, n)
    # Synthetic target: same spirit as heuristic_adjustment
    adj = (
        (flood - 0.3) * 15
        + (heat - 36) * 0.8
        + (aqi_pct - 60) * 0.05
        + cv * 40
        - (consistency - 0.7) * 10
        + disrupt * 0.5
        + rng.normal(0, 1.2, n)
    )
    adj = np.clip(adj, -10.0, 25.0)
    X = pd.DataFrame(
        {
            "zone_flood_risk_score": flood,
            "zone_heat_index": heat,
            "zone_aqi_percentile": aqi_pct,
            "worker_income_cv": cv,
            "worker_consistency_score": consistency,
            "disruption_frequency_local": disrupt,
        }
    )
    return X, adj.astype(float)


def main():
    X, y = synth_dataset()
    model = XGBRegressor(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        random_state=42,
    )
    model.fit(X, y)
    joblib.dump(model, OUT)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
