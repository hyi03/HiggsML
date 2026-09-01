import math
import unittest

from src.pairing import (
    FourVector,
    Lepton,
    all_sfos_pair_masses,
    delta_phi,
    invariant_mass,
    is_sfos,
    pair_four_leptons,
)


def at_rest(mass):
    return FourVector(mass, 0.0, 0.0, 0.0)


class PairingTests(unittest.TestCase):
    def test_rest_mass(self):
        self.assertAlmostEqual(at_rest(12.5).mass, 12.5)

    def test_combination_mass(self):
        first = FourVector(50, 30, 0, 0)
        second = FourVector(50, -30, 0, 0)
        self.assertAlmostEqual(invariant_mass([first, second]), 100.0)

    def test_sfos(self):
        electron_plus = Lepton(at_rest(10), 1, 11)
        electron_minus = Lepton(at_rest(10), -1, -11)
        muon_minus = Lepton(at_rest(10), -1, 13)
        self.assertTrue(is_sfos(electron_plus, electron_minus))
        self.assertFalse(is_sfos(electron_plus, muon_minus))

    def test_z1_is_closest_to_z_mass(self):
        leptons = [
            Lepton(at_rest(46), 1, 11),
            Lepton(at_rest(45), -1, 11),
            Lepton(at_rest(16), 1, 13),
            Lepton(at_rest(14), -1, 13),
        ]
        result = pair_four_leptons(leptons)
        self.assertTrue(result.valid)
        self.assertEqual(result.z1_indices, (0, 1))
        self.assertEqual(result.z2_indices, (2, 3))

    def test_no_valid_pairing_has_explicit_state(self):
        leptons = [Lepton(at_rest(10), 1, 11) for _ in range(4)]
        result = pair_four_leptons(leptons)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "no two-SFOS pairing")

    def test_all_sfos_pair_masses_include_alternative_pairs(self):
        leptons = [
            Lepton(at_rest(46), 1, 11),
            Lepton(at_rest(45), -1, 11),
            Lepton(at_rest(16), 1, 11),
            Lepton(at_rest(14), -1, 11),
        ]
        self.assertEqual(all_sfos_pair_masses(leptons), (91.0, 60.0, 61.0, 30.0))

    def test_all_sfos_pair_masses_empty_without_sfos_pair(self):
        leptons = [Lepton(at_rest(10), 1, 11) for _ in range(4)]
        self.assertEqual(all_sfos_pair_masses(leptons), ())

    def test_delta_phi_wraps_boundary(self):
        value = delta_phi(-math.pi + 0.1, math.pi - 0.1)
        self.assertAlmostEqual(value, 0.2)


if __name__ == "__main__":
    unittest.main()
