# Research notes (gaps report and channel notes)


---

## 1. Categories missing entirely

1. **Metal / steel building kits — zero records.** A 20x20 or 16x24 steel garage kit is the cheapest per-sq-ft option in this size band and is a genuine alternative to a wood 16x20. Absent: VersaTube, Mueller Inc., General Steel, Absolute Steel, Carport Central / Eagle Carports (vertical-roof steel garages), Pioneer/Olympia. Only one steel record exists anywhere (Arrow Murryhill 12x24) and it was dropped.
2. **Shipping-container conversion — zero records.** A 40 ft container is 8x40 = 320 sq ft, an exact footprint match, and container workshop/studio conversion plan sets exist. Not a single record.
3. **SIP / panelized / structural-panel kits — zero.** No Premier SIPS, Extreme Panel Technologies, Enercept, no steel-stud. Panelized whole-kit DIY is represented only by Best Barns/EZ-Fit (pre-cut lumber), not true panel systems.
4. **Lumberyard post-frame material packages with free plans — zero live records.** Menards post-frame project packages, Sutherlands, Carter Lumber, 84 Lumber, Do It Best. The only two attempts (Menards, Sutherlands) were dropped, and the Menards one is a 2015 Wayback URL. These packages come *with* plans and a real 2026 price, which is exactly what the user needs.
5. **Permit / engineer-stamped plan services — zero.** At 320 sq ft, nearly every US jurisdiction requires a permit (thresholds are typically 120–200 sq ft), so "will this set get approved, and can I get a stamp?" is the gating question. Nobody looked at 24hplans.com or equivalent per-state stamping services.
6. **Material-manufacturer free engineered plans — zero.** APA – The Engineered Wood Association, Simpson Strong-Tie (shed/garage plans plus prescriptive hardware schedules), LP SmartSide, Weyerhaeuser. These are free, credible, and code-referenced — the ideal counterweight to the 1935–1949 USDA sheets.
7. **CAD / SketchUp / editable-model sources — zero.** No 3D Warehouse, GrabCAD, Etsy digital plans, and no record captures whether *any* plan ships DWG/SKP/Revit files. Plan+3D-model bundles exist (Den Outdoors, Studio Home) but both were dropped.
8. **Non-US sources — zero.** CA (Summerwood, Backyard Products Canada; Cedarshed dropped), AU/NZ (Stratco, Fair Dinkum Sheds, Best Sheds, Spanbilt — metric 6x6 m ≈ 388 sq ft is in range), UK (Dunster House, Tuin, Power Sheds garden workshops).
9. **Extension/government plan libraries other than NDSU.** 8 of the 30 records and ~10 dropped ones are all NDSU — a single-source monoculture. Missing: Oklahoma State, Virginia Cooperative Extension, Univ. of Tennessee, Purdue/MWPS catalog proper, Alberta Agriculture, Canada Plan Service, LSU (dropped).
10. **Timber-frame / post-and-beam beyond Jamaica Cottage Shop.** No Country Carpenters/The Barn Yard, Barn Pros, Timber Frame HQ, Vermont Frames, Shelter Institute, Shelter-Kit.
11. **Amish/Mennonite builder kit lines beyond Sheds Unlimited** (Pine Creek Structures, Horizon Structures, Weaver Barns, Glick Woodworks, Stoltzfus, Backyard Unlimited) — several now sell DIY kit versions of assembled buildings.
12. **Big-box DIY kit SKUs.** Handy Home Products, Heartland/Backyard Products, Yardline, Backyard Discovery — sold through HD/Lowe's, 12x20–16x24 exists, and only one Home Depot URL appears (dropped).
13. **Build-documentation as a category** (only 2 YouTube entries, both dropped) — this is the sole realistic route to true 2026 costs.
14. **Adaptive/repurpose plans**: garage-conversion, carport-enclosure, small barndominium shells, greenhouse hybrids. None.

## 2. Specific unreached vendors + verified URL status

Verified this session (curl, desktop UA):

