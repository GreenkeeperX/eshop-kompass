"use strict";
/* Korb, Wishlist als Tabelle, Preisverlauf (Teil der Oberfläche, Reihenfolge in index.html) */
/* ---------- Länder: gemeinsamer Korb als Vergleichstabelle ---------- */
function viewCompare(){
  // Beim ersten Zeichnen sind die Körbe noch nicht gerechnet (0.85; vorher brach die Seite ab,
  // wenn sie direkt in der Ansicht Korb geöffnet wurde)
  if(!S.bplans) return `<p class="mut">Korb wird berechnet …</p>`;
  const inB = new Set(S.ui.basket);
  // Mit dem günstigsten zählenden Preis wie in Kaufplan und Länderkarten mit dem Landespreis (0.94)
  const low = r => { const o = cheapestOffer(S.state.radar.find(x => x.slug === r.slug) || {}); return o ? `ab ${o.est ? "ca. " : ""}${eur(o.eur)} in ${o.name}` : ""; };
  const opts = wishOpts(S.state.matrix.rows.filter(r => !inB.has(r.slug) && !r.no_ids), low, {code: null, skip: inB});
  const shown = S.bplans.filter(p => p.is_ref || !S.ui.hidden.includes(p.code));
  const usable = shown.filter(p => p.rate && p.items.length);
  // Spalten von leicht nach schwer, innerhalb einer Stufe die günstigeren zuerst (0.69; vorher in der
  // Reihenfolge des Servers, nach fehlenden Titeln und Ersparnis, das wirkte willkürlich)
  const cols = usable.filter(p => p.is_ref).concat(usable.filter(p => !p.is_ref)
    .sort((a, b) => a.tier - b.tier || (a.missing.length - b.missing.length) || (a.cost ?? 1e9) - (b.cost ?? 1e9)));
  const none = shown.filter(p => !usable.includes(p));
  const complete = cols.filter(p => !p.missing.length && p.cost !== null);
  const win = complete.length > 1 ? complete.reduce((a, b) => b.cost < a.cost ? b : a) : null;
  const easy = complete.filter(p => p.tier <= 2);
  const winEasy = easy.length ? easy.reduce((a, b) => b.cost < a.cost ? b : a) : null;

  const single = complete.filter(p => p.tier === 1 && p.via === "card" || p.is_ref).reduce((a, b) => !a || b.cost < a.cost ? b : a, null);
  const mixWins = !!(S.mix && S.mix.parts.length > 1 && (!single || S.mix.cost < single.cost - 0.5));
  let verdict = `<span class="hint">Kein Land bietet den ganzen Korb, deshalb ist nichts hervorgehoben.</span>`;
  if(win){
    verdict = `<span>Günstigstes Land: <b>${esc(win.name)}</b>, ${win.estimated ? "ca. " : ""}${eur(win.cost)}` +
      (winEasy && winEasy.code !== win.code ? ` · leicht erreichbar: <b>${esc(winEasy.name)}</b>, ${eur(winEasy.cost)}` : "") +
      (mixWins ? ` · <span title="Jeder Titel im günstigsten Land mit Kartenzahlung, Aufteilung steht unter der Tabelle">aufgeteilt: <b>${eur(S.mix.cost)}</b></span>` : "") + `</span>`;
  } else if(complete.length === 1){
    verdict = `<span class="hint">Nur ${esc(complete[0].name)} bietet den ganzen Korb.</span>`;
  }
  // Werkzeugzeile wie in den anderen Reitern: links dazunehmen, rechts Korb leeren; das Ergebnis darunter (0.60)
  let h = `<div class="tools">${pickWrap(`<select data-act="bpick" title="Deine Wishlist-Titel und die Online-Mitgliedschaft, soweit noch nicht im Korb"><option value="">Titel dazunehmen …</option>${opts}</select>`)}
    <button class="sm" data-act="unshare" title="Korb leeren; die Länder behalten ihre eigenen Körbe">Korb leeren</button>${viewSeg()}</div>
    <div class="bar on">${verdict}</div>
    <details class="fold" data-k="korbhow" ${S.folds.korbhow ? "open" : ""}><summary class="hint">So liest du den Korb</summary><p class="hint" style="margin:2px 0 8px">Was genau diese Titel in jedem Land kosten, mit Guthabenkarten und Rest wie auf den Länderkarten. Zellfarbe wie in der Titel-Tabelle: dunkelgrün „kaufen“, hellgrün „gut“, gold umrandet der Bestpreis; rot nur der Betrag darüber. Ein Klick auf den Preis öffnet die Seite im eShop, bei DLC den Verlauf bei DekuDeals (für DLC gibt es keinen festen eShop-Link); ein Klick auf den Ländernamen sortiert.</p></details>`;
  if(!cols.length) return h + `<p class="restline">Kein Titel aus dem Korb ist in einem aktiven Land kaufbar.</p>` + hiddenLine();

  const cls = p => (win && p.code === win.code ? "win " : "") + (p.missing.length ? "incomplete " : "");
  const ks = S.sorts.korb, arrow = k => ks && ks.k === k ? `<span class="sa">${ks.dir > 0 ? "▲" : "▼"}</span>` : "";
  const sortTh = (k, cls2, inner, tip) => `<th class="sth ${ks && ks.k === k ? "on" : ""} ${cls2}" tabindex="0" data-act="tsort" data-t="korb" data-k="${esc(k)}" title="${esc(tip)} · Klick sortiert">${inner}${arrow(k)}</th>`;
  h += `<div class="cmp fitbox"><table><thead><tr>${sortTh("title", "", `${S.ui.basket.length} Titel`, "nach Titel")}${sortTh("best", "", "Bestpreis<small>24 Monate, alle Länder</small>", "Niedrigster Einkaufspreis der letzten 24 Monate über alle zählenden Länder")}` + cols.map(p =>
    sortTh(p.code, cls(p), `${win && p.code === win.code ? `<span class="tagwin">günstigstes</span><br>` : ""}${esc(p.name)}
      <small>${p.is_ref ? "Vergleichsbasis" : TIER[p.tier] || ""}${p.current ? " · Konto hier" : ""}${p.missing.length ? ` · ${p.items.length} von ${S.ui.basket.length}` : ""}</small>`, `nach dem Preis in ${p.name}`)).join("") + `</tr></thead><tbody>`;
  const itemIn = (p, slug) => p.items.find(i => i.slug === slug) || null;
  const order = sortRows("korb", S.ui.basket.slice(), Object.assign({title: s => rowOf(s).title, best: s => (rowOf(s).champ || {}).eur ?? null},
    Object.fromEntries(cols.map(p => [p.code, s => (itemIn(p, s) || {}).eur ?? null]))));
  for(const slug of order){
    const r = rowOf(slug);
    const cells = cols.map(p => itemIn(p, slug));
    h += `<tr><td title="${esc(r.title)}"><button class="x" data-act="bdrop" data-s="${esc(slug)}" title="aus dem Korb nehmen">×</button>${r.dlc_of ? `<span class="dlc">DLC</span>` : ""}${r.nso ? `<button class="link" data-act="gonso" title="Zum Kasten Online-Mitgliedschaft unter Jetzt">${esc(r.title)}</button>` : `<a class="tl" href="${deku(slug)}" target="_blank" rel="noopener">${dlcLabel(r)}</a>`}</td>` +
      `<td class="bp">${r.champ ? `${ax(r.champ)}<b title="Bestpreis in ${esc(country(r.champ.code).name)}">${eur(r.champ.eur)}</b> <small class="inl">${r.champ.code}</small>` : `<span class="mut">–</span>`}</td>` +
      cols.map((p, k) => {
        const i = cells[k];
        if(!i){
          const m = p.missing.find(x => x.slug === slug);
          return `<td class="na ${cls(p)}" title="${m && m.nolang ? "keine deutsche Fassung" : "dort nicht kaufbar"}">${m && m.nolang ? "ohne DE" : "–"}</td>`;
        }
        // Eine Zeile wie in der Titel-Tabelle (0.61): Preis, Rabatt, Abstand zum Bestpreis. Landeswährung,
        // Zahlweg und Angebotsende stehen im Tooltip; die Zelle färbt sich nach dem Urteil
        const ch = r.champ ? r.champ.eur : null, gap = ch !== null && !atBest(i.eur, ch) ? i.eur - ch : 0;
        const champHere = r.champ && r.champ.code === p.code;
        const counts = !i.nocard && i.lang !== "unknown";
        const g = counts && i.sale && i.grade && i.grade !== "wait" ? "c-" + i.grade : "";
        const need = i.needs_parent ? needsRegion(r.dlc_of, p.code, slug) : "";
        const url = i.own && i.own.url ? i.own.url : shopUrl(p.code, i.nsuid);
        const tip = [compose(p.code, i), p.currency === "EUR" ? "" : `im Shop ${money(i.local, p.currency)}`,
          i.sale && i.end ? `Angebot bis ${dm(i.end)}` : "",
          champHere ? "Hier gab es den Bestpreis" : "", need ? needTip(p.code, need) : "",
          i.own && i.own.url ? `Klick öffnet ${i.own.src}` : url ? `Klick öffnet den eShop ${country(p.code).name}` : "Klick öffnet den Verlauf bei DekuDeals"].filter(Boolean).join(" · ");
        const price = `<a class="pl" href="${esc(url || deku(slug, p.code))}" target="_blank" rel="noopener">${num(i.eur)}</a>`;
        const marks = cellMarks(i, need ? needMark(p.code, need) : "");
        return `<td class="${cls(p)}${g} ${champHere ? "champ" : ""} ${counts ? "" : "nc"} ${need === "need" ? "needr" : ""}" title="${esc(tip)}">` +
          // ★ nach dem Preis im Korb, nicht dem eines Einzelkaufs: Guthabenkarten teilen sich hier auf (0.65)
          // Zwei Zeilen (0.70): oben Preis | Abstand, die Fuge mittig in der Spalte, damit Preise und
          // Abstände untereinander stehen; darunter Rabatt und Marken
          twoLine(`${counts && ch !== null && atBest(i.eur, ch) ? star({mark: "best"}) : ""}${ax(i)}${counts ? "" : `<span class="q">?</span>`}`, price, gap, marks, gapTip(r, i.eur)) + `</td>`;
      }).join("") + `</tr>`;
  }
  const row = (label, fn, extra) => `<tr class="${extra || ""}"><td>${label}</td><td></td>${cols.map(p => `<td class="${cls(p)}">${fn(p)}</td>`).join("")}</tr>`;
  h += `</tbody><tfoot>` +
    row("Einkaufspreis", p => `<span title="${esc(costTip(p))}">${p.estimated ? "ca. " : ""}${eur(p.cost)}</span>`, "pay sumtop") +
    row("Preis", p => p.opt_gap === null || p.opt_gap === undefined ? "–" : `${atBest(p.optimum + p.opt_gap, p.optimum) ? `<span class="g-${p.grade || "buy"}"${nearTip(p.opt_gap)}>am Bestpreis</span>` : `<span class="abv">+${eur(p.opt_gap)}</span>`}<small>Bestpreis-Summe ${eur(p.optimum)}</small>`) +
    row("Wechsel", p => {
      if(p.is_ref) return `<span class="mut">Basis</span>`;
      if(p.gain === null || p.gain === undefined) return "–";
      const g = `${p.gain >= 0 ? "spart" : "kostet"} ${eur(Math.abs(p.gain))}`;
      return (p.current ? `Konto hier` : p.worth ? `<b>✓ lohnt</b>` : `<b class="bad">lohnt nicht</b>`) +
        `<small>${g}${p.missing.length ? `, ${p.items.length} von ${S.ui.basket.length} Titeln` : ""}</small>`;
    }) +
    row("Rest", p => p.is_ref ? "0" : restHtml(p, true)) +
    row("Shop", p => money(p.total, p.currency)) +
    row("Karten", p => p.cards.length ? cardsHtml(p) : (p.is_ref ? ((S.state.pay[p.code] || {}).card ? "Guthabenkarten" : "exakter Betrag") : p.via === "card" ? "Kartenzahlung" : "–")) +
    row("Passt dazu", p => {
      const f = p.fillers[0];
      if(!f) return "";
      return `<button class="fl" data-act="add" data-c="${p.code}" data-s="${esc(f.slugs.join(","))}" title="${esc(fillTip(f, p.currency, "Klick legt ihn für alle Länder in den Korb."))}">+ ${f.shorts.map(esc).join(" + ")} <b>spart ${eur(f.gain)}</b>${fillBest(f)}</button>`;
    }) +
    row("Hinweise", p => { const c = hurdles(p); return c.length ? c.join("<br>") : ""; }) +
    row("Jetzt", p => jetztBtn(p)) +
    `</tfoot></table></div>`;
  h += korbPhone(cols, win, order, rowOf, itemIn);
  if(mixWins)
    h += `<p class="restline"><b>Aufgeteilt auf Länder mit Kartenzahlung:</b> ${eur(S.mix.cost)}` +
      (single ? `, das sind ${eur(single.cost - S.mix.cost)} weniger als alles in ${esc(single.name)}` : "") + `. ` +
      S.mix.parts.map(x => `${esc(x.name)} ${eur(x.cost)} (${x.titles.map(esc).join(", ")})`).join(" · ") + `</p>`;
  if(none.length)
    h += `<p class="restline">Korb dort nicht kaufbar: ` + none.map(p => esc(p.name)).join(" · ") + `</p>`;
  return h + hiddenLine();
}

