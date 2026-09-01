import unittest

import numpy as np
import pytest

from src.weights import (
    MCNormalization,
    physical_event_weight,
    physical_event_weights,
    training_weights,
    weight_summary,
)


def normalization_event(**overrides):
    event = {
        "mcWeight": -0.5,
        "xsec": 2.0,
        "kfac": 1.2,
        "filteff": 0.5,
        "sum_of_weights": 100.0,
    }
    event.update(overrides)
    return event


def test_mc_normalization_parses_fields_and_effective_cross_section():
    normalization = MCNormalization.from_event(normalization_event())

    assert normalization == MCNormalization(
        xsec_pb=2.0,
        k_factor=1.2,
        filter_efficiency=0.5,
        sum_of_weights=100.0,
    )
    assert normalization.effective_cross_section_pb == pytest.approx(1.2)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"xsec": float("nan")}, "finite"),
        ({"xsec": -1.0}, "xsec_pb must be non-negative"),
        ({"kfac": 0.0}, "k_factor must be strictly positive"),
        ({"kfac": -1.0}, "k_factor must be strictly positive"),
        ({"filteff": -0.01}, "filter_efficiency must be in"),
        ({"filteff": 1.01}, "filter_efficiency must be in"),
        ({"sum_of_weights": 0.0}, "sum_of_weights must be non-zero"),
        ({"sum_of_weights": float("inf")}, "finite"),
    ],
)
def test_mc_normalization_rejects_invalid_values(overrides, message):
    with pytest.raises(ValueError, match=message):
        MCNormalization.from_event(normalization_event(**overrides))


def test_mc_normalization_accepts_only_values_within_fixed_tolerance():
    normalization = MCNormalization.from_event(normalization_event())
    normalization.assert_matches(normalization_event(xsec=2.0 * (1.0 + 5e-13)))

    with pytest.raises(ValueError, match="xsec_pb changed within one MC sample"):
        normalization.assert_matches(normalization_event(xsec=2.0 * (1.0 + 2e-12)))


def test_scalar_weight_uses_validated_normalization_object():
    event = normalization_event(xsec=2.0 * (1.0 + 5e-13))
    normalization = MCNormalization.from_event(normalization_event())

    assert physical_event_weight(
        event, 1000.0, normalization=normalization
    ) == pytest.approx(-6.0)


def test_external_normalization_does_not_require_absent_event_constants():
    event = {"mcWeight": -2.0}
    normalization = MCNormalization(1.2564, 1.0, 1.0, 7538705.808)

    value = physical_event_weight(
        event,
        10000.0,
        normalization=normalization,
        require_event_normalization=False,
    )

    assert value == pytest.approx(10000.0 * 1.2564 / 7538705.808 * -2.0)


def test_partial_event_normalization_constants_are_never_mixed_with_override():
    with pytest.raises(KeyError, match="MC event normalization fields are incomplete"):
        physical_event_weight(
            {"mcWeight": -2.0, "xsec": 1.2564},
            10000.0,
            normalization=MCNormalization(1.2564, 1.0, 1.0, 7538705.808),
            require_event_normalization=False,
        )


class WeightTests(unittest.TestCase):
    def test_physical_weight_formula_and_negative_weight(self):
        result = physical_event_weights(
            mc_weight=[1.0, -0.5],
            xsec_pb=2.0,
            k_factor=1.2,
            filter_efficiency=0.5,
            sum_of_weights=100.0,
            luminosity_pb=1000.0,
        )
        np.testing.assert_allclose(result, [12.0, -6.0])
        self.assertEqual(weight_summary(result)["negative_events"], 1)

    def test_training_weights_are_finite_and_nonnegative(self):
        result = training_weights([2.0, -1.0, 0.0])
        self.assertTrue(np.isfinite(result).all())
        self.assertTrue((result >= 0).all())
        self.assertAlmostEqual(result.mean(), 1.0)

    def test_zero_sum_of_weights_fails(self):
        with self.assertRaises(ValueError):
            physical_event_weights([1], 1, 1, 1, 0, 1)

    def test_scalar_physical_event_weight_matches_vector_formula(self):
        event = {
            "mcWeight": -0.5,
            "xsec": 2.0,
            "kfac": 1.2,
            "filteff": 0.5,
            "sum_of_weights": 100.0,
        }
        self.assertAlmostEqual(physical_event_weight(event, 1000.0), -6.0)


if __name__ == "__main__":
    unittest.main()