| Vendor | URL | Status |
|---|---|---|
| Handy Home Products | https://handyhome.com/ | **200 live** (222 KB). Not Shopify (`/products.json` 404); use `/sitemap.xml` → `page-sitemap.xml`. Never reached. |
| Backyard Products / Heartland | https://www.backyardbuildings.com/ | **200 live**, title "Wooden Sheds \| Wood Storage Sheds \| Heartland Sheds". Never reached. |
| Pine Creek Structures | https://www.pinecreekstructures.com/ | **200 live** (251 KB). Never reached. |
| Mueller Inc (steel) | https://www.muellerinc.com/ | **200 live** (134 KB). Note: `mueller-inc.com` is dead (000). |
| Summerwood Products (CA) | https://www.summerwood.com/products/sheds | **200 live**; sitemap is a 2018-era perl-generated index, pricing page at `/products/sheds-pool-studios/pricing`. |
| Tuff Shed | https://www.tuffshed.com/products/ | **200 live**. |
| The Barn Yard / Country Carpenters | https://www.thebarnyardstore.com/ | **200 live**. |
| Menards post-frame | https://www.menards.com/main/c-9893.htm | **200 live** — contradicts the assumption that Menards is unreachable; the deep `/farm-ranch/post-frame-building-packages/c-13288.htm` path 404s, so re-crawl from c-9893. |
| SketchUp 3D Warehouse | https://3dwarehouse.sketchup.com/search/?q=16x20+shed | **200** (JS-rendered; needs the JSON API). |
| Shelter-Kit | https://www.shelter-kit.com/ | **200 live**; product list at `/dynamic-kits_p_b911e8e4…-sitemap.xml` (34 kits). Verified `/kits/emily-kit` = 24x24, **$67,700** — house-scale, so likely out of budget scope even though in footprint range. |
| Ana White | https://www.ana-white.com/woodworking-projects/shed | 200 but "Plan Not Found" — needs the correct category path. |
| Construct101 | https://www.construct101.com/shed-plans/ | **403 to curl, WebFetch works.** I enumerated its full `product-sitemap.xml`: largest plan is **12x16 (192 sq ft)**. → **Verified dead end, do not re-chase** (despite 16x20/12x20 *forum threads* showing up in CDX). |
| Canada Plan Service | http://www.cps.gov.on.ca/english/plans.htm | **Dead (000) and never archived** (Wayback 404). `canadaplan.ca` returns 200 but a 114-byte stub. → CPS plans must be found on university mirrors, not the origin. |
| Cloudflare-403 but live, use Wayback | 24hplans.com/shed-plans/, timberframehq.com, extension.okstate.edu/programs/building-plans/, stratco.com.au, versatube.com, lelandsbarns.com, etsy.com | all 403/JS-challenge — reachable only via Wayback or WebFetch. |
| 404 on guessed path, site alive | horizonstructures.com/sheds/, barnpros.com/collections/barn-kits, 84lumber.com/products/sheds/, architecturaldesigns.com/…/garage-plans, absolutesteel.com/steel-buildings/garages/ | re-derive paths from each sitemap. |

Also never touched and worth adding: General Steel, Carport Central, Eagle Carports, Premier SIPS, Extreme Panel, Enercept, Carter Lumber, Do It Best, APA (apawood.org), Simpson Strong-Tie (strongtie.com), Weaver Barns, Glick Woodworks, Stoltzfus Structures, Backyard Unlimited, Yardline, Backyard Discovery, Dunster House, Tuin, Fair Dinkum Sheds, Best Sheds, Spanbilt, Shelter Institute, Vermont Frames, RR Buildings / Perkins Builder Brothers (YouTube cost data).

## 3. Records that look factually shaky

