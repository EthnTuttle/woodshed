/* Woodshed — local shed-plan browser. No dependencies; reads data/plans.json. */

const KINDS = [
  { key: 'free-plan',       label: 'Free plan',       slot: 1 },
  { key: 'paid-plan',       label: 'Paid plan',       slot: 2 },
  { key: 'kit',             label: 'Kit',             slot: 3 },
  { key: 'engineered-plan', label: 'Engineered/free', slot: 4 },
  { key: 'video-build',     label: 'Video build',     slot: 5 },
  { key: 'plan-bundle',     label: 'Bundle',          slot: 6 },
  { key: 'reference',       label: 'Reference',       slot: 7 },
];
const isOption = r => r.kind !== 'reference';   // reference docs aren't build options
const kindMeta = k => KINDS.find(x => x.key === k) || { key: k || 'other', label: k || 'Other', slot: 0 };
const kindColor = k => { const s = kindMeta(k).slot; return s ? `var(--series-${s})` : 'var(--text-muted)'; };

const SEQ = ['var(--seq-250)', 'var(--seq-400)', 'var(--seq-450)', 'var(--seq-550)', 'var(--seq-650)'];

const state = {
  all: [], meta: {}, view: 'cards', onlyPinned: false,
  kinds: new Set(), q: '', foot: '', style: '', loft: '', price: '', enc: '', sort: 'pick', showExcluded: false,
  pinned: new Set(JSON.parse(localStorage.getItem('woodshed.pins') || '[]')),
};

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const has = v => v != null && String(v).trim() !== '' && !/^(not stated|unknown|n\/a|none stated|-)$/i.test(String(v).trim());
const savePins = () => localStorage.setItem('woodshed.pins', JSON.stringify([...state.pinned]));

/* ---------- price helpers ---------- */
function priceNum(r) {                       // -1 = unknown, 0 = free
  if (typeof r.price_usd === 'number' && r.price_usd >= 0) return r.price_usd;
  if (typeof r.price_usd === 'number' && r.price_usd < 0) return -1;
  if (/^free$/i.test(String(r.price || ''))) return 0;
  const m = String(r.price || '').match(/\$\s?([\d,]+(?:\.\d{2})?)/);
  return m ? parseFloat(m[1].replace(/,/g, '')) : -1;
}
function priceHTML(r) {
  const n = priceNum(r);
  if (n === 0) return '<span class="price free">Free</span>';
  if (n < 0) return `<span class="price unknown">${esc(has(r.price) ? r.price : 'Price not published')}</span>`;
  return `<span class="price">$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>`;
}
const shortCords = v => {
  const m = String(v || '').match(/~?\s*[\d.]+(?:\s*[–-]\s*[\d.]+)?\s*cords?/i);
  return m ? m[0].replace(/\s+/g, ' ').trim() : '';
};
const hasLoft = r => /\b(yes|loft)\b/i.test(String(r.loft || '')) && !/^(no|none)\b/i.test(String(r.loft || '').trim());

/* ---------- verification chip ---------- */
function verifyBadge(r) {
  const v = String(r.verified || '').toUpperCase();
  const map = {
    CONFIRMED: ['Source checked', 'var(--good)'],
    PARTIAL: ['Partly checked', 'var(--warning)'],
    UNSUPPORTED: ['Claims unverified', 'var(--serious)'],
    DEAD_LINK: ['Link dead', 'var(--critical)'],
    UNVERIFIED_SELF: ['Read from source', 'var(--series-1)'],
  };
  const [label, color] = map[v] || ['Unchecked', 'var(--text-muted)'];
  const icon = { CONFIRMED: '✓', PARTIAL: '◐', UNSUPPORTED: '!', DEAD_LINK: '✕', UNVERIFIED_SELF: '◍' }[v] || '·';
  return `<span class="badge status" style="color:${color}">${icon} ${label}</span>`;
}

/* ---------- data load ---------- */
async function load() {
  let payload;
  try {
    payload = await (await fetch('data/plans.json', { cache: 'no-store' })).json();
  } catch (e) {
    $('#grid').innerHTML = `<div class="empty">Could not load <code>data/plans.json</code>.<br>
      Serve this folder over HTTP (<code>python3 -m http.server</code>) rather than opening the file directly.</div>`;
    return;
  }
  state.all = (payload.plans || []).slice();
  state.meta = payload.meta || {};
  $('#asof').textContent = state.meta.compiled_at ? `data compiled ${state.meta.compiled_at}` : '';
  buildKindChips();
  const pool0 = state.all.filter(r => !r.disqualified);
  fillSelect('#fFoot', uniq(pool0.map(r => r.footprint)).sort(footSort));
  fillSelect('#fStyle', uniq(pool0.map(r => prettyStyle(r))).sort());
  renderKpis();
  renderPicks();
  renderNotice();
  renderFooter();
  wire();
  render();
}
const uniq = a => [...new Set(a.filter(has).map(s => String(s).trim()))];
const sqftOf = s => { const m = String(s).match(/(\d+)\s*[x×]\s*(\d+)/i); return m ? +m[1] * +m[2] : 0; };
const footSort = (a, b) => sqftOf(a) - sqftOf(b);
const prettyStyle = r => (r && typeof r === 'object')
  ? (r.style_group || String(r.style || '').split(/[,;/]/)[0].trim() || 'other')
  : (String(r || '').split(/[,;/]/)[0].trim() || 'other');

