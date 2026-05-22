"""
Parse TitanGPS Fleet Reports (weekly or monthly) into structured JSON.

Usage:
    python3 parse_titan.py "<path/to/file.pdf>"          # single file
    python3 parse_titan.py "<path/to/folder>"            # whole folder
    python3 parse_titan.py                               # default: ./weekly reports + ./monthly reports

Output:
    Writes a sibling .json next to each PDF (e.g. foo.pdf -> foo.json).
    Also writes a consolidated index file:
        weekly reports/_parsed_index.json
        monthly reports/_parsed_index.json
"""
import pdfplumber, json, re, sys, os, glob

NAME_MAP = {
    "Dylan":   "d1",
    "Will":    "d2", "Willem": "d2",
    "Jackson": "d3",
    "Austin":  "d4",
    "Paddy":   "d5", "Patrick": "d5", "Raj": "d5",
    "Harsh":   "d6",
}
NAMES_RE = "|".join(sorted(NAME_MAP.keys(), key=len, reverse=True))

MONTH_IDX = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
             "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}

def signed(arrow, val):
    return float(val) * (-1 if arrow == "↓" else 1)

def parse_period(full, fallback_year):
    """Extract the period header. Returns dict with start_iso, end_iso, label, type, raw."""
    period = {"raw": None, "start_iso": None, "end_iso": None, "label": None, "type": None}
    m = re.search(r"\((\d{1,2}) (\w+)\) [\d:]+ [AP]M \((\w+)\)\s*-\s*\w+\s*\((\d{1,2}) (\w+)\)", full)
    if m:
        sd, sm, _tz, ed, em = m.groups()
        sm_n = MONTH_IDX.get(sm[:3])
        em_n = MONTH_IDX.get(em[:3])
        if sm_n and em_n:
            period["start_iso"] = f"{fallback_year}-{sm_n:02d}-{int(sd):02d}"
            end_yr = fallback_year + (1 if em_n < sm_n else 0)
            period["end_iso"] = f"{end_yr}-{em_n:02d}-{int(ed):02d}"
            period["label"] = f"{sm} {int(sd)}-{em} {int(ed)}, {fallback_year}"
        period["raw"] = m.group(0)
    if re.search(r"Weekly Report", full, re.I):
        period["type"] = "weekly"
    elif re.search(r"Monthly Report", full, re.I):
        period["type"] = "monthly"
    else:
        period["type"] = "unknown"
    return period

