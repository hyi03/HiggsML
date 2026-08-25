import math
import unittest

from src.angular5 import ANGULAR5_FEATURES, build_angular5, lorentz_boost
from src.pairing import FourVector, Lepton, PairingResult, sum_vectors
from src.reconstruction import FourLeptonCandidate, NormalizedLeptons, normalize_leptons, reconstruct_candidate


def _candidate(leptons):
    pairing = PairingResult(True, (0, 1), (2, 3))
    z1 = sum_vectors([leptons[0].vector, leptons[1].vector])
    z2 = sum_vectors([leptons[2].vector, leptons[3].vector])
    return FourLeptonCandidate(
        normalized=NormalizedLeptons([], [], [], [], [], []),
        leptons=tuple(leptons),
        pairing=pairing,
        z1=z1,
        z2=z2,
        four_lepton=z1 + z2,
        all_sfos_masses=(),
    )


def _reference_candidate():
    """X-rest-frame event with orthogonal decay planes and unambiguous charges."""
    return _candidate(
        [
            Lepton(FourVector(2.0, 1.0, 0.0, 1.0), -1, 11),
            Lepton(FourVector(2.0, 1.0, 0.0, -1.0), 1, 11),
            Lepton(FourVector(2.0, -1.0, 1.0, 0.0), -1, 13),
            Lepton(FourVector(2.0, -1.0, -1.0, 0.0), 1, 13),
        ]
    )