function fillSelect(sel, vals) {
  const el = $(sel);
  vals.forEach(v => { const o = document.createElement('option'); o.value = v; o.textContent = v; el.appendChild(o); });
}

function buildKindChips() {
  const pool = state.all.filter(r => !r.disqualified);
  const present = KINDS.filter(k => pool.some(r => r.kind === k.key));
  $('#kindChips').innerHTML = present.map(k => {
    const n = pool.filter(r => r.kind === k.key).length;
    return `<button class="chip" type="button" aria-pressed="false" data-kind="${k.key}">
      <span class="dot" style="background:${kindColor(k.key)}"></span>${esc(k.label)} ${n}</button>`;
  }).join('');
}

/* ---------- KPI row (bare stat tiles — no sparklines) ---------- */
function renderKpis() {
  const all = state.all.filter(r => !r.disqualified && isOption(r));
  const freePlans = all.filter(r => priceNum(r) === 0 && /^(free-plan|engineered-plan|plan-bundle)$/.test(r.kind));
  const freeVideos = all.filter(r => priceNum(r) === 0 && r.kind === 'video-build').length;
  const free = freePlans.length;
  const priced = all.map(priceNum).filter(n => n > 0);
  const cheapest = priced.length ? Math.min(...priced) : null;
  const lofts = all.filter(hasLoft).length;
  const foots = uniq(all.map(r => r.footprint)).length;
  const tiles = [
    { label: 'Options', value: all.length, sub: `${uniq(all.map(r => r.vendor)).length} distinct sources` },
    { label: 'Free plan sets', value: free, sub: freeVideos ? `plus ${freeVideos} free video build series` : `${all.length - free} cost money` },
    { label: 'Cheapest paid set', value: cheapest == null ? '—' : `$${cheapest}`, sub: priced.length ? `${priced.length} with published prices` : 'no published prices' },
    { label: 'Open-sided', value: all.filter(r => /^(Roof only|Open front)/.test(String(r.enclosure))).length,
      sub: `${all.filter(r => r.cord_capacity).length} rated in cords · ${lofts} with a loft` },
  ];
  $('#kpis').innerHTML = tiles.map(t =>
    `<div class="tile"><div class="label">${esc(t.label)}</div><div class="value">${esc(t.value)}</div><div class="sub">${esc(t.sub)}</div></div>`
  ).join('');
}

/* ---------- "Where to start": one pick per stated criterion, computed from the data ---------- */
const PICK_RULES = [
  {
    label: 'Best for firewood',
    why: 'Purpose-designed for wood storage: open front, slatted sides and a slatted floor over gravel, so air moves under and through the stack. Ranked by cords held.',
    filter: r => /slatted/.test(String(r.enclosure)) && r.cord_capacity,
    rank: r => (parseFloat((String(r.cord_capacity).match(/[\d.]+/) || [0])[0]) || 0),
  },
  {
    label: 'No walls at all',
    why: 'Roof on posts and nothing else — maximum airflow, but wind-driven rain reaches the stack from every side.',
    filter: r => /^Roof only/.test(String(r.enclosure)),
    rank: r => (r.pick_score || 0),
  },
  {
    label: 'Best free plan',
    why: 'Free, with the materials list published on the page rather than gated behind an upsell.',
    filter: r => priceNum(r) === 0 && r.kind !== 'kit' && r.kind !== 'video-build'
      && !/pole|post-frame/i.test(String(r.style_group)),
    rank: r => (/free-on-page/.test(String(r.materials_list_available)) ? 40 : 0) + (r.pick_score || 0),
  },
  {
    label: 'Best documented for the money',
    why: 'Cheapest paid set that still ships blueprints, a build guide and a materials list.',
    filter: r => priceNum(r) > 0 && priceNum(r) <= 120 && (r.includes || []).length >= 3,
    rank: r => (r.pick_score || 0) - priceNum(r) * 0.25,
  },
  {
    label: 'Most usable space',
    why: 'Largest interior once a loft is counted — the biggest jump in room per dollar of lumber.',
    filter: r => hasLoft(r) && r.kind !== 'video-build',
    rank: r => sqftOf(r.footprint) * 1.5 + (r.pick_score || 0) * 0.4,
  },
  {
    label: 'Easiest to permit',
    why: 'Engineered or institutionally published drawings, which plan reviewers accept far more readily than site-built trusses.',
    filter: r => r.kind === 'engineered-plan' || /engineer/i.test(String(r.roof) + String(r.includes || []).toString() + String(r.permit_notes)),
    rank: r => (r.kind === 'engineered-plan' ? 30 : 0) + (r.pick_score || 0),
  },
  {
    label: 'Cheapest to build',
    why: 'Lowest researched materials bill of everything priced here — post-frame skips the floor frame entirely.',
    filter: r => r.cost_estimate || /pole|post[\s-]?frame/i.test(String(r.style_group) + String(r.style)),
    // a real priced bill beats a guess: lowest researched materials cost wins outright
    rank: r => (r.cost_estimate ? 10000 - r.cost_estimate.total_low_usd : (priceNum(r) === 0 ? 20 : 0) + (r.pick_score || 0)),
  },
  {
    label: 'Watch someone build it first',
    why: 'A start-to-finish video series at this size — often more instructive than a plan sheet if you have not framed before.',
    filter: r => r.kind === 'video-build',
    rank: r => (r.pick_score || 0),
  },
];

