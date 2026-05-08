#!/usr/bin/env python3
import argparse, csv, os, re, subprocess, sys
from typing import Optional, Tuple

def read_user_sys_sum(path: str) -> float:
    """
    Parse a /usr/bin/time output file containing lines:
      user=<float>
      sys=<float>
    Return user+sys in seconds. If missing, return 0.0.
    """
    if not path or not os.path.isfile(path):
        return 0.0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        u = re.search(r"^user=([0-9.]+)", txt, re.M)
        s = re.search(r"^sys=([0-9.]+)", txt, re.M)
        uu = float(u.group(1)) if u else 0.0
        ss = float(s.group(1)) if s else 0.0
        return uu + ss
    except Exception:
        return 0.0

def hms_to_sec(tok: str) -> Optional[int]:
    """
    Converts Slurm time tokens like [DD-]HH:MM:SS(.sss) or MM:SS to total seconds.
    Returns None if unknown/empty.
    """
    if not tok or tok == "Unknown":
        return None
    d = 0
    if "-" in tok:
        d_str, tok = tok.split("-", 1)
        d = int(d_str)
    parts = tok.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            s = int(float(s))
        elif len(parts) == 2:
            h = 0
            m, s = parts
            s = int(float(s))
        else:
            return None
        return d * 86400 + int(h) * 3600 + int(m) * 60 + s
    except Exception:
        return None

def get_sacct_line(job_id: str) -> Optional[str]:
    """
    Call 'sacct' for job_id and return the most relevant pipe-separated line:
    prefer '<job_id>.batch', else '<job_id>'.
    Columns requested: JobID|Elapsed|TotalCPU|AveCPU|AllocCPUS|MaxRSS|ReqMem
    """
    if not job_id:
        return None
    try:
        out = subprocess.check_output(
            ["sacct", "-j", job_id, "-o", "JobID,Elapsed,TotalCPU,AveCPU,AllocCPUS,MaxRSS,ReqMem", "-P", "-n"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        for L in lines:
            if L.startswith(f"{job_id}.batch|"):
                return L
        for L in lines:
            if L.startswith(f"{job_id}|"):
                return L
    except Exception:
        return None
    return None

def write_csv(csv_path: str, rows: list) -> None:
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "metric", "value", "unit", "notes"])
        for r in rows:
            w.writerow(r)

def main():
    ap = argparse.ArgumentParser(description="Aggregate CPU/wall metrics into CSV")
    ap.add_argument("--job-dir", required=True, help="Job directory (contains post_json/)")
    ap.add_argument("--suffix", default="SIM", help="Suffix for output filename (default: SIM)")
    ap.add_argument("--time-sim", required=False, default="", help="Path to /usr/bin/time output for simulation")
    ap.add_argument("--time-post", required=False, default="", help="Path to /usr/bin/time output for postprocess")
    ap.add_argument("--slurm-job-id", required=False, default="", help="SLURM_JOB_ID to query sacct")
    args = ap.parse_args()

    job_dir = os.path.abspath(args.job_dir)
    out_csv = os.path.join(job_dir, "post_json", f"CPU_time_{args.suffix}.csv")

    sim_us = read_user_sys_sum(args.time_sim)
    post_us = read_user_sys_sum(args.time_post)
    steps_total = sim_us + post_us

    rows = []
    rows.append(["timers", "StepUserSys_sim",  f"{sim_us:.3f}", "s", "user+sys (GNU time)"])
    rows.append(["timers", "StepUserSys_post", f"{post_us:.3f}", "s", "user+sys (GNU time)"])
    rows.append(["timers", "StepUserSys_total", f"{steps_total:.3f}", "s", "sum of steps"])

    line = get_sacct_line(args.slurm_job_id)
    if line:
        # JobID|Elapsed|TotalCPU|AveCPU|AllocCPUS|MaxRSS|ReqMem
        try:
            jid, elapsed, totalcpu, avecpu, alloc, maxrss, reqmem = line.split("|")
            tc = hms_to_sec(totalcpu)
            el = hms_to_sec(elapsed)
            av = hms_to_sec(avecpu)
            rows.append(["sacct", "TotalCPU", tc if tc is not None else "", "s", "Slurm TotalCPU"])
            rows.append(["sacct", "Elapsed",  el if el is not None else "", "s", "Slurm Elapsed"])
            rows.append(["sacct", "AveCPU",   av if av is not None else "", "s", "Slurm AveCPU"])
            rows.append(["sacct", "AllocCPUS", alloc, "cores", "allocated cores"])
            rows.append(["sacct", "MaxRSS",   maxrss, "KB", "max resident set size"])
            rows.append(["sacct", "ReqMem",   reqmem, "", "requested memory"])
        except Exception:
            # If parsing fails, at least keep timers rows
            pass
    else:
        rows.append(["sacct", "TotalCPU", "", "s", "unavailable at job end"])
        rows.append(["sacct", "Elapsed",  "", "s", "unavailable at job end"])

    write_csv(out_csv, rows)
    print(f"Wrote: {out_csv}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