/* Korb am Handy (0.85): statt der breiten Tabelle ein Land nach dem anderen. Oben die Auswahl mit
   Preis je Land, darunter die Titel mit derselben Preiszelle und die Summenzeilen; die Rechnung
   (sonst nur im Tooltip) klappt unter dem Einkaufspreis auf. Ab 641 px bleibt die Tabelle */
function korbPhone(cols, win, order, rowOf, itemIn){
  const n = S.ui.basket.length;
  const pc = cols.find(p => p.code === S.korbLand) || win || cols[0];
  const label = p => `${p.name} · ${p.missing.length ? `${p.items.length} von ${n}` : `${p.estimated ? "ca. " : ""}${eur(p.cost)}`}${win && p.code === win.code ? " · günstigstes" : ""}`;
  let m = `<div class="kphone"><label class="f"><select data-act="korbland" aria-label="Land" title="Land, dessen Preise die Karte zeigt">${cols.map(p =>
    `<option value="${p.code}" ${p === pc ? "selected" : ""}>${esc(label(p))}</option>`).join("")}</select></label><table class="kpt"><tbody>`;
  for(const slug of order){
    const r = rowOf(slug), i = itemIn(pc, slug);
    let cell;
    if(!i){
      const miss = pc.missing.find(x => x.slug === slug);
      cell = `<td class="na">${miss && miss.nolang ? "ohne DE" : "nicht kaufbar"}</td>`;
    } else {
      const ch = r.champ ? r.champ.eur : null, gap = ch !== null && !atBest(i.eur, ch) ? i.eur - ch : 0;
      const counts = !i.nocard && i.lang !== "unknown";
      const g = counts && i.sale && i.grade && i.grade !== "wait" ? "c-" + i.grade : "";
      const need = i.needs_parent ? needsRegion(r.dlc_of, pc.code, slug) : "";
      const url = i.own && i.own.url ? i.own.url : shopUrl(pc.code, i.nsuid);
      cell = `<td class="${g} ${counts ? "" : "nc"}">` + twoLine(`${counts && ch !== null && atBest(i.eur, ch) ? star({mark: "best"}) : ""}${ax(i)}${counts ? "" : `<span class="q">?</span>`}`,
        `<a class="pl" href="${esc(url || deku(slug, pc.code))}" target="_blank" rel="noopener">${num(i.eur)}</a>`, gap, cellMarks(i, need ? needMark(pc.code, need) : ""), gapTip(r, i.eur)) + `</td>`;
    }
    m += `<tr><td><button class="x" data-act="bdrop" data-s="${esc(slug)}" title="aus dem Korb nehmen">×</button>${r.dlc_of ? `<span class="dlc">DLC</span>` : ""}${r.nso ? `<button class="link" data-act="gonso">${esc(r.title)}</button>` : `<a class="tl" href="${deku(slug)}" target="_blank" rel="noopener">${dlcLabel(r)}</a>`}</td>${cell}</tr>`;
  }
  const line = (k, v) => v ? `<div><span class="mut">${k}</span> ${v}</div>` : "";
  const gain = pc.is_ref ? `<span class="mut">Basis</span>` : pc.gain === null || pc.gain === undefined ? "" :
    `${pc.current ? "Konto hier" : pc.worth ? "<b>✓ lohnt</b>" : `<b class="bad">lohnt nicht</b>`} <small>${pc.gain >= 0 ? "spart" : "kostet"} ${eur(Math.abs(pc.gain))}</small>`;
  const hs = hurdles(pc);
  m += `</tbody></table><div class="kps">` +
    `<details><summary><b>Einkaufspreis ${pc.estimated ? "ca. " : ""}${eur(pc.cost)}</b> <span class="mut">Rechnung</span></summary><p class="hint">${esc(costTip(pc))}</p></details>` +
    line("Preis", pc.opt_gap === null || pc.opt_gap === undefined ? "" : atBest(pc.optimum + pc.opt_gap, pc.optimum) ? `<span class="g-${pc.grade || "buy"}">am Bestpreis</span>` : `<span class="abv">+${eur(pc.opt_gap)}</span> <small>über der Bestpreis-Summe ${eur(pc.optimum)}</small>`) +
    line("Wechsel", gain) + line("Rest", pc.is_ref ? "" : restHtml(pc, true)) + line("Shop", money(pc.total, pc.currency)) +
    line("Karten", pc.cards.length ? cardsHtml(pc) : "") + line("Hinweise", hs.length ? hs.join("<br>") : "") + line("Jetzt", jetztBtn(pc)) + `</div></div>`;
  return m;
}