function renderPicks() {
  const used = new Set();
  const picks = [];
  for (const rule of PICK_RULES) {
    const cands = state.all.filter(r => !r.disqualified && !r.price_doubt && isOption(r)).filter(rule.filter).filter(r => !used.has(r.slug));
    if (!cands.length) continue;
    const best = cands.sort((a, b) => rule.rank(b) - rule.rank(a))[0];
    used.add(best.slug);
    picks.push({ rule, r: best });
  }
  $('#startPanel').hidden = picks.length < 2;
  $('#picks').innerHTML = picks.map(({ rule, r }) => `
    <button class="pick" type="button" data-open="${esc(r.slug)}">
      <span class="pick-label">${esc(rule.label)}</span>
      <span class="pick-name">${esc(r.name)}</span>
      <span class="pick-meta">${esc(r.vendor)} · ${esc(r.footprint)}${sqftOf(r.footprint) ? ` · ${sqftOf(r.footprint)} sq ft` : ''} · ${priceNum(r) === 0 ? 'free' : priceNum(r) > 0 ? '$' + priceNum(r).toLocaleString() : 'price not published'}</span>
      <span class="pick-why">${esc(rule.why)}</span>
    </button>`).join('');
}

function renderFooter() {
  const m = state.meta, el = $('#footer');
  if (!el) return;
  const bits = [];
  if (m.publish) {
    bits.push(`<strong>What this is.</strong> A research index of DIY shed and firewood-shelter plans
      in the ~240–480 sq ft range. Every specification, price and quote is attributed to the vendor
      page it came from — follow the “Open the plan page” link on any record to buy or download from
      the source.`);
    if (m.assets_rehosted === false) {
      bits.push(`<strong>Nothing is rehosted.</strong> Vendor images, drawings and PDFs are
        deliberately not copied here; each record links back to its source. No plan sheets, cut
        lists or copyrighted drawings are redistributed.`);
    }
    bits.push(`<strong>No warranty.</strong> Specs and prices are only as current as the source page
      on ${esc(m.compiled_at || 'the compile date')}, some values are explicitly derived rather than
      published, and a structure this size normally needs a permit. Verify everything against the
      vendor and your local building department before you buy lumber or cut anything.`);
  }
  el.innerHTML = bits.map(b => `<p>${b}</p>`).join('');
  el.hidden = !bits.length;
}

function renderNotice() {
  const m = state.meta;
  const bits = [];
  if (m.note) bits.push(m.note);
  const shaky = state.all.filter(r => /UNSUPPORTED|DEAD_LINK/i.test(String(r.verified || ''))).length;
  if (shaky) bits.push(`${shaky} record${shaky > 1 ? 's' : ''} failed fact-checking and are flagged in the detail panel — read those before trusting them.`);
  $('#notice').innerHTML = bits.length
    ? `<strong>Read me.</strong> ${bits.map(esc).join(' ')}`
    : '';
  $('#notice').hidden = !bits.length;
}

/* ---------- filtering ---------- */
function filtered() {
  let rows = state.all.filter(r => state.showExcluded || !r.disqualified);
  if (state.onlyPinned) rows = rows.filter(r => state.pinned.has(r.slug));
  if (state.kinds.size) rows = rows.filter(r => state.kinds.has(r.kind));
  if (state.foot) rows = rows.filter(r => String(r.footprint).trim() === state.foot);
  if (state.style) rows = rows.filter(r => prettyStyle(r) === state.style);
  if (state.enc === 'open') rows = rows.filter(r => /^(Roof only|Open front)/.test(String(r.enclosure)));
  else if (state.enc) rows = rows.filter(r => String(r.enclosure) === state.enc);
  if (state.loft === 'yes') rows = rows.filter(hasLoft);
  if (state.loft === 'no') rows = rows.filter(r => !hasLoft(r));
  if (state.price === 'free') rows = rows.filter(r => priceNum(r) === 0);
  if (state.price === 'known') rows = rows.filter(r => priceNum(r) >= 0);
  if (state.price === '50') rows = rows.filter(r => { const n = priceNum(r); return n >= 0 && n < 50; });
  if (state.price === '200') rows = rows.filter(r => { const n = priceNum(r); return n >= 0 && n < 200; });
  if (state.q) {
    const q = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    rows = rows.filter(r => {
      const hay = JSON.stringify(r).toLowerCase();
      return q.every(t => hay.includes(t));
    });
  }
  const rank = r => (r.pick_score != null ? -r.pick_score : 0);
  const cmp = {
    pick: (a, b) => rank(a) - rank(b) || sqftOf(b.footprint) - sqftOf(a.footprint),
    'price-asc': (a, b) => norm(priceNum(a)) - norm(priceNum(b)),
    'price-desc': (a, b) => norm(priceNum(b)) - norm(priceNum(a)),
    'sqft-desc': (a, b) => sqftOf(b.footprint) - sqftOf(a.footprint),
    'sqft-asc': (a, b) => sqftOf(a.footprint) - sqftOf(b.footprint),
    vendor: (a, b) => String(a.vendor).localeCompare(String(b.vendor)),
  }[state.sort];
  const norm = n => (n < 0 ? Number.MAX_SAFE_INTEGER : n);   // unknown prices sort last either way
  return rows.sort(cmp);
}

