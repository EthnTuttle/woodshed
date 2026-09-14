#!/usr/bin/env python3
"""Parse published materials lists, and derive one where a vendor gates or omits theirs.

Two halves:

  parse_list()  turns a vendor's published list into structured quantities. 92 records have one,
                which makes them a calibration set with known-good answers.

  derive()      computes a quantity take-off from footprint + wall height + roof geometry.

Because the calibration set exists, derive() can be scored rather than merely asserted: run it
against every record that already has a real list, measure the error per material, and use that
measured error to label each derived line's confidence. That is the whole point — a derived number
with a measured error bar is useful; one without is a guess.

    python3 tools/cutlist.py calibrate    # score derive() against the 92 known lists
    python3 tools/cutlist.py apply        # write derived lists into tools/derived.json
"""
import json
import math
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ceil = lambda x: int(math.ceil(x - 1e-9))

# Nominal cross-sections we care about, plus sheet goods.
DIMS = ["2x4", "2x6", "2x8", "2x10", "2x12", "4x4", "4x6", "4x8", "6x6", "1x4", "1x6", "1x8", "1x2", "1x3"]
SHEET_RX = re.compile(r"(plywood|osb|t1-?11|siding|sheeting|sheathing|roofing|decking sheet)", re.I)


def norm(s):
    """Vendor lists use curly quotes, × and non-breaking spaces. Flatten them."""
    return (str(s).replace("×", "x").replace("″", '"').replace("”", '"')
            .replace("′", "'").replace("’", "'").replace(" ", " ")
            .replace("–", "-").replace("—", "-"))


def to_inches(qty, unit):
    return qty * (12.0 if unit and unit.startswith("f") else 1.0)


def _len_in(txt, unit_hint=None):
    """'141 1/2\"' / '16\'-0\"' / '20 ft' -> inches. None if unreadable."""
    t = norm(txt).strip()
    m = re.match(r"^(\d+)\s*'\s*-?\s*(\d+)?\s*\"?$", t)          # 16'-0"
    if m:
        return float(m.group(1)) * 12 + float(m.group(2) or 0)
    m = re.match(r"^(\d+)\s*(?:\.(\d+))?\s*(?:x|\s)", t)
    m = re.match(r"^(\d+(?:\.\d+)?)(?:\s+(\d+)/(\d+))?\s*(\"|in\b|inch|ft\b|feet|')?", t)
    if not m:
        return None
    val = float(m.group(1))
    if m.group(2):
        val += float(m.group(2)) / float(m.group(3))
    unit = (m.group(4) or unit_hint or '"')
    return val * (12.0 if unit.startswith(("f", "'")) else 1.0)


def _dim_in(txt):
    low = norm(txt).lower()
    for d in sorted(DIMS, key=len, reverse=True):
        if re.search(r"(?<![\d.])" + d.replace("x", r"\s*x\s*") + r"(?![\d.])", low):
            return d
    return None


NOISE = re.compile(r"screw|nail|glue|paint|filler|\btie\b|latch|hinge|felt|tar paper|shingle|"
                   r"gravel|adhesive|clip|anchor|caulk|fastener|\blag\b|bolt|stain|primer|"
                   r"^===|^total|^fasteners|^tools|^materials\b|^exterior|^foundation|^floor "
                   r"framing|^wall framing|^roof framing|^door\b|^loft|hardware|window|vent|"
                   r"flashing|drip edge|squares|\bsf\b|cupola|shutter", re.I)


