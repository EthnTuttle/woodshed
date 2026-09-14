#!/usr/bin/env python3
"""Build a publishable copy of the site into dist/.

Where the line sits, and why:

  THUMBNAILS ARE PUBLISHED. A visual catalogue with no visuals is useless, and a downscaled
  thumbnail beside an attribution and a link to the source is ordinary index/review practice.
  Originals average 227 KB and up to 1920px; these are capped at 520px wide, so they identify a
  design without substituting for it. ~6 MB total.

  FULL-SIZE IMAGES AND PLAN PDFS ARE NOT. Those 75 PDFs are the product itself — several are
  complete plan sets. Rehosting them would replace a purchase. They stay local; records link out.

  python3 tools/build_pages.py                 # default: thumbnails only, no PDFs
  python3 tools/build_pages.py --no-thumbs     # strip images entirely, link out instead
  python3 tools/build_pages.py --with-assets   # full-size images AND PDFs; PRIVATE repo only

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


def make_thumbs(payload, max_w):
    """Downscale each hero image into dist/assets/thumb/. Returns stats."""
    from PIL import Image
    src_dir = os.path.join(ROOT, "assets", "img")
    out_dir = os.path.join(DIST, "assets", "thumb")
    os.makedirs(out_dir, exist_ok=True)
    made = missing = 0
    for rec in payload.get("plans", []):
        rel = rec.get("image_local_path")
        if not rel:
            continue
        src = os.path.join(ROOT, str(rel).lstrip("/"))
        if not os.path.exists(src):
            rec["image_local_path"] = ""
            missing += 1
            continue
        name = os.path.splitext(os.path.basename(src))[0] + ".jpg"
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                if im.width > max_w:
                    im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
                im.save(os.path.join(out_dir, name), "JPEG", quality=72, optimize=True,
                        progressive=True)
        except Exception:
            rec["image_local_path"] = ""
            missing += 1
            continue
        rec["image_local_path"] = f"assets/thumb/{name}"
        rec["image_is_thumb"] = True
        made += 1
    # PDFs are never published — drop the local: refs regardless
    pdfs = 0
    for rec in payload.get("plans", []):
        urls = rec.get("extra_urls") or []
        kept = [u for u in urls if not str(u).startswith("local:")]
        pdfs += len(urls) - len(kept)
        rec["extra_urls"] = kept
    return dict(thumbs=made, missing=missing, pdfs_dropped=pdfs)


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
                    help="rehost FULL-SIZE images and plan PDFs (private repo only)")
    ap.add_argument("--no-thumbs", action="store_true",
                    help="publish no images at all; link out instead")
    ap.add_argument("--thumb-width", type=int, default=520,
                    help="max thumbnail width in px (default 520)")
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

    NOTE_BASE = ("Every record was fetched from its source, extracted, then independently "
                 "fact-checked by a second agent; corrections are shown in each detail panel. "
                 "Prices and specs are only as current as the source page.")
    if args.with_assets:
        for sub in ("img", "pdf"):
            sd = os.path.join(ROOT, "assets", sub)
            if os.path.isdir(sd):
                shutil.copytree(sd, os.path.join(DIST, "assets", sub))
        stats = None
        payload["meta"]["mode"] = "full-assets"
    elif args.no_thumbs:
        stats = strip_assets(payload)
        payload["meta"]["mode"] = "no-images"
        payload["meta"]["note"] = NOTE_BASE + (" Vendor images and PDFs are not rehosted here — "
                                               "each record links back to the source page.")
    else:
        stats = make_thumbs(payload, args.thumb_width)
        payload["meta"]["mode"] = "thumbnails"
        payload["meta"]["thumb_width"] = args.thumb_width
        payload["meta"]["note"] = NOTE_BASE + (
            f" Preview images are downscaled thumbnails (max {args.thumb_width}px) shown for "
            "identification, each credited to and linked back to its source. Full-size drawings "
            "and plan PDFs are not rehosted — follow the link to the vendor for those.")

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
    if stats and "thumbs" in stats:
        print(f"  {stats['thumbs']} thumbnails at max {args.thumb_width}px "
              f"({stats['missing']} unavailable); {stats['pdfs_dropped']} plan-PDF refs removed")
    elif stats:
        print(f"  no images published: {stats['images_dropped']} dropped "
              f"({stats['images_linked']} have a source link), {stats['pdfs_dropped']} PDF refs removed")
    else:
        print("  WARNING: --with-assets rehosts FULL-SIZE images and plan PDFs. Use a PRIVATE repo.")


if __name__ == "__main__":
    main()
