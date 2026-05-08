#!/usr/bin/env python3
import os
import sys
import json
import gzip
import argparse
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple

# opzionale ma utile per robustezza
try:
    import pandas as pd  # noqa: F401
except Exception:
    pass

# pctk per leggere MultiCellDS
from pctk import multicellds


def _format_time_key(t: float) -> str:
    if abs(t - round(t)) < 1e-9:
        return str(int(round(t)))
    return f"{t:.6f}".rstrip("0").rstrip(".")


def _parse_settings(settings_xml: str) -> Tuple[Optional[float], Optional[float], Dict[str, Any]]:
    """
    Estrae da PhysiCell_settings.xml:
      - max_time (float)
      - save interval (float)
      - dizionario input_parameters con i path reali
    """
    if not os.path.isfile(settings_xml):
        return None, None, {}

    tree = ET.parse(settings_xml)
    root = tree.getroot()

    # max_time
    max_time = None
    mt = root.find(".//max_time")
    if mt is not None and mt.text:
        try:
            max_time = float(mt.text.strip())
        except Exception:
            pass

    # interval
    interval = None
    for xp in (".//save/full_data/interval", ".//full_data/interval"):
        node = root.find(xp)
        if node is not None and node.text:
            try:
                interval = float(node.text.strip())
                break
            except Exception:
                continue

    # parametri che salviamo (assoluti)
    def _get_text(p: str) -> Optional[str]:
        n = root.find(p)
        return n.text.strip() if (n is not None and n.text is not None) else None

    as_float = lambda x: (float(x) if x is not None else None)

    params = {
        "treatment_period":   {"value": as_float(_get_text(".//treatment_period")),   "path": "user_parameters/treatment_period"},
        "treatment_duration": {"value": as_float(_get_text(".//treatment_duration")), "path": "user_parameters/treatment_duration"},
        "TNF_dirichlet_xmin": {"value": as_float(_get_text(".//Dirichlet_options/boundary_value[@ID='xmin']")), "path": "user_parameters/TNF_dirichlet_xmin"},
        "TNF_dirichlet_xmax": {"value": as_float(_get_text(".//Dirichlet_options/boundary_value[@ID='xmax']")), "path": "user_parameters/TNF_dirichlet_xmax"},
        "TNF_dirichlet_ymin": {"value": as_float(_get_text(".//Dirichlet_options/boundary_value[@ID='ymin']")), "path": "user_parameters/TNF_dirichlet_ymin"},
        "TNF_dirichlet_ymax": {"value": as_float(_get_text(".//Dirichlet_options/boundary_value[@ID='ymax']")), "path": "user_parameters/TNF_dirichlet_ymax"},
    }
    if interval is not None:
        params["save_time"] = {"value": interval, "path": "save/full_data/interval"}

    return max_time, interval, params


def _cell_data_to_json_gz(out_basename_no_ext: str, sim_output_folder: str,
                          max_time: Optional[float], interval: Optional[float]) -> bool:
    """
    Converte l'output MultiCellDS in JSON compresso, con eventuale padding.
    Scrive <out_basename_no_ext>.json.gz
    """
    if not os.path.isdir(sim_output_folder):
        return False

    reader = multicellds.MultiCellDS(output_folder=sim_output_folder)
    df_iter = reader.cells_as_frames_iterator()

    data_dict: Dict[str, Dict[str, list]] = {}
    for (t, df) in df_iter:
        # colonne minime
        for col in ("x_position", "y_position", "z_position", "current_phase"):
            if col not in df.columns:
                df[col] = None

        # mappature fasi (come da tua pipeline)
        df = df.copy()
        df["current_phase"] = df["current_phase"].astype(str)
        df.loc[df.current_phase == "14.0",  "current_phase"] = "alive"
        df.loc[df.current_phase == "102.0", "current_phase"] = "alive"
        df.loc[df.current_phase == "100.0", "current_phase"] = "apoptotic"
        df.loc[df.current_phase == "101.0", "current_phase"] = "necrotic"

        key = _format_time_key(float(t))
        data_dict[key] = {
            "x_position":   df["x_position"].tolist(),
            "y_position":   df["y_position"].tolist(),
            "z_position":   df["z_position"].tolist(),
            "current_phase": df["current_phase"].tolist(),
        }

    # ordina per tempo
    ordered_keys = sorted(data_dict.keys(), key=lambda s: float(s))
    ordered = {k: data_dict[k] for k in ordered_keys}

    # padding se possibile
    if ordered_keys and max_time is not None and interval is not None and interval > 0:
        expected = []
        t = 0.0
        while t <= max_time + 1e-9:
            expected.append(t)
            t += interval

        if len(ordered) < len(expected):
            last_key = ordered_keys[-1]
            last_frame = ordered[last_key]
            for tt in expected[len(ordered):]:
                k = _format_time_key(tt)
                if k not in ordered:
                    ordered[k] = last_frame
            ordered = {k: ordered[k] for k in sorted(ordered.keys(), key=lambda s: float(s))}

    gz_path = out_basename_no_ext + ".json.gz"
    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        json.dump(ordered, f, separators=(",", ":"))

    return True


def _write_json(path: str, payload: Dict[str, Any]) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="Postprocess PhysiCell job folder")
    ap.add_argument("--job-dir", required=True, help="Job directory (contains config/ and output/)")
    ap.add_argument("--suffix", default="SIM", help="Suffix for output filenames (e.g. simulation index)")
    args = ap.parse_args()

    job_dir = os.path.abspath(args.job_dir)
    cfg = os.path.join(job_dir, "config", "PhysiCell_settings.xml")
    out_dir = os.path.join(job_dir, "output")
    pj_dir = os.path.join(job_dir, "post_json")
    os.makedirs(pj_dir, exist_ok=True)

    # parse settings
    max_time, interval, params = _parse_settings(cfg)

    # salva input_parameters_<suffix>.json
    ok_params = _write_json(
        os.path.join(pj_dir, f"input_parameters_{args.suffix}.json"),
        params if params else {}
    )

    # cell_data_<suffix>.json.gz
    ok_cells = _cell_data_to_json_gz(
        out_basename_no_ext=os.path.join(pj_dir, f"cell_data_{args.suffix}"),
        sim_output_folder=out_dir,
        max_time=max_time,
        interval=interval
    )

    # exit code sensato
    if ok_cells and ok_params:
        return 0
    # se una delle due mancante, ma l'altra OK, considera comunque successo parziale
    return 0 if (ok_cells or ok_params) else 2


if __name__ == "__main__":
    sys.exit(main())

