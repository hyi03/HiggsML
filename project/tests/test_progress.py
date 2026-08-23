from __future__ import annotations

from src.progress import TrainingProgress
from src.train import build_training_progress


class FakeProgressBar:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.n = 0
        self.postfix = {}
        self.closed = False

    def update(self, amount):
        self.n += amount

    def set_postfix(self, values, refresh=False):
        self.postfix = values

    def close(self):
        self.closed = True


def test_training_progress_updates_round_and_validation_auc():
    bar = FakeProgressBar()
    progress = TrainingProgress(3, progress_factory=lambda **kwargs: bar)

    should_stop = progress.after_iteration(
        model=None,
        epoch=0,
        evals_log={"validation_0": {"auc": [0.91]}},
    )

    assert should_stop is False
    assert bar.n == 1
    assert bar.postfix == {"validation_auc": "0.9100"}


def test_training_progress_advances_without_validation_auc():
    bar = FakeProgressBar()
    progress = TrainingProgress(2, progress_factory=lambda **kwargs: bar)

    progress.after_iteration(model=None, epoch=0, evals_log={})

    assert bar.n == 1
    assert bar.postfix == {}


def test_training_progress_uses_configured_total_and_closes():
    bar = FakeProgressBar()
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return bar

    progress = TrainingProgress(17, progress_factory=factory)
    model = object()
    returned_model = progress.after_training(model)

    assert captured == {
        "total": 17,
        "desc": "Training",
        "unit": "round",
        "dynamic_ncols": True,
    }
    assert returned_model is model
    assert bar.closed is True


def test_training_progress_close_is_idempotent():
    bar = FakeProgressBar()
    close_calls = 0

    def close_once():
        nonlocal close_calls
        close_calls += 1

    bar.close = close_once
    progress = TrainingProgress(1, progress_factory=lambda **kwargs: bar)

    progress.close()
    progress.close()

    assert close_calls == 1


def test_build_training_progress_uses_effective_estimator_count():
    bars = []

    def factory(**kwargs):
        bar = FakeProgressBar(**kwargs)
        bars.append(bar)
        return bar

    progress = build_training_progress(
        {"n_estimators": 17},
        progress_factory=factory,
    )

    assert progress.total_rounds == 17
    assert bars[0].kwargs["total"] == 17