/* Korb in den Kaufplan (1.3.0): Die Titel dieses Lands kommen als dazugenommene Titel in seinen Schritt;
   gibt es keinen, bekommt das Land einen. Danach zeigt „Jetzt“ den Schritt mit „Auf Null“ und allem anderen */
function jetztBtn(p){
  if(!p.items.length) return "";
  return `<button class="sm" data-act="tojetzt" data-c="${p.code}" title="Die ${p.items.length === 1 ? "Titel" : `${p.items.length} Titel`} dieses Lands in den Kaufplan unter Jetzt übernehmen, als Schritt ${esc(p.name)}. Titel aus anderen Schritten ziehen dorthin um.">In Jetzt übernehmen</button>`;
}
/* Preiszelle in Tabelle und Korb (0.81, im Korb seit 0.70): oben Preis | rotes „+x“ über dem Bestpreis,
   die Fuge mittig, damit Preise und Abstände untereinander stehen; darunter Rabatt und Marken.
   Das „+x“ hat einen eigenen Tooltip (1.2.0), der Preis den seines Links, die Zelle den Rest */
function twoLine(lead, price, gap, marks, gtip){
  return `<span class="kc"><span class="kp">${lead}${price}</span><span class="kg">${gap > 0.005 ? `<span class="abv gap"${gtip ? ` title="${esc(gtip)}"` : ""}>+${num(gap)}</span>` : ""}</span></span>` +
    (marks.length ? `<span class="kl">${marks.join("")}</span>` : "");
}
/* Tooltip am „+x“ (1.2.0): wo es den Bestpreis gab, darunter die Tiefstpreise der Länder der letzten
   24 Monate, günstigste zuerst, mit dem Abstand dieses Preises dazu. Vorher wiederholte der Tooltip
   die Rechnung des Preises */