/* ---------- render ---------- */
function render() {
  const rows = filtered();
  $('#count').textContent = `${rows.length} of ${state.all.length}`;
  $('#pinCount').textContent = state.pinned.size ? `(${state.pinned.size})` : '';
  $('#cardsView').hidden = state.view !== 'cards';
  $('#tableView').hidden = state.view !== 'table';
  $('#compareView').hidden = state.view !== 'compare';
  $('#vCards').classList.toggle('on', state.view === 'cards');
  $('#vTable').classList.toggle('on', state.view === 'table');
  $('#vCompare').classList.toggle('on', state.view === 'compare');
  renderCharts(rows);
  if (state.view === 'cards') renderCards(rows);
  if (state.view === 'table') renderTable(rows);
  if (state.view === 'compare') renderCompare();
}

function renderCards(rows) {
  if (!rows.length) { $('#grid').innerHTML = `<div class="empty">Nothing matches those filters.</div>`; return; }
  $('#grid').innerHTML = rows.map(r => {
    const img = has(r.image_local_path)
      ? `<img src="${esc(r.image_local_path)}" alt="${esc(r.name)}" loading="lazy" onerror="this.parentNode.innerHTML='<span class=\\'noimg\\'>no image saved</span>'">`
      : (r.image_was_local && has(r.image_source_url)
          ? `<a class="noimg srclink" href="${esc(r.image_source_url)}" target="_blank" rel="noopener nofollow"
               onclick="event.stopPropagation()">View image at source ↗</a>`
          : `<span class="noimg">${r.image_was_local ? 'image not rehosted' : 'no image saved'}</span>`);
    const km = kindMeta(r.kind);
    const specs = [
      ['Holds', shortCords(r.cord_capacity)],
      ['Walls', /not stated/i.test(String(r.enclosure)) ? '' : r.enclosure],
      ['Footprint', r.footprint],
      ['Style', prettyStyle(r)],
      ['Walls', r.wall_height],
      ['Loft', r.loft],
      ['Foundation', r.foundation],
    ].filter(([, v]) => has(v)).slice(0, 4);
    return `<article class="card" data-slug="${esc(r.slug)}">
      <div class="thumb">${img}
        <button class="pin ${state.pinned.has(r.slug) ? 'on' : ''}" type="button" data-pin="${esc(r.slug)}"
          title="Add to shortlist / compare" aria-label="Shortlist ${esc(r.name)}">${state.pinned.has(r.slug) ? '★' : '☆'}</button>
      </div>
      <div class="body">
        <div>
          <h3>${esc(r.name)}</h3>
          <div class="vendor">${esc(r.vendor)}</div>
        </div>
        <div class="badges">
          <span class="badge"><span class="dot" style="background:${kindColor(r.kind)}"></span>${esc(km.label)}</span>
          ${has(r.footprint) ? `<span class="badge">${esc(r.footprint)}${sqftOf(r.footprint) ? ` · ${sqftOf(r.footprint)} sq ft` : ''}</span>` : ''}
          ${shortCords(r.cord_capacity) ? `<span class="badge">${esc(shortCords(r.cord_capacity))}${/derived/i.test(String(r.cord_capacity)) ? ' est.' : ''}</span>` : ''}
          ${/^(Roof only|Open front)/.test(String(r.enclosure)) ? `<span class="badge">open-sided</span>` : ''}
          ${hasLoft(r) ? `<span class="badge">loft</span>` : ''}
          ${verifyBadge(r)}
          ${r.price_doubt ? `<span class="badge status" style="color:var(--serious)">! price in doubt</span>` : ''}
        </div>
        <dl class="spec">${specs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(trunc(v, 78))}</dd>`).join('')}</dl>
        <div class="foot">${priceHTML(r)}<button class="btn" type="button" data-open="${esc(r.slug)}">Details</button></div>
      </div>
    </article>`;
  }).join('');
}

function renderTable(rows) {
  $('#tbody').innerHTML = rows.map(r => `<tr>
    <td><span class="lname" data-open="${esc(r.slug)}">${esc(r.name)}</span></td>
    <td>${esc(r.vendor)}</td>
    <td>${esc(kindMeta(r.kind).label)}</td>
    <td>${esc(r.footprint)}</td>
    <td class="num">${sqftOf(r.footprint) || ''}</td>
    <td>${esc(trunc(r.enclosure, 30))}</td>
    <td>${esc(shortCords(r.cord_capacity) || '—')}</td>
    <td>${esc(prettyStyle(r))}</td>
    <td>${esc(trunc(r.roof, 34))}</td>
    <td>${esc(trunc(r.wall_height, 18))}</td>
    <td>${esc(trunc(r.loft, 26))}</td>
    <td>${esc(trunc(r.foundation, 30))}</td>
    <td class="num">${priceNum(r) === 0 ? 'Free' : priceNum(r) > 0 ? '$' + priceNum(r) : '—'}</td>
    <td>${esc(trunc(r.materials_list_available, 26))}</td>
    <td>${esc(trunc(r.format, 24))}</td>
    <td>${esc(r.verified || '—')}</td>
  </tr>`).join('');
}
const trunc = (v, n) => (has(v) ? (String(v).length > n ? String(v).slice(0, n - 1) + '…' : String(v)) : '—');

const CMP_ROWS = [
  ['Type', r => kindMeta(r.kind).label], ['Price', r => (priceNum(r) === 0 ? 'Free' : priceNum(r) > 0 ? '$' + priceNum(r) : has(r.price) ? r.price : 'Not published')],
  ['Footprint', r => `${r.footprint}${sqftOf(r.footprint) ? ` (${sqftOf(r.footprint)} sq ft)` : ''}`],
  ['Walls / enclosure', r => r.enclosure], ['Firewood capacity', r => r.cord_capacity], ['Airflow', r => r.airflow],
  ['Other sizes', r => (r.other_sizes || []).join(', ')], ['Style', r => r.style], ['Roof', r => r.roof],
  ['Wall height', r => r.wall_height], ['Overall height', r => r.overall_height], ['Loft', r => r.loft],
  ['Doors', r => r.doors], ['Windows', r => r.windows], ['Foundation', r => r.foundation],
  ['Floor framing', r => r.floor_framing], ['Wall framing', r => r.wall_framing], ['Siding', r => r.siding],
  ['Materials list', r => r.materials_list_available], ['Page count', r => r.page_count], ['Format', r => r.format],
  ['Skill level', r => r.skill_level], ['Build time', r => r.build_time], ['Material cost', r => r.est_material_cost],
  ['Permits', r => r.permit_notes], ['Refunds', r => r.refund_policy],
  ['Fact-check', r => r.verified], ['Source', r => (r.url ? `<a href="${esc(r.url)}" target="_blank" rel="noopener">open ↗</a>` : '')],
];

function renderCompare() {
  const rows = state.all.filter(r => state.pinned.has(r.slug));
  if (!rows.length) {
    $('#cmpwrap').innerHTML = `<div class="empty">Shortlist is empty. Click ☆ on a card to pin options here, then compare them side by side.</div>`;
    return;
  }
  $('#cmpwrap').innerHTML = `<table class="cmp">
    <thead><tr><th></th>${rows.map(r => `<th>${esc(r.name)}<br><span style="font-weight:400;color:var(--text-muted);font-size:12px">${esc(r.vendor)}</span></th>`).join('')}</tr></thead>
    <tbody>${CMP_ROWS.map(([label, fn]) => {
      const cells = rows.map(r => { let v; try { v = fn(r); } catch (e) { v = ''; } return v; });
      if (!cells.some(has)) return '';
      return `<tr><th>${esc(label)}</th>${cells.map(v => `<td>${label === 'Source' ? (v || '—') : (has(v) ? esc(v) : '<span style="color:var(--text-muted)">—</span>')}</td>`).join('')}</tr>`;
    }).join('')}
    <tr><th>Pros</th>${rows.map(r => `<td>${(r.pros || []).length ? `<ul class="tight pro">${r.pros.map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : '—'}</td>`).join('')}</tr>
    <tr><th>Cons</th>${rows.map(r => `<td>${(r.cons || []).length ? `<ul class="tight con">${r.cons.map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : '—'}</td>`).join('')}</tr>
    </tbody></table>`;
}

/* ---------- cost charts: magnitude low→high, sequential single hue.
   Plans and kits are DIFFERENT measures (drawings vs. delivered materials), so they get
   separate charts with their own axes rather than one axis that makes $30 look like zero. */
function renderCharts(rows) {
  const isKit = r => r.kind === 'kit';
  const drawn = [
    drawBars('#chartPlans', '#barsPlans', '#notePlans', rows.filter(r => !isKit(r) && isOption(r)), 'price of the plan set'),
    drawBars('#chartKits', '#barsKits', '#noteKits', rows.filter(isKit), 'delivered kit price'),
    drawRanges('#chartBuild', '#barsBuild', '#noteBuild', rows.filter(r => r.cost_estimate)),
  ];
  $('#chartPanel').hidden = !drawn.some(Boolean);
}

function drawBars(figSel, barsSel, noteSel, group, measure) {
  const priced = group.filter(r => priceNum(r) >= 0).sort((a, b) => priceNum(a) - priceNum(b));
  const unpriced = group.filter(r => priceNum(r) < 0);
  if (priced.length < 2) { $(figSel).hidden = true; return false; }
  const rawMax = Math.max(...priced.map(priceNum));
  if (rawMax === 0) {   // everything in view is free; a chart of zeros is noise
    $(figSel).hidden = false;
    $(barsSel).innerHTML = `<p class="allfree">All ${priced.length} of these cost nothing to download.</p>`;
    $(noteSel).textContent = `No ${measure} to compare — every option matching your filters is free.`;
    return true;
  }
  $(figSel).hidden = false;
  const max = rawMax;
  const money = n => '$' + n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  $(barsSel).innerHTML = priced.map(r => {
    const n = priceNum(r);
    const pct = Math.max(n / max * 100, n === 0 ? 0 : 0.8);
    const step = SEQ[Math.min(SEQ.length - 1, Math.floor(n / max * SEQ.length * 0.999))];
    return `<div class="bar-row" data-open="${esc(r.slug)}" data-tip="${esc(r.name)}||${esc(r.vendor)} · ${n === 0 ? 'free' : money(n)} · ${esc(r.footprint)} ${esc(prettyStyle(r))}">
      <div class="bar-name">${esc(r.vendor)} — ${esc(trunc(r.name, 40))}</div>
      <div class="bar-track">
        ${n === 0 ? '' : `<div class="bar-fill" style="width:${pct}%;background:${step}"></div>`}
      </div>
      <span class="bar-val">${n === 0 ? 'free' : money(n)}</span>
    </div>`;
  }).join('');
  $(noteSel).textContent = `Bar length = ${measure}, $0 to ${money(max)}.` + (unpriced.length
    ? ` ${unpriced.length} omitted — no published price: ${unpriced.map(r => r.vendor).join(', ')}.` : '');
  return true;
}

/* Range bars: a materials estimate has a low and a high, and drawing it as a point value would
   claim precision the research does not have. Bar spans low→high, anchored at 0. */
function drawRanges(figSel, barsSel, noteSel, group) {
  const g = group.filter(r => (r.cost_estimate.total_low_usd || 0) > 0)
    .sort((a, b) => a.cost_estimate.total_low_usd - b.cost_estimate.total_low_usd);
  if (!g.length) { $(figSel).hidden = true; return false; }
  $(figSel).hidden = false;
  const max = Math.max(...g.map(r => r.cost_estimate.total_high_usd || r.cost_estimate.total_low_usd));
  const money = n => '$' + Math.round(n).toLocaleString();
  const partial = g.filter(r => String(r.cost_estimate.priced).toUpperCase() === 'PARTIAL').length;
  $(barsSel).innerHTML = g.map(r => {
    const c = r.cost_estimate;
    const lo = c.total_low_usd, hi = c.total_high_usd > lo ? c.total_high_usd : lo;
    const left = lo / max * 100, width = Math.max((hi - lo) / max * 100, 1.2);
    const psf = c.cost_per_sqft_low && c.cost_per_sqft_high
      ? ` · $${c.cost_per_sqft_low}–${c.cost_per_sqft_high}/sq ft` : '';
    return `<div class="bar-row" data-open="${esc(r.slug)}" data-tip="${esc(r.name)}||materials ${money(lo)}–${money(hi)}${esc(psf)} · ${esc(String(c.priced).toUpperCase() === 'PARTIAL' ? 'partly estimated' : 'priced')} · excludes foundation, permits, tools and labor">
      <div class="bar-name">${esc(r.vendor)} — ${esc(trunc(r.name, 40))}</div>
      <div class="bar-track">
        <div class="bar-range" style="margin-left:${left}%;width:${width}%"></div>
      </div>
      <span class="bar-val">${money(lo)}–${money(hi)}</span>
    </div>`;
  }).join('');
  $(noteSel).textContent = `Bar spans the low–high materials estimate, $0 to ${money(max)}. `
    + `Excludes foundation/concrete, permits, tools, delivery and labor. `
    + (partial ? `${partial} of ${g.length} are partly estimated rather than fully retailer-priced — ` : '')
    + `open a bar for the priced line items and their sources.`;
  return true;
}

/* ---------- detail drawer ---------- */
function openDrawer(slug) {
  const r = state.all.find(x => x.slug === slug);
  if (!r) return;
  $('#dTitle').textContent = r.name;
  $('#dVendor').textContent = `${r.vendor}${has(r.footprint) ? ` · ${r.footprint}` : ''}${sqftOf(r.footprint) ? ` · ${sqftOf(r.footprint)} sq ft` : ''}`;

  const kv = [
    ['Type', kindMeta(r.kind).label], ['Price', priceNum(r) === 0 ? 'Free' : has(r.price) ? r.price : 'Not published'],
    ['Footprint', r.footprint], ['Footprint caveat', r.footprint_note],
    ['Other sizes offered', (r.other_sizes || []).join(', ')],
    ['Walls / enclosure', r.enclosure], ['Firewood capacity', r.cord_capacity],
    ['Airflow', r.airflow],
    ['Style', r.style], ['Roof', r.roof], ['Wall height', r.wall_height], ['Overall height', r.overall_height],
    ['Loft', r.loft], ['Doors', r.doors], ['Windows', r.windows],
    ['Kit cost per sq ft', r.kit_cost_per_sqft ? '$' + r.kit_cost_per_sqft : ''],
    ['Foundation', r.foundation], ['Floor framing', r.floor_framing], ['Wall framing', r.wall_framing],
    ['Siding', r.siding], ['Materials list', r.materials_list_available], ['Page count', r.page_count],
    ['Delivery format', r.format], ['Refund policy', r.refund_policy], ['Skill level', r.skill_level],
    ['Build time', r.build_time], ['Est. material cost', r.est_material_cost], ['Permit notes', r.permit_notes],
  ];

  const v = r._verification || {};
  const corrections = (v.corrections || []).filter(c => c && c.field);
  const unsupported = v.unsupported_claims || [];
  const localPdf = (r.extra_urls || []).find(u => /^local:/.test(String(u)));
  const otherUrls = (r.extra_urls || []).filter(u => !/^local:/.test(String(u)));

  $('#dBody').innerHTML = `
    ${has(r.image_local_path)
        ? `<img class="hero" src="${esc(r.image_local_path)}" alt="${esc(r.name)}" onerror="this.remove()">`
        : (r.image_was_local && has(r.image_source_url)
            ? `<a class="herolink" href="${esc(r.image_source_url)}" target="_blank" rel="noopener nofollow">View the plan image at ${esc((r.image_source_url.split('/')[2] || 'the source'))} ↗</a>`
            : '')}
    <div class="badges">
      <span class="badge"><span class="dot" style="background:${kindColor(r.kind)}"></span>${esc(kindMeta(r.kind).label)}</span>
      ${hasLoft(r) ? '<span class="badge">loft</span>' : ''}
      ${verifyBadge(r)}
      <span class="badge">data confidence: ${esc(r.data_confidence || 'unknown')}</span>
    </div>
    <div class="linkrow">
      <a class="btn on" href="${esc(r.url)}" target="_blank" rel="noopener">Open the plan page ↗</a>
      ${localPdf ? `<a class="btn" href="${esc(String(localPdf).replace(/^local:/, ''))}" target="_blank">Local PDF (saved)</a>` : ''}
      <button class="btn ${state.pinned.has(r.slug) ? 'on' : ''}" type="button" data-pin="${esc(r.slug)}">${state.pinned.has(r.slug) ? '★ Shortlisted' : '☆ Shortlist'}</button>
    </div>

    ${r.disqualified ? `<div class="notice" style="margin:0"><strong>Excluded from the main list.</strong> ${esc(r.disqualified)}</div>` : ''}
    ${r.reference_note ? `<div class="notice" style="margin:0;border-left-color:var(--series-7)"><strong>Reference, not a plan.</strong> ${esc(r.reference_note)}</div>` : ''}
    ${r.price_doubt ? `<div class="notice" style="margin:0;border-left-color:var(--serious)"><strong>Price in doubt.</strong> ${esc(r.price_doubt)}</div>` : ''}
    ${has(r.summary) ? `<div class="sect"><h4>The gist</h4><p>${esc(r.summary)}</p></div>` : ''}

    <div class="sect"><h4>Specifications</h4><dl class="kv">${
      kv.filter(([, val]) => true).map(([k, val]) =>
        `<dt>${esc(k)}</dt><dd class="${has(val) ? '' : 'na'}">${has(val) ? esc(val) : 'not stated by the source'}</dd>`).join('')
    }</dl></div>

    ${(r.includes || []).length ? `<div class="sect"><h4>What you get</h4><ul class="tight">${r.includes.map(i => `<li>${esc(i)}</li>`).join('')}</ul></div>` : ''}

    ${(r.pros || []).length ? `<div class="sect"><h4>Strengths</h4><ul class="tight pro">${r.pros.map(i => `<li>${esc(i)}</li>`).join('')}</ul></div>` : ''}
    ${(r.cons || []).length ? `<div class="sect"><h4>Watch out for</h4><ul class="tight con">${r.cons.map(i => `<li>${esc(i)}</li>`).join('')}</ul></div>` : ''}

    ${r.cost_estimate ? costSection(r.cost_estimate, r) : ''}

    ${(r.derived_lumber_list || []).length ? `<div class="sect"><h4>Derived materials take-off</h4>
      <div class="notice" style="margin:0 0 10px;border-left-color:var(--series-4)"><strong>Estimated, not the author's list.</strong> ${esc(r.derived_list_note || '')}</div>
      <details class="lumber" open><summary>${r.derived_lumber_list.length} derived line items</summary>
      <pre>${esc(r.derived_lumber_list.join('\n'))}</pre></details></div>` : ''}

    ${(r.lumber_list || []).length ? `<div class="sect"><h4>Materials / cut list as published</h4>
      <details class="lumber"><summary>${r.lumber_list.length} lines — click to expand</summary>
      <pre>${esc(r.lumber_list.join('\n'))}</pre></details></div>` : ''}

    ${(r.quotes || []).length ? `<div class="sect"><h4>From the source</h4>${r.quotes.map(q => `<blockquote class="q">${esc(q)}</blockquote>`).join('')}</div>` : ''}

    <div class="sect"><h4>Fact-check trail</h4><div class="verifybox">
      <div class="row">${verifyBadge(r)} <span style="color:var(--text-secondary)">${esc(v.notes || 'no verifier notes')}</span></div>
      <div class="row" style="color:var(--text-muted);font-size:12px">
        link status when checked: <code>${esc(r.url_live || r.http_status || '?')}</code>
        &nbsp;·&nbsp; image: <code>${esc(r.image_ok || (has(r.image_local_path) ? 'saved' : 'none'))}</code>
      </div>
      ${corrections.length ? `<div class="corr"><strong>${corrections.length} field${corrections.length > 1 ? 's' : ''} corrected by the fact-checker:</strong><ul class="tight">${
        corrections.map(c => `<li><code>${esc(c.field)}</code> was “${esc(c.reported)}” → now “${esc(c.correct)}”</li>`).join('')
      }</ul></div>` : ''}
      ${unsupported.length ? `<div class="corr"><strong>Unsupported claims flagged:</strong><ul class="tight">${unsupported.map(u => `<li>${esc(u)}</li>`).join('')}</ul></div>` : ''}
      ${(r.unknowns || []).length ? `<div class="corr" style="color:var(--text-muted)">Not determinable from the source: ${esc((r.unknowns || []).join(', '))}</div>` : ''}
    </div></div>

    ${otherUrls.length ? `<div class="sect"><h4>Related pages &amp; parts</h4><ul class="tight">${
      otherUrls.map(u => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></li>`).join('')}</ul></div>` : ''}
  `;
  $('#drawer').classList.add('open');
  $('#scrim').classList.add('open');
  $('#dBody').scrollTop = 0;
}
function costSection(c, r) {
  const money = n => '$' + Math.round(n).toLocaleString();
  const psf = c.cost_per_sqft_low ? `$${c.cost_per_sqft_low}–${c.cost_per_sqft_high} per sq ft` : '';
  const isPartial = String(c.priced).toUpperCase() === 'PARTIAL';
  return `<div class="sect"><h4>What the materials will actually cost</h4>
    <div class="costbox">
      <div class="cost-hero">${money(c.total_low_usd)} – ${money(c.total_high_usd)}</div>
      <div class="cost-sub">${esc(psf)}${psf ? ' · ' : ''}materials only, on top of the ${priceNum(r) === 0 ? 'free' : money(priceNum(r))} plan set</div>
      ${isPartial ? `<div class="cost-warn">◐ Partly estimated — some lines are researched retail prices, others are estimates. Check the source column.</div>` : ''}
      ${has(c.caveats) ? `<p class="cost-caveat">${esc(c.caveats)}</p>` : ''}
      ${(c.excludes || []).length ? `<div class="cost-ex"><strong>Not included:</strong> ${esc(c.excludes.join(', '))}</div>` : ''}
      ${(c.price_sources || []).length ? `<div class="cost-ex"><strong>Priced from:</strong> ${esc(c.price_sources.join(' · '))}</div>` : ''}
      ${(c.priced_lines || []).length ? `<details class="lumber" style="margin-top:10px">
        <summary>${c.priced_lines.length} priced line items</summary>
        <table class="costtable"><thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Extended</th><th>Source</th></tr></thead>
        <tbody>${c.priced_lines.map(l => `<tr><td>${esc(l.item)}</td><td>${esc(l.qty)}</td><td class="num">${esc(l.unit_price)}</td><td class="num">${esc(l.extended)}</td><td class="src">${esc(l.source)}</td></tr>`).join('')}</tbody></table>
      </details>` : ''}
      <div class="cost-conf">confidence: ${esc(c.confidence || 'unstated')}</div>
    </div></div>`;
}

