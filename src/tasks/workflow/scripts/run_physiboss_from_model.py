import argparse
import json
import os
import sys
from pathlib import Path

from initial_positions import InitialPosition
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters
from physiboss import LocalPhysiboss


def run(base_path: Path, family: str, name: str, output_dir: Path, protocol: Protocols):
    cfg_path = base_path / family / f"{name}.cfg"
    bnd_path = base_path / family / f"{name}.bnd"
    
    if not cfg_path.exists():
        sys.exit(f"Error: .cfg file not found at {cfg_path}")
    if not bnd_path.exists():
        sys.exit(f"Error: .bnd file not found at {bnd_path}")
    
    model = ModelParameters(
        boolean_family=family,
        boolean_model=name
    )
    sim_params = SimulationParameters.get_test_defaults()
    base_path_str = str(base_path)

    physiboss_output_dir = LocalPhysiboss.run_local(model, protocol, sim_params, base_path_str)
    os.system(f"cp -r {physiboss_output_dir}/* {output_dir}")

def main():
    parser = argparse.ArgumentParser(
        description="Run Physiboss from a specified model."
    )

    parser.add_argument(
        "--base-models-dir",
        required=True,
        type=Path,
        help="Path to the base models directory. Must exist."
    )
    
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Path to the output directory. Created if it doesn't exist."
    )
    
    parser.add_argument(
        "--override-output",
        action="store_true",
        help="Override the output directory if it already exists."
    )

    parser.add_argument(
        "--manifest-id",
        type=int,
        help="Numeric ID for the manifest."
    )
    
    parser.add_argument(
        "--model-family",
        type=str,
        help="Model family string."
    )
    
    parser.add_argument(
        "--model-name",
        type=str,
        help="Model name string."
    )

    # Protocols arguments
    parser.add_argument("--treatment-duration", type=float, required=True, help="Treatment duration (0-1)")
    parser.add_argument("--treatment-period", type=float, required=True, help="Treatment period (0-0.5)")
    parser.add_argument("--xmin", type=float, required=True, help="xmin (0-10)")
    parser.add_argument("--xmax", type=float, required=True, help="xmax (0-10)")
    parser.add_argument("--ymin", type=float, required=True, help="ymin (0-10)")
    parser.add_argument("--ymax", type=float, required=True, help="ymax (0-10)")

    # InitialPosition arguments
    parser.add_argument("--ip-type", type=str, required=True, choices=["circle", "square"], help="Initial position type ('circle' or 'square')")
    parser.add_argument("--ip-center-x", type=float, required=True, help="Initial position center X coordinate")
    parser.add_argument("--ip-center-y", type=float, required=True, help="Initial position center Y coordinate")
    parser.add_argument("--ip-density", type=float, default=0.1, help="Initial position density (0-1)")
    parser.add_argument("--ip-cell-type", type=str, default="default", help="Initial position cell type")
    parser.add_argument("--ip-mode", type=str, default="sparse", choices=["sparse", "dense", "contour"], help="Initial position mode")
    parser.add_argument("--ip-length", type=float, default=0.0, help="Initial position length (radius for circle, half-side for square)")

    args = parser.parse_args()

    # 1. Validate that base-models-dir exists
    if not args.base_models_dir.exists():
        sys.exit(f"Error: The base models directory '{args.base_models_dir}' does not exist.")

    if not args.base_models_dir.is_dir():
        sys.exit(f"Error: '{args.base_models_dir}' is not a directory.")

    # 2. Validate output-dir
    if args.output_dir.exists():
        if not args.override_output:
            sys.exit(f"Error: The output directory '{args.output_dir}' already exists. Use --override-output to bypass.")
    
    # Create the output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Validate mutually exclusive arguments: manifest-id OR (model-family AND model-name)
    has_manifest = args.manifest_id is not None
    has_family = args.model_family is not None
    has_name = args.model_name is not None

    if has_manifest:
        if has_family or has_name:
            sys.exit("Error: --manifest-id cannot be provided with --model-family or --model-name.")
        
        manifest_path = args.base_models_dir / "manifest.json"
        if not manifest_path.exists():
            sys.exit(f"Error: Manifest file not found at {manifest_path}")
            
        with open(manifest_path, 'r') as f:
            manifest_data = json.load(f)
            
        entry = next((item for item in manifest_data if item.get("model_ID") == args.manifest_id), None)
        if entry is None:
            sys.exit(f"Error: Manifest entry with ID {args.manifest_id} not found.")
            
        family = entry["reference_model"]
        name = entry["variant_ID"]
    else:
        if not has_family or not has_name:
            sys.exit("Error: Must provide either --manifest-id OR both --model-family and --model-name.")
        family = args.model_family
        name = args.model_name

    initial_pos = InitialPosition(
        type=args.ip_type,
        center=(args.ip_center_x, args.ip_center_y),
        density=args.ip_density,
        cell_type=args.ip_cell_type,
        mode=args.ip_mode,
        length=args.ip_length
    )

    protocol = Protocols(
        treatment_duration=args.treatment_duration,
        treatment_period=args.treatment_period,
        xmin=args.xmin,
        xmax=args.xmax,
        ymin=args.ymin,
        ymax=args.ymax,
        initial_positions=initial_pos
    )

    run(args.base_models_dir, family, name, args.output_dir, protocol)


if __name__ == "__main__":
    main()
