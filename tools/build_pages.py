#!/usr/bin/env python3
"""Build a publishable copy of the site into dist/.

The local site rehosts 139 hero images and 75 PDFs pulled from vendor sites — fine as private
research, not something to republish. So by default this build ships ONLY our own work (the
structured research, the code, the derived estimates) and links every image and PDF back to
where it came from.

  python3 tools/build_pages.py                 # safe to publish: no vendor assets rehosted
  python3 tools/build_pages.py --with-assets   # includes them; for a PRIVATE repo or local use

usage note: --base is for project pages served from /<repo>/ rather than a domain root.
"""
import argparse
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
CODE = ["index.html", "app.js", "styles.css"]


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def dir_size(path):
    total = 0
    for dp, _, fns in os.walk(path):
        for fn in fns:
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return total


def strip_assets(payload):
    """Drop references to rehosted files, keeping a link out in their place."""
    stats = dict(images_dropped=0, images_linked=0, pdfs_dropped=0)
    for rec in payload.get("plans", []):
        if rec.get("image_local_path"):
            stats["images_dropped"] += 1
            rec["image_was_local"] = True
            rec["image_local_path"] = ""
            if rec.get("image_source_url"):
                stats["images_linked"] += 1
        # "local:assets/pdf/x.pdf" entries point at files we are not shipping
        urls = rec.get("extra_urls") or []
        kept = [u for u in urls if not str(u).startswith("local:")]
        stats["pdfs_dropped"] += len(urls) - len(kept)
        rec["extra_urls"] = kept
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-assets", action="store_true",
                    help="rehost the vendor images and PDFs (private repo only)")
    ap.add_argument("--base", default="",
                    help="path prefix for project pages, e.g. /woodshed")
    args = ap.parse_args()

    src_json = os.path.join(ROOT, "data", "plans.json")
    if not os.path.exists(src_json):
        sys.exit("data/plans.json missing — run tools/merge.py first")

    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "data"), exist_ok=True)

    for f in CODE:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(DIST, f))

    payload = json.load(open(src_json))
    payload.setdefault("meta", {})
    payload["meta"]["publish"] = True
    payload["meta"]["assets_rehosted"] = bool(args.with_assets)

    if args.with_assets:
        for sub in ("img", "pdf"):
            s = os.path.join(ROOT, "assets", sub)
            if os.path.isdir(s):
                shutil.copytree(s, os.path.join(DIST, "assets", sub))
        stats = None
    else:
        stats = strip_assets(payload)
        payload["meta"]["note"] = (
            "Every record was fetched from its source, extracted, then independently fact-checked "
            "by a second agent; corrections are shown in each detail panel. Vendor images and PDFs "
            "are deliberately NOT rehosted here — each record links back to the source page. "
            "Prices and specs are only as current as the source page."
        )

    # research-notes is our own analysis, safe to ship
    notes = os.path.join(ROOT, "data", "research-notes.md")
    if os.path.exists(notes):
        shutil.copy2(notes, os.path.join(DIST, "data", "research-notes.md"))

    json.dump(payload, open(os.path.join(DIST, "data", "plans.json"), "w"), indent=1)

    # Jekyll would otherwise swallow paths beginning with _ and slow the build down
    open(os.path.join(DIST, ".nojekyll"), "w").close()

    if args.base:
        base = "/" + args.base.strip("/")
        idx = os.path.join(DIST, "index.html")
        html = open(idx).read().replace('<head>', f'<head>\n<base href="{base}/">', 1)
        open(idx, "w").write(html)

    plans = payload.get("plans", [])
    live = [p for p in plans if not p.get("disqualified")]
    opts = [p for p in live if p.get("kind") != "reference"]
    print(f"dist/ built: {human(dir_size(DIST))}")
    print(f"  {len(plans)} records ({len(opts)} build options, {len({p['vendor'] for p in opts})} vendors)")
    if stats:
        print(f"  assets NOT rehosted: {stats['images_dropped']} images dropped "
              f"({stats['images_linked']} have a source link), {stats['pdfs_dropped']} local PDF refs removed")
    else:
        print("  WARNING: --with-assets rehosts vendor images and PDFs. Use a PRIVATE repo.")


if __name__ == "__main__":
    main()