function gapTip(r, price){
  if(!r.champ) return "";
  const lows = Object.entries(r.cells || {}).filter(([, x]) => x && !x.na && !x.nocard && x.lang !== "unknown" && x.low_eur !== null && x.low_eur !== undefined)
    .sort((a, b) => a[1].low_eur - b[1].low_eur);
  const diff = d => d > 0.005 ? `+${eur(d)}` : d < -0.005 ? `−${eur(-d)}` : "gleich";
  return [`${eur(price - r.champ.eur)} über dem Bestpreis ${r.champ.est ? "ca. " : ""}${eur(r.champ.eur)} in ${country(r.champ.code).name}`]
    .concat(lows.length > 1 ? ["", "Tiefstpreise der Länder, 24 Monate:"].concat(lows.slice(0, 10).map(([c, x]) =>
      `${country(c).name} ${x.est ? "ca. " : ""}${eur(x.low_eur)} (${diff(price - x.low_eur)})`)) : [])
    .concat(lows.length > 10 ? [`und ${lows.length - 10} weitere`] : []).join("\n");
}
const cellMarks = (x, need) => [x.sale ? `<span class="pct">−${x.pct} %</span>` : "", x.own ? ownMark(x) : "", need, langTag(x, false)].filter(Boolean);
/* ---------- Titel als Tabelle (bisher Preisvergleich) ---------- */
function viewMatrix(){
  const mx = S.state.matrix, q = S.rq.toLowerCase(), f = S.vf || "all";
  const verdictOf = Object.fromEntries(S.state.radar.map(r => [r.slug, r.verdict]));
  const cellEur = (r, code) => { const x = r.cells[code]; return x && !x.na ? x.eur : null; };
  const match = mx.rows.filter(r => hits(q, r.title) && (f === "all" || verdictOf[r.slug] === f) &&
    (!S.onlySale || Object.values(r.cells).some(c => c.sale)));
  const rows = sortRows("matrix", match.filter(dlcShown), new Proxy({title: r => r.title, best: r => r.champ ? r.champ.eur : null},
    {get: (o, k) => o[k] || (r => cellEur(r, k))}));
  // Mit „nur Angebote“ fallen auch Länder ohne ein Angebot in den gezeigten Zeilen weg
  let cols = S.onlySale ? mx.cols.filter(c => rows.some(r => r.cells[c.code] && r.cells[c.code].sale)) : mx.cols;
  // Spalten nach Wechselstufe; Länder, in denen gerade nichts zählt (ohne Karte), ans Ende
  const dead = c => rows.length && rows.every(r => !r.cells[c.code] || r.cells[c.code].na || r.cells[c.code].nocard);
  const tierOf = c => c.code === "DE" ? 0 : c.tier;
  // Bestpreise je Land in den gezeigten Zeilen. Deutschland bleibt vorn.
  const bests = Object.fromEntries(cols.map(c => [c.code, rows.filter(r => r.champ && r.champ.code === c.code).length]));
  const byBest = (a, b) => (b.code === "DE") - (a.code === "DE") || bests[b.code] - bests[a.code];
  cols = [...cols].sort(S.colOrder === "best" ? (a, b) => (dead(a) - dead(b)) || byBest(a, b)
    : S.colOrder === "tier" ? (a, b) => (dead(a) - dead(b)) || (tierOf(a) - tierOf(b))
    : (a, b) => (dead(a) - dead(b)) || (tierOf(a) - tierOf(b)) || byBest(a, b));
  const groups = [];
  for(const c of cols){
    const g = dead(c) ? "zählt gerade nicht" : S.colOrder === "best" ? (c.code === "DE" ? "" : "nach Bestpreisen") : TIER[Math.max(1, tierOf(c))];
    if(groups.length && groups[groups.length - 1][0] === g) groups[groups.length - 1][1]++; else groups.push([g, 1]);
  }
  const det = !!S.mDetails;
  // Reihenfolge wie in allen Reitern: Suche, Sortierung, Filter, rechts die Ansicht (0.60)
  let h = `<div class="tools">${searchBox("Titel filtern")}
    <select class="srt" data-act="colorder" title="Reihenfolge der Länderspalten">${[["tierbest", "Länder nach Stufe, darin Bestpreise"], ["best", "Länder nach Bestpreisen"], ["tier", "Länder nach Stufe"]].map(([v, l]) => `<option value="${v}" ${S.colOrder === v ? "selected" : ""}>${l}</option>`).join("")}</select>${titleFilterBar()}
    <label><input type="checkbox" data-act="onlysale" ${S.onlySale ? "checked" : ""}> nur Angebote</label>
    <label title="Landestief, Angebotsende und Sprache in jeder Zelle"><input type="checkbox" data-act="mdet" ${det ? "checked" : ""}> Details</label>${viewSeg()}</div>
    <div class="matrix scroll fitbox ${det ? "" : "compact"}"><table><thead><tr class="grp"><th></th><th></th>${groups.map(([g, n]) => `<th colspan="${n}">${g}</th>`).join("")}</tr>
    <tr>${sth("matrix", "title", "Titel")}${sth("matrix", "best", "Bestpreis", "Niedrigster Einkaufspreis der letzten 24 Monate über alle zählenden Länder. Das Land ist in der Zeile gold umrandet.")}${cols.map(c => sth("matrix", c.code, `${c.code}${bests[c.code] ? `<small class="bc">${bests[c.code]}★</small>` : ""}`, `${c.name} · ${bests[c.code] === 1 ? "1 Bestpreis" : `${bests[c.code]} Bestpreise`} in den gezeigten Titeln`)).join("")}</tr></thead><tbody>`;
  h += rows.map(r => `<tr><td><div class="tl"><button class="kb sm ${inBasket(r.slug) ? "on" : ""}" data-act="star" data-s="${esc(r.slug)}" title="${inBasket(r.slug) ? "aus dem Korb nehmen" : "in den Korb"}">${inBasket(r.slug) ? "✓" : "+"}</button><button class="tbtn" data-act="gotitle" data-s="${esc(r.slug)}" title="Einzelheiten in der Liste">${r.dlc_of ? `<span class="dlc">DLC</span>` : ""}${dlcLabel(r)}</button></div>${r.no_ids ? ` <small class="hint">nicht im eShop gefunden</small>` : ""}</td>` +
    ((() => {
      // Zeilen ohne Unterschied (0.65): kostenlos überall oder nirgends ein Preis, dann eine Zeile mit Grund statt lauter gleicher Zellen
      const cs = cols.map(c => r.cells[c.code]).filter(Boolean), priced = cs.filter(x => !x.na);
      const why = !priced.length ? ((S.state.radar.find(x => x.slug === r.slug) || {}).reason || "in keinem Land ein Preis") : priced.every(x => x.eur === 0) ? "kostenlos" : null;
      return why ? `<td class="bp">${why === "kostenlos" ? "kostenlos" : `<span class="mut">–</span>`}</td><td class="mut l" colspan="${cols.length}">${esc(why)}${why === "kostenlos" ? ` in ${priced.length === 1 ? "einem Land" : `allen ${priced.length} Ländern mit Preis`}` : ""}</td></tr>` : null;
    })() ??
    `<td class="bp">${r.champ ? `${ax(r.champ)}<b>${eur(r.champ.eur)}</b> <small style="display:inline">${r.champ.code}</small>` : `<span class="mut">–</span>`}${det && r.typical ? `<small title="Typischer Angebotspreis in ${esc(country(r.typical.code).name)}, aus ${r.typical.runs} Angeboten der letzten zwei Jahre">typisch ${ax(r.typical)}${eur(r.typical.eur)}</small>` : ""}</td>` +
    cols.map(c => {
      const x = r.cells[c.code];
      if(!x) return `<td class="mut"></td>`;
      if(x.na) return `<td class="mut" ${x.nolang ? `title="Hier gibt es keine deutsche Fassung"` : ""}>${x.nolang ? "ohne DE" : "–"}</td>`;
      const champ = r.champ && r.champ.code === c.code;
      const counts = !x.nocard && x.lang !== "unknown";
      const g = counts && x.sale && x.grade && x.grade !== "wait" ? "c-" + x.grade : "";
      const tip = compose(c.code, x) + (champ ? " · Hier gab es den Bestpreis" : "") +
        (x.lang === "unknown" ? " · Sprache ungeprüft: zählt nicht" : "") + (x.nocard ? " · ohne Guthabenkarte mit Preis: zählt nicht" : "") +
        (needsRegion(r.dlc_of, c.code, r.slug) ? " · " + needTip(c.code, needsRegion(r.dlc_of, c.code, r.slug)) : "") +
(x.low_eur !== null && x.low_eur !== undefined ? ` · Landestief ${eur(x.low_eur)}` : "") + (x.sale && x.end ? ` · Angebot bis ${dm(x.end)}` : "");
      // Zwei Zeilen wie im Korb (0.81; vorher eine Zeile ohne Abstand zum Bestpreis): oben Preis | +x,
      // darunter Rabatt und Marken
      const need = needsRegion(r.dlc_of, c.code, r.slug), gap = r.champ && !atBest(x.eur, r.champ.eur) ? x.eur - r.champ.eur : 0;
      return `<td class="${g} ${champ ? "champ" : ""} ${counts ? "" : "nc"} ${need === "need" ? "needr" : ""}" title="${esc(tip)}">` +
        twoLine(`${star(x)}${ax(x)}${counts ? "" : `<span class="q">?</span>`}`, shopLink(r.slug, c.code, x, num(x.eur), c.currency), gap, cellMarks(x, ""), gapTip(r, x.eur)) +
        (det ? `<small>Landestief ${x.low_eur === null || x.low_eur === undefined ? "?" : eur(x.low_eur)}</small>${x.sale && x.end ? `<small>${endCell(x.end, "bis ")}</small>` : ""}${x.nocard ? `<small>ohne Karte</small>` : x.lang === "unknown" ? `<small><button class="link" data-act="gotitle" data-s="${esc(r.slug)}">Sprache?</button></small>` : ""}` : "") + `</td>`;
    }).join("") + `</tr>`)).join("");
  if(!rows.length) h += `<tr><td colspan="${cols.length + 2}" class="mut">Kein Titel passt zum Filter.</td></tr>`;
  return h + `</tbody></table></div>${noDlcLine(match)}<p class="hint" style="margin-top:6px">Zellfarbe für Angebote: dunkelgrün „kaufen“, hellgrün „gut“. Gold umrandet: hier gab es den Bestpreis. <span class="q">?</span> zählt nicht. Ein Klick auf den Preis öffnet den eShop des Lands, ohne eShop-Seite den Verlauf bei DekuDeals, auf den Titel die Einzelheiten.</p>`;
}
function viewSeg(){
  const b = (v, l, tip) => `<button data-act="tview" data-v="${v}" class="${S.tview === v ? "on" : ""}" title="${tip}">${l}</button>`;
  const n = S.ui && S.ui.basket ? S.ui.basket.length : 0;
  return `<span class="seg">${b("list", "Liste", "Eine Zeile je Titel mit Urteil und bestem Angebot")}${b("table", "Tabelle", "Alle Titel in allen Ländern")}${b("korb", `Korb${n ? ` <small>${n}</small>` : ""}`, "Deine Auswahl in allen Ländern, mit Summen, Karten und Rest")}</span>`;
}