function closeDrawer() { $('#drawer').classList.remove('open'); $('#scrim').classList.remove('open'); }

/* ---------- events ---------- */
function wire() {
  $('#q').addEventListener('input', e => { state.q = e.target.value.trim(); render(); });
  $('#fFoot').addEventListener('change', e => { state.foot = e.target.value; render(); });
  $('#fStyle').addEventListener('change', e => { state.style = e.target.value; render(); });
  $('#fEnc').addEventListener('change', e => { state.enc = e.target.value; render(); });
  $('#fLoft').addEventListener('change', e => { state.loft = e.target.value; render(); });
  $('#fPrice').addEventListener('change', e => { state.price = e.target.value; render(); });
  $('#fSort').addEventListener('change', e => { state.sort = e.target.value; render(); });
  $('#vCards').addEventListener('click', () => { state.view = 'cards'; render(); });
  $('#vTable').addEventListener('click', () => { state.view = 'table'; render(); });
  $('#vCompare').addEventListener('click', () => { state.view = 'compare'; render(); });
  $('#showExcluded').addEventListener('click', e => {
    state.showExcluded = !state.showExcluded;
    e.currentTarget.setAttribute('aria-pressed', String(state.showExcluded));
    e.currentTarget.classList.toggle('on', state.showExcluded);
    render();
  });
  $('#onlyPinned').addEventListener('click', e => {
    state.onlyPinned = !state.onlyPinned;
    e.currentTarget.setAttribute('aria-pressed', String(state.onlyPinned));
    e.currentTarget.classList.toggle('on', state.onlyPinned);
    render();
  });
  $('#kindChips').addEventListener('click', e => {
    const b = e.target.closest('[data-kind]'); if (!b) return;
    const k = b.dataset.kind;
    state.kinds.has(k) ? state.kinds.delete(k) : state.kinds.add(k);
    b.setAttribute('aria-pressed', String(state.kinds.has(k)));
    render();
  });
  document.addEventListener('click', e => {
    const pin = e.target.closest('[data-pin]');
    if (pin) {
      e.stopPropagation();
      const s = pin.dataset.pin;
      state.pinned.has(s) ? state.pinned.delete(s) : state.pinned.add(s);
      savePins(); render();
      if ($('#drawer').classList.contains('open')) openDrawer(s);
      return;
    }
    const open = e.target.closest('[data-open]');
    if (open) { openDrawer(open.dataset.open); return; }
    const card = e.target.closest('.card');
    if (card && card.dataset.slug) openDrawer(card.dataset.slug);
  });
  $('#dClose').addEventListener('click', closeDrawer);
  $('#scrim').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDrawer();
    if (e.key === '/' && document.activeElement !== $('#q')) { e.preventDefault(); $('#q').focus(); }
  });
  $('#themeBtn').addEventListener('click', () => {
    const now = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = now;
    localStorage.setItem('woodshed.theme', now);
    $('#themeBtn').textContent = now === 'light' ? 'Dark' : 'Light';
  });

  // hover layer for the bar chart
  const tip = $('#tip');
  document.addEventListener('mousemove', e => {
    const host = e.target.closest('[data-tip]');
    if (!host) { tip.classList.remove('on'); return; }
    const [t, s] = host.dataset.tip.split('||');
    tip.innerHTML = `<div class="t">${esc(t)}</div><div class="s">${esc(s)}</div>`;
    tip.classList.add('on');
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(e.clientX + pad, innerWidth - w - 8) + 'px';
    tip.style.top = Math.max(8, Math.min(e.clientY + pad, innerHeight - h - 8)) + 'px';
  });
}

const savedTheme = localStorage.getItem('woodshed.theme');
if (savedTheme) {
  document.documentElement.dataset.theme = savedTheme;
  document.addEventListener('DOMContentLoaded', () => { $('#themeBtn').textContent = savedTheme === 'light' ? 'Dark' : 'Light'; });
}
load();
