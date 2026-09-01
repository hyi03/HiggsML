import unittest

import numpy as np

from src.features import (
    FEATURES,
    FORBIDDEN_FEATURES,
    build_candidate_features,
    build_event_features,
)
from src.reconstruction import normalize_leptons, reconstruct_candidate


class FeatureTests(unittest.TestCase):
    def test_feature_list_has_no_leakage(self):
        self.assertFalse(set(FEATURES) & FORBIDDEN_FEATURES)

    def test_builds_finite_features_in_gev(self):
        event = {
            "lep_pt": [45000, 42000, 16000, 14000],
            "lep_eta": [0, 0, 0, 0],
            "lep_phi": [0, np.pi, np.pi / 2, -np.pi / 2],
            "lep_e": [45000, 42000, 16000, 14000],
            "lep_charge": [1, -1, 1, -1],
            "lep_type": [11, 11, 13, 13],
            "eventNumber": 7,
            "channelNumber": 42,
        }
        output = build_event_features(event, "MeV")
        self.assertIsNotNone(output)
        self.assertAlmostEqual(output["lep1_pt"], 45.0)
        self.assertTrue(np.isfinite([output[name] for name in FEATURES]).all())
        self.assertIn("m4l", output)
        self.assertNotIn("m4l", FEATURES)

    def test_shared_reconstruction_sorts_all_lepton_fields_together(self):
        event = {
            "lep_pt": [16000, 45000, 14000, 42000],
            "lep_eta": [0.3, 0.1, 0.4, 0.2],
            "lep_phi": [np.pi / 2, 0, -np.pi / 2, np.pi],
            "lep_e": [16000, 45000, 14000, 42000],
            "lep_charge": [1, 1, -1, -1],
            "lep_type": [13, 11, 13, 11],
            "eventNumber": 9,
            "channelNumber": 42,
        }

        normalized = normalize_leptons(event, "MeV")

        np.testing.assert_allclose(normalized.pt, [45.0, 42.0, 16.0, 14.0])
        np.testing.assert_allclose(normalized.eta, [0.1, 0.2, 0.3, 0.4])
        np.testing.assert_array_equal(normalized.charge, [1, -1, 1, -1])
        np.testing.assert_array_equal(normalized.flavour, [11, 11, 13, 13])

    def test_candidate_feature_builder_matches_legacy_wrapper(self):
        event = {
            "lep_pt": [45000, 42000, 16000, 14000],
            "lep_eta": [0, 0, 0, 0],
            "lep_phi": [0, np.pi, np.pi / 2, -np.pi / 2],
            "lep_e": [45000, 42000, 16000, 14000],
            "lep_charge": [1, -1, 1, -1],
            "lep_type": [11, 11, 13, 13],
            "eventNumber": 7,
            "channelNumber": 42,
        }
        candidate = reconstruct_candidate(normalize_leptons(event, "MeV"))
        self.assertIsNotNone(candidate)

        direct = build_candidate_features(event, candidate)
        legacy = build_event_features(event, "MeV")

        self.assertEqual(direct, legacy)


if __name__ == "__main__":
    unittest.main()
