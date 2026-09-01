from __future__ import annotations

from collections.abc import Callable

from tqdm.auto import tqdm
from xgboost.callback import TrainingCallback


class TrainingProgress(TrainingCallback):
    """Display XGBoost boosting-round progress and the latest validation AUC."""

    def __init__(
        self,
        total_rounds: int,
        description: str = "Training",
        leave: bool | None = None,
        progress_factory: Callable[..., object] = tqdm,
    ) -> None:
        self.total_rounds = int(total_rounds)
        progress_options = {
            "total": self.total_rounds,
            "desc": description,
            "unit": "round",
            "dynamic_ncols": True,
        }
        if leave is not None:
            progress_options["leave"] = leave
        self._progress = progress_factory(**progress_options)
        self._closed = False

    def after_iteration(self, model, epoch: int, evals_log: dict) -> bool:
        auc_values = evals_log.get("validation_0", {}).get("auc", [])
        if auc_values:
            self._progress.set_postfix(
                {"validation_auc": f"{float(auc_values[-1]):.4f}"},
                refresh=False,
            )
        self._progress.update(1)
        return False

    def after_training(self, model):
        self.close()
        return model

    def close(self) -> None:
        if not self._closed:
            self._progress.close()
            self._closed = True