/* ---------- Preisverlauf aus der eigenen Aufzeichnung ---------- */
const LINE_COLORS = ["#0d6b4f", "#c2410c", "#2563eb", "#9333ea", "#b45309", "#0891b2", "#be185d", "#4d7c0f", "#64748b", "#a16207", "#7c3aed"];
const dmy = iso => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit", year:"numeric"}); };
const dm = iso => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit"}); };
async function openVerlauf(slug){
  const v = await api("/api/verlauf?slug=" + encodeURIComponent(slug));
  // Sichtbar: Deutschland und jedes Land, in dem es ein Angebot gab
  S.vl = {data: v, show: new Set(v.countries.filter(c => c.code === "DE" || c.sale_count).map(c => c.code))};
  drawVerlauf();
  const d = $("verlauf");
  if(!d.open) d.showModal();
}
function drawVerlauf(){
  const v = S.vl.data, d = $("verlauf");
  const color = code => code === "DE" ? "var(--ink)" : LINE_COLORS[v.countries.findIndex(c => c.code === code) % LINE_COLORS.length];
  let h = `<header><h2>${esc(v.title)}</h2><a class="mini" href="/api/fall?slug=${encodeURIComponent(v.slug)}" download="fall-${esc(v.slug)}.json" title="Alle Daten dieses Titels als Datei (Preise, Tiefstwerte, Verlauf, Karten, Kurse, Einstellungen ohne Wishlist-Link). Schickst du sie mir, kann ich deinen Fall genau nachrechnen.">Fall exportieren</a><button data-act="vlclose" autofocus>Schließen</button></header>`;
  if(!v.countries.length){
    d.innerHTML = h + `<p class="hint">Noch keine Aufzeichnung für diesen Titel. Jeder Abgleich hält fest, wenn sich ein Preis ändert.</p>`;
    return;
  }
  const days = Math.max(0, (new Date(v.now) - new Date(v.since)) / 864e5);
  h += `<p class="hint">Aufgezeichnet seit ${dmy(v.since)} (${Math.round(days)} ${Math.round(days) === 1 ? "Tag" : "Tage"}). Europreise zum heutigen Kurs und Zahlweg, damit Länder und Zeitpunkte vergleichbar sind. Die Aufzeichnung kennt nur Zeiten, in denen das Tool lief.${days < 30 ? " Noch wenig Daten: Die Kurven werden mit jedem Abgleich aussagekräftiger." : ""}</p>`;
  h += `<div class="lg">` + v.countries.map(c => `<button class="${S.vl.show.has(c.code) ? "" : "off"}" data-act="vltoggle" data-c="${c.code}" title="ein- oder ausblenden"><i style="background:${color(c.code)}"></i>${esc(c.name)}</button>`).join("") + `</div>`;
  h += chartSvg(v, color);
  const V = "verlauf", vrows = sortRows(V, v.countries, {name: c => c.name, now: c => c.now_eur, regular: c => c.regular_eur,
    low: c => c.low_eur, sales: c => c.deku_sales ?? c.sale_count, days: c => c.typical_days, pct: c => c.on_sale_pct,
    last: c => { const l = c.sales[c.sales.length - 1]; return l ? -new Date(l.start) : null; }});
  h += `<div class="scroll"><table><thead><tr>${sth(V, "name", "Land")}${sth(V, "now", "jetzt")}${sth(V, "regular", "normal")}${sth(V, "low", "tiefster", "Niedrigster aufgezeichneter Preis")}${sth(V, "sales", "Angebote", "Angebote der letzten 24 Monate laut DekuDeals. Fehlt diese Angabe: wie oft der Titel in der eigenen Aufzeichnung unter dem heutigen Normalpreis lag")}${sth(V, "days", "Dauer", "Mittlere Dauer der abgeschlossenen Angebote")}${sth(V, "pct", "im Angebot", "Anteil der aufgezeichneten Zeit im Angebot")}${sth(V, "last", "zuletzt")}</tr></thead><tbody>` +
    vrows.map(c => {
      const a = c.est ? APPROX : "", last = c.sales[c.sales.length - 1];
      const lastTxt = !last ? "–" : last.end ? `${dm(last.start)}–${dm(last.end)}<small>−${last.pct} %, ${a}${eur(last.low_eur)}</small>` : `läuft seit ${dm(last.start)}<small>−${last.pct} %, ${a}${eur(last.low_eur)}</small>`;
      return `<tr><td>${esc(c.name)}</td><td>${c.now_eur === null ? "–" : a + eur(c.now_eur)}</td><td>${a}${eur(c.regular_eur)}</td>
        <td>${a}${eur(c.low_eur)}<small>${c.currency === "EUR" ? "" : money(c.low, c.currency) + " · "}${dm(c.low_at)}</small></td>
        <td>${c.deku_sales !== null && c.deku_sales !== undefined ? `${c.deku_sales}<small>24 Monate</small>` : `${c.sale_count}<small>aufgezeichnet</small>`}</td><td>${c.typical_days === null ? "–" : String(c.typical_days).replace(".", ",") + " T."}</td><td>${c.on_sale_pct} %</td><td>${lastTxt}</td></tr>`;
    }).join("") + `</tbody></table></div>`;
  d.innerHTML = h;
}
function chartSvg(v, color){
  // Breite nach Bildschirm, damit die Schrift auch auf dem Handy lesbar bleibt
  const W = Math.max(320, Math.min(860, window.innerWidth - 70)), H = W < 600 ? 220 : 260, L = 44, R = 10, T = 12, B = 26;
  const shown = v.countries.filter(c => S.vl.show.has(c.code));
  const t0 = +new Date(v.since), t1 = Math.max(+new Date(v.now), t0 + 864e5);
  const refs = [];
  if(v.champ) refs.push({y: v.champ.eur, label: "Bestpreis", col: "var(--gold)"});
  if(v.typical) refs.push({y: v.typical.eur, label: "typisch", col: "var(--muted)"});
  if(v.target !== null && v.target !== undefined) refs.push({y: v.target, label: "Ziel", col: "var(--accent)"});
  const top = Math.max(1, ...shown.map(c => Math.max(c.regular_eur, ...c.points.map(p => p[2]))), ...refs.map(r => r.y)) * 1.08;
  const x = t => L + (W - L - R) * (t - t0) / (t1 - t0), y = e => T + (H - T - B) * (1 - e / top);
  let g = "";
  const step = top > 40 ? 10 : top > 16 ? 5 : top > 6 ? 2 : 1;
  for(let e = 0; e <= top; e += step) g += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(e)}" y2="${y(e)}"/><text x="${L - 6}" y="${y(e) + 4}" text-anchor="end">${e} €</text>`;
  const ticks = W < 600 ? 3 : 5;
  for(let i = 0; i <= ticks; i++){
    const t = t0 + (t1 - t0) * i / ticks;
    g += `<text x="${x(t)}" y="${H - 8}" text-anchor="${i === 0 ? "start" : i === ticks ? "end" : "middle"}">${dm(new Date(t).toISOString())}</text>`;
  }
  for(const r of refs) g += `<line class="ref" x1="${L}" x2="${W - R}" y1="${y(r.y)}" y2="${y(r.y)}" style="stroke:${r.col}"><title>${esc(r.label)}: ${eur(r.y)}</title></line><text x="${W - R}" y="${y(r.y) - 4}" text-anchor="end" style="fill:${r.col}">${esc(r.label)} ${eur(r.y)}</text>`;
  for(const c of shown){
    const pts = c.points, col = color(c.code);
    let p = `M${x(+new Date(pts[0][0]))},${y(pts[0][2])}`;
    for(let i = 1; i < pts.length; i++) p += `H${x(+new Date(pts[i][0]))}V${y(pts[i][2])}`;
    p += `H${x(t1)}`;
    g += `<path class="ln" d="${p}" style="stroke:${col}"${c.code === "DE" ? ` stroke-dasharray="6 4"` : ""}/>`;
    g += pts.map(q => `<circle cx="${x(+new Date(q[0]))}" cy="${y(q[2])}" r="3.5" style="fill:${col}"><title>${esc(c.name)} ${dmy(q[0])}: ${c.currency === "EUR" ? "" : money(q[1], c.currency) + ", "}${c.est ? "ca. " : ""}${eur(q[2])}</title></circle>`).join("");
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Preisverlauf in Euro">${g}</svg>`;
}
