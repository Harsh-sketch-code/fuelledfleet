# Fuelled Fleet Dashboard — Weekly Workflow

The dashboard is a single self-contained file (`index.html`). All driver data is baked into it at build time. To update it, you put new reports in folders, run one command, and push to GitHub Pages.

## Folder layout

```
fleet-dashboard/
├── index.html                       ← the dashboard (deploy this to GitHub Pages)
├── feedback.json                    ← edit to add coaching notes per driver
├── build.py                         ← one command to rebuild everything
├── parse_titan.py                   ← PDF parser (used by build.py)
├── parse_stats.py                   ← XLSX parser (used by build.py)
├── weeks.json                       ← generated cache (don't edit by hand)
│
├── weekly reports/                  ← drop weekly Fleet Report PDFs here
├── monthly reports/                 ← drop monthly Fleet Report PDFs here
└── driver statistics report/        ← drop weekly Driver Statistics XLSX files here
```

## Each week — what you do

1. **In TitanGPS, run two reports for the week:**
   - *Fleet Report* (Weekly) — saves a PDF
   - *Driver Statistics Report (GZV4)* — saves an XLSX
2. **Drop them in the matching folders** (file names from TitanGPS work as-is — don't rename):
   - PDF → `weekly reports/`
   - XLSX → `driver statistics report/`
3. **(Optional) Add coaching notes** by editing `feedback.json`. Each driver has an array; append a `{date, category, note}` entry. Categories: `positive`, `coaching`, `warning`, `general`.
4. **Run the build:**
   ```
   cd fleet-dashboard
   python3 build.py
   ```
5. **Commit + push to GitHub:**
   ```
   git add index.html weeks.json feedback.json
   git add "weekly reports" "driver statistics report"
   git commit -m "Update dashboard for week ending YYYY-MM-DD"
   git push
   ```
6. GitHub Pages picks it up in about a minute. The link stays the same: `https://harsh-sketch-code.github.io/fuelledfleet/`

## Each month — same flow, plus two monthly reports

1. In TitanGPS, run two monthly reports:
   - *Fleet Report (Monthly)* — saves a PDF
   - *Driver Statistics Report (GZV4) — Monthly* — saves an XLSX
2. Drop both into `monthly reports/`. Names from TitanGPS work as-is — don't rename.
3. Run `python3 build.py` and push. The Monthly view picks them up automatically.

> Note on monthly numbers: scores in the Monthly view come from the monthly PDF (TitanGPS's portal-canonical figure). When the monthly Driver Statistics XLSX is also present, it provides the canonical per-driver minutes, stars, infractions, and FD — these override the weekly-aggregated sums because TitanGPS sometimes backfills events server-side after the weekly snapshot. If only the PDF is present, weekly XLSX sums are used. If neither is present, the month is marked provisional until either monthly file lands.

## What the build does

`build.py` runs three things in order:

1. **`parse_titan.py`** — reads every PDF in `weekly reports/` and `monthly reports/`, turns each into a sibling `.json`, and writes a `_parsed_index.json` summary in each folder.
2. **`parse_stats.py`** — reads every XLSX in `driver statistics report/`, merges in the canonical scores from the PDF parses, builds monthly aggregates, and writes the unified `weeks.json`.
3. **`build.py` itself** — injects `weeks.json` and `feedback.json` into `index.html` as inline data, replacing whatever data block was in there before.

The result is a single self-contained `index.html` that GitHub Pages can serve directly. No backend, no API calls, no `npoint`, nothing to break.

## Feedback notes — when they get written

- **Monday rebuild (full week available)**: I write one fresh feedback note per active driver in the standard format, plus a monthly summary note per driver at month-end.
- **Mid-week rebuild (in-progress week)**: No new notes. The dashboard's amber "IN PROGRESS" banner, the chip next to the Fleet Average, and the "· in progress" suffix in the week dropdown communicate that the data is partial.

That keeps the feedback feed clean — no half-truth notes that need rewriting once Monday's full data lands.

## What I (Claude) do for you

If you'd rather not run the script yourself, just drop new reports into the folders and message me with "rebuild the dashboard." I'll run `build.py` and confirm. You then `git push` to publish.

If you want the rebuild + push automated end-to-end too, set up a GitHub Action that runs `python3 build.py` on push to `main` and commits the updated `index.html` back. Tell me and I'll add the Action workflow YAML.

## Switching to GitHub Pages

If your existing repo at `harsh-sketch-code.github.io/fuelledfleet/` is what you want to keep using, drop the contents of this folder in there (replace `fuelled_fleet_npoint.html` with `index.html`). The Pages settings should already serve `index.html` from the repo root.

If you want it on a fresh repo, create one called `fuelledfleet` (or whatever), copy this folder's contents in, and enable Pages in repo settings → Pages → Deploy from branch → `main`.

## Roster changes

If a driver leaves or joins, edit the `ROSTER` array in two places (kept simple — no central config yet):
- `parse_stats.py` — top of file
- `index.html` — search for `const ROSTER` (auto-overwritten on next build, so prefer editing `parse_stats.py`)

Then run `python3 build.py`.

## The 6 metric boxes

Per-driver infraction boxes show: Rolling Stop, Following Close, Hard Accel, Hard Brake, Speeding, Traffic Lights. (Distracted Driving isn't broken out per-driver by TitanGPS — only at fleet level — so Traffic Lights took its slot.)

## Monthly winner eligibility (internal: $100 prize, started May 2026)

The monthly leaderboard does NOT rank by score alone from May 2026 onward. A driver who only drove one day with a high score shouldn't outrank someone who drove the whole month — and we don't want to hand the prize out for a small-sample fluke.

**The rule:** to be eligible for the monthly winner spot, a driver must log **at least 900 driving minutes** in the month. That's it — no week-count requirement, no sliding threshold.

Drivers under 900 minutes still appear on the monthly view, but in a separate "Not eligible for monthly winner" section with their score shown and no rank assigned. The weekly leaderboard is unaffected (every driver-week is its own datapoint).

The dashboard does **not** mention the prize amount — keep the "$100" language internal to this doc and how you communicate with drivers directly.

**Pre-May 2026 months (March, April):** the rule did not exist yet, so all drivers rank normally regardless of minutes. These months are historical and shouldn't be retroactively re-judged.

To change the threshold edit `MIN_MONTHLY_MINUTES` in `parse_stats.py`; to change the start month edit `ELIGIBILITY_START` in the same file.

## Driver name aliases

TitanGPS sometimes emits a different name than the everyday one. The parser handles both — add new aliases to `NAME_MAP` in both `parse_titan.py` and `parse_stats.py`. Current aliases:

- d2 — Willem (also: Will)
- d5 — Paddy (also: Patrick — the name registered in TitanGPS; also: Raj for pre-May 2026 data)
