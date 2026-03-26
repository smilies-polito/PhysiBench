#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Generate a manifest.json from simulation folders stored under /mnt."
    )
    parser.add_argument(
        "--mnt-root",
        default="/mnt",
        help="Root directory containing one folder per model.",
    )
    parser.add_argument(
        "--output",
        default=str(here / "multiscale_simulations_manifest.json"),
        help="Output manifest path.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def simulation_id_from_path(path: Path) -> int:
    prefix = "input_parameters_"
    suffix = ".json"
    name = path.name
    if not name.startswith(prefix) or not name.endswith(suffix):
        raise ValueError(f"Unexpected input parameters filename: {name}")
    return int(name[len(prefix):-len(suffix)])


def parse_model_key(model_key: str) -> Tuple[str, str, Optional[str]]:
    parts = model_key.split("_")
    if len(parts) < 2:
        raise ValueError(f"Invalid model key format: {model_key}")
    if parts[-1].startswith("V"):
        return "_".join(parts[:-1]), parts[-1], None
    if len(parts) < 3 or not parts[-2].startswith("V"):
        raise ValueError(f"Invalid model key format: {model_key}")
    return "_".join(parts[:-2]), parts[-2], parts[-1]


def build_manifest(
    mnt_root: Path,
) -> List[Dict[str, Any]]:
    if not mnt_root.exists():
        raise FileNotFoundError(f"Mount root does not exist: {mnt_root}")

    manifest: List[Dict[str, Any]] = []

    for model_dir in sorted(path for path in mnt_root.iterdir() if path.is_dir()):
        input_dir = model_dir / "data" / "input_parameters"
        if not input_dir.is_dir():
            continue

        reference_model, variant_id, model_id = parse_model_key(model_dir.name)

        for input_path in sorted(input_dir.glob("input_parameters_*.json")):
            simulation_id = simulation_id_from_path(input_path)
            # Validate file content is readable, but do not store it in the manifest.
            load_json(input_path)

            manifest.append(
                {
                    "reference_model": reference_model,
                    "variant_ID": variant_id,
                    "model_ID": model_id,
                    "simulation_ID": simulation_id,
                }
            )

    manifest.sort(
        key=lambda entry: (
            entry["reference_model"],
            entry["variant_ID"],
            "" if entry["model_ID"] is None else entry["model_ID"],
            entry["simulation_ID"],
        )
    )
    return manifest


def main() -> int:
    args = parse_args()

    manifest = build_manifest(
        mnt_root=Path(args.mnt_root).resolve(),
    )

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")

    print(f"Wrote {len(manifest)} manifest entries to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
