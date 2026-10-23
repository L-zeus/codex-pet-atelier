"""Synthetic component metadata only; not character or motion acceptance."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from extract_companion_frames import pair_companions


def component(area, x, width=20, height=20):
    return {'area': area, 'center_x': x, 'bbox': (x-width/2, 0, x+width/2, height)}


class CompanionTests(unittest.TestCase):
    def test_rank_pairing_preserves_cloud_that_is_nearer_next_body(self):
        bodies = [component(40000, 100, 250, 350), component(41000, 360, 260, 350)]
        clouds = [component(900, 245, 36, 32), component(910, 510, 36, 32)]
        groups, noise = pair_companions(bodies+clouds+[component(30, 180)], 2)
        self.assertEqual([group[1]['center_x'] for group in groups], [245, 510])
        self.assertEqual(len(noise), 1)
        self.assertEqual(groups[0][0]['center_x'], 100)

    def test_missing_or_ambiguous_companions_fail(self):
        bodies = [component(40000, 100), component(40000, 400)]
        with self.assertRaisesRegex(ValueError, 'separate body'):
            pair_companions(bodies+[component(900, 200)], 2)
        with self.assertRaisesRegex(ValueError, 'substantial component'):
            pair_companions(bodies+[component(900, 200), component(900, 500), component(500, 600)], 2)


if __name__ == '__main__':
    unittest.main()
