import sys
import tempfile
import unittest
import gzip
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


class DemultiplexTests(unittest.TestCase):
    def write_fastq(self, path, records):
        with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
            for index, seq in enumerate(records, start=1):
                handle.write(f"@read{index}\n{seq}\n+\n{'I' * len(seq)}\n")

    def count_gz_fastq(self, path):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return sum(1 for _line in handle) // 4

    def test_demultiplex_supports_multiple_sample_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            r1 = tmp_path / "mixed_R1.fastq"
            self.write_fastq(
                r1,
                [
                    "TAGAAAAAA",
                    "ATCAAAAAA",
                    "GGGAAAAAA",
                    "CCCAAAAAA",
                    "TTTAAAAAA",
                ],
            )
            config = {
                "output_dir": str(tmp_path / "out"),
                "input": {"r1": str(r1)},
                "demux": {
                    "search_bases": 3,
                    "max_mismatches": 0,
                    "anchored": True,
                    "samples": [
                        {"group": "RNA1", "name": "rna1_plus", "role": "modified", "r1_primers": ["TAG"]},
                        {"group": "RNA1", "name": "rna1_minus", "role": "untreated", "r1_primers": ["ATC"]},
                        {"group": "RNA2", "name": "rna2_plus", "role": "modified", "r1_primers": ["GGG"]},
                        {"group": "RNA2", "name": "rna2_minus", "role": "untreated", "r1_primers": ["CCC"]},
                    ],
                },
            }

            demux_dir, counts = shape_map_local.demultiplex(config, tmp_path)

            self.assertEqual(counts["layout"], "grouped")
            self.assertEqual(counts["unmatched"], 1)
            self.assertEqual(counts["groups"]["RNA1"]["roles"]["modified"], 1)
            self.assertEqual(counts["groups"]["RNA1"]["roles"]["untreated"], 1)
            self.assertEqual(counts["groups"]["RNA2"]["roles"]["modified"], 1)
            self.assertEqual(counts["groups"]["RNA2"]["roles"]["untreated"], 1)
            self.assertEqual(self.count_gz_fastq(demux_dir / "RNA1" / "modified" / "modified.fastq.gz"), 1)
            self.assertEqual(self.count_gz_fastq(demux_dir / "RNA2" / "untreated" / "untreated.fastq.gz"), 1)


if __name__ == "__main__":
    unittest.main()
