#!/usr/bin/env python3
"""Core local SHAPE-MaP workflow.

This script can assemble reference FASTA fragments, demultiplex mixed FASTQ
files by short barcode/primer sequences, and launch ShapeMapper2 with the
generated sample folders.
"""

import argparse
import gzip
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


VALID_ROLES = {"modified", "untreated", "denatured"}


def normalize_seq(seq):
    return seq.strip().upper().replace("U", "T")


def revcomp(seq):
    table = str.maketrans("ACGTN", "TGCAN")
    return normalize_seq(seq).translate(table)[::-1]


def open_fastq(path, mode):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, mode + "t")
    return path.open(mode, encoding="utf-8", newline="")


def read_fastq(handle):
    while True:
        header = handle.readline()
        if not header:
            return
        seq = handle.readline()
        plus = handle.readline()
        qual = handle.readline()
        if not qual:
            raise ValueError("FASTQ ended in the middle of a record.")
        yield header, seq, plus, qual


def write_record(handle, record):
    handle.write("".join(record))


def read_fasta(path):
    records = []
    name = None
    seq_parts = []
    with Path(path).open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    records.append((name, normalize_seq("".join(seq_parts))))
                name = line[1:].split()[0]
                seq_parts = []
            else:
                seq_parts.append(line)
    if name is not None:
        records.append((name, normalize_seq("".join(seq_parts))))
    if not records:
        raise ValueError(f"No FASTA records found in {path}")
    return records


def write_fasta(path, name, seq, line_width=80):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f">{name}\n")
        for start in range(0, len(seq), line_width):
            handle.write(seq[start : start + line_width] + "\n")


def best_suffix_prefix_overlap(left, right, min_overlap, max_mismatches):
    max_overlap = min(len(left), len(right))
    for overlap in range(max_overlap, min_overlap - 1, -1):
        suffix = left[-overlap:]
        prefix = right[:overlap]
        mismatches = sum(1 for a, b in zip(suffix, prefix) if a != b)
        if mismatches <= max_mismatches:
            return overlap, mismatches
    return 0, None


