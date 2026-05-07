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

    # Step 4+5: load weeks.json + feedback.json, inject into index.html
    weeks_path = os.path.join(BASE, "weeks.json")
    fb_path    = os.path.join(BASE, "feedback.json")
    html_path  = os.path.join(BASE, "index.html")

    if not os.path.exists(weeks_path):
        print(f"  ✗ {weeks_path} not found"); sys.exit(1)
    if not os.path.exists(fb_path):
        print(f"  ✗ {fb_path} not found");    sys.exit(1)
    if not os.path.exists(html_path):
        print(f"  ✗ {html_path} not found");  sys.exit(1)

    with open(weeks_path) as f: weeks = json.load(f)
    with open(fb_path)    as f: fb    = json.load(f)
    fb = {k: v for k, v in fb.items() if not k.startswith("_") and isinstance(v, list)}

    with open(html_path) as f: html = f.read()

    # Replace either the placeholders (first build) or any previously injected data block.
    # Anchor on start-of-line + match to end-of-line so semicolons inside note text don't
    # cause early termination. Lambda replacement avoids regex backref interpretation of
    # JSON escape sequences (\u, \\, etc.).
    import re
    data_js     = "const DATA = "     + json.dumps(weeks, separators=(',',':'), ensure_ascii=False) + ";"
    feedback_js = "const FEEDBACK = " + json.dumps(fb,    separators=(',',':'), ensure_ascii=False) + ";"
    html = re.sub(r"^const DATA = .*$",     lambda m: data_js,     html, count=1, flags=re.M)
    html = re.sub(r"^const FEEDBACK = .*$", lambda m: feedback_js, html, count=1, flags=re.M)

    with open(html_path, "w") as f:
        f.write(html)

    print(f"\n✓ build complete")
    print(f"  weeks:  {len(weeks.get('weeks',[]))}")
    print(f"  months: {len(weeks.get('months',[]))}")
    print(f"  feedback notes: {sum(len(v) for v in fb.values())}")
    print(f"  index.html: {len(html):,} bytes")
    print(f"\nNext: commit + push index.html to your GitHub Pages repo.")

if __name__ == "__main__":
    main()
