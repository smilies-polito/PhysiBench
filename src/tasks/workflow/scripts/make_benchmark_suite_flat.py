import argparse
import json
import os
import shutil

"""
Creates a slightly different structure for the benchmark suite,
where models are distributed in subdirectories named after the original reference model.
"""


def load_manifest(src_root_dir):
    manifest_path = os.path.join(src_root_dir, "variant_models_manifest.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Missing file: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Manifest must be a list of entries")
    return data


def copy_model_files(src_dir, dest_family_dir, model_name):
    for ext in ("bnd", "cfg"):
        src_path = os.path.join(src_dir, f"model.{ext}")
        if not os.path.isfile(src_path):
            raise FileNotFoundError(f"Missing file: {src_path}")
        dest_path = os.path.join(dest_family_dir, f"{model_name}.{ext}")
        shutil.copy2(src_path, dest_path)


def copy_manifest(src_root_dir, dest_root_dir):
    src_manifest = os.path.join(src_root_dir, "variant_models_manifest.json")
    if not os.path.isfile(src_manifest):
        raise FileNotFoundError(f"Missing file: {src_manifest}")
    dest_manifest = os.path.join(dest_root_dir, "manifest.json")
    if not os.path.exists(dest_manifest):
        shutil.copy2(src_manifest, dest_manifest)


def build_flat_suite(benchmark_suite, flat_benchmark_suite):
    if not os.path.isdir(benchmark_suite):
        raise NotADirectoryError(f"Not a directory: {benchmark_suite}")

    os.makedirs(flat_benchmark_suite, exist_ok=True)

    manifest_entries = load_manifest(benchmark_suite)
    if manifest_entries:
        copy_manifest(benchmark_suite, flat_benchmark_suite)

    for entry in manifest_entries:
        family = entry.get("reference_model")
        model = entry.get("variant_ID")
        model_id = entry.get("model_ID")
        if not family or not model or model_id is None:
            raise ValueError(f"Invalid manifest entry: {entry}")

        src_dir_name = f"{family}_{model}_{model_id}"
        src_dir = os.path.join(benchmark_suite, src_dir_name)
        if not os.path.isdir(src_dir):
            raise FileNotFoundError(f"Missing model directory: {src_dir}")

        dest_family_dir = os.path.join(flat_benchmark_suite, family)
        os.makedirs(dest_family_dir, exist_ok=True)

        copy_model_files(src_dir, dest_family_dir, model)


def main():
    parser = argparse.ArgumentParser(
        description="Create a flattened benchmark suite organized by family."
    )
    parser.add_argument("benchmark_suite", help="Path to the original benchmark suite")
    parser.add_argument(
        "flat_benchmark_suite", help="Path to the flattened benchmark suite"
    )
    args = parser.parse_args()

    build_flat_suite(args.benchmark_suite, args.flat_benchmark_suite)


if __name__ == "__main__":
    main()