def assemble_reference(config, config_dir):
    assembly = config.get("reference_assembly")
    if not assembly:
        return resolve_path(config["target"], config_dir)

    fragments_path = resolve_path(assembly["fragments_fasta"], config_dir)
    records = read_fasta(fragments_path)
    if assembly.get("order"):
        lookup = {name: seq for name, seq in records}
        missing = [name for name in assembly["order"] if name not in lookup]
        if missing:
            raise ValueError(f"Fragments listed in reference_assembly.order were not found: {missing}")
        records = [(name, lookup[name]) for name in assembly["order"]]

    min_overlap = int(assembly.get("min_overlap", 20))
    max_mismatches = int(assembly.get("max_mismatches", 0))
    allow_no_overlap = bool(assembly.get("allow_no_overlap", False))
    gap = normalize_seq(assembly.get("gap", "NNNNNNNNNN"))

    assembled_name, assembled_seq = records[0]
    summary = []
    for name, seq in records[1:]:
        overlap, mismatches = best_suffix_prefix_overlap(assembled_seq, seq, min_overlap, max_mismatches)
        if overlap == 0:
            if not allow_no_overlap:
                raise ValueError(
                    f"No overlap found between assembled sequence and fragment {name}. "
                    f"Lower min_overlap, provide the correct order, or set allow_no_overlap=true."
                )
            assembled_seq = assembled_seq + gap + seq
            summary.append({"fragment": name, "overlap": 0, "mismatches": None, "gap_inserted": len(gap)})
        else:
            assembled_seq = assembled_seq + seq[overlap:]
            summary.append({"fragment": name, "overlap": overlap, "mismatches": mismatches, "gap_inserted": 0})

    output_dir = resolve_path(config.get("output_dir", "results"), config_dir)
    output_fasta = resolve_path(assembly.get("output_fasta", str(output_dir / "assembled_target.fa")), config_dir)
    output_name = assembly.get("name", config.get("project_name", assembled_name))
    write_fasta(output_fasta, output_name, assembled_seq)

    summary_path = output_fasta.with_suffix(output_fasta.suffix + ".assembly_summary.json")
    summary_path.write_text(
        json.dumps(
            {
                "fragments_fasta": str(fragments_path),
                "output_fasta": str(output_fasta),
                "output_name": output_name,
                "assembled_length": len(assembled_seq),
                "steps": summary,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Reference assembly complete: {output_fasta}", flush=True)
    print(f"Reference assembly summary: {summary_path}", flush=True)
    return output_fasta


def mismatches_at(read_seq, primer, start):
    window = read_seq[start : start + len(primer)]
    if len(window) != len(primer):
        return None
    return sum(1 for a, b in zip(window, primer) if a != b)


def best_primer_hit(read_seq, primers, search_bases, max_mismatches, anchored):
    read_seq = normalize_seq(read_seq)
    best = None
    for primer in primers:
        if len(primer) == 0 or len(primer) > len(read_seq):
            continue
        last_start = 0 if anchored else min(search_bases, len(read_seq) - len(primer))
        for start in range(last_start + 1):
            mm = mismatches_at(read_seq, primer, start)
            if mm is None or mm > max_mismatches:
                continue
            hit = (mm, start, len(primer), primer)
            if best is None or hit[:3] < best[:3]:
                best = hit
    return best


@dataclass
class Sample:
    name: str
    role: str
    r1_primers: list
    r2_primers: list
    match_mode: str


def load_samples(config):
    demux = config.get("demux", {})
    check_rc = bool(demux.get("check_reverse_complement", False))
    samples = []
    for item in demux.get("samples", []):
        role = item.get("role", "").lower()
        if role not in VALID_ROLES:
            raise ValueError(f"Sample {item.get('name')} has invalid role: {role}")
        r1 = [normalize_seq(p) for p in item.get("r1_primers", [])]
        r2 = [normalize_seq(p) for p in item.get("r2_primers", [])]
        if check_rc:
            r1 = sorted(set(r1 + [revcomp(p) for p in r1]))
            r2 = sorted(set(r2 + [revcomp(p) for p in r2]))
        if not r1 and not r2:
            raise ValueError(f"Sample {item.get('name')} has no primers.")
        samples.append(
            Sample(
                name=item["name"],
                role=role,
                r1_primers=r1,
                r2_primers=r2,
                match_mode=item.get("match_mode", demux.get("match_mode", "any")).lower(),
            )
        )
    if not samples:
        raise ValueError("Config has no demux.samples entries.")
    return samples


def classify_record(r1_seq, r2_seq, samples, search_bases, max_mismatches, anchored):
    candidates = []
    for sample in samples:
        r1_hit = best_primer_hit(r1_seq, sample.r1_primers, search_bases, max_mismatches, anchored) if sample.r1_primers else None
        r2_hit = best_primer_hit(r2_seq, sample.r2_primers, search_bases, max_mismatches, anchored) if r2_seq and sample.r2_primers else None
        specified_sides = int(bool(sample.r1_primers)) + int(bool(sample.r2_primers))
        matched_sides = int(r1_hit is not None) + int(r2_hit is not None)
        if sample.match_mode == "all" and matched_sides != specified_sides:
            continue
        if sample.match_mode != "all" and matched_sides == 0:
            continue
        mismatches = (r1_hit[0] if r1_hit else 0) + (r2_hit[0] if r2_hit else 0)
        start_sum = (r1_hit[1] if r1_hit else 0) + (r2_hit[1] if r2_hit else 0)
        candidates.append(((mismatches, -matched_sides, start_sum), sample))
    if not candidates:
        return None, "unmatched"
    candidates.sort(key=lambda x: x[0])
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None, "ambiguous"
    return candidates[0][1], "matched"


def demultiplex(config, config_dir):
    input_cfg = config["input"]
    output_dir = resolve_path(config.get("output_dir", "results"), config_dir)
    demux_dir = output_dir / "demux"
    demux_dir.mkdir(parents=True, exist_ok=True)

    r1_path = resolve_path(input_cfg["r1"], config_dir)
    r2_path = resolve_path(input_cfg["r2"], config_dir) if input_cfg.get("r2") else None

    demux_cfg = config.get("demux", {})
    samples = load_samples(config)
    search_bases = int(demux_cfg.get("search_bases", 40))
    max_mismatches = int(demux_cfg.get("max_mismatches", 1))
    anchored = bool(demux_cfg.get("anchored", False))

    role_handles = {}
    for role in VALID_ROLES:
        role_dir = demux_dir / role
        role_dir.mkdir(exist_ok=True)
        if r2_path:
            role_handles[role] = (
                gzip.open(role_dir / f"{role}_R1.fastq.gz", "wt"),
                gzip.open(role_dir / f"{role}_R2.fastq.gz", "wt"),
            )
        else:
            role_handles[role] = (gzip.open(role_dir / f"{role}.fastq.gz", "wt"), None)

    counts = {
        "total": 0,
        "unmatched": 0,
        "ambiguous": 0,
        "samples": {sample.name: 0 for sample in samples},
        "roles": {role: 0 for role in VALID_ROLES},
    }

    with open_fastq(r1_path, "r") as r1_handle:
        if r2_path:
            r2_handle = open_fastq(r2_path, "r")
        else:
            r2_handle = None
        try:
            r2_iter = read_fastq(r2_handle) if r2_handle else None
            for r1_record in read_fastq(r1_handle):
                r2_record = next(r2_iter) if r2_iter else None
                counts["total"] += 1
                sample, status = classify_record(
                    r1_record[1],
                    r2_record[1] if r2_record else "",
                    samples,
                    search_bases,
                    max_mismatches,
                    anchored,
                )
                if status != "matched":
                    counts[status] += 1
                    continue
                counts["samples"][sample.name] += 1
                counts["roles"][sample.role] += 1
                out1, out2 = role_handles[sample.role]
                write_record(out1, r1_record)
                if r2_record:
                    write_record(out2, r2_record)
        finally:
            if r2_handle:
                r2_handle.close()
            for out1, out2 in role_handles.values():
                out1.close()
                if out2:
                    out2.close()

    summary_path = demux_dir / "demux_summary.json"
    summary_path.write_text(json.dumps(counts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Demux complete: {summary_path}", flush=True)
    print(json.dumps(counts, indent=2, ensure_ascii=False), flush=True)
    return demux_dir, counts


def resolve_path(value, config_dir):
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (config_dir / path).resolve()


def run_shapemapper(config, config_dir, demux_dir, target):
    sm_cfg = config.get("shapemapper", {})
    shapemapper = Path(sm_cfg.get("executable", "~/tools/shapemapper2-2.3/shapemapper")).expanduser()
    output_dir = resolve_path(config.get("output_dir", "results"), config_dir)
    shape_out = output_dir / "shapemapper"
    temp_dir = Path(sm_cfg.get("temp_dir", f"~/shape_map_runs/{config['project_name']}/temp")).expanduser()
    temp_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(shapemapper),
        "--name",
        config["project_name"],
        "--target",
        str(target),
        "--out",
        str(shape_out),
        "--temp",
        str(temp_dir),
        "--overwrite",
        "--nproc",
        str(sm_cfg.get("nproc", 4)),
        "--min-depth",
        str(sm_cfg.get("min_depth", 1000)),
        "--min-mapq",
        str(sm_cfg.get("min_mapq", 10)),
        "--min-qual-to-trim",
        str(sm_cfg.get("min_qual_to_trim", 20)),
        "--window-to-trim",
        str(sm_cfg.get("window_to_trim", 5)),
        "--min-qual-to-count",
        str(sm_cfg.get("min_qual_to_count", 30)),
        "--max-bg",
        str(sm_cfg.get("max_bg", 0.05)),
    ]

    if sm_cfg.get("amplicon", True):
        cmd.append("--amplicon")
    if sm_cfg.get("primers_file"):
        primers_file = resolve_path(sm_cfg["primers_file"], config_dir)
        cmd.extend(["--primers", str(primers_file)])
    if sm_cfg.get("random_primer_len", 0):
        cmd.extend(["--random-primer-len", str(sm_cfg["random_primer_len"])])
    if sm_cfg.get("max_paired_fragment_length"):
        cmd.extend(["--max-paired-fragment-length", str(sm_cfg["max_paired_fragment_length"])])
    if sm_cfg.get("indiv_norm", False):
        cmd.append("--indiv-norm")
    if sm_cfg.get("star_aligner", False):
        cmd.append("--star-aligner")
    if sm_cfg.get("extra_args"):
        cmd.extend([str(x) for x in sm_cfg["extra_args"]])

    summary_path = demux_dir / "demux_summary.json"
    demux_counts = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {"roles": {}}
    included_roles = []
    for role, flag in [("modified", "--modified"), ("untreated", "--untreated"), ("denatured", "--denatured")]:
        role_dir = demux_dir / role
        if int(demux_counts.get("roles", {}).get(role, 0)) > 0:
            cmd.extend([flag, "--folder", str(role_dir)])
            included_roles.append(role)

    if "modified" not in included_roles or "untreated" not in included_roles:
        raise ValueError(
            "Demultiplexing did not produce enough reads for ShapeMapper2. "
            f"Included roles: {included_roles}. At minimum, modified and untreated need non-zero reads. "
            "Check barcode sequences, read direction, anchored setting, and search_bases."
        )

    print("Running ShapeMapper2:", flush=True)
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(Path.home()))
    print(f"ShapeMapper2 complete: {shape_out}", flush=True)


def write_run_summary(config, target, status, message, demux_counts=None, shapemapper_out=None):
    output_dir = resolve_path(config.get("output_dir", "results"), Path.cwd())
    summary = {
        "project_name": config.get("project_name"),
        "status": status,
        "message": message,
        "target": str(target) if target else None,
        "output_dir": str(output_dir),
        "demux": demux_counts,
        "shapemapper_out": str(shapemapper_out) if shapemapper_out else None,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Run summary: {summary_path}", flush=True)
    return summary_path


def main():
    parser = argparse.ArgumentParser(description="Demultiplex mixed SHAPE-MaP FASTQ files and run ShapeMapper2.")
    parser.add_argument("config", help="Project JSON config.")
    parser.add_argument("--assemble-only", action="store_true", help="Only assemble reference fragments; do not split FASTQ files or run ShapeMapper2.")
    parser.add_argument("--demux-only", action="store_true", help="Only split FASTQ files; do not run ShapeMapper2.")
    parser.add_argument("--skip-demux", action="store_true", help="Use an existing output_dir/demux folder.")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    config_dir = config_path.parent
    config = json.loads(config_path.read_text(encoding="utf-8"))
    target = assemble_reference(config, config_dir)
    if args.assemble_only:
        print(f"Assembled target ready: {target}", flush=True)
        write_run_summary(config, target, "complete", "Reference assembly completed.")
        return

    if args.skip_demux:
        demux_dir = resolve_path(config.get("output_dir", "results"), config_dir) / "demux"
        demux_counts = json.loads((demux_dir / "demux_summary.json").read_text(encoding="utf-8")) if (demux_dir / "demux_summary.json").exists() else None
    else:
        demux_dir, demux_counts = demultiplex(config, config_dir)

    if not args.demux_only:
        run_shapemapper(config, config_dir, demux_dir, target)
        write_run_summary(
            config,
            target,
            "complete",
            "Demultiplexing and ShapeMapper2 analysis completed.",
            demux_counts=demux_counts,
            shapemapper_out=resolve_path(config.get("output_dir", "results"), config_dir) / "shapemapper",
        )
    else:
        write_run_summary(config, target, "complete", "Demultiplexing completed.", demux_counts=demux_counts)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
