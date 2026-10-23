"""
build.py — one command to refresh the dashboard from the latest reports.

What it does:
  1. Parses every PDF in 'weekly reports/' and 'monthly reports/' (TitanGPS Fleet Reports).
  2. Parses every XLSX in 'driver statistics report/' (per-driver infractions + stars).
  3. Merges them into weeks.json (canonical scores from PDFs, infractions/stars from XLSX,
     plus monthly aggregates).
  4. Reads feedback.json (your editable notes per driver).
  5. Injects both data files into index.html so it's a single self-contained file
     that GitHub Pages can serve directly.

Run it after dropping new reports into the report folders:
    python3 build.py
"""
import json, os, sys, subprocess, shutil

BASE = os.path.dirname(os.path.abspath(__file__))

def run(cmd):
    print(f"\n→ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=BASE)
    if r.returncode != 0:
        print(f"  ✗ failed (exit {r.returncode})")
        sys.exit(r.returncode)

def main():
    # Step 1+2: parse PDFs (weekly + monthly Fleet Reports)
    run([sys.executable, "parse_titan.py"])

    # Step 3: parse XLSX + merge into weeks.json
    run([sys.executable, "parse_stats.py"])

    # Step 4+5: load weeks.json + feedback.json + rentals.json, inject into index.html
    weeks_path   = os.path.join(BASE, "weeks.json")
    fb_path      = os.path.join(BASE, "feedback.json")
    rentals_path = os.path.join(BASE, "rentals.json")
    notes_path   = os.path.join(BASE, "driver_notes.json")
    html_path    = os.path.join(BASE, "index.html")

    if not os.path.exists(weeks_path):
        print(f"  ✗ {weeks_path} not found"); sys.exit(1)
    if not os.path.exists(fb_path):
        print(f"  ✗ {fb_path} not found");    sys.exit(1)
    if not os.path.exists(html_path):
        print(f"  ✗ {html_path} not found");  sys.exit(1)

    with open(weeks_path) as f: weeks = json.load(f)
    with open(fb_path)    as f: fb    = json.load(f)
    fb = {k: v for k, v in fb.items() if not k.startswith("_") and isinstance(v, list)}

    # Rentals are optional — if rentals.json doesn't exist yet, default to an empty list
    # so old setups don't break. Only the "trips" array is consumed by the dashboard.
    # Wrap the read in try/except so a transient filesystem lock (iCloud/Dropbox sync,
    # editor lock, Time Machine snapshot) doesn't kill the whole build.
    rentals = {"trips": []}
    if os.path.exists(rentals_path):
        try:
            with open(rentals_path) as f: rentals_raw = json.load(f)
            if isinstance(rentals_raw, dict):
                rentals = {"trips": rentals_raw.get("trips", [])}
        except (OSError, json.JSONDecodeError) as e:
            print(f"  ⚠ could not read rentals.json ({e}); using empty list")

    # Driver notes (substitute drivers for specific weeks) — optional, same resilient pattern.
    driver_notes = {}
    if os.path.exists(notes_path):
        try:
            with open(notes_path) as f: notes_raw = json.load(f)
            if isinstance(notes_raw, dict):
                driver_notes = notes_raw.get("notes", {}) if "notes" in notes_raw else {k: v for k, v in notes_raw.items() if not k.startswith("_")}
        except (OSError, json.JSONDecodeError) as e:
            print(f"  ⚠ could not read driver_notes.json ({e}); using empty dict")

    # Stamp the build with a refresh timestamp so the dashboard can tell the team how fresh the data is.
    from datetime import datetime
    weeks["last_refreshed_iso"] = datetime.now().isoformat(timespec="minutes")

    with open(html_path) as f: html = f.read()

    # Replace either the placeholders (first build) or any previously injected data block.
    # Anchor on start-of-line + match to end-of-line so semicolons inside note text don't
    # cause early termination. Lambda replacement avoids regex backref interpretation of
    # JSON escape sequences (\u, \\, etc.).
    import re
    data_js      = "const DATA = "          + json.dumps(weeks,        separators=(',',':'), ensure_ascii=False) + ";"
    feedback_js  = "const FEEDBACK = "      + json.dumps(fb,           separators=(',',':'), ensure_ascii=False) + ";"
    rentals_js   = "const RENTALS = "       + json.dumps(rentals,      separators=(',',':'), ensure_ascii=False) + ";"
    notes_js     = "const DRIVER_NOTES = "  + json.dumps(driver_notes, separators=(',',':'), ensure_ascii=False) + ";"
    html = re.sub(r"^const DATA = .*$",          lambda m: data_js,     html, count=1, flags=re.M)
    html = re.sub(r"^const FEEDBACK = .*$",      lambda m: feedback_js, html, count=1, flags=re.M)
    html = re.sub(r"^const RENTALS = .*$",       lambda m: rentals_js,  html, count=1, flags=re.M)
    html = re.sub(r"^const DRIVER_NOTES = .*$",  lambda m: notes_js,    html, count=1, flags=re.M)

    with open(html_path, "w") as f:
        f.write(html)

    print(f"\n✓ build complete")
    print(f"  weeks:  {len(weeks.get('weeks',[]))}")
    print(f"  months: {len(weeks.get('months',[]))}")
    print(f"  feedback notes: {sum(len(v) for v in fb.values())}")
    print(f"  rental trips: {len(rentals['trips'])}")
    print(f"  driver sub notes: {sum(len(v) for v in driver_notes.values()) if driver_notes else 0}")
    print(f"  index.html: {len(html):,} bytes")
    print(f"\nNext: commit + push index.html to your GitHub Pages repo.")

if __name__ == "__main__":
    main()
