"""MLflow tracking and the model registry: every training run is logged; a candidate becomes the
champion (alias) only through the gate in config/release.yaml."""

from __future__ import annotations

import json
import os
import pickle
import tempfile
from pathlib import Path

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from ..shared.config import load
from .scorer import Scorer
from .train import flat_metrics

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


class ScorerModel(mlflow.pyfunc.PythonModel):
    """pyfunc wrapper: predict() returns p_contact and p_win per row of features."""

    def load_context(self, context):
        with open(context.artifacts["scorer"], "rb") as f:
            self.scorer: Scorer = pickle.load(f)

    def predict(self, context, model_input: pd.DataFrame, params=None):
        pc, pw = self.scorer.predict(model_input[self.scorer.features].to_numpy(float))
        return pd.DataFrame({"p_contact": pc, "p_win": pw})


def configure(store: Path) -> None:
    store.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{store / 'mlflow.db'}")
    mlflow.set_registry_uri(f"sqlite:///{store / 'mlflow.db'}")
    if mlflow.get_experiment_by_name("partner-matching") is None:
        mlflow.create_experiment("partner-matching", artifact_location=(store / "artifacts").as_uri())
    mlflow.set_experiment("partner-matching")


def log_candidate(scorer: Scorer, metrics: dict, extra: dict, store: Path) -> str:
    """Logs a training run and registers its scorer as a new model version. Returns the version."""
    configure(store)
    name = load("models")["registry"]["model_name"]
    with mlflow.start_run(run_name=f"train-cutoff-{metrics['cutoff']:.0f}") as run:
        mlflow.log_params({"cutoff": metrics["cutoff"], **{f"lgb_{k}": v for k, v in load("models")["lightgbm"].items()}})
        mlflow.log_metrics({**flat_metrics(metrics), **{k: float(v) for k, v in extra.items()}})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "scorer.pkl"
            with open(p, "wb") as f:
                pickle.dump(scorer, f)
            (Path(d) / "metrics.json").write_text(json.dumps(metrics, indent=1, default=float))
            mlflow.log_artifact(str(Path(d) / "metrics.json"))
            mlflow.pyfunc.log_model(
                name="scorer", python_model=ScorerModel(), artifacts={"scorer": str(p)}, registered_model_name=name
            )
        client = MlflowClient()
        versions = [v for v in client.search_model_versions(f"name='{name}'") if v.run_id == run.info.run_id]
        version = versions[0].version
    return str(version)


def champion(store: Path) -> tuple[str, dict] | None:
    configure(store)
    c = load("models")["registry"]
    client = MlflowClient()
    try:
        v = client.get_model_version_by_alias(c["model_name"], c["champion_alias"])
    except Exception:
        return None
    return v.version, client.get_run(v.run_id).data.metrics


def gate(candidate: dict[str, float], champion_metrics: dict[str, float] | None, mismatches: int) -> tuple[bool, list[str]]:
    g = load("release")["model"]
    why = []
    for m in ("contact", "win"):
        if candidate[f"{m}_ece"] > g["max_ece"][m]:
            why.append(f"{m} ECE {candidate[f'{m}_ece']:.4f} > {g['max_ece'][m]}")
        if candidate[f"{m}_auc"] < g["min_auc"][m]:
            why.append(f"{m} AUC {candidate[f'{m}_auc']:.3f} < {g['min_auc'][m]}")
        if champion_metrics and candidate[f"{m}_auc"] < champion_metrics.get(f"{m}_auc", 0) - g["max_auc_drop_vs_champion"]:
            why.append(f"{m} AUC drops more than {g['max_auc_drop_vs_champion']} below the champion")
    if mismatches > g["max_feature_mismatches"]:
        why.append(f"{mismatches} training/serving feature mismatches")
    return not why, why


def promote(version: str, store: Path) -> None:
    configure(store)
    c = load("models")["registry"]
    MlflowClient().set_registered_model_alias(c["model_name"], c["champion_alias"], version)


def load_champion(store: Path) -> Scorer:
    configure(store)
    c = load("models")["registry"]
    m = mlflow.pyfunc.load_model(f"models:/{c['model_name']}@{c['champion_alias']}")
    return m.unwrap_python_model().scorer