class Angular5Tests(unittest.TestCase):
    def test_feature_order_is_the_frozen_five_observables(self):
        self.assertEqual(
            ANGULAR5_FEATURES,
            (
                "cos_theta_star",
                "cos_theta_1",
                "cos_theta_2",
                "phi_decay_planes",
                "phi_production_plane",
            ),
        )

    def test_rest_frame_boost_has_hand_derived_energy_and_momentum(self):
        boosted = lorentz_boost(FourVector(10.0, 0.0, 0.0, 0.0), (0.6, 0.0, 0.0))

        self.assertAlmostEqual(boosted.energy, 12.5)
        self.assertAlmostEqual(boosted.px, -7.5)
        self.assertAlmostEqual(boosted.py, 0.0)
        self.assertAlmostEqual(boosted.pz, 0.0)

    def test_inverse_common_longitudinal_boost_restores_the_vector(self):
        vector = FourVector(10.0, 3.0, 4.0, 5.0)

        restored = lorentz_boost(lorentz_boost(vector, (0.0, 0.0, 0.25)), (0.0, 0.0, -0.25))

        self.assertAlmostEqual(restored.energy, vector.energy)
        self.assertAlmostEqual(restored.px, vector.px)
        self.assertAlmostEqual(restored.py, vector.py)
        self.assertAlmostEqual(restored.pz, vector.pz)

    def test_reference_geometry_has_hand_derived_cosines_and_signed_plane_angle(self):
        angles = build_angular5(_reference_candidate())

        self.assertAlmostEqual(angles["cos_theta_star"], 0.0)
        self.assertAlmostEqual(angles["cos_theta_1"], 0.0)
        self.assertAlmostEqual(angles["cos_theta_2"], 0.0)
        self.assertAlmostEqual(angles["phi_decay_planes"], math.pi / 2)
        self.assertAlmostEqual(angles["phi_production_plane"], 0.0)

    def test_observables_stay_in_their_declared_ranges(self):
        angles = build_angular5(_reference_candidate())

        for name in ANGULAR5_FEATURES[:3]:
            self.assertGreaterEqual(angles[name], -1.0)
            self.assertLessEqual(angles[name], 1.0)
        for name in ANGULAR5_FEATURES[3:]:
            self.assertGreaterEqual(angles[name], -math.pi)
            self.assertLess(angles[name], math.pi)

    def test_positive_pi_from_collinear_plane_normals_is_represented_as_negative_pi(self):
        candidate = _candidate(
            [
                Lepton(FourVector(2.0, 1.0, 0.0, -1.0), -1, 11),
                Lepton(FourVector(2.0, 1.0, 0.0, 1.0), 1, 11),
                Lepton(FourVector(2.0, -1.0, 0.0, -1.0), -1, 13),
                Lepton(FourVector(2.0, -1.0, 0.0, 1.0), 1, 13),
            ]
        )

        angles = build_angular5(candidate)

        self.assertEqual(angles["phi_decay_planes"], -math.pi)
        self.assertEqual(angles["phi_production_plane"], -math.pi)

    def test_charge_orientation_selects_negative_leptons_and_fixes_plane_sign(self):
        candidate = _reference_candidate()
        swapped_z1_charges = _candidate(
            [
                Lepton(candidate.leptons[0].vector, 1, 11),
                Lepton(candidate.leptons[1].vector, -1, 11),
                candidate.leptons[2],
                candidate.leptons[3],
            ]
        )

        self.assertAlmostEqual(build_angular5(candidate)["phi_decay_planes"], math.pi / 2)
        self.assertAlmostEqual(build_angular5(swapped_z1_charges)["phi_decay_planes"], -math.pi / 2)

    def test_input_permutation_cannot_change_reconstructed_angles(self):
        vectors = [
            (1.0, math.asinh(1.0), 0.0, 50.0, -1, 11),
            (1.0, -math.asinh(1.0), 0.0, 50.0, 1, 11),
            (math.sqrt(2.0), 0.0, 3 * math.pi / 4, 20.0, -1, 13),
            (math.sqrt(2.0), 0.0, -3 * math.pi / 4, 20.0, 1, 13),
        ]

        def reconstruct(rows):
            event = {
                "lep_pt": [row[0] for row in rows],
                "lep_eta": [row[1] for row in rows],
                "lep_phi": [row[2] for row in rows],
                "lep_e": [row[3] for row in rows],
                "lep_charge": [row[4] for row in rows],
                "lep_type": [row[5] for row in rows],
            }
            candidate = reconstruct_candidate(normalize_leptons(event, "GeV"))
            self.assertIsNotNone(candidate)
            return build_angular5(candidate)

        self.assertEqual(reconstruct(vectors), reconstruct(list(reversed(vectors))))

    def test_nonfinite_vector_is_rejected_instead_of_producing_an_angle(self):
        candidate = _reference_candidate()
        invalid = _candidate(
            [
                Lepton(FourVector(math.nan, 1.0, 0.0, 1.0), -1, 11),
                *candidate.leptons[1:],
            ]
        )

        with self.assertRaisesRegex(ValueError, "finite"):
            build_angular5(invalid)

    def test_light_speed_or_nonfinite_boost_is_rejected(self):
        vector = FourVector(1.0, 0.0, 0.0, 0.0)

        with self.assertRaisesRegex(ValueError, "beta"):
            lorentz_boost(vector, (1.0, 0.0, 0.0))
        with self.assertRaisesRegex(ValueError, "finite"):
            lorentz_boost(vector, (math.nan, 0.0, 0.0))

    def test_pair_without_one_negative_and_one_positive_lepton_is_rejected(self):
        candidate = _reference_candidate()
        invalid = _candidate(
            [
                Lepton(candidate.leptons[0].vector, 1, 11),
                candidate.leptons[1],
                candidate.leptons[2],
                candidate.leptons[3],
            ]
        )

        with self.assertRaisesRegex(ValueError, "charges"):
            build_angular5(invalid)

    def test_zero_helicity_axis_is_rejected(self):
        at_rest = _candidate(
            [
                Lepton(FourVector(1.0, 0.0, 0.0, 0.0), -1, 11),
                Lepton(FourVector(1.0, 0.0, 0.0, 0.0), 1, 11),
                Lepton(FourVector(1.0, 0.0, 0.0, 0.0), -1, 13),
                Lepton(FourVector(1.0, 0.0, 0.0, 0.0), 1, 13),
            ]
        )

        with self.assertRaisesRegex(ValueError, "zero"):
            build_angular5(at_rest)

    def test_collinear_decay_plane_is_rejected(self):
        degenerate = _candidate(
            [
                Lepton(FourVector(2.0, 1.0, 0.0, 0.0), -1, 11),
                Lepton(FourVector(2.0, 1.0, 0.0, 0.0), 1, 11),
                Lepton(FourVector(2.0, -1.0, 1.0, 0.0), -1, 13),
                Lepton(FourVector(2.0, -1.0, -1.0, 0.0), 1, 13),
            ]
        )

        with self.assertRaisesRegex(ValueError, "zero"):
            build_angular5(degenerate)


if __name__ == "__main__":
    unittest.main()
