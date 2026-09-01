import unittest

from src.split import event_split


class SplitTests(unittest.TestCase):
    def test_split_is_deterministic(self):
        self.assertEqual(event_split(12345, 100), event_split(12345, 100))

    def test_event_sets_do_not_overlap(self):
        groups = {"train": set(), "validation": set(), "test": set()}
        for event in range(1000):
            groups[event_split(event, 99)].add(event)
        self.assertFalse(groups["train"] & groups["validation"])
        self.assertFalse(groups["train"] & groups["test"])
        self.assertFalse(groups["validation"] & groups["test"])
        self.assertEqual(set.union(*groups.values()), set(range(1000)))


if __name__ == "__main__":
    unittest.main()