1. **Sheds Unlimited pricing is internally implausible across all three records.** MaxiBarn 12x20 $6,741 → 14x20 $8,453 → **16x20 $14,170**: a 68% price jump for a 14% area increase. Same shape on Classic Workshop ($14,795 for 16x20 vs a line "starting at" ~$7k) and Standard Workshop Garage ($15,303). All three records also admit the vendor's own peak-height table **stops at 15'6" wide** — strong evidence the "16×20" column is a different product tier (assembled building, or garage line), not the kit. Re-verify before publishing; this is the largest price error risk in the set.
2. **Four Best Barns records cover two products, and they contradict each other.** One says shedkitstore.com "is not a third-party reseller — it is the manufacturer's own web store"; two others call it an "authorized Best Barns dealer." Handcrafted Homestead XL 16x20 and Maker's Loft XL 16x20 are both quoted at **exactly $11,190 / $12,740** with different SKUs (HHOMND20 vs MLOFND20), and the same $1,550 upgrade is called a "shingle roof package" in one record and a "metal roof package" in another. Two of these four slots are wasted duplicates.
3. **Three records don't meet the target at all and should be reclassified or dropped**, freeing slots: USDA 5625 (a 1949 gambrel *rafter cross-section*, no length/floor plan/sq ft — the record itself says so), USDA 5491 (earth-banked root cellar), and Hansen Pole Buildings (a blog Q&A about a 50x70 commercial building, no plan, no price, and Hansen's minimum is 576 sq ft).
4. **iCreatables has a demonstrated CDN cache-bleed problem.** One record documents Imperva serving the 16x20 Modern Studio page under the Gambrel URL; the 16x20-B record notes a "G-vs-B naming inconsistency" and a stray "overhead door" heading — the same signature. Since all six iCreatables prices come from mapping an on-page Shopify buy-button product ID to `products.json`, a cache mix-up would silently attach the wrong price/spec to the wrong plan. Every iCreatables record needs one cache-busted re-fetch.
5. **Jamaica Cottage Shop 16x20 Loft Barn: price is ~2 years stale** ($14,118 from a 2024-05-28 "Cabin Fever SALE" snapshot, site permanently 403). Publishing that as a 2026 price is misleading; also duplicates the dropped JCS "16x20 Barn" entry.
6. **Behm 320-1's style/kind field is corrupted** — it literally contains a reviewer's note ("Non-engineered / prescriptive permit drawing set. The value contradicts the vendor…"). That will render on the website as-is. Price ($299 PDF / $309 paper) is also 5–10x every other shed plan in the set and deserves a second read.
7. **Naming collision waiting to mislead users:** Best Barns' factory model name for the Handcrafted Homestead XL 16x20 is given as "Richmond," and Ashland Barns' $50 plan is also called "Richmond." Unrelated products, adjacent rows.
8. **Houseplans.com 23-2749** — the record itself says the site "sometimes serves a different plan's HTML on a concurrent request." Marked CONFIRMED, but confirmation rests on a server known to be nondeterministic.
9. **Shedplans.org (Mediage LLC) 16x20 at $19.99** — the researcher found a *free* 19-page PDF of the same design. That points at recycled/relicensed content; authorship and what the $19.99 actually buys are unverified.
10. **HowToSpecialist 16x20 gable** carries an unresolved 192-vs-240-inch cut-list contradiction (a real build-blocking error, not a metadata nit), and the **HowToSpecialist 16x20 pole barn appears twice** as two separate records.

## 4. The thin data field(s)

**#1 gap: nobody produced a real 2026 build cost for a single plan.** Kit prices are well captured ($11k–$20k), but for all 15 plan records the actual decision — "plans cost $30, so what will the lumber bill be?" — is unanswered. Several researchers *downloaded and parsed the materials lists* and still never priced them. One priced list (16x20 gambrel, at current Menards/HD/Lowe's unit prices) would be the single most decision-relevant artifact on the website, and it makes the $59.99 plan vs $11,190 kit comparison possible.

**#2: permit-readiness / engineering.** Almost nothing captures: is the set engineer-stamped or stampable; what snow/wind loads it's designed to; whether trusses are engineered (only Houseplans and Best Barns' permit sets say); which IRC edition it references; whether a jurisdiction will accept it for a 320 sq ft structure. For a build this size that's the difference between buildable and not.

**#3: overall height.** Listed as "unknown" in ~8 records, yet many jurisdictions permit-exempt or height-cap at 15 ft, and Behm even tags plans "Under 15' High." Every gambrel option is at risk here and none of them state it.

**#4: loft usability.** "Has a loft" is captured; loft *headroom*, floor loading, and whether stairs are included/designed are inconsistent — and one Best Barns record flags an outright "stairs-included contradiction." For a 16x20 gambrel this is the main reason to choose it.

**Also thin:** page/sheet count, build time, crew size and skill level (soft in most records); door opening width and overhead-door option (can a vehicle/tractor fit?); foundation options offered (skid vs pier vs slab) and frost-depth guidance; whether a materials list is included (should be a hard boolean, not prose); license/redistribution and refund terms (present only where Gumroad exposes them); kit shipping cost, lead time, and whether the floor is included; and a normalized **$/sq ft** and **cost-to-complete** column so the site can sort free-plan, paid-plan and kit options against each other at all.
