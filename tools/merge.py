#!/usr/bin/env python3
"""Rebuild data/plans.json from a workflow run's journal.jsonl.

The journal records every agent's return value, so we can assemble the dataset
without ever loading it all into a model context. Enrich results are matched to
their verifier's corrections by slug, corrections are applied, and a pick_score
is computed for the "Recommended" sort.

usage: python3 tools/merge.py <journal.jsonl> [more-journals...]
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def coerce(raw):
    """Journal results are stored as Python reprs, sometimes as JSON. Try both."""
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s or s[0] not in "{[":
        return None
    for fn in (json.loads, ast.literal_eval):
        try:
            return fn(s)
        except Exception:
            pass
    return None


def sqft(footprint):
    m = re.search(r"(\d+)\s*[x×]\s*(\d+)", str(footprint or ""))
    return int(m.group(1)) * int(m.group(2)) if m else 0


def price_num(rec):
    p = rec.get("price_usd")
    if isinstance(p, (int, float)):
        return float(p)
    s = str(rec.get("price") or "")
    if re.match(r"^\s*free\s*$", s, re.I):
        return 0.0
    m = re.search(r"\$\s?([\d,]+(?:\.\d{2})?)", s)
    return float(m.group(1).replace(",", "")) if m else -1.0


def has(v):
    return v is not None and str(v).strip() != "" and not re.match(
        r"^(not stated|not stated by the source|unknown|n/a|none stated|-)$", str(v).strip(), re.I
    )


def pick_score(rec):
    """Rank for the 'Recommended' sort: reward completeness, verification, fit."""
    s = 0.0
    v = str(rec.get("verified") or "").upper()
    s += {"CONFIRMED": 26, "PARTIAL": 12, "UNSUPPORTED": -18, "DEAD_LINK": -60}.get(v, 0)
    conf = str(rec.get("data_confidence") or "").lower()
    s += 10 if conf.startswith("high") else 4 if conf.startswith("medium") else 0

    area = sqft(rec.get("footprint"))
    if area:
        s += 16 - min(16, abs(area - 320) / 12.0)  # 320 sq ft is the target
    kind = rec.get("kind")
    s += {"free-plan": 12, "paid-plan": 12, "engineered-plan": 9,
          "plan-bundle": 6, "kit": 4, "video-build": 5}.get(kind, 0)

    pn = price_num(rec)
    if pn == 0:
        s += 8
    elif 0 < pn <= 60:
        s += 7
    elif 60 < pn <= 200:
        s += 3
    elif pn < 0:
        s -= 5  # no published price is a real strike against a paid product

    # richness of the record actually determines how useful the page is
    detail_fields = ["roof", "wall_height", "loft", "doors", "windows", "foundation",
                     "floor_framing", "wall_framing", "siding", "page_count", "format",
                     "overall_height", "refund_policy", "permit_notes", "est_material_cost"]
    s += 0.9 * sum(1 for f in detail_fields if has(rec.get(f)))
    s += min(10, 2.0 * len(rec.get("lumber_list") or []) ** 0.5)
    s += min(6, 1.2 * len(rec.get("includes") or []))
    s += min(6, 1.0 * len(rec.get("pros") or []))
    s += min(4, 0.8 * len(rec.get("quotes") or []))
    if has(rec.get("image_local_path")):
        s += 5
    mla = str(rec.get("materials_list_available") or "")
    if "free-on-page" in mla:
        s += 6
    elif "included" in mla:
        s += 4
    elif "gated" in mla:
        s -= 2
    if re.search(r"\b(yes|full loft|loft)\b", str(rec.get("loft") or ""), re.I) and not \
       re.match(r"^\s*(no|none)\b", str(rec.get("loft") or ""), re.I):
        s += 4
    return round(s, 1)


KINDS = {"free-plan", "paid-plan", "kit", "engineered-plan", "video-build", "plan-bundle"}
# Fields the UI renders as a compact value (badge, cell, sort key) rather than prose.
SHORT_FIELDS = {"kind", "footprint", "sqft", "price", "price_usd", "wall_height",
                "overall_height", "page_count", "format", "skill_level", "build_time",
                "data_confidence", "materials_list_available", "style", "vendor", "name"}

# Sources describe roof style in free prose; the filter needs a small closed vocabulary.
# Order matters: the FIRST match wins, so specific systems must precede generic shapes.
# "pole-barn" contains "barn", so post-frame has to be tested before gambrel/barn.
STYLE_GROUPS = [
    ("pole barn / post-frame", r"pole\s*-?barn|post[\s-]?frame|post\s*&\s*beam|post and beam|quonset|steel arch"),
    ("timber frame",    r"timber\s*frame|king\s*post|mortise"),
    ("gambrel / barn",  r"gambrel|\bbarn\b|maxibarn|monitor"),
    ("lean-to",         r"lean[\s-]?to|shed roof|single[\s-]?slope|skillion"),
    ("saltbox",         r"saltbox"),
    ("modern / studio", r"modern|studio|contemporary|flat roof|clerestory|shed-?style office"),
    ("dormer",          r"dormer"),
    ("hip roof",        r"hip\b"),
    ("garage",          r"garage|carport"),
    ("gable",           r"gable|traditional|craftsman|farmhouse|colonial|nantucket|cottage|cabin|a-?frame"),
]


# How open is it? This is the deciding question for firewood: air has to move through the stack.
# Deliberately conservative — a wrong "roof only" label on an enclosed garage would mislead badly,
# so anything without explicit openness language is reported as "not stated" rather than guessed.
_ENCLOSED_TELL = re.compile(
    r"\bgarage door|overhead door|pre-?hung|double[\s-]hung|insulat|drywall|\bstudio\b|"
    r"fully enclosed|\bcabin\b|\bloft\b|\bgarage\b|\bworkshop\b|\bquonset\b|steel arch", re.I)
_OPEN_EXPLICIT = [
    ("Roof only — no walls",
     r"\broof only\b|\bno walls\b|without walls|open[\s-]?air structure|"
     r"\bpavilion\b|\bgazebo\b|\bramada\b|open[\s-]?sided shelter"),
    ("Open front, three sides slatted",
     r"enclosed with slats|sides? (?:are |is )?enclosed with slats|slatted (?:walls?|sides?)|"
     r"(?:firewood|wood ?shed|woodshed)[^.]{0,120}slat|slat[^.]{0,120}(?:firewood|drying|dry the wood)"),
    ("Open front, three sides solid",
     r"\brun[\s-]?in\b|\bloafing\b|open[\s-]?front|open[\s-]?sided|three[\s-]?sided|\b3[\s-]?sided\b|"
     r"\bmachine shed\b|\bhay shed\b|equipment shelter"),
]


def enclosure(rec):
    if rec.get("enclosure"):
        return rec["enclosure"]
    # Only the record's own description of the STRUCTURE — never the vendor name, which is how
    # "Eagle Carports" got mislabelled as a roof-only building.
    # A building declares its TYPE in its name and style. Prose mentions are unreliable —
    # a video about building a garage mentions carports; a vendor is called "Eagle Carports".
    decl = " ".join(str(rec.get(f) or "") for f in ("name", "style"))
    body = " ".join(str(rec.get(f) or "") for f in
                    ("summary", "roof", "doors", "windows", "siding", "wall_framing"))
    for label, pat in _OPEN_EXPLICIT:
        if re.search(pat, decl, re.I) and not _ENCLOSED_TELL.search(decl):
            return label
    # slatted-for-drying is specific enough to trust from the body text too
    if re.search(_OPEN_EXPLICIT[1][1], body, re.I):
        return _OPEN_EXPLICIT[1][0]
    if _ENCLOSED_TELL.search(decl + " " + body):
        return "Fully enclosed"
    return "not stated"


def style_group(rec):
    blob = " ".join(str(rec.get(f) or "") for f in ("style", "roof", "name"))
    for label, pat in STYLE_GROUPS:
        if re.search(pat, blob, re.I):
            return label
    return "other"


def acceptable_correction(field, correct):
    """A correction must be a *value*, not a critique. Reject prose in compact fields."""
    s = str(correct or "").strip()
    if not s:
        return False
    if field == "kind":
        return s in KINDS
    if field == "footprint":
        return bool(re.search(r"\d+\s*[x×]\s*\d+", s)) and len(s) <= 40
    if field in SHORT_FIELDS:
        return len(s) <= 90 and not re.search(
            r"\b(contradict|the record|the vendor|actually|this is not|misleading|should be noted)\b", s, re.I)
    return True


# Findings from the round-1 completeness critic. These records exist and are kept in the data,
# but they do not answer "what should I build?", so the browser hides them behind a toggle
# instead of padding the option count with them.
DISQUALIFY = {
    "ndsu-5625-gambrel-braced-rafter-16-24ft":
        "Not a building plan — a gambrel rafter cross-section detail with no floor plan or length.",
    "ndsu-5491-16x20-gable":
        "Earth-banked root cellar, not a shed or workshop.",
    "blocklayer-gambrel-roof-calculator":
        "A roof-geometry calculator, not a plan set. Genuinely useful alongside a plan — just not an option in itself.",
    "hansen-varies-post-frame-post-spacing":
        "A blog Q&A about column spacing on a 50x70 commercial building. No plan, no price; vendor's minimum is 576 sq ft.",
    "hansen-custom-post-frame-gable":
        "A blog post about column spacing, not a purchasable plan set for this size.",
}

# Price/spec doubts the critic raised that a later pass has not yet resolved.
PRICE_DOUBT = {
    "sheds-unlimited-16x20-gambrel-barn":
        "Price is internally implausible: this vendor's own line runs 12x20 $6,741 → 14x20 $8,453 → 16x20 $14,170, a 68% jump for 14% more area, and their height table stops at 15'6\" wide. The 16x20 figure may belong to an assembled building rather than the DIY kit.",
    "shedsunlimited-16x20-gable":
        "Same vendor, same pricing anomaly as the MaxiBarn record — treat $15,303 as unconfirmed.",
    "jcs-16x20-gable-loft-barn":
        "Price comes from a May 2024 sale snapshot; the live site blocks all requests, so this is roughly two years stale.",
    "behm-16x20-gable-garage":
        "At $299–309 this is 5–10x every other plan set here; worth a second look before buying.",
}


def image_ok(rel):
    if not rel:
        return False
    p = os.path.join(ROOT, str(rel).lstrip("/"))
    try:
        if os.path.getsize(p) < 5000:
            return False
    except OSError:
        return False
    with open(p, "rb") as f:
        head = f.read(16)
    return (head[:3] == b"\xff\xd8\xff" or head[:8] == b"\x89PNG\r\n\x1a\n"
            or head[:6] in (b"GIF87a", b"GIF89a") or head[:4] == b"RIFF"
            or head[:4] == b"II*\x00" or head[:4] == b"MM\x00*")


def main():
    details, verifies, candidates, notes = {}, {}, [], []
    for path in sys.argv[1:]:
        if not os.path.exists(path):
            print(f"skip missing {path}", file=sys.stderr)
            continue
        for line in open(path):
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") != "result":
                continue
            obj = coerce(ev.get("result"))
            if not isinstance(obj, dict):
                if isinstance(ev.get("result"), str) and len(ev["result"]) > 400:
                    notes.append(ev["result"])
                continue
            if "candidates" in obj:
                candidates.extend(obj.get("candidates") or [])
            elif "slug" in obj and "overall" in obj:
                verifies[obj["slug"]] = obj
            elif "slug" in obj and ("kind" in obj or "summary" in obj):
                slug = obj["slug"]
                # keep the richer record if a slug somehow repeats
                if slug not in details or len(json.dumps(obj)) > len(json.dumps(details[slug])):
                    details[slug] = obj
            elif "overall" in obj and "corrections" in obj:
                verifies[obj.get("slug", "")] = obj

    # Human-reviewed overrides from the repair pass: {slug: {field: value}}, plus "_drop".
    ov_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overrides.json")
    overrides, drops = {}, set()
    if os.path.exists(ov_path):
        raw_ov = json.load(open(ov_path))
        drops = set(raw_ov.pop("_drop", []) or [])
        overrides = raw_ov

    # Records authored directly from source in a follow-up pass: {slug: {...}}
    add_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "additions.json")
    additions = json.load(open(add_path)) if os.path.exists(add_path) else {}
    for slug, rec in additions.items():
        details.setdefault(slug, rec)

    # Derived cut lists from tools/cutlist.py: {slug: {...}}
    der_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "derived.json")
    derived = json.load(open(der_path)) if os.path.exists(der_path) else {}

    # Materials-cost estimates from the costing pass: {slug: {...}}
    cost_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "costs.json")
    costs = json.load(open(cost_path)) if os.path.exists(cost_path) else {}

    plans, corrections_applied, rejected_corrections = [], 0, 0
    for slug, rec in details.items():
        if slug in drops:
            continue
        rec = dict(rec)
        v = verifies.get(slug)
        if v:
            for c in v.get("corrections") or []:
                f = c.get("field")
                if not f or f not in rec or isinstance(rec[f], (list, dict)):
                    continue
                correct = c.get("correct")
                if str(rec[f]).strip() == str(correct or "").strip():
                    continue
                if not acceptable_correction(f, correct):
                    # Verifiers sometimes write a critique where a value belongs. Keep the
                    # original value; the correction still shows in the fact-check trail.
                    rejected_corrections += 1
                    continue
                if f == "price_usd":
                    m = re.search(r"-?[\d.]+", str(correct))
                    if not m:
                        rejected_corrections += 1
                        continue
                    correct = float(m.group(0))
                rec[f + "_original"] = rec[f]
                rec[f] = correct
                corrections_applied += 1
            rec["verified"] = v.get("overall")
            rec["url_live"] = v.get("url_live")
            rec["image_ok"] = v.get("image_ok")
            rec["_verification"] = {
                "overall": v.get("overall"),
                "notes": v.get("notes"),
                "corrections": v.get("corrections") or [],
                "unsupported_claims": v.get("unsupported_claims") or [],
            }
        # drop image references that aren't real image files on disk
        if not image_ok(rec.get("image_local_path")):
            if rec.get("image_local_path"):
                rec["image_missing"] = rec["image_local_path"]
            rec["image_local_path"] = ""
        # Extractors sometimes write an explanation where a footprint belongs. Keep the
        # prose as a note so nothing is lost, but give the UI a compact value to render.
        fp = str(rec.get("footprint") or "").strip()
        if len(fp) > 24 or not re.match(r"^\s*\d+\s*[x×]", fp):
            rec["footprint_note"] = fp
            rec["footprint"] = "varies"
            # Only trust a footprint mined out of prose if it lands in a plausible shed range —
            # otherwise we'd label a vendor "50x70" off an unrelated example in their copy.
            for a, bb in re.findall(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)", fp):
                if 150 <= float(a) * float(bb) <= 700:
                    rec["footprint"] = f"{a}x{bb}"
                    break
        try:
            rec["sqft"] = int(float(rec.get("sqft") or 0)) or sqft(rec.get("footprint"))
        except (TypeError, ValueError):
            rec["sqft"] = sqft(rec.get("footprint"))
        rec["style_group"] = style_group(rec)
        rec["enclosure"] = enclosure(rec)
        # A vendor name is a name; if a verifier or extractor wrote a sentence, keep the first clause.
        ven = str(rec.get("vendor") or "").strip()
        if len(ven) > 64:
            rec["vendor_note"] = ven
            rec["vendor"] = re.split(r"\s+[—–-]\s+|[.;(]", ven)[0].strip()[:64] or "unknown"
        # Seed the known doubts first so a reviewed override below can clear them.
        if slug in PRICE_DOUBT:
            rec["price_doubt"] = PRICE_DOUBT[slug]
        # Overrides win over both the extractor and the verifier — they are the reviewed answer.
        for f, val in (overrides.get(slug) or {}).items():
            m_idx = re.match(r"^([A-Za-z_]+)\[(\d+)\]$", f)
            if m_idx:                                  # e.g. cons[0]
                base, i = m_idx.group(1), int(m_idx.group(2))
                lst = rec.get(base)
                if isinstance(lst, list) and 0 <= i < len(lst):
                    rec.setdefault(base + "_original", list(lst))
                    lst[i] = val
                elif isinstance(lst, list):
                    lst.append(val)
                else:
                    rec[base] = [val]
                continue
            if val == "__DELETE__":
                rec.pop(f, None)
                continue
            if f in rec and rec[f] != val:
                rec.setdefault(f + "_original", rec[f])
            rec[f] = val
        if slug in DISQUALIFY:
            rec["disqualified"] = DISQUALIFY[slug]
        elif rec["footprint"] == "varies" and rec.get("kind") != "plan-bundle":
            rec["kind"] = "reference"
            rec["reference_note"] = (
                "Reference material rather than a plan for one building — no single footprint. "
                "Useful alongside whichever plan you pick.")
        elif rec.get("kind") != "plan-bundle" and rec.get("sqft") and not (120 <= rec["sqft"] <= 700):
            rec["disqualified"] = (
                f"{rec['footprint']} is {rec['sqft']} sq ft — outside the ~240-480 sq ft range this "
                "collection is about.")
        # $/sq ft only means something within a measure — a kit price and a plan price aren't
        # the same thing, so only kits get a delivered cost per square foot.
        if rec.get("kind") == "kit" and price_num(rec) > 0 and rec.get("sqft"):
            rec["kit_cost_per_sqft"] = round(price_num(rec) / rec["sqft"], 2)
        dv = derived.get(slug)
        # a hand-written derivation (e.g. the 12x20) already on the record wins over the generated one
        if dv and not rec.get("derived_lumber_list"):
            rec.update(dv)
        c = costs.get(slug)
        if c and str(c.get("priced", "")).upper() in ("YES", "PARTIAL") and (c.get("total_low_usd") or -1) > 0:
            rec["cost_estimate"] = c
        rec["pick_score"] = pick_score(rec)
        if rec.get("cost_estimate"):
            rec["pick_score"] += 12   # a real cost-to-build makes a record much more decision-ready
        if rec.get("disqualified"):
            rec["pick_score"] -= 500
        plans.append(rec)

    # Different rounds can enrich the same URL under different slugs. Keep the richer record.
    by_url, deduped_out = {}, 0
    def norm_url(u):
        """Normalize for dedup WITHOUT discarding the query string — for YouTube and many
        storefronts the query (?v=..., ?p=...) is the only thing identifying the resource."""
        u = re.sub(r"^https?://(www\.)?", "", str(u or "")).lower()
        u = re.sub(r"#.*$", "", u)
        if "?" in u:
            base, _, qs = u.partition("?")
            keep = [kv for kv in qs.split("&")
                    if kv and not re.match(r"^(utm_[a-z]+|fbclid|gclid|cb|ref|source)=", kv)]
            u = base + ("?" + "&".join(sorted(keep)) if keep else "")
        return u.rstrip("/")
    for rec in plans:
        k = norm_url(rec.get("url")) or rec["slug"]
        prior = by_url.get(k)
        if prior is None:
            by_url[k] = rec
            continue
        deduped_out += 1
        keep, toss = (rec, prior) if len(json.dumps(rec)) > len(json.dumps(prior)) else (prior, rec)
        # don't lose anything the discarded copy had
        keep.setdefault("also_seen_as", []).append(toss["slug"])
        for f in ("lumber_list", "includes", "pros", "cons", "quotes", "extra_urls", "other_sizes"):
            if len(toss.get(f) or []) > len(keep.get(f) or []):
                keep[f] = toss[f]
        if not keep.get("image_local_path") and toss.get("image_local_path"):
            keep["image_local_path"] = toss["image_local_path"]
        if not keep.get("cost_estimate") and toss.get("cost_estimate"):
            keep["cost_estimate"] = toss["cost_estimate"]
        keep["pick_score"] = max(keep["pick_score"], toss["pick_score"])
        by_url[k] = keep
    plans = list(by_url.values())
    if deduped_out:
        print(f"deduped {deduped_out} records that shared a URL", file=sys.stderr)

    plans.sort(key=lambda r: -r["pick_score"])
    dead = [p for p in plans if str(p.get("verified") or "").upper() == "DEAD_LINK"]
    payload = {
        "meta": {
            "compiled_at": os.environ.get("WOODSHED_DATE", "2026-09-07"),
            "plan_count": len(plans),
            "with_images": sum(1 for p in plans if p.get("image_local_path")),
            "corrections_applied": corrections_applied,
            "corrections_rejected_as_prose": rejected_corrections,
            "raw_candidates_found": len(candidates),
            "note": (
                "Every record was fetched from its source, extracted, then independently "
                "fact-checked by a second agent; corrections are shown in each detail panel. "
                "Prices and specs are only as current as the source page."
            ),
        },
        "plans": plans,
        "raw_candidates": candidates,
    }
    out = os.path.join(ROOT, "data", "plans.json")
    with open(out, "w") as f:
        json.dump(payload, f, indent=1)
    print(f"wrote {out}: {len(plans)} plans, {payload['meta']['with_images']} with images, "
          f"{corrections_applied} corrections applied ({rejected_corrections} rejected as prose), "
          f"{len(candidates)} raw candidates, {len(dead)} dead links")
    if notes:
        with open(os.path.join(ROOT, "data", "research-notes.md"), "w") as f:
            f.write("# Research notes (gaps report and channel notes)\n\n")
            for n in notes:
                f.write("\n---\n\n" + n + "\n")
        print("wrote data/research-notes.md")


if __name__ == "__main__":
    main()
