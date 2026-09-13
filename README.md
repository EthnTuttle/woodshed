# Woodshed

A local, offline-capable browser for ~16×20 ft (320 sq ft) DIY shed plans. Every option was
fetched from its source, extracted into a structured record, then independently fact-checked by
a second agent. Hero images and free plan PDFs are downloaded to disk, so the site works with
no network.

**What's in here:** 111 build options from 73 distinct vendors across 25 footprint sizes — 49 free plans, 24 paid plan sets ($6–$650), 22 pre-cut kits, 13 start-to-finish video build series and 2 free engineered/institutional plan sets — plus 8 reference documents and 7 records kept but excluded as out of scope. 92 carry the vendor's actual materials list and 6 have been priced at 2026 retail. 139 images and 75 PDFs are saved locally.

## Run it

```bash
./serve.sh          # → http://localhost:8787
./serve.sh 8080     # or pick your own port
```

Then open <http://localhost:8787>. It must be served over HTTP — opening `index.html` as a
`file://` URL will fail because the browser blocks the `fetch` of `data/plans.json`.

## Using it

| | |
|---|---|
| **Cards** | Browse. Click any card (or **Details**) for the full spec sheet, materials list, quotes and fact-check trail. |
| **Table** | Every option and every key spec in one scannable grid. Also the accessible fallback for the color-coded type badges. |
| **Compare** | Star (☆) options on the cards to shortlist them, then compare them field by field. The shortlist persists in `localStorage`. |
| **Filters** | Type, footprint, style, loft, price, plus full-text search across the entire record (specs, quotes, pros/cons — not just titles). |
| `/` | Jump to search. `Esc` closes the detail panel. |

The **Cost of the plan set** chart is the price of the *drawings*, not the lumber. Options with
no published price are excluded from the chart and named underneath it, so nothing is silently
dropped.

## Layout

```
index.html            the app shell
app.js                rendering, filtering, compare, detail drawer — no dependencies
styles.css            dark + light themes
serve.sh              local static server
data/plans.json       the dataset (plans[] plus raw_candidates[] of everything found)
data/research-notes.md  gaps report: what's missing, which vendors weren't reached
assets/img/<slug>.*   hero images, downloaded locally
assets/pdf/<slug>.pdf  free plan PDFs, downloaded locally
tools/merge.py        rebuilds data/plans.json from a research run's journal
```

## Open-sided shelters and firewood storage

Firewood needs a roof and moving air, not walls — sealing wood in traps moisture and it never
seasons. Every record is therefore classified by **enclosure**, filterable under **Walls**:

| Enclosure | Count |
|---|---|
| Roof only — no walls | 2 |
| Open front, three sides slatted | 6 |
| Open front, three sides solid | 4 |
| Fully enclosed | 84 |
| Not stated by the source | 15 |

8 records carry a **firewood capacity in cords**. Where the vendor states it, the figure is
theirs; where it is derived from floor area at a 6 ft stack height, the card says `est.` and the
detail panel says so explicitly.

The purpose-built firewood sheds share a design worth understanding before you pick one:

- **Lean-to (single-slope) roof at 2:12–3:12** — no trusses, no ridge, and it throws water off the
  back rather than into the open front. At that pitch you need metal roofing; shingles are not rated
  for it.
- **Open front, three sides of 1x6 slats with 2¼" spacers** — the gaps are the design, not a
  shortcut.
- **A slatted floor** — 2x4 or 2x6 decking with 7/8" gaps on 4x4 pressure-treated skids over 3–4"
  of compacted gravel, so air moves *under* the stack. This is the detail a general-purpose shed
  plan gets wrong, and it matters more than the walls.
- **Long and shallow beats square.** Every plan in this family is 10–12 ft deep, because you stack
  roughly 4 ft deep and have to reach it. A 16 ft deep building puts the back of the stack out of
  arm's reach from the open front.

Enclosure is inferred conservatively from each source's own description. Anything without explicit
openness language reads **"not stated"** rather than being guessed at — a wrong "roof only" label on
an enclosed garage would be worse than an honest blank.

## Provenance of the open-sided records

The eight open-sided records added in the follow-up pass are marked **"Read from source"** rather
than "Source checked". Their specs were read directly off the source article, but they did not go
through the adversarial second-agent fact-check that the other records did. Their `_verification`
block says exactly this.

## Publishing to GitHub Pages

```bash
python3 tools/build_pages.py          # -> dist/, ~4 MB, safe to publish
python3 -m http.server 8788 -d dist   # preview it
```

**The build deliberately does not republish vendor assets.** Locally this site rehosts 139 hero
images and 75 PDFs pulled from vendor pages — fine as private research, not something to put on a
public URL. `build_pages.py` therefore strips all of them and substitutes a *View image at source*
link on each record (117 of 125 have one). That takes the payload from 171 MB to 4.3 MB and means
no plan sheets, cut lists or copyrighted drawings are redistributed. `assets/` and `dist/` are both
gitignored.

What does get published is our own work: the structured research, the fact-check trail, the derived
cost and quantity estimates, and the code. Every record links back to the vendor to buy or download.

`.github/workflows/pages.yml` deploys on push to `main`. It runs the build without `--with-assets`
and then **fails the deploy** if `dist/assets` exists or if any `image_local_path` / `local:` PDF
reference survived — so a future change can't quietly start publishing third-party files.

If you do want the images (a private repo, or purely local use):

```bash
python3 tools/build_pages.py --with-assets   # 169 MB — PRIVATE repos only
```

For a project page served from `https://<user>.github.io/<repo>/` rather than a domain root, add
`--base /<repo>` so relative paths resolve.

### One-time repo setup

```bash
git init && git add -A && git commit -m "Woodshed: shed plan research browser"
gh repo create woodshed --public --source=. --push
gh api -X POST repos/:owner/woodshed/pages -f build_type=workflow   # or enable in Settings > Pages
```

## Reading the data honestly

- **`verified`** is the second agent's verdict after re-fetching the source: `CONFIRMED`,
  `PARTIAL`, `UNSUPPORTED`, or `DEAD_LINK`. Anything not `CONFIRMED` is worth reading the
  fact-check trail on before trusting it.
- **Corrections are shown, not hidden.** Where the fact-checker overruled the extractor, the
  detail panel lists the field, the original value and the corrected one.
- **"not stated by the source"** means exactly that. No spec on this site was inferred or
  invented; a blank is a real gap in the vendor's page, not a gap in the research.
- **Prices drift.** They were read off the live page on the compile date shown in the header.
  Two vendors inject prices via JavaScript and were only obtainable at checkout.

## Before you build

320 sq ft is over the permit-exemption threshold in most jurisdictions (commonly 120 or
200 sq ft). That usually means a site plan, setback compliance, and often *engineered* trusses
rather than site-built ones. Check your own code before buying a plan set — it can change which
option makes sense. The `permit_notes` field carries whatever each source says about this.