def parse_list(lines):
    """Vendors publish lists in at least four shapes. Handle each, and count what we cannot read.

    F1 MyOutdoorPlans:  'A - FLOOR FRAME - 2x6 lumber 20 ft - 2 pieces'
    F2 HowToSpecialist:  'A - 2 pieces of 4x4 lumber - 192" long, 11 pieces - 141" long'
    F3 Best Barns table: '4   2x4   8\'   Wall Plates'
    F4 iCreatables table:'T4  1x4 Trim  16\'-0"  15'
    """
    lumber, sheets, unread = {}, 0, 0
    # ShedKing packs several items per line separated by ';'
    flat = []
    for raw in lines or []:
        t = norm(raw)
        flat.extend(x for x in re.split(r";", t) if x.strip()) if t.count(";") >= 1 else flat.append(t)
    for raw in flat:
        s = norm(raw).strip()
        low = s.lower()
        if not s:
            continue

        # F7 USDA/NDSU:  '32 - 2"X4"X10'-0"'   (count - dim x length)
        m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*\"?\s*x\s*(\d+)\s*\"?\s*x\s*"
                     r"(\d+)\s*'\s*-?\s*(\d+)?", s, re.I)
        if m:
            dim = f"{m.group(2)}x{m.group(3)}"
            li = float(m.group(4)) * 12 + float(m.group(5) or 0)
            if dim in DIMS and 6 <= li <= 700:
                lumber[dim] = lumber.get(dim, 0.0) + int(m.group(1)) * li
                continue

        # F5 ShedKing:  '2x8x16 - 16 - Floor Joists'  /  '2x6x92-5/8" - 16 - Wall Studs'
        m = re.match(r"^[^0-9]{0,28}?(\d+)\s*x\s*(\d+)\s*x\s*"
                     r"(\d+(?:-\d+/\d+)?)\s*(\"?)\s*-\s*(\d+)\s*-", s, re.I)
        if m:
            dim = f"{m.group(1)}x{m.group(2)}"
            raw_len, quoted = m.group(3), m.group(4)
            if "-" in raw_len:                       # 92-5/8"
                a, fr = raw_len.split("-"); nn, dd = fr.split("/")
                li = float(a) + float(nn) / float(dd)
            else:
                li = float(raw_len) * (1.0 if quoted else 12.0)
            if dim in DIMS and 6 <= li <= 700:
                lumber[dim] = lumber.get(dim, 0.0) + int(m.group(5)) * li
                continue

        # F6 MWPS estimating list: "Studs...: 2x4's, ft ....... 410"  (already linear FEET)
        m = re.search(r"(\d+)\s*x\s*(\d+)'?s?\s*,\s*ft\b[\s.]*?(\d[\d,]*)\s*$", s, re.I)
        if m:
            dim = f"{m.group(1)}x{m.group(2)}"
            if dim in DIMS:
                lumber[dim] = lumber.get(dim, 0.0) + float(m.group(3).replace(",", "")) * 12
                continue
        # "Rafters: 2x6's, 10 ft long ....... 11"  (count at the end)
        m = re.search(r"(\d+)\s*x\s*(\d+)'?s?\s*,\s*(\d+)\s*ft\b[^.]*?[\s.]+(\d+)\s*$", s, re.I)
        if m:
            dim = f"{m.group(1)}x{m.group(2)}"
            if dim in DIMS:
                lumber[dim] = lumber.get(dim, 0.0) + int(m.group(4)) * float(m.group(3)) * 12
                continue

        # sheet goods first — they have an area, not a length
        if SHEET_RX.search(low) and not re.search(r"\b\d+\s*x\s*(4|6|8|10|12)\b\s*(lumber|trim|trt|pt)?", low):
            m = (re.search(r"(\d+)\s*(?:pieces?|sheets?)\b", low)
                 or re.search(r"\bx\s*\d+/\d+\"?\s+(\d+)\s*$", low)
                 or re.search(r"\s(\d{1,3})\s*$", s))
            if m:
                sheets += int(m.group(1))
                continue

        if NOISE.search(low):
            continue

        dim = _dim_in(s)
        if not dim:
            unread += 1
            continue

        got = False

        # F1: '... <dim> lumber <len> - <n> piece(s)'
        m = re.search(r"\b" + dim.replace("x", r"\s*x\s*") +
                      r"\b[^0-9]{0,14}([\d./\s'\"-]{1,14}?)\s*[-–]\s*(\d+)\s*pieces?\b", s, re.I)
        if m:
            li = _len_in(m.group(1))
            if li and 6 <= li <= 700:
                lumber[dim] = lumber.get(dim, 0.0) + int(m.group(2)) * li
                got = True

        # F2: '<n> pieces of <dim> ... - <len> long' plus trailing ', <n> pieces - <len>'
        if not got:
            for m in re.finditer(r"(\d+)\s*pieces?\b[^,;]{0,40}?[-–:]\s*"
                                 r"([\d./\s'\"]{1,14}?)\s*(?:long|\b)", s, re.I):
                li = _len_in(m.group(2))
                if li and 6 <= li <= 700:
                    lumber[dim] = lumber.get(dim, 0.0) + int(m.group(1)) * li
                    got = True

        # F3: '<n>  <dim>  <len>'  (leading count, tabular)
        if not got:
            m = re.match(r"^\s*(\d+)\s+" + dim.replace("x", r"\s*x\s*") +
                         r"\s+([\d'\"\-/\s]{1,12}?)\s{2,}", s, re.I)
            if m:
                li = _len_in(m.group(2))
                if li and 6 <= li <= 700:
                    lumber[dim] = lumber.get(dim, 0.0) + int(m.group(1)) * li
                    got = True

        # F4: '<code> <dim> <desc> <len>  <count>'  (trailing count, tabular)
        if not got:
            m = re.search(r"([\d]+\s*'\s*-?\s*\d*\s*\"?|\d+\s*(?:ft|feet|\"))\s{1,}(\d{1,3})\s*$", s, re.I)
            if m:
                li = _len_in(m.group(1))
                if li and 6 <= li <= 700:
                    lumber[dim] = lumber.get(dim, 0.0) + int(m.group(2)) * li
                    got = True

        if not got:
            unread += 1
    return lumber, sheets, unread


