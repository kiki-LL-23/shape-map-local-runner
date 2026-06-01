import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import shape_map_local


class SequenceUtilityTests(unittest.TestCase):
    def test_normalize_seq_replaces_u_with_t(self):
        self.assertEqual(shape_map_local.normalize_seq("acguu"), "ACGTT")

    def test_revcomp(self):
        self.assertEqual(shape_map_local.revcomp("ACGTN"), "NACGT")

    def test_best_primer_hit_exact_at_start(self):
        hit = shape_map_local.best_primer_hit("TAGCTTGTAAAA", ["TAGCTTGT"], 10, 0, True)
        self.assertEqual(hit[:3], (0, 0, 8))

    def test_best_primer_hit_allows_offset_when_unanchored(self):
        hit = shape_map_local.best_primer_hit("NNNTAGCTTGTAAAA", ["TAGCTTGT"], 12, 0, False)
        self.assertEqual(hit[:3], (0, 3, 8))

    def test_best_suffix_prefix_overlap(self):
        overlap, mismatches = shape_map_local.best_suffix_prefix_overlap(
            "AAACCCGGGTTT", "GGGTTTAAAA", min_overlap=6, max_mismatches=0
        )
        self.assertEqual(overlap, 6)
        self.assertEqual(mismatches, 0)


class FastaTests(unittest.TestCase):
    def test_read_and_write_fasta(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.fa"
            shape_map_local.write_fasta(path, "target", "ACGT" * 30, line_width=10)
            records = shape_map_local.read_fasta(path)
        self.assertEqual(records, [("target", "ACGT" * 30)])


if __name__ == "__main__":
    unittest.main()