def parse_pdf(path):
    """Parse one TitanGPS Fleet Report PDF into a structured dict."""
    fname = os.path.basename(path)
    yr_m = re.search(r"(20\d{2})", fname)
    fallback_year = int(yr_m.group(1)) if yr_m else 2026

    with pdfplumber.open(path) as pdf:
        full = "\n".join(p.extract_text() or "" for p in pdf.pages)

    period = parse_period(full, fallback_year)

    # Fleet header line: "<score> <arrow> <delta> <count> <arrow> <delta>"
    fleet_avg = drivers_with_score = None
    m = re.search(
        r"(\d{3,4})\s*([↓↑])\s*(\d+)\s+(\d+)\s*([↓↑])\s*(\d+)\s*\n\s*Fleet Average Score",
        full,
    )
    if m:
        fleet_avg = {"score": int(m.group(1)),
                     "delta": int(m.group(3)) * (-1 if m.group(2) == "↓" else 1)}
        drivers_with_score = {"count": int(m.group(4)),
                              "delta": int(m.group(6)) * (-1 if m.group(5) == "↓" else 1)}

    # Driver scores
    driver_scores = {}
    for nm in re.findall(rf"^({NAMES_RE})\s+(\d{{3,4}})\s+([↓↑])\s+([\d.]+)\s*$",
                         full, flags=re.M):
        name, score, arrow, delta = nm
        did = NAME_MAP[name]
        if did not in driver_scores:
            driver_scores[did] = {"name": name, "driver_id": did,
                                   "score": int(score), "delta": signed(arrow, delta)}
    driver_scores = sorted(driver_scores.values(), key=lambda r: -r["score"])

    # Risk profile
    risk = []
    for k, unit_pat in [("Accelerations","alerts"),("Brakings","alerts"),
                        ("turns","alerts"),("Traffic lights","alerts"),
                        ("Stoppings","alerts"),("Speeding","Minutes"),
                        ("Driver Distraction","Minutes")]:
        pat = re.compile(rf"{re.escape(k)}\(({unit_pat})\)\s+(\d+)\s*\(([\d.]+)\s*%\)\s+(\d+)\s*\(([\d.]+)\s*%\)\s+(\d+)\s*\(([\d.]+)\s*%\)")
        mm = pat.search(full)
        if mm:
            risk.append({
                "metric": k.title(),
                "unit": mm.group(1),
                "below_threshold": {"count": int(mm.group(2)), "pct": float(mm.group(3))},
                "moderate":        {"count": int(mm.group(4)), "pct": float(mm.group(5))},
                "severe":          {"count": int(mm.group(6)), "pct": float(mm.group(7))},
            })

    # Following Distance per driver
    fd_per_driver = {}
    for row in re.finditer(
            rf"^({NAMES_RE})\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$",
            full, flags=re.M):
        nm, mins, fd, c1, c2, c3 = row.groups()
        did = NAME_MAP[nm]
        if did not in fd_per_driver:
            fd_per_driver[did] = {
                "name": nm, "driver_id": did,
                "driving_minutes": int(mins),
                "avg_fd_seconds": float(fd),
                "congestion_light_min": float(c1),
                "congestion_medium_min": float(c2),
                "congestion_heavy_min": float(c3),
            }
    fd_per_driver = sorted(fd_per_driver.values(), key=lambda r: r["avg_fd_seconds"])

    # Most severe FD alerts
    severe_fd = []
    for row in re.finditer(
            rf"^({NAMES_RE})\s+(\d{{8,}})\s+([\d.]+)\s+([\d.]+)\s*$",
            full, flags=re.M):
        nm, aid, closest, dur = row.groups()
        severe_fd.append({"name": nm, "driver_id": NAME_MAP[nm],
                           "alert_id": aid,
                           "closest_fd_sec": float(closest),
                           "duration_sec": float(dur)})

    # Stars
    sm = re.search(r"Total\s+(\d+)\s+driver\s+stars?\s+rewarded", full, re.I)
    driver_stars = int(sm.group(1)) if sm else 0

    # Unavailable sections
    unavailable = []
    for label in ["Most severe hard braking alerts",
                  "Most severe stop sign alerts",
                  "Most severe speeding alerts"]:
        if re.search(rf"{re.escape(label)}\s*\nData unavailable", full):
            unavailable.append(label)

    return {
        "source_file": fname,
        "report_type": (period["type"] + "_fleet") if period["type"] in ("weekly","monthly") else "fleet",
        "period": period,
        "fleet_average_score": fleet_avg,
        "drivers_with_greenzone_score": drivers_with_score,
        "driver_performance": driver_scores,
        "risk_profile": risk,
        "following_distance_per_driver": fd_per_driver,
        "most_severe_fd_alerts": severe_fd,
        "driver_stars_awarded": driver_stars,
        "data_unavailable_sections": unavailable,
    }

def parse_folder(folder):
    pdfs = sorted(glob.glob(os.path.join(folder, "*.pdf")))
    out = []
    for p in pdfs:
        try:
            data = parse_pdf(p)
        except Exception as e:
            print(f"  !! {os.path.basename(p)}: {e}")
            continue
        sib = os.path.splitext(p)[0] + ".json"
        with open(sib, "w") as f:
            json.dump(data, f, indent=2)
        out.append(data)
        print(f"  ok  {os.path.basename(p)}  ->  {data['period']['label']}  ({data['report_type']})")
    idx = os.path.join(folder, "_parsed_index.json")
    with open(idx, "w") as f:
        json.dump({"folder": folder, "count": len(out), "reports": out}, f, indent=2)
    print(f"  index: {idx}")
    return out

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        base = os.path.dirname(os.path.abspath(__file__))
        args = [os.path.join(base, "weekly reports"), os.path.join(base, "monthly reports")]
    for a in args:
        if os.path.isdir(a):
            print(f"\n[folder] {a}")
            parse_folder(a)
        elif os.path.isfile(a):
            print(f"\n[file] {a}")
            d = parse_pdf(a)
            sib = os.path.splitext(a)[0] + ".json"
            with open(sib, "w") as f:
                json.dump(d, f, indent=2)
            print(f"  ok  {os.path.basename(a)}  ->  {d['period']['label']}  ({d['report_type']})")
        else:
            print(f"  not found: {a}")