# --------------------------------------------------------------------------- derive

def geom(rec):
    """Pull the numbers a take-off needs out of a record. Returns None if footprint is unusable."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*$", str(rec.get("footprint", "")))
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    depth, length = min(a, b), max(a, b)          # depth = the shorter span
    g = dict(depth_ft=depth, length_ft=length, sqft=a * b)

    whf = str(rec.get("wall_height", ""))
    # "not stated (Behm lists ... 9')" must NOT yield a 9 ft wall — a hedged field is no field
    hedged = re.match(r"^\s*(not stated|unknown|n/a|none)", whf, re.I)
    wh = None if hedged else re.search(r"(\d+)\s*(?:'|ft|feet)[\s-]*(\d+)?", whf)
    g["wall_ft"] = (float(wh.group(1)) + (float(wh.group(2) or 0) / 12.0)) if wh else 8.0
    g["wall_assumed"] = not bool(wh)

    pm = re.search(r"(\d+)\s*[:/]\s*12", str(rec.get("roof", "")))
    style = str(rec.get("style_group", ""))
    if pm:
        g["pitch"] = float(pm.group(1)) / 12.0
    elif "lean-to" in style or "pole barn" in style:
        g["pitch"] = 2 / 12
    elif "gambrel" in style:
        g["pitch"] = None                          # gambrel is two slopes; handled separately
    else:
        g["pitch"] = 4 / 12
    g["pitch_assumed"] = not bool(pm)

    def spacing(field, default=16.0):
        m = re.search(r"(\d+)\s*\"?\s*(?:o\.?c\.?|on cent)", str(rec.get(field, "")), re.I)
        v = float(m.group(1)) if m else default
        return v if 8.0 <= v <= 48.0 else default      # anything else is a misparse
    g["stud_oc"] = spacing("wall_framing")
    g["joist_oc"] = spacing("floor_framing")
    g["style"] = style
    g["enclosure"] = str(rec.get("enclosure", ""))
    g["has_floor"] = not re.search(r"\bnone\b|no floor|posts? in ground|slab",
                                   str(rec.get("floor_framing", "")) + str(rec.get("foundation", "")), re.I)
    return g


def derive(rec):
    """A quantity take-off. Returns (lines, totals) where lines carry their own reasoning."""
    g = geom(rec)
    if not g:
        return None, None
    D, L, W = g["depth_ft"], g["length_ft"], g["wall_ft"]
    lines, tot = [], {}

    def add(label, dim, count, length_in, why, conf):
        tot[dim] = tot.get(dim, 0.0) + count * length_in
        lines.append(dict(label=label, dim=dim, count=count, length_in=round(length_in, 1),
                          why=why, conf=conf))

    slatted = "slatted" in g["enclosure"]
    roofonly = g["enclosure"].startswith("Roof only")
    openfront = g["enclosure"].startswith("Open front")

    # ---- floor
    if g["has_floor"]:
        joists = ceil(L * 12 / g["joist_oc"]) + 1
        add("Floor joists", "2x6", joists, D * 12 - 3,
            f"{L:.0f} ft run at {g['joist_oc']:.0f}\" OC, cut to the {D:.0f} ft depth less two rims", "high")
        add("Rim joists", "2x6", 2, L * 12,
            "one each side, running the length", "high")
        if slatted:
            pitch = 3.5 + 0.875                    # 2x4 slat + the published 7/8" gap
            add("Floor slats (gapped)", "2x4", ceil(L * 12 / pitch), D * 12,
                f"3-1/2\" board + 7/8\" gap = {pitch:.3f}\" pitch (published for this family)", "high")
        else:
            add("Floor sheathing", "sheet", ceil(g["sqft"] / 32.0), 0,
                "3/4\" T&G at 32 sq ft per 4x8 sheet", "high")
        add("Skids", "4x4", max(3, ceil(L / 3.0)), D * 12,
            "one skid roughly every 3 ft of length, running the depth", "medium")

    # ---- walls
    if roofonly:
        posts = 2 * (ceil(L / 10.0) + 1)
        add("Posts", "6x6", posts, W * 12,
            f"two rows of {posts // 2} at about 10 ft centres — no walls to carry load", "medium")
        add("Top plates / beams", "6x6", 2, L * 12, "one beam line per post row", "medium")
        add("Knee braces", "6x6", posts * 2, 30, "two per post", "low")
    elif openfront or slatted:
        rise = D * 12 * (g["pitch"] or 2 / 12)
        posts = 3 * (ceil(L / 10.0) + 1)
        add("Posts (front tall, back short)", "4x4", posts, W * 12,
            f"3 depth lines x {ceil(L / 10.0) + 1} along the length; front posts taller by "
            f"{rise:.0f}\" for the {12 * (g['pitch'] or 2/12):.0f}:12 slope", "medium")
        add("Support beams", "4x8", 3 * ceil(L / 10.0), 120,
            "3 beam lines along the length, in 10 ft pieces", "medium")
        add("Knee braces", "4x4", posts, 36, "one per post", "low")
        if slatted:
            sp = 5.5 + 2.25                        # 1x6 + the published 2-1/4" gap
            back_rows = ceil(W * 12 / sp)
            side_rows = ceil((W * 12 + rise / 2) / sp)
            add("Wall slats - back", "1x6", back_rows, L * 12,
                f"5-1/2\" board + 2-1/4\" gap = {sp:.2f}\" pitch over a {W*12:.0f}\" wall", "medium")
            add("Wall slats - two sides", "1x6", side_rows * 2, D * 12,
                "sides taper with the roof slope; averaged", "low")
        else:
            wall_area = (L + 2 * D) * W
            add("Wall studs", "2x4", ceil((L + 2 * D) * 12 / g["stud_oc"]) + 6, W * 12,
                f"three walls at {g['stud_oc']:.0f}\" OC plus corners", "medium")
            add("Siding", "sheet", ceil(wall_area / 32.0), 0, "three walls at 32 sq ft per sheet", "medium")
    else:
        perim = 2 * (L + D)
        add("Wall studs", "2x4", ceil(perim * 12 / g["stud_oc"]) + 8, W * 12,
            f"{perim:.0f} ft perimeter at {g['stud_oc']:.0f}\" OC plus corners and openings", "medium")
        add("Plates (1 bottom + 2 top)", "2x4", 3, perim * 12,
            "single bottom plate, double top plate", "high")
        add("Siding", "sheet", ceil(perim * W / 32.0), 0,
            f"{perim * W:.0f} sq ft of wall at 32 sq ft per sheet", "medium")

    # ---- roof
    if "gambrel" in g["style"]:
        slope_in = D * 12 * 0.78                   # both slopes of a gambrel, empirically ~1.56x half-span
        n = ceil(L * 12 / 24.0) + 1
        add("Gambrel truss chords", "2x6", n * 4, slope_in / 2 + 6,
            f"{n} trusses at 24\" OC, 4 chords each (two slopes per side)", "low")
        add("Truss gussets", "sheet", ceil(n / 5.0), 0, "plywood gussets, ~5 trusses per sheet", "low")
        roof_area = L * (D * 1.30)
    else:
        p = g["pitch"] or 4 / 12
        run = D / 2 if not (roofonly or openfront or slatted) else D
        slope_in = math.hypot(run * 12, run * 12 * p)
        n = ceil(L * 12 / 24.0) + 1
        mult = 2 if run == D / 2 else 1            # gable needs a pair per bay
        add("Rafters", "2x6", n * mult, slope_in + 12,
            f"{n} bays at 24\" OC{' x2 for the gable pair' if mult == 2 else ''}; "
            f"slope length {slope_in:.0f}\" + 12\" overhang", "medium")
        roof_area = L * (D * math.hypot(1, p) if run == D else D * math.hypot(1, p))

    if slatted or roofonly:
        add("Purlins", "2x4", 8, L * 12, "8 purlin lines up the slope (metal roofing needs no deck)", "medium")
        add("Metal roofing 3'x8'", "sheet", ceil(L / 3.0) * 2 + 2,
            0, f"{ceil(L / 3.0)} columns across the length x 2 courses up the slope, + lap", "high")
    else:
        add("Roof sheathing", "sheet", ceil(roof_area / 32.0), 0,
            f"{roof_area:.0f} sq ft of roof at 32 sq ft per sheet", "medium")
        add("Shingles (squares)", "square", ceil(roof_area / 100.0) + 1, 0,
            "roof area in 100 sq ft squares, + waste", "medium")
    return lines, tot


# --------------------------------------------------------------------------- scoring

def load_plans():
    return json.load(open(os.path.join(ROOT, "data", "plans.json")))


def calibrate():
    d = load_plans()
    P = [p for p in d["plans"] if not p.get("disqualified") and p.get("kind") != "reference"]
    have = [p for p in P if len(p.get("lumber_list") or []) >= 8]
    print(f"calibration set: {len(have)} records with a published list\n")

    ratios, unread_tot, parsed_ok, by_style = {}, 0, 0, {}
    for p in have:
        actual, sheets, unread = parse_list(p["lumber_list"])
        unread_tot += unread
        if not actual:
            continue
        parsed_ok += 1
        lines, pred = derive(p)
        if not pred:
            continue
        style = p.get("style_group", "?")
        for dim, act_in in actual.items():
            pr = pred.get(dim)
            if not pr or act_in < 120:            # ignore trivia
                continue
            r = pr / act_in
            ratios.setdefault(dim, []).append(r)
            by_style.setdefault(style, []).append(r)

    print(f"parsed {parsed_ok}/{len(have)} lists into quantities ({unread_tot} lines unreadable)\n")
    print(f"{'MATERIAL':<10}{'N':>4}  {'median pred/actual':>19}  {'spread (p25-p75)':>20}  verdict")
    print("-" * 78)
    summary = {}
    for dim in sorted(ratios, key=lambda k: -len(ratios[k])):
        v = sorted(ratios[dim])
        if len(v) < 4:
            continue
        med = statistics.median(v)
        p25, p75 = v[len(v) // 4], v[(3 * len(v)) // 4]
        err = abs(med - 1)
        verdict = ("good" if err < 0.25 and (p75 / max(p25, .01)) < 2.5 else
                   "usable" if err < 0.6 else "poor")
        summary[dim] = dict(n=len(v), median=round(med, 2), p25=round(p25, 2),
                            p75=round(p75, 2), verdict=verdict)
        print(f"{dim:<10}{len(v):>4}  {med:>19.2f}  {p25:>9.2f}-{p75:<10.2f}  {verdict}")

    print(f"\n{'STYLE':<26}{'N':>4}  median")
    print("-" * 44)
    for st in sorted(by_style, key=lambda k: -len(by_style[k])):
        v = by_style[st]
        if len(v) < 4:
            continue
        print(f"{st[:25]:<26}{len(v):>4}  {statistics.median(v):.2f}")

    json.dump(summary, open(os.path.join(ROOT, "tools", "cutlist_calibration.json"), "w"), indent=1)
    print("\nwrote tools/cutlist_calibration.json")
    return summary


def apply():
    """Two tiers, because the calibration says they deserve very different confidence.

    TIER 1 family-calibrated: the MyOutdoorPlans slatted-firewood family. Same author, same design
      language, and three siblings (12x12, 12x30, 12x36) publish COMPLETE lists for free. The
      published design rules (16" OC joists, 7/8" floor gaps, 2-1/4" slat gaps, 3'x8' metal, 2:12)
      let the geometry be reproduced, and spot-checks land exactly on the siblings' sheet and row
      counts. Safe to call a take-off.

    TIER 2 generic: everything else. Measured against 38 published lists, a footprint-only take-off
      lands within about a factor of two. That is a lumber BUDGET, not a cut list, and it says so.
    """
    cal_path = os.path.join(ROOT, "tools", "cutlist_calibration.json")
    cal = json.load(open(cal_path)) if os.path.exists(cal_path) else {}
    d = load_plans()
    P = [p for p in d["plans"] if not p.get("disqualified") and p.get("kind") != "reference"]
    need = [p for p in P if len(p.get("lumber_list") or []) < 8]

    band = ", ".join(f"{k} runs {v['median']:.2f}x actual (p25-p75 {v['p25']:.2f}-{v['p75']:.2f})"
                     for k, v in sorted(cal.items()) if v.get("n", 0) >= 4)
    n_cal = max([v.get("n", 0) for v in cal.values()] or [0])

    out, skipped, tiers = {}, [], {"family": 0, "generic": 0}
    for p in need:
        lines, tot = derive(p)
        if not lines:
            skipped.append((p["slug"], "no usable footprint to derive from"))
            continue
        g = geom(p)
        family = ("slatted" in g["enclosure"]
                  and re.search(r"myoutdoorplans|howtospecialist", str(p.get("vendor", "")), re.I))
        tier = "family" if family else "generic"
        tiers[tier] += 1

        caveats = []
        if g["wall_assumed"]:
            caveats.append("wall height is NOT published — 8 ft assumed")
        if g["pitch_assumed"] and "gambrel" not in g["style"]:
            caveats.append(f"roof pitch is NOT published — {12*g['pitch']:.0f}:12 assumed from the style")
        if "gambrel" in g["style"]:
            caveats.append("gambrel truss chords are the weakest line here — two slopes and a "
                           "knee-wall geometry that a footprint alone does not pin down")

        rendered = []
        for ln in lines:
            c = cal.get(ln["dim"], {})
            conf = ln["conf"]
            if tier == "generic" and conf == "high":
                conf = "medium"          # the calibration does not support "high" generically
            note = ""
            if c.get("n", 0) >= 4:
                note = (f"; across {c['n']} published lists this method runs {c['median']:.2f}x "
                        f"actual for {ln['dim']} (p25-p75 {c['p25']:.2f}-{c['p75']:.2f}, {c['verdict']})")
            qty = f"{ln['count']} @ {ln['length_in']:.0f}\"" if ln["length_in"] else f"{ln['count']}"
            rendered.append(f"{ln['label']} — {ln['dim']} — {qty} [confidence: {conf}]"
                            f" — {ln['why']}{note}")

        if tier == "family":
            note = (
                "DERIVED, not the author's cut list — that is behind their premium unlock. Computed "
                "from the design rules this plan family publishes free (2x6 joists at 16\" OC, 7/8\" "
                "floor-slat gaps, 1x6 walls with 2-1/4\" gaps, 2:12 lean-to, 3'x8' metal roofing) and "
                "calibrated against the COMPLETE free lists of its 12x12, 12x30 and 12x36 siblings by "
                "the same author. Spot-checks reproduce the siblings' roofing sheet counts and floor-slat "
                "row counts. Good enough to price and order lumber; the notched-post, brace and "
                "birdsmouth layout is still yours to do. Buy the premium plan before cutting — it is a "
                "few dollars and it pays the designer."
            )
        else:
            note = (
                "BUDGET ESTIMATE, NOT A CUT LIST. This is a quantity take-off computed from footprint, "
                f"wall height and roof geometry only. Scored against {n_cal} published materials lists "
                f"in this collection, it lands within roughly a FACTOR OF TWO: {band}. Use it to sanity-check "
                "a lumber budget or compare two designs — do not order or cut from it. The vendor's own "
                "list is the only reliable source, and for most of these records that means buying the plan."
            )
        out[p["slug"]] = dict(derived_lumber_list=rendered, derived_caveats=caveats,
                              derived_tier=tier, derived_list_note=note)

    json.dump(out, open(os.path.join(ROOT, "tools", "derived.json"), "w"), indent=1)
    print(f"derived {len(out)} lists — {tiers['family']} family-calibrated, {tiers['generic']} generic budget")
    print(f"skipped {len(skipped)}:")
    for s_, why in skipped:
        print(f"  {s_}: {why}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "calibrate"
    (calibrate if cmd == "calibrate" else apply)()
