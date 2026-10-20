"use strict";
/* Kaufplan und Länderkarten (Teil der Oberfläche, Reihenfolge in index.html) */
/* ---------- Kaufplan: was jetzt wo kaufen ---------- */
function planSums(steps){
  const opt = steps.reduce((a, p) => a + (p.optimum ?? 0), 0);
  const gap = steps.reduce((a, p) => a + (p.opt_gap ?? 0), 0);
  return {opt, gap};
}
/* Eigene Änderungen am Kaufplan (× und dazugenommen), für „Plan zurücksetzen“ (1.0.3) */
const planMine = () => [S.ui.plan_skip, S.ui.plan_fill].some(m => Object.values(m || {}).some(l => (l || []).length));
function viewKauf(){
  const k = S.kauf;
  if(!k) return `<p class="hint">Kaufplan wird berechnet …</p>`;
  const sums = planSums(k.steps);
  const head = k.count
    ? `<b class="big">${eur(k.cost)}</b><span>${k.count} Titel in ${k.steps.length} ${k.steps.length === 1 ? "Land" : "Ländern"} · ${atBest(sums.opt + sums.gap, sums.opt) && k.steps.every(p => itemsAtBest(p.items)) ? `<span class="g-buy"${nearTip(sums.gap)}>am Bestpreis</span>` : `<span class="abv">+${eur(sums.gap)}</span> über Bestpreis-Summe ${eur(sums.opt)}`}${k.rest_lost ? ` · <span class="bad">${eur(k.rest_lost)}</span> Rest verfällt beim Wechsel` : ""}</span>`
    : `<span>Gerade steht kein Titel auf „kaufen“${!S.ui.plan_good && k.good_left ? `, aber ${k.good_left} auf „gut“: rechts „auch gute Angebote“ anhaken` : ""}.</span>`;
  let h = `<div class="bar on"><b>Jetzt kaufen</b>${head}<span class="sp"></span>
    <label title="Neben „kaufen“ auch Titel mit dem Urteil „gut“ einplanen"><input type="checkbox" data-act="plangood" ${S.ui.plan_good ? "checked" : ""}> auch gute Angebote${!S.ui.plan_good && k.good_left ? ` (${k.good_left})` : ""}</label>
    ${planMine() ? `<button class="link" data-act="planresetall" title="Alles, was du in den Schritten herausgenommen oder dazugenommen hast, verwerfen: der Plan wie vorgeschlagen">Plan zurücksetzen</button>` : ""}
    </div>`;
  if(k.lock) h += lockBox(k);
  // Alte Preise in einem Schritt (0.95): oben sagen, nicht nur an der Karte
  const stale = k.steps.filter(p => p.price_stale);
  if(stale.length) h += `<p class="restline"><span class="bad">Preise nicht aktuell:</span> ${stale.map(p => `${esc(p.name)} vom ${esc(dmy(p.price_at))}`).join(", ")}. Der letzte Abruf dort scheiterte, Angebote können inzwischen geendet haben. <button class="link" data-act="showlog">Protokoll</button></p>`;
  if(k.steps.length) h += `<div class="grid steps masonry">` + k.steps.map((p, n) => planCard(p, n + 1)).join("") + `</div>`;
  else h += emptyPlan();
  h += notPlanned(k);
  h += `<p class="restline">Jedes Land mit seinem eigenen Korb, zum Durchspielen: <button class="link" data-act="allland">alle Länderkarten</button></p>`;
  h += boughtBox(k);
  return h;
}
function emptyPlan(){
  // Die nächsten Chancen: Angebote mit dem kleinsten Abstand zum Bestpreis
  const near = S.state.radar.filter(r => r.verdict === "good" || r.verdict === "wait")
    .filter(r => shownOffer(r) && shownOffer(r).sale).sort((a, b) => (a.diff ?? 1e9) - (b.diff ?? 1e9)).slice(0, 3);
  if(!near.length) return `<p class="restline">Heute ist nichts auf „kaufen“.</p>`;
  return `<p class="restline">Heute ist nichts auf „kaufen“. Am nächsten dran:</p><div class="box"><table class="mini-t">` + near.map(r => {
    const x = shownOffer(r);
    return `<tr><td><button class="link" data-act="gotitle" data-s="${esc(r.slug)}">${esc(r.title)}</button></td><td class="l">${pill(r.verdict)}</td><td>${ax(x)}${eur(x.eur)} ${esc(x.name)}</td><td>+${eur(r.diff || 0)} über Bestpreis</td><td>${x.end ? endCell(x.end, "bis ") : ""}</td></tr>`;
  }).join("") + `</table></div>`;
}
/* Konto in einem Land, dessen Rest den Wechsel blockiert: Der Plan bleibt dort */
function lockBox(k){
  const l = k.lock, cur = l.currency || "";
  const step = k.steps.find(p => p.code === l.code);
  const after = step ? (l.left ? ` Nach dem Kauf bleiben ${money(l.left, cur)}.` : " Der Kauf braucht es ganz auf, danach ist der Wechsel frei.") : "";
  return `<p class="restline"><span class="bad">Konto steht in ${esc(l.name)} mit ${money(l.balance, cur)} Guthaben.</span> Ein Rest dort blockiert den Länderwechsel, deshalb plant der Kaufplan nur dort.${after}` +
    ` Andere Länder kommen dran, wenn das Guthaben aufgebraucht ist oder der Support es löst.` +
    (l.fits.length ? ` Passt hinein: ${l.fits.map(esc).join(", ")}.` : "") +
    ((k.held || []).length ? ` Wartet deshalb: ${k.held.map(h => esc(h.short)).join(", ")}.` : "") + `</p>`;
}
/* Nicht im Plan (0.96, 0.98 neu gebaut): nach Grund, darin nach Land oder Quelle, darin nach Spiel; jede Ebene
   klappbar (data-kc: offen, gemerkt wird das Zuklappen; „alle aufklappen · alle zuklappen“ oben). Jeder Titel
   eine Zeile im selben Raster wie die Kopfzeile, damit Preise untereinander stehen (`.npr`): Name wie in der
   Wishlist (voller Name, in einer Spielgruppe ohne Spielnamen), Urteil, Einkaufspreis mit ★ (Link in den
   eShop, ohne eShop-Seite wie bei DLC zu DekuDeals), Rabatt, Land (Link zum Preisverlauf bei DekuDeals),
   über Bestpreis, bis, Handlung. */
const NP_COLS = `<div class="npr nph"><span>Titel</span><span>Urteil</span><span class="r">Einkaufspreis</span><span></span><span title="Land mit dem günstigsten Einkaufspreis jetzt; Klick: Preisverlauf bei DekuDeals">Land</span><span class="r">über Bestpreis</span><span>bis</span><span></span></div>`;
function npRow(slug, o){
  o = o || {};
  const r = S.state.radar.find(x => x.slug === slug), m = rowOf(slug) || {};
  const title = (r || m).title || slug, dlc = (r || m).dlc_of;
  const short = o.game && title.toLowerCase().startsWith(o.game.toLowerCase()) ? title.slice(o.game.length).replace(/^[\s:–\-+]+/, "") || title : title;
  const name = `${dlc ? `<span class="dlc${(r || m).parent_owned ? " has" : ""}" title="DLC zu ${esc(dlc)}">DLC</span>` : ""}<button class="link np-n" data-act="gotitle" data-s="${esc(slug)}" title="Einzelheiten zu ${esc(title)}">${esc(short)}</button>`;
  const off = r ? cheapestOffer(r) : null, ce = r && r.champ;
  const x = off ? Object.assign({}, off, (m.cells || {})[off.code] || {}, {eur: off.eur}) : null;   // Zelle bringt die eShop-ID für den Link
  // Dazunehmen in jeden Schritt, in dem es den Titel gibt, mit dem Preis dort (wie „Titel dazunehmen …“ am Schritt)
  const steps = (S.kauf ? S.kauf.steps : []).map((p, n) => ({p, n, c: (m.cells || {})[p.code]}))
    .filter(y => y.c && !y.c.na && y.c.eur !== null && y.c.eur !== undefined && !y.p.items.some(i => i.slug === slug));
  const act = o.act !== undefined ? o.act : steps.length
    ? `<select class="np-add" data-act="npadd" data-s="${esc(slug)}" title="${esc(title)} in einen Schritt des Kaufplans nehmen; der Plan rechnet neu"><option value="">dazunehmen …</option>${steps.map(y => `<option value="${y.p.code}">Schritt ${y.n + 1}, ${esc(y.p.name)} · ${eur(y.c.eur)}${off && y.c.eur > off.eur + 0.005 ? ` (+${eur(y.c.eur - off.eur)})` : ""}</option>`).join("")}</select>`
    : `<small class="mut" title="Kein Schritt des Kaufplans bietet den Titel an">in keinem Schritt</small>`;
  return `<div class="npr"><span class="t">${name}${o.note ? `<small class="np-w">${o.note}</small>` : ""}</span>` +
    `<span class="c-vd">${r ? pill(r.verdict) : ""}${r && r.nohist ? ` <span class="nohist" title="DekuDeals hat noch keinen Tiefstpreis geliefert">ohne Verlauf</span>` : ""}</span>` +
    `<span class="r c-eur">${x ? `${star(x)}${ax(x)}${shopLink(slug, x.code, x, eur(x.eur), x.currency)}` : `<span class="mut">–</span>`}</span>` +
    `<span class="c-pct">${x && x.sale ? `<span class="pct">−${x.pct} %</span>` : ""}</span>` +
    `<span class="c-land">${x ? priceLink(slug, x.code, esc(x.name), x, x.currency) : ""}</span>` +
    `<span class="r c-best">${x && ce ? overBest(x.eur, ce.eur, r.verdict === "none" ? null : r.verdict) : `<span class="mut">–</span>`}</span>` +
    `<span class="c-end">${x && x.sale && x.end ? endCell(x.end) : ""}</span><span class="c-act">${act}</span></div>`;
}
/* Titel eines Blocks nach Spiel: zwei und mehr Titel eines Spiels unter einer klappbaren Zeile mit seinem Namen,
   wie die Gruppen der Wishlist; ein einzelner mit vollem Namen */
function npTitles(slugs, key, o){
  o = o || {};
  const units = new Map();
  for(const s of slugs){
    const r = S.state.radar.find(x => x.slug === s) || rowOf(s) || {};
    const g = r.dlc_of || r.title || s;
    if(!units.has(g)) units.set(g, []);
    units.get(g).push(s);
  }
  const opt = s => ({note: o.note ? o.note(s) : "", act: o.act ? o.act(s) : undefined});
  return [...units].sort((a, b) => a[0].localeCompare(b[0], "de")).map(([g, list]) => list.length < 2
    ? npRow(list[0], opt(list[0]))
    : npFold(`np:t:${key}:${g}`, `<b>${esc(g)}</b> <small class="mut">${list.length} Titel</small>`, list.map(s => npRow(s, Object.assign(opt(s), {game: g}))).join(""), "npg")).join("");
}
/* Mit × aus einem Schritt genommen (0.99.4): Der Grund steht am Titel, wo er auch landet */
function skippedFrom(slug){
  const from = Object.entries(S.ui.plan_skip || {}).filter(([, l]) => (l || []).includes(slug)).map(([c]) => country(c).name);
  return from.length ? `von dir aus ${esc(from.join(", "))} herausgenommen, wartet` : "";
}
function npFold(k, head, body, cls){
  return `<details class="npf ${cls || ""}" data-kc="${esc(k)}" ${S.folds[k] ? "" : "open"}><summary>${head}</summary>${body}</details>`;
}
function notPlanned(k){
  const groups = [], seen = new Set(), mark = list => list.forEach(s => seen.add(s));
  const add = (key, label, why, body, n) => { if(body) groups.push(npFold(`np:g:${key}`, `${esc(label)}${n ? ` <span class="mut">${n}</span>` : ""}`, (why ? `<p class="hint">${why}</p>` : "") + body, "npgrp")); return n; };
  const gap = d => d.blocked_by ? `<span class="bad">nur ein Land mit blockierendem Rest je Plan</span>, ${esc(d.blocked_by.join(", "))} bringt mehr`
    : `Wechsel ${d.gain >= 0 ? `spart nur <span class="bad">${eur(d.gain)}</span>` : `kostet <span class="bad">${eur(-d.gain)}</span> mehr`}${d.threshold !== null && d.threshold !== undefined ? `, lohnt ab ${eur(d.threshold)} Ersparnis` : ""}`;
  const sums = [];
  // Wechsel: Konto gesperrt oder Land lohnt nicht. Je Land klappbar; was der Plan woanders kauft, steht zur Erklärung dabei
  let sw = "", nsw = 0;
  if((k.held || []).length){
    const list = k.held.map(h => h.slug); mark(list); nsw += list.length;
    sw += npFold("np:c:lock", `Konto in <b>${esc(k.lock.name)}</b>: <span class="bad">Wechsel blockiert</span>, bis das Guthaben dort aufgebraucht ist`,
      npTitles(list, "lock", {note: s => `günstiger in ${esc((k.held.find(h => h.slug === s) || {}).name || "")}`}));
  }
  for(const d of k.dropped){
    const open = d.open_slugs || [], moved = d.moved || [];
    if(!open.length && !moved.length) continue;
    mark(open); nsw += open.length;
    const note = s => { const m = moved.find(x => x.slug === s); if(!m) return skippedFrom(s) || "wartet"; const n = S.kauf.steps.findIndex(p => p.code === m.to); return `<span class="chip">im Plan</span> Schritt ${n + 1}, ${esc(country(m.to).name)}`; };
    sw += npFold(`np:c:${d.code}`, `<b>${esc(d.name)}</b> ${tierTag(TIER_OF(d))} <span class="mut">${open.length ? `${open.length} wartet` : ""}${open.length && moved.length ? ", " : ""}${moved.length ? `${moved.length} im Plan` : ""}</span> · ${gap(d)} · <button class="link" data-act="goland" data-c="${d.code}" title="Die Länderkarte von ${esc(d.name)} mit eigenem Korb öffnen">Länderkarte</button>`,
      npTitles(open.concat(moved.map(m => m.slug)), d.code, {note, act: s => moved.some(m => m.slug === s) ? "" : undefined}));
  }
  if(add("sw", "Wechsel lohnt nicht", "Im günstigsten Land spart der Kauf zu wenig, um den Wechsel dorthin zu rechtfertigen. Was wartet, kannst du trotzdem dazunehmen; was „im Plan“ trägt, kauft der Plan in einem anderen Land.", sw, nsw)) sums.push(`Wechsel lohnt nicht ${nsw}`);
  // Kleinkram (0.92): wartet, bis du ihn über „Passt in den Rest“ dazunimmst (0.98). Je Land mit Summe;
  // füllt er eine Karte fast ganz, ein Vorschlag (0.93)
  let sm = "", nsm = 0;
  const grouped = new Set();
  for(const g of k.small_groups || []){
    g.slugs.forEach(x => grouped.add(x)); mark(g.slugs); nsm += g.slugs.length;
    const faces = (g.cards || []).reduce((n, c) => n + c.face * c.count, 0);
    const card = (g.cards || []).map(c => `${c.count > 1 ? c.count + "× " : ""}${money(c.face, g.currency)}`).join(" + ");
    const of = g.smallest && faces ? `zusammen ${money(g.local, g.currency)} von ${card} <span class="mut">(${Math.round(100 * g.local / faces)} %)</span>` : `zusammen ${money(g.local, g.currency)}`;
    const take = !g.full ? "" : ` · <span class="gn">reicht für eine eigene Karte</span> ` + (g.step
      ? `<button class="sm" data-act="planfill" data-c="${g.code}" data-s="${esc(g.slugs.join(","))}" title="Nimmt den Kleinkram in den Schritt ${esc(g.name)}; der Plan kauft dafür ${esc(card)}">alle dazunehmen</button>`
      : `<button class="sm" data-act="add" data-c="${g.code}" data-s="${esc(g.slugs.join(","))}" title="Legt den Kleinkram in den Korb der Länderkarte ${esc(g.name)}">in die Länderkarte</button>`);
    sm += npFold(`np:k:${g.code}`, `<b>${esc(g.name)}</b> <span class="mut">${g.slugs.length} Titel</span> · ${of}${take}`, npTitles(g.slugs, "k" + g.code));
  }
  const loose = (k.small || []).filter(x => !grouped.has(x.slug)).map(x => x.slug);
  if(loose.length){ mark(loose); nsm += loose.length; sm += npTitles(loose, "kx"); }
  if(add("small", "Kleinkram", `Unter ${eur(S.state.settings.deal_eur.mini)} macht ein Titel keine Guthabenkarte größer. Er wartet und steht unter „Passt in den Rest“ zur Auswahl, sobald ein Rest bleibt.`, sm, nsm)) sums.push(`Kleinkram ${nsm}`);
  const later = k.later.map(l => l.slug); mark(later);
  if(add("later", "Lieber warten", "Den guten Preis gibt es nur in einem Land, dessen Wechsel sich nicht rechnet; in den übrigen ist es kein Kauf.",
    later.length ? npTitles(later, "later", {note: s => esc((k.later.find(l => l.slug === s) || {}).reason || "")}) : "", later.length)) sums.push(`Lieber warten ${later.length}`);
  // Was du geändert hast: herausgenommen aus einem Land ohne Schritt (0.94), übernommen ohne Schritt (0.95)
  const skipped = k.skipped || [], idle = k.fill_idle || [];
  mark(skipped.map(x => x.slug)); mark(idle.map(x => x.slug));
  const mine = (skipped.length ? npTitles(skipped.map(x => x.slug), "skip", {
      note: s => { const x = skipped.find(y => y.slug === s); return `aus ${esc(x.name)} herausgenommen${x.to ? `, jetzt in ${esc(country(x.to).name)}` : ""}`; },
      act: s => { const x = skipped.find(y => y.slug === s); return `<button class="sm" data-act="planunskip" data-c="${x.code}" data-s="${esc(s)}">zurück</button>`; }}) : "") +
    (idle.length ? npTitles(idle.map(x => x.slug), "idle", {
      note: s => { const x = idle.find(y => y.slug === s); return `für ${esc(x.name)} übernommen${x.to ? `, gerade in ${esc(country(x.to).name)}` : ""}${x.step ? "" : "; kommt dazu, sobald dort ein Schritt kauft"}`; },
      act: s => { const x = idle.find(y => y.slug === s); return `<button class="sm" data-act="planunfill" data-c="${x.code}" data-s="${esc(s)}" title="Nicht mehr für ${esc(x.name)} vormerken">entfernen</button>`; }}) : "");
  if(add("mine", "Von dir geändert", "Steht hier, solange es dazu keinen Schritt gibt.", mine, skipped.length + idle.length)) sums.push(`Von dir geändert ${skipped.length + idle.length}`);
  // Schon gekauft, mit Quelle (0.95); entfernen geht nur bei DekuDeals
  const HOW = {plan: "Im Kaufplan als gekauft vermerkt", collection: "In deiner Sammlung", eshop: "Laut eShop-Kaufverlauf gekauft"};
  const how = k.bought_how || [], dk = s => `<a class="pl" href="${esc(deku(s))}" target="_blank" rel="noopener" title="Bei DekuDeals öffnen und von der Wishlist nehmen">bei DekuDeals</a>`;
  let ow = "";
  for(const key of ["plan", "collection", "eshop"]){
    const list = how.filter(x => x.how === key).map(x => x.slug);
    if(list.length) ow += npFold(`np:o:${key}`, `${HOW[key]} <span class="mut">${list.length}</span>`, npTitles(list, "o" + key, {act: dk}));
  }
  const packs = {};
  for(const x of how.filter(x => x.how === "pack")) (packs[x.via] = packs[x.via] || []).push(x.slug);
  for(const [via, list] of Object.entries(packs)) ow += npFold(`np:o:p:${via}`, `Steckt in <b>${esc(via)}</b>, das du schon hast <span class="mut">${list.length}</span>`, npTitles(list, "op", {act: dk}));
  mark(how.map(x => x.slug));
  if(add("owned", "Schon gekauft", "Steht noch auf der Wishlist; entfernen kannst du es bei DekuDeals.", ow, how.length)) sums.push(`Schon gekauft ${how.length}`);
  const s2 = k.s2_skip || [], packed = k.packed || [], nowhere = k.nowhere_slugs || [];
  mark(s2.map(x => x.slug)); mark(packed.map(x => x.slug)); mark(nowhere);
  const other = (s2.length ? npTitles(s2.map(x => x.slug), "s2", {note: s => `nur ein Weg zur Switch 2: ${esc((s2.find(x => x.slug === s) || {}).reason || "")}`, act: () => ""}) : "") +
    (packed.length ? npTitles(packed.map(x => x.slug), "pk", {note: s => `steckt in ${esc((packed.find(x => x.slug === s) || {}).pack || "")}, das ebenfalls zum Kauf ansteht`, act: () => ""}) : "") +
    (nowhere.length ? npTitles(nowhere, "nw", {note: () => "nirgends kaufbar, wo es zählt", act: () => ""}) : "");
  const nother = s2.length + packed.length + nowhere.length;
  if(add("other", "Sonst nicht im Plan", "", other, nother)) sums.push(`Sonst ${nother}`);
  if(!groups.length) return "";
  const n = seen.size;      // nur was wirklich nicht im Plan ist; „im Plan“-Zeilen sind nicht markiert
  return `<details class="box fold np" data-k="notplan" ${S.folds.notplan ? "open" : ""}><summary>Nicht im Plan <span class="mut">· ${n ? `${n} Titel: ${sums.join(" · ")}` : "alles im Plan, hier nur günstigere Länder ohne lohnenden Wechsel"}</span></summary>` +
    `<p class="hint np-tools"><span class="foldall"><button class="link" data-act="foldall" data-v="1">alle aufklappen</button> · <button class="link" data-act="foldall" data-v="">alle zuklappen</button></span></p>` +
    `<div class="np-grid">${NP_COLS}${groups.join("")}</div></details>`;
}
const TIER_OF = d => ({leicht:1, mittel:2, schwer:3})[d.tier_name];
function boughtBox(k){
  if(!k.bought.length) return "";
  return `<details class="box fold" data-k="bought" ${S.folds.bought ? "open" : ""}><summary>Gekauft (${k.bought.length}) <span class="mut">· insgesamt ${eur(k.bought_saving)} unter dem deutschen Preis</span></summary><table class="mini-t">` +
    k.bought.map(b => `<tr><td>${dmy(b.at)}</td><td class="l">${esc(country(b.code).name)}: ${b.titles.map(esc).join(", ")}</td><td title="${b.games !== null && b.games !== undefined ? `Spiele ${eur(b.games)}, Karten ${eur(b.cost)}: der Rest bleibt als Guthaben` : `Kartenkosten`}">${eur(b.games ?? b.cost)}${b.de !== null && b.de !== undefined ? ` <small style="display:inline" class="mut">statt ${eur(b.de)} in DE</small>` : ""}</td><td>${b.rest ? `Rest ${money(b.rest, b.currency)}` : ""}</td></tr>`).join("") +
    `</table><p class="hint" style="margin-top:6px"><button class="link" data-act="unbought" title="Den letzten Kauf zurücknehmen, Land und Guthaben wie vorher">letzten Kauf zurücknehmen</button></p></details>`;
}
function altNames(codes){
  return (codes || []).length ? codes.map(c => country(c).name).join(", ") : "Deutschland";
}

/* ---------- Länder: Angebote je Land ---------- */
function sortPlans(list){
  const endOf = p => Math.min(Infinity, ...p.items.filter(i => i.end).map(i => +new Date(i.end)));
  const sav = (a, b) => (b.gain ?? b.saving ?? -1e9) - (a.gain ?? a.saving ?? -1e9);
  const opt = (a, b) => (a.opt_gap ?? 1e9) - (b.opt_gap ?? 1e9) || sav(a, b);
  const by = {optimum: opt, saving: sav, rest: (a, b) => (a.rest_value ?? a.rest_eur ?? 1e9) - (b.rest_value ?? b.rest_eur ?? 1e9) || sav(a, b),
              end: (a, b) => endOf(a) - endOf(b) || sav(a, b), tier: (a, b) => a.tier - b.tier || sav(a, b)}[S.lsort] || sav;
  // Das Land, in dem das Konto steht, vorn, dann die Alternativen, Deutschland als Vergleich am Ende
  const cur = list.filter(p => p.current), rest = list.filter(p => !p.current);
  return cur.concat(rest.filter(p => !p.is_ref).sort(by), rest.filter(p => p.is_ref));
}
function hiddenLine(){
  if(!S.ui.hidden.length) return "";
  return `<p class="restline">Ausgeblendet: ` + S.ui.hidden.map(c =>
    `${esc(country(c).name)} <button class="link" data-act="unhide" data-c="${c}">einblenden</button>`).join(" · ") + `</p>`;
}
function viewCards(){
  const back = `<button class="link" data-act="gotab" data-v="jetzt" title="Zurück zum Kaufplan">← Kaufplan</button>`;
  // Ein Land aus „Andere Länder“ (0.74): nur seine Karte, darunter der Weg zu allen
  const focus = S.landFocus && cardPlans().find(p => p.code === S.landFocus);
  // Aus „Andere Länder“: erst die Titel des Schritts in diesem Land, darunter sein eigener Korb
  const lp = S.landStep && S.landStep.code === S.landFocus ? S.landStep : null;
  if(focus || lp) return `<div class="tools">${back}<span class="sp"></span><button class="sm" data-act="allland">alle Länder</button></div>` +
    (lp ? `<p class="restline">Die Titel aus Schritt ${lp.step} (${esc(lp.from)}) in ${esc(lp.p.name)}, zum Vergleich:</p><div class="grid list">${planCard(lp.p)}</div>` : "") +
    (focus ? `${lp ? `<p class="restline">${esc(focus.name)} mit eigenem Korb, aus allen Titeln, die dort im Angebot sind:</p>` : ""}<div class="grid list">${planCard(focus)}</div>` : "");
  const opt = (v, l) => `<option value="${v}" ${S.lsort === v ? "selected" : ""}>${l}</option>`;
  // Werkzeugzeile wie in Titel: links Reihenfolge, rechts der Ansichtsschalter (0.59)
  let h = `<div class="tools">${back}<select class="srt" data-act="sort" title="Reihenfolge der Länder">${opt("optimum","nach Abstand zum Bestpreis")}${opt("saving","nach Wechselgewinn")}${opt("rest","nach Rest")}${opt("end","nach Angebotsende")}${opt("tier","nach Stufe")}</select>
    ${Object.values(S.ui.overrides).some(ov => ov && ((ov.add || []).length || (ov.remove || []).length)) ? `<button class="sm" data-act="resetall" title="Eigene Änderungen an allen Warenkörben verwerfen">alle zurücksetzen</button>` : ""}
    <span class="seg"><button data-act="dense" data-v="1" class="${S.dense ? "on" : ""}">Raster</button><button data-act="dense" data-v="0" class="${S.dense ? "" : "on"}">Liste</button></span></div>`;
  const cards = [], empty = [];
  for(const p of sortPlans(cardPlans())){
    if(S.ui.hidden.includes(p.code) && !p.is_ref) continue;
    (!p.items.length && !p.fillers.length ? empty : cards).push(p);
  }
  h += `<div class="grid ${S.dense ? "masonry" : "list"}">${cards.map(p => planCard(p)).join("")}</div>`;
  if(empty.length)
    h += `<p class="restline">Ohne passendes Angebot: ` + empty.map(p =>
      `${esc(p.name)} <small>(${p.rate ? p.available + " kaufbar" : "noch keine Preise"})</small>`).join(" · ") + `</p>`;
  return h + hiddenLine();
}
/* Ansicht Korb ohne Korb: wie man einen anlegt (0.59) */
function viewKorbEmpty(){
  return `<div class="tools"><span class="sp"></span>${viewSeg()}</div><div class="box"><p><b>Noch kein Korb.</b> Ein Korb ist deine eigene Auswahl an Titeln, verglichen in allen Ländern: Was kostet genau das hier, dort und aufgeteilt?</p>
    <p class="hint">So legst du einen an: „+“ in der Spalte Korb der Liste oder vor dem Titel in der Tabelle, „Titel dazunehmen …“ oder „als Korb vergleichen“ an einem Schritt des Kaufplans. Der Kaufplan unter „Jetzt“ kauft dagegen in mehreren Ländern nacheinander, das ist kein Korb.</p>
    </div>`;
}
function cardsHtml(p){
  return p.cards.map(c => {
    const t = `${c.count}× ${num(c.face, p.currency)}`;
    return c.url ? `<a class="pl" href="${esc(c.url)}" target="_blank" rel="noopener" title="Karte kaufen">${t}</a>` : t;
  }).join(" + ");
}
/* Zeile „Preis“: wie nah das Paket an der Summe der Bestpreise liegt */
function priceLine(p){
  if(p.opt_gap === null || p.opt_gap === undefined) return `<span class="mut">Bestpreise noch nicht bekannt</span>`;
  const games = (p.games_cost ?? p.cost) - (p.rest_lost || 0);
  // Unter der Bestpreis-Summe nur mit Angeboten, die nicht zählen. Im Paket teilen sich die
  // Titel die Karten und kommen oft etwas unter die einzeln gerechneten Bestpreise: Das ist richtig
  const under = games < p.optimum - 0.5 && p.items.some(i => i.lang === "unknown" || i.nocard);
  const counts = ["buy", "good", "wait"].map(g => [g, p.items.filter(i => i.grade === g).length]).filter(([, n]) => n)
    .map(([g, n]) => `${n}× ${VERDICT[g]}`).join(", ");
  const spiele = p.rest_value >= 0.5 || p.balance_value ? `Spiele ${eur(games)} · ` : "";
  const tip = `Bestpreis-Summe ${eur(p.optimum)}: was diese ${p.items.length} Titel zum jeweiligen Bestpreis gekostet hätten. Die Spiele kosten hier ${eur(games)}` +
    (p.rest_value >= 0.5 ? ` (von ${eur(p.cost)} für die Karten bleiben ${eur(p.rest_value)} als Rest)` : "") + `. Rot ist der Betrag über der Bestpreis-Summe, die Urteile stehen dahinter.`;
  const main = under ? `<span class="warnc" title="${esc(tip)} So billig nur mit Angeboten, die nicht zählen (Sprache ungeprüft oder ohne Guthabenkarte): erst prüfen."><span class="q">?</span> ${eur(p.optimum - games)} unter Bestpreis-Summe, zählt nicht</span>`
    : `<span title="${esc(tip)}">${atBest(p.optimum + p.opt_gap, p.optimum) && itemsAtBest(p.items) ? `<span class="g-${p.grade || "buy"}"${nearTip(p.opt_gap)}>am Bestpreis</span>` : `<span class="abv">+${eur(p.opt_gap)}</span> über Bestpreis-Summe ${eur(p.optimum)}${p.opt_pct ? ` (${p.opt_pct} %)` : ""}`}</span>`;
  return `${spiele}${main}${counts ? ` <span class="mut">· ${counts}</span>` : ""}`;
}
/* Was beim Wechsel verfällt: Guthaben aus dem Kontoland, Rest dieses Schritts */
function lostTxt(p){
  const bal = p.balance_lost || 0, rest = (p.rest_lost || 0) - bal;
  return [bal >= 0.005 ? `${eur(bal)} Guthaben im Kontoland, das beim Wechsel hierher verfällt` : "",
          rest >= 0.005 ? `${eur(rest)} Rest, der beim nächsten Wechsel verfällt` : ""].filter(Boolean).join(" und ");
}
/* Zeile „Wechsel“: lohnt der Weg in dieses Land gegenüber der Alternative? */
function switchLine(p){
  if(p.home) return `<span class="mut" title="Kein Kontoland eingetragen: Deutschland gilt als dein Konto. Deutschland zum Shop-Preis ist die Vergleichsbasis.">Vergleichsbasis, kein Wechsel</span>`;
  if(p.gain === null || p.gain === undefined) return `<span class="mut">–</span>`;
  const tip = `Wechselgewinn: was diese Titel ohne den Wechsel kosten (${eur(p.alt_total)} in ${altNames(p.alt_codes)}) minus was sie hier kosten (${eur(p.games_cost)})` +
    (p.rest_lost ? `, samt ${lostTxt(p)}` : "") +
    `. Gegenüber Deutschland: ${p.saving >= 0 ? "spart " : "kostet "}${eur(Math.abs(p.saving))}.`;
  const vs = `gegenüber ${esc(altNames((p.alt_codes || []).slice(0, 2)))}`;
  const amount = p.gain >= 0 ? `spart ${eur(p.gain)} ${vs}` : `kostet ${eur(-p.gain)} mehr als ${esc(altNames((p.alt_codes || []).slice(0, 2)))}`;
  const lost = p.rest_lost ? ` · darin ${lostTxt(p)}` : "";
  if(p.current) return `<span title="${esc(tip)}">Konto steht hier, kein Wechsel</span>`;
  if(p.worth) return `<span title="${esc(tip)}"><b>✓ lohnt</b> · ${amount}${lost}</span>`;
  return `<span title="${esc(tip)}"><b class="bad">lohnt nicht</b> · ${amount}, lohnt ab ${eur(p.threshold)}${lost}</span>`;
}
/* Zeile „Rest“: was übrig bleibt und ob ein Wishlist-Titel hineinpasst */
function restLine(p, last){
  if(p.is_ref || p.via === "card") return "";
  if(p.rest === null) return `<span class="warnc">Rest unbekannt</span>`;
  if(!p.rest) return `<span>kein Rest</span>`;
  const blocked = !last && p.warnings.some(w => w.startsWith("Rest blockiert"));
  const fits = (p.fill || []).length ? [] : p.fillers.filter(f => f.slugs.length === 1 && f.extra < 0.005);
  // Ein Rest aus vorhandenem Guthaben hat keinen neuen Preis: dann ohne Europreis statt „(0,00 €)“
  const rv = p.rest_value ?? p.rest_eur;
  return `<span class="${blocked ? "bad" : rv >= 5 ? "warnc" : ""}">${money(p.rest, p.currency)}${rv > 0.005 ? ` (${eur(rv)})` : p.balance_value ? " aus deinem Guthaben" : ""}</span>` +
    (fits.length ? ` · passt hinein: ${fits.map(f => esc(f.shorts[0])).join(", ")}` : "");
}
/* DLC, deren Hauptspiel nicht im Korb liegt und aus dieser Region kommen muss (Europa passt zum deutschen Konto) */
/* Auswahl „Titel dazunehmen“ (0.60, bis 0.68 „Wishlist-Titel dazunehmen“): nach Urteil gruppiert, darin nach Namen, damit man findet,
   was man sucht; Tippen springt im geöffneten Feld zum Titel */
function wishOpts(rows, label, nso){
  const vd = slug => (S.state.radar.find(x => x.slug === slug) || {}).verdict || "none";
  const groups = [["buy", "kaufen"], ["good", "gut"], ["wait", "warten"], ["none", "ohne Urteil"]];
  return groups.map(([v, l]) => {
    const g = rows.filter(r => vd(r.slug) === v).sort((a, b) => a.title.localeCompare(b.title, "de"));
    return g.length ? `<optgroup label="${l}">${g.map(r => { const t = label ? label(r) : ""; return `<option value="${esc(r.slug)}">${esc(r.title)}${(r.dlc_of || rowOf(r.slug).dlc_of) ? " (DLC)" : ""}${t ? " · " + t : ""}</option>`; }).join("")}</optgroup>` : "";
  }).join("") + (nso ? extraOpts(nso.code, nso.skip) + nsoOpts(nso.code, nso.skip) : "");
}
/* Fehlende DLC deiner Spiele, die nicht auf der Wishlist stehen (0.72): im Land mit dem Preis dort */
function extraOpts(code, skip){
  const o = (S.state.extra_offers || []).filter(x => !skip.has(x.slug) && (!code || x.local[code] !== undefined)).map(x =>
    `<option value="${esc(x.slug)}">${x.game ? esc(x.game) + ": " : ""}${esc(x.title)} · ${code ? money(x.local[code], (S.state.pay[code] || {}).currency || "EUR") : eur(x.eur)}</option>`).join("");
  return o ? `<optgroup label="Fehlende DLC deiner Spiele">${o}</optgroup>` : "";
}
/* Online-Mitgliedschaft unter „Titel dazunehmen“ (0.69): jede Variante mit Preis, im Land mit dem Preis dort */
function nsoOpts(code, skip){
  const o = ((S.state.nso || {}).variants || []).filter(v => !skip.has("nso-" + v.key)).map(v => {
    const rows = (v.rows || []).filter(r => !code || r.code === code);
    const r = code ? rows.find(x => !x.src) || rows[0] : v.best;
    return r ? `<option value="nso-${v.key}">${esc(v.label)} · ${code ? money(r.local, r.currency) : eur(r.eur)}</option>` : "";
  }).join("");
  return o ? `<optgroup label="Online-Mitgliedschaft">${o}</optgroup>` : "";
}
/* DLC außerhalb Europas (ab 0.61): Ob er zum Spiel aus Europa passt, sagt die Programm-ID in titledb.
   "need": eigene Fassung in dieser Region, braucht das Hauptspiel von dort; "open": noch ungeprüft; "" passt */
function needsRegion(dlc, code, slug){
  const fam = code && country(code).family;
  if(!dlc || !fam || fam === "EU") return "";
  const fit = ((S.state.dlc_fit || {})[slug] || {})[fam];
  return fit === true ? "" : fit === false ? "need" : "open";
}
/* Preis stammt aus einem eigenen Angebot (ab 0.62), etwa einem Code bei Amazon */
const ownMark = x => x && x.own ? `<span class="dlc ownm" title="Eigenes Angebot: ${esc(x.own.src)}-Code, mit Kreditkarte bezahlt">${esc(x.own.src)}</span>` : "";
const needMark = (code, kind) => kind === "need" ? `<span class="dlc need" title="${esc(needTip(code, kind))}">DLC</span>`
  : kind === "open" ? `<span class="dlc open" title="${esc(needTip(code, kind))}">DLC?</span>` : "";
const needTip = (code, kind) => kind === "need" ? `Eigene Fassung in ${country(code).family_name}: Dieser DLC braucht das Hauptspiel aus dieser Region, zu deinem Spiel aus Europa passt er nicht`
  : kind === "open" ? `Ob dieser DLC zu deinem Spiel aus Europa passt, ist noch ungeprüft (titledb kennt die Programm-ID nicht). Meist passt er` : "";
/* Faktor der Karten eines Schritts: Kartenkosten ÷ Wert zum Mittelkurs */
function planFactor(p){
  const info = S.state.pay[p.code] || {}, face = p.cards.reduce((a, c) => a + c.count * c.face, 0);
  if(!face || !info.rate || p.estimated) return null;
  return p.cost / (face / (p.currency === "EUR" ? 1 : info.rate));
}
/* Nur Guthaben: wie weit die Karte gerade über ihrem 90-Tage-Bestwert liegt, ab „teuer“ */
function giftOver(p){
  const r = (S.state.pay[p.code] || {}).rating, k = (S.state.pay[p.code] || {}).card;
  if(p.is_ref || !r || r.level !== "bad" || !r.best || !k || p.currency === "EUR") return 0;
  return Math.round(100 * (k.factor / r.best - 1));
}
/* Hürden: was den Kauf hier erschwert, rot heißt nein, violett heißt prüfen */
function hurdles(p, last){
  const out = [];
  if(giftOver(p)) out.push(`<span class="warnc" title="Guthaben gerade ${giftOver(p)} % über seinem Bestwert der letzten 90 Tage. Wenn die Titel nicht drängen: Warten lohnt eher wegen des Guthabens.">Guthaben teuer</span>`);
  // Alte Preise (0.95): Der letzte Abruf hier scheiterte, es gelten noch die vom genannten Tag
  if(p.price_stale) out.push(`<span class="warnc" title="Der letzte Preisabruf in ${esc(p.name)} scheiterte, es gelten noch die Preise vom ${esc(dmy(p.price_at))}. Angebote können inzwischen geendet haben. Einzelheiten im Protokoll unter Einstellungen.">Preise vom ${esc(dmy(p.price_at))}</span>`);
  for(const w of p.warnings){
    // Im letzten Schritt des Kaufplans folgt kein Wechsel mehr: Der Rest bleibt, ein späterer Wechsel wartet auf ihn
    if(w.startsWith("Rest blockiert") && last) out.push(`<span class="warnc" title="Der Kaufplan wechselt danach nicht mehr. Ein späterer Wechsel geht erst, wenn das Guthaben aufgebraucht ist.">Rest bleibt, blockiert spätere Wechsel</span>`);
    else if(w.startsWith("Rest blockiert")) out.push(`<span class="bad" title="${esc(w)}, bis das Guthaben 0 ist">Rest blockiert Wechsel</span>`);
    else if(w.startsWith("Keine Guthabenkarte")) out.push(`<span class="warnc" title="${esc(w)}">${w.startsWith("Keine Guthabenkarten") ? "Karten fehlen" : w.includes("vorrätig") ? "keine Karte vorrätig" : "kein Kartenpreis"}, geschätzt</span>`);
    // In Europa passt das Hauptspiel ohnehin. Sonst nur DLC mit eigener Fassung in dieser Region (Programm-ID, 0.61)
    else if(w.startsWith("DLC braucht")){
      const kind = i => i.needs_parent ? needsRegion(i.dlc_of, p.code, i.slug) : "";
      const need = p.items.filter(i => kind(i) === "need"), open = p.items.filter(i => kind(i) === "open");
      if(need.length) out.push(`<span class="warnc" title="Eigene Fassung in ${esc(p.family)}: Diese DLC brauchen das Hauptspiel aus dieser Region. Betroffen: ${esc(need.map(i => i.short).join(", "))}"><span class="dlc need">DLC</span>${need.length === 1 ? "braucht" : `${need.length}× brauchen`} Region ${esc(p.family)}</span>`);
      if(open.length) out.push(`<span class="mut" title="Ob diese DLC zu deinem Spiel aus Europa passen, ist noch ungeprüft; meist passen sie. Betroffen: ${esc(open.map(i => i.short).join(", "))}"><span class="dlc open">DLC?</span>${open.length}× Fassung ungeprüft</span>`);
    }
    else if(/ohne deutschen Vergleichspreis/.test(w)) out.push(`<span class="mut" title="${esc(w)}">${parseInt(w)} ohne DE-Preis</span>`);
    else if(/ungeprüfter Sprache/.test(w)) out.push(`<span class="warnc" title="Für diese Region liegt noch keine Sprachangabe vor">${parseInt(w)}× Sprache ungeprüft</span>`);
    else if(/ohne deutsche Fassung/.test(w)) out.push(`<span class="bad">${esc(w)}</span>`);
    else if(/hoher Rest/.test(w)) continue;          // steht in der Zeile „Rest“
    else out.push(`<span class="warnc">${esc(w)}</span>`);
  }
  return out;
}
/* Rechnung: alles, was hinter den Zahlen steckt */
function billHtml(p){
  const cur = p.currency, rows = [];
  rows.push(`Shop: ${money(p.total, cur)}${p.tax ? ` inkl. ${String(p.tax).replace(".", ",")} % Steuer` : ""} → ${p.estimated ? "ca. " : ""}${eur(p.cost)}: ${esc(costTip(p))}`);
  if(p.cards.length){
    const f = planFactor(p), r = (S.state.pay[p.code] || {}).rating;
    rows.push(`Karten: ${cardsHtml(p)}${f ? ` · Faktor ${fac(f)}${r && r.level && !["cheaper", "same", "dearer"].includes(r.level) ? ` · ${esc(r.text.split(",")[0])}` : ""}` : ""}`);
    const over = giftOver(p);
    if(over) rows.push(`<span class="warnc">Guthaben gerade ${over} % über seinem Bestwert. Wenn die Titel nicht drängen: Warten lohnt eher wegen des Guthabens.</span>`);
  }
  if(p.balance_value) rows.push(`Vorhandenes Guthaben zählt zum Kurs mit: ${eur(p.balance_value)}`);
  if(!p.is_ref && p.rest_value >= 0.5) rows.push(`Rest: ${eur(p.rest_value)} der Kartenkosten bleiben als Guthaben, die Spiele kosten ${eur(p.games_cost - (p.rest_lost || 0))}`);
  if(p.gain !== null && p.gain !== undefined && !p.home) rows.push(`Ohne diesen Wechsel: ${eur(p.alt_total)} in ${esc(altNames(p.alt_codes))}`);
  if(p.saving !== null && p.saving !== undefined && !p.is_ref) rows.push(`In Deutschland: ${eur(p.ref_total)} (${p.saving >= 0 ? "spart" : "kostet"} hier ${eur(Math.abs(p.saving))}${p.saving >= 0 ? "" : " mehr"})`);
  if(p.note && !p.is_ref) rows.push(esc(p.note));
  return rows.map(r => `<div>${r}</div>`).join("");
}
function planCard(p, step){
  const has = p.items.length > 0, cur = p.currency, key = "pc:" + p.code;
  const dim = has && !p.home && !p.current && p.worth === false && !step;
  let h = `<article class="pc ${p.current ? "cur" : ""} ${dim ? "dim" : ""}"><header><h2>${step ? step + ". " : ""}${esc(p.name)} ${p.is_ref ? "" : tierTag(p.tier)}${p.current ? ` <span class="tier cur" title="Dein Konto steht hier">Konto</span>` : ""}</h2>
    ${step ? `<button class="sm" data-act="bought" data-c="${esc(p.code)}" title="Vermerkt den Kauf: Dein Konto steht danach hier, ein Rest bleibt als Guthaben, die Titel verschwinden aus dem Plan">gekauft</button>`
      : p.is_ref || p.ro ? "" : `<button class="hide" data-act="hide" data-c="${p.code}" title="Land ausblenden">×</button>`}</header>`;
  if(has){
    h += `<div class="money" title="${esc(costTip(p))}">${p.estimated ? "ca. " : ""}${eur(p.cost)}${cur === "EUR" ? "" : `<small>${money(p.total, cur)}</small>`}${p.balance_value ? `<small>${p.cost < 0.005 ? "ganz aus deinem Guthaben" : "neu zu zahlen, dazu dein Guthaben"}</small>` : ""}</div>`;
    if(p.from_step && !step) h += `<div class="ln"><span class="k">Korb</span><span class="mut" title="Die Karte rechnet mit den Titeln, die der Kaufplan hier kauft. Ändern, entfernen oder hinzufügen macht daraus einen eigenen Korb.">wie im Kaufplan, Schritt ${p.from_step}</span></div>`;
    h += `<div class="ln"><span class="k">Preis</span>${priceLine(p)}</div>`;
    h += `<div class="ln"><span class="k">Wechsel</span>${switchLine(p)}</div>`;
    const last = !!(step && S.kauf && step === S.kauf.steps.length);
    const rl = restLine(p, last);
    if(rl) h += `<div class="ln"><span class="k">Rest</span>${rl}</div>`;
    const hd = hurdles(p, last);
    if(hd.length) h += `<div class="hurd">${hd.join(" · ")}</div>`;
    const wide = !S.dense || step;
    const T = step ? "schritt" : "land";     // eine Sortierung für alle Karten einer Ansicht
    h += `<div class="scroll"><table class="it"><thead><tr>${sth(T, "title", "Titel")}${wide ? sth(T, "local", `Shop ${esc(cur || "")}`, "Preis im eShop des Landes") : ""}${sth(T, "end", "bis")}${sth(T, "eur", "Einkaufspreis", "Was du bezahlst: mit Steuer, Kurs und Kosten fürs Guthaben")}${sth(T, "over", "über Bestpreis", "Einkaufspreis minus Bestpreis")}${wide && !p.is_ref ? sth(T, "alt", "sonst", "Was der Titel ohne diesen Wechsel kostet: günstigstes zählendes Land gleicher oder leichterer Stufe oder dein aktuelles Land") : ""}</tr></thead><tbody>` +
      sortRows(T, p.items, {title: i => i.short, local: i => i.local, end: i => i.sale && i.end ? +new Date(i.end) : null, eur: i => i.eur,
        over: i => i.champ === null || i.champ === undefined ? null : i.eur - i.champ, alt: i => i.alt}).map(i => {
        const tip = i.title + (i.dlc_of ? ` (DLC zu ${i.dlc_of}${i.parent_owned ? ", Hauptspiel in deiner Sammlung" : ""})` : "") + (i.owned ? " · schon in deiner Sammlung" : "") + (step && p.reasons ? " · " + (p.reasons[i.slug] || "") : "");
        const need = i.needs_parent ? needsRegion(i.dlc_of, p.code, i.slug) : "";
        const nm = `<span class="nm">${i.dlc_of ? `<span class="dlc ${need || (i.parent_owned ? "has" : "")}"${need ? ` title="${esc(needTip(p.code, need))}"` : ""}>DLC${need === "open" ? "?" : ""}</span>` : ""}${i.owned ? `<span class="dlc own">✓</span>` : ""}${i.dlc_of && i.short !== i.title ? `<small class="gm">${esc(i.dlc_of)}:</small><br>` : ""}${esc(i.short)}${i.own ? " " + ownMark(i) : ""}${i.lang === "unknown" ? ` <span class="q" title="Sprache ungeprüft, zählt nicht">?</span>` : ""}${langTag(i, false)}</span>`;
        const filled = step && (p.fill_slugs || []).includes(i.slug) ? ` <small class="mut">dazugenommen</small>` : "";
        // Überall dasselbe × (0.94): im Kaufplan „nicht in diesem Schritt“, auf der Länderkarte aus dem Korb
        const first = `<td class="t" title="${esc(tip)}">${xBtn(p, i, step)}${nm}${filled}</td>`;
        // Klassen c-… ordnen die Zellen am Handy zu einer Karte je Titel (0.75)
        return `<tr>${first}${wide ? `<td class="c-loc" data-l="Shop">${priceLink(i.slug, p.code, num(i.local, cur), i, cur)}</td>` : ""}<td class="c-end"${i.sale ? ` data-l="bis"` : ""}>${i.sale ? endCell(i.end) : `<span class="mut">normal</span>`}</td>
          <td class="c-eur ${i.over ? "over" : ""}" ${i.over ? `title="hier teurer als ohne den Wechsel"` : ""}>${star(i)}${ax(i)}${buyLink(p.code, i, num(i.eur))}${i.sale ? ` <span class="pct">−${i.pct} %</span>` : ""}</td>
          <td class="c-best">${i.champ === null || i.champ === undefined ? `<span class="mut">–</span>` : atBest(i.eur, i.champ) ? `<span class="g-${i.grade || "buy"}" title="Bestpreis ${eur(i.champ)} in ${esc(country(i.champ_code).name)}${i.eur - i.champ >= 0.005 ? `, ${eur(i.eur - i.champ)} darüber zählt noch als Bestpreis (bis 2 %)` : ""}">am Bestpreis</span>${(S.state.radar.find(r => r.slug === i.slug) || {}).nohist ? `<br><span class="nohist" title="DekuDeals hat für diesen Titel noch keinen Tiefstpreis geliefert: Der Bestpreis stützt sich nur auf heutige Preise und die eigene Aufzeichnung">ohne Verlauf</span>` : ""}` : `<span class="abv" title="Bestpreis ${eur(i.champ)} in ${esc(country(i.champ_code).name)}">+${num(i.eur - i.champ)}</span>`}</td>
          ${wide && !p.is_ref ? altCell(i) : ""}</tr>`;
      }).join("") + `</tbody></table></div>`;
  } else {
    h += `<p class="line"><small>Kein Wishlist-Titel im Angebot.</small></p>`;
  }
  h += removedLine(p, step) + suggestHtml(p, step);
  let foot = has ? `<details class="bill" data-k="${key}" ${S.folds[key] ? "open" : ""}><summary>Rechnung</summary>${billHtml(p)}</details>` : "";
  if(step && (p.others || []).length) foot += othersHtml(p, step);
  if(p.rate && !step && !p.ro){
    const inPlan = new Set(p.items.map(i => i.slug));
    const opts = p.is_ref ? "" : wishOpts(S.state.matrix.rows.filter(r => r.cells[p.code] && !r.cells[p.code].na && !inPlan.has(r.slug)),
      r => money(r.cells[p.code].local, cur), {code: p.code, skip: inPlan});
    const ov = S.ui.overrides[p.code];
    const changed = ov && ((ov.add||[]).length || (ov.remove||[]).length);
    foot += (has ? `<button data-act="share" data-c="${p.code}" title="Diesen Warenkorb als Korb übernehmen und in allen Ländern vergleichen (Wishlist, Ansicht Korb)">als Korb vergleichen</button>` : "") +
      (opts ? `<select data-act="pick" data-c="${p.code}" title="Deine Wishlist-Titel und die Online-Mitgliedschaft, soweit es sie hier gibt und sie noch nicht im Korb dieses Landes sind. Andere Titel kennt das Tool nicht: Preise holt es nur für die Wishlist."><option value="">Titel dazunehmen …</option>${opts}</select>` : "") +
      (changed ? `<button class="link" data-act="reset" data-c="${p.code}">zurücksetzen</button>` : "");
  }
  if(p.rate && step){
    // Im Kaufplan wie auf den Länderkarten (0.68): Korb vergleichen und Titel dazunehmen. Dazugenommenes
    // kommt als Füllartikel in diesen Schritt (S.ui.plan_fill), der Plan rechnet neu.
    const inPlan = new Set(p.items.map(i => i.slug));
    const opts = wishOpts(S.state.matrix.rows.filter(r => r.cells[p.code] && !r.cells[p.code].na && !inPlan.has(r.slug) && !r.cells[p.code].own),
      r => money(r.cells[p.code].local, cur), {code: p.code, skip: inPlan});
    const mine = ((S.ui.plan_fill || {})[p.code] || []).length + ((S.ui.plan_skip || {})[p.code] || []).length;
    foot += (has ? `<button data-act="share" data-c="${p.code}" data-step="1" title="Die Titel dieses Schritts als Korb übernehmen und in allen Ländern vergleichen (Wishlist, Ansicht Korb)">als Korb vergleichen</button>` : "") +
      (opts ? `<select data-act="planpick" data-c="${p.code}" title="Deine Wishlist-Titel und die Online-Mitgliedschaft, soweit es sie hier gibt und sie noch nicht in diesem Schritt sind. Sie kommen als Füllartikel dazu."><option value="">Titel dazunehmen …</option>${opts}</select>` : "") +
      (mine ? `<button class="link" data-act="planreset" data-c="${p.code}" title="Was du in diesem Schritt dazugenommen oder herausgenommen hast, verwerfen">zurücksetzen</button>` : "");
  }
  if(foot) h += `<div class="foot">${foot}</div>`;
  return h + `</article>`;
}
/* Eine Karte für Kaufplan und Länderkarten (0.94): dieselben Werkzeuge an beiden Orten. Im Kaufplan
   wirkt alles auf den Plan (dazunehmen, herausnehmen), auf der Länderkarte auf den Korb des Landes. */
function xBtn(p, i, step){
  if(p.ro) return "";
  if(step && (p.fill_slugs || []).includes(i.slug))
    return `<button class="x" data-act="planunfill" data-c="${p.code}" data-s="${esc(i.slug)}" title="Von dir dazugenommen. Klick nimmt ihn wieder heraus.">×</button>`;
  if(step)
    return `<button class="x" data-act="planskip" data-c="${p.code}" data-s="${esc(i.slug)}" title="Nicht in diesem Schritt kaufen: Der Plan rechnet ohne ihn neu, er geht ins nächstbeste Land oder wartet. Er steht danach unter der Tabelle, ein Klick holt ihn zurück.">×</button>`;
  return `<button class="x" data-act="drop" data-c="${p.code}" data-s="${esc(i.slug)}" title="Aus dem Korb dieses Landes nehmen. Er steht danach unter der Tabelle, ein Klick holt ihn zurück.">×</button>`;
}
/* Was du herausgenommen hast, bleibt sichtbar, mit dem Weg zurück: nichts verschwindet still */
function removedLine(p, step){
  if(p.ro) return "";
  const list = step ? (p.skipped || [])
    : ((S.ui.overrides[p.code] || {}).remove || []).map(s => ({slug: s, short: (rowOf(s) || {}).title || s}));
  if(!list.length) return "";
  const where = x => !step ? "" : x.to ? ` <small class="mut">jetzt in ${esc(country(x.to).name)}</small>` : ` <small class="mut">wartet</small>`;
  // Name wie in den Zeilen (0.99.4): voller Titel, DLC-Marke davor, in Schritt und Länderkarte gleich
  const name = x => { const r = rowOf(x.slug); return `${r && r.dlc_of ? `<span class="dlc">DLC</span>` : ""}${esc(r ? r.title : x.short)}`; };
  return `<p class="restline removed">Herausgenommen: ` + list.map(x =>
    `${name(x)}${where(x)} <button class="link" data-act="${step ? "planunskip" : "undrop"}" data-c="${p.code}" data-s="${esc(x.slug)}" title="Wieder hineinnehmen">zurück</button>`).join(" · ") + `</p>`;
}
/* Vorschläge in drei Zeilen, überall gleich: was in den Rest passt, was dazu lohnt, was weglassen spart */
function suggestHtml(p, step){
  if(p.ro || p.is_ref || !p.rate) return "";
  const cur = p.currency, act = step ? "planfill" : "add";
  const verb = step ? "Klick nimmt ihn in diesen Schritt." : "Klick legt ihn in den Korb dieses Landes.";
  const verb2 = step ? "Klick nimmt beide in diesen Schritt." : "Klick legt beide in den Korb dieses Landes.";
  // Im Kaufplan nichts, was schon ein anderer Schritt kauft
  const planned = new Set(step && S.kauf ? S.kauf.steps.flatMap(x => x.items.map(i => i.slug)) : p.items.map(i => i.slug));
  // Was du hier mit × herausgenommen hast, schlägt die Karte nicht gleich wieder vor (0.95.1)
  (step ? (p.skipped || []).map(x => x.slug) : ((S.ui.overrides || {})[p.code] || {}).remove || []).forEach(x => planned.add(x));
  let h = "";
  const inRest = new Set();
  if(p.rest > 0){
    // Mitgliedschaft passt in den Rest (0.57.1); die besten Treffer als Knöpfe, auch zwei Titel zusammen,
    // alles andere im Auswahlfeld (0.70, 0.78); fehlende DLC deiner Spiele dahinter (0.77)
    const nsoFit = (p.fill_nso || []).map(f => `<button class="sm" data-act="${act}" data-c="${p.code}" data-s="nso-${esc(f.key)}" title="Online-Mitgliedschaft ${esc(f.label)} für ${esc(money(f.local, cur))}${f.at_best ? ", am Bestpreis" : ""}. Danach bleiben ${esc(money(f.left, cur))}. Sie verlängert deine laufende Mitgliedschaft. ${verb.replace("ihn", "sie")}">${f.at_best ? `<span class="star">★</span>` : ""}Mitgliedschaft ${esc(f.label)} <small style="display:inline">${money(f.local, cur)}</small></button>`);
    const one = f => f.extra
      ? `<button class="sm" data-act="${act}" data-c="${p.code}" data-s="${esc(f.slug)}" title="Fehlender DLC zu ${esc(f.game)} aus deiner Sammlung, nicht auf der Wishlist: ${esc(money(f.local, cur))}${f.eur !== null ? `, umgerechnet ca. ${eur(f.eur)}` : ""}. Danach bleiben ${esc(money(f.left, cur))}. DLC gelten nur in der Region des Hauptspiels. ${verb}">+ <span class="dlc">DLC</span>${esc(f.short)} <small style="display:inline">${money(f.local, cur)}</small></button>`
      : `<button class="sm" data-act="${act}" data-c="${p.code}" data-s="${esc(f.slug)}" title="${esc(f.title)}${f.dlc ? " (DLC)" : ""}: ${esc(money(f.local, cur))}${f.eur !== null ? `, umgerechnet ca. ${eur(f.eur)}` : ""}. Danach bleiben ${esc(money(f.left, cur))}. ${verb}">+ ${f.dlc ? `<span class="dlc">DLC</span>` : ""}${esc(f.short)} <small style="display:inline">${money(f.local, cur)}${f.sale ? " · Angebot" : ""}</small></button>`;
    const two = f => `<button class="sm" data-act="${act}" data-c="${p.code}" data-s="${esc(f.slugs.join(","))}" title="${esc(f.titles.join(" + "))}: zusammen ${esc(money(f.local, cur))}. Danach bleiben ${esc(money(f.left, cur))}. ${verb2}">+ ${f.shorts.map(esc).join(" + ")} <small style="display:inline">${money(f.local, cur)}</small></button>`;
    const fill = (p.fill || []).filter(f => !planned.has(f.slug)), more = fill.filter(f => !f.extra), xs = fill.filter(f => f.extra);
    const top = more.map(f => ({left: f.left, h: one(f)})).concat((p.fill_pairs || []).filter(f => !f.slugs.some(x => planned.has(x))).map(f => ({left: f.left, h: two(f)})))
      .sort((x, y) => x.left - y.left).slice(0, 4)
      .concat(xs.slice(0, 2).map(f => ({h: one(f)})));
    const optOf = (f, name) => `<option value="${esc(f.slug)}">${esc(name)} · ${esc(money(f.local, cur))} · bleiben ${esc(money(f.left, cur))}</option>`;
    const xsSorted = [...xs].sort((a, b) => (a.game || "").localeCompare(b.game || "", "de") || a.short.localeCompare(b.short, "de"));
    const sel = more.length + xs.length > 1 ? ` <select data-act="${step ? "planpick" : "pick"}" data-c="${p.code}" title="Alles, was in den Rest passt, mit dem, was danach bleibt: deine Wishlist und die DLC deiner Spiele, die nicht auf der Wishlist stehen"><option value="">alles, was passt (${more.length + xs.length}) …</option>` +
      (more.length ? `<optgroup label="Wishlist">${more.map(f => optOf(f, f.title + (f.dlc ? " (DLC)" : ""))).join("")}</optgroup>` : "") +
      (xs.length ? `<optgroup label="DLC deiner Spiele, nicht auf der Wishlist">${xsSorted.map(f => optOf(f, (f.game ? f.game + ": " : "") + f.short)).join("")}</optgroup>` : "") + `</select>` : "";
    const btns = nsoFit.concat(top.map(x => x.h));
    fill.forEach(f => inRest.add(f.slug));
    // Auch ohne Treffer sichtbar (0.94): Die Zeile fehlt nicht, sie sagt, dass nichts passt
    h += `<div class="fillrow"><span class="mut">Passt in den Rest (${money(p.rest, cur)}):</span> ` +
      (btns.length || sel ? btns.join(" ") + sel : `<small class="mut">nichts von deiner Wishlist oder den DLC deiner Spiele</small>`) + `</div>`;
    h += zeroHtml(p, step, planned);
  }
  // Was dazu lohnt: Ein weiterer Titel spart hier gegenüber dem Kauf ohne diesen Wechsel (0.76)
  // Immer, als Alternative zum Auffüllen: Der Korb wird größer, der Rest ein anderer (0.98.1). Ohne Titel,
  // die schon unter „Passt in den Rest“ stehen, sonst stünden sie zweimal da
  const fillers = (p.fillers || []).filter(f => !f.slugs.some(x => planned.has(x) || inRest.has(x))).slice(0, S.dense && !step ? 1 : 2);
  if(fillers.length) h += `<div class="fillrow"><span class="mut">Passt dazu:</span> ` + fillers.map(f =>
    `<button class="sm" data-act="${act}" data-c="${p.code}" data-s="${esc(f.slugs.join(","))}" title="${esc(fillTip(f, cur, f.slugs.length > 1 ? verb2 : verb))}">+ ${f.shorts.map(esc).join(" + ")} <b>spart ${eur(f.gain)}</b>${fillBest(f)}</button>`).join(" ") + `</div>`;
  // Was weglassen spart: Ohne diesen Titel kostet der Kauf hier weniger, als er anderswo kostet
  const trims = (p.trims || []).slice(0, 2);
  if(trims.length) h += `<div class="fillrow"><span class="mut">Weglassen spart:</span> ` + trims.map(t =>
    `<button class="sm" data-act="${step ? "planskip" : "trim"}" data-c="${p.code}" data-s="${esc(t.slug)}" title="Ohne ${esc(t.short)} kostet der Kauf hier ${eur(t.marginal)} weniger; ohne den Wechsel kostet der Titel ${eur(t.ref)}${t.rest === null ? "" : `, danach bleiben ${money(t.rest, cur)} Rest`}. ${step ? "Klick nimmt ihn aus diesem Schritt." : "Klick nimmt ihn aus dem Korb dieses Landes."}">− ${esc(t.short)} <b>spart ${eur(t.gain)}</b></button>`).join(" ") + `</div>`;
  return h;
}
/* Auf Null (1.1.0): wo ein Rest stört (verfällt, Stufe schwer, Rest blockiert), der günstigste Weg auf
   genau 0 und, wenn günstiger, einer auf fast 0. Die Titel stehen offen da, ein Knopf nimmt alle dazu */
function zeroHtml(p, step, planned){
  const z = p.fill_zero;
  if(!z) return "";
  const cur = p.currency, act = step ? "planfill" : "add";
  // Was sonst bleibt: verfällt er im Plan, sein Wert in Euro, sonst der Rest in Landeswährung (1.1.1)
  const was = p.rest_lost ? eur(p.rest_lost) : money(p.rest, cur);
  // Klappbar wie „Rechnung“ (1.1.1): Kopfzeile mit Betrag, Titel und Knopf beim Aufklappen
  const line = (x, kind) => {
    if(!x || x.slugs.some(s => planned.has(s))) return "";
    const key = `zero:${p.code}:${kind}`;
    const cards = x.cards.map(k => `${k.count}× ${money(k.face, cur)}`).join(" + ");
    const cost = x.extra >= 0.005 ? `für <b>${eur(x.extra)}</b> mehr` : `<b>ohne Zuzahlung</b>`;
    // Fast Null in derselben Einheit wie „statt“ (1.1.2): der Rest danach zum selben Kurs, Landeswährung im Tooltip
    const left = !p.rest_lost ? money(x.left, cur) : x.left * p.rest_lost / p.rest < 0.005 ? "unter 0,01 €" : eur(x.left * p.rest_lost / p.rest);
    const head = `${kind === "exact" ? "Genau Null" : "Fast Null"} ${cost} (${kind === "near" ? `Rest ${left} statt ${was}` : `statt ${was} Rest`})`;
    const best = x.known ? ` <small style="display:inline">· ${x.at_best} von ${x.known} am Bestpreis${x.over >= 0.005 ? `, zusammen <span class="abv">+${eur(x.over)}</span> über Bestpreis` : ""}</small>` : "";
    // Preise als Link wie überall (in den eShop, ohne eShop-Seite zum Verlauf bei DekuDeals)
    const price = i => { const r = rowOf(i.slug), cell = r && r.cells ? r.cells[p.code] : null;
      return cell ? shopLink(i.slug, p.code, cell, money(i.local, cur), cur) : priceLink(i.slug, p.code, money(i.local, cur), null, cur); };
    const names = x.items.map(i => `<span class="nw">${i.dlc ? `<span class="dlc">DLC</span>` : ""}${esc(i.extra && i.game ? i.game + ": " + i.short : i.short)} <small style="display:inline">${price(i)}</small></span>`).join(", ");
    const tip = `Mit ${x.items.length === 1 ? "diesem Titel" : "diesen Titeln"} (zusammen ${money(x.local, cur)}) bleiben ${money(x.left, cur)}. Guthabenkarten dann: ${cards}. Das kostet ${eur(x.extra)} mehr als der Schritt jetzt${p.rest_lost ? `, statt ${eur(p.rest_lost)} Rest verfallen zu lassen` : ""}. ${step ? "Klick nimmt alle in diesen Schritt." : "Klick legt alle in den Korb dieses Landes."}`;
    return `<details class="zero" data-k="${key}" ${S.folds[key] ? "open" : ""}><summary class="mut">${head}</summary>` +
      `<div class="fillrow"><span>${x.items.length} Titel: ${names}${best}</span> ` +
      `<button class="sm" data-act="${act}" data-c="${p.code}" data-s="${esc(x.slugs.join(","))}" title="${esc(tip)}">alle dazunehmen</button></div></details>`;
  };
  const h = line(z.exact, "exact") + line(z.near, "near");
  return h || (!z.exact && !z.near ? `<div class="fillrow"><span class="mut">Genau Null</span> <small class="mut">mit deiner Wishlist und den DLC deiner Spiele kein Weg</small></div>` : "");
}
/* Andere Länder an einem Schritt des Kaufplans (0.74): dieselben Titel dort, nach Mehrkosten.
   Ein Klick auf ein Land öffnet seine Karte. */
function othersHtml(p, step){
  const key = "ol:" + p.code, list = p.others.filter(o => !S.ui.hidden.includes(o.code));
  if(!list.length) return "";
  const amt = o => o.diff >= 0.005 ? `<span class="abv">+${eur(o.diff)}</span>` : o.diff <= -0.005 ? `<span class="gn">−${eur(-o.diff)}</span>` : `<span class="mut">gleich</span>`;
  const first = list.find(o => !o.missing.length);
  // Ein Land aufgeklappt (0.94): dieselbe Karte, nur zum Ansehen; weiterspielen auf seiner Länderkarte
  const ol = S.olInline && S.olInline.from === p.code ? S.olInline : null;
  const inline = ol ? `<div class="olin">${planCard(ol.p)}<p class="restline"><button class="link" data-act="goland" data-c="${ol.code}" title="Die Länderkarte von ${esc(ol.p.name)} mit eigenem Korb öffnen">Länderkarte von ${esc(ol.p.name)} öffnen</button> · <button class="link" data-act="olshow" data-c="${ol.code}" data-from="${p.code}">zuklappen</button></p></div>` : "";
  const tip = `Was die Titel dieses Schritts in anderen Ländern kosten, verglichen mit ${p.name}. Wie bei „Preis“ zählt, was die Spiele kosten; ein Rest bleibt als Guthaben. Grün heißt günstiger: Der Plan nimmt dann ${p.name}, weil der Wechsel dorthin sich nicht rechnet oder weil er jeden Titel einzeln dem günstigsten Land gibt.`;
  const rows = list.map(o => {
    const note = [o.current ? "Konto steht dort, kein Wechsel" : "", o.missing.length ? `ohne ${o.missing.map(esc).join(", ")}` : ""].filter(Boolean).join(" · ");
    return `<tr><td class="l"><span class="nw"><button class="link" data-act="olshow" data-c="${o.code}" data-from="${p.code}" title="Diese Titel in ${esc(o.name)} hier aufklappen, mit Preis, Wechsel und Rechnung">${esc(o.name)}</button> ${o.is_ref ? "" : tierTag(o.tier)}</span>${note ? `<br><small class="mut">${note}</small>` : ""}</td>` +
      `<td title="Die Spiele kosten dort ${o.estimated ? "ca. " : ""}${eur(o.games_cost)}">${o.estimated ? "ca. " : ""}${amt(o)}</td></tr>` +
      // Aufgeklappt direkt unter seiner Zeile (1.0.4): am Ende der Liste lag es oft außer Sicht
      (ol && ol.code === o.code ? `<tr class="olrow"><td colspan="2">${inline}</td></tr>` : "");
  }).join("");
  return `<details class="bill" data-k="${key}" ${S.folds[key] ? "open" : ""}><summary title="${esc(tip)}">Andere Länder${first ? ` <span class="mut">· ${esc(first.name)} ${first.diff >= 0.005 ? "+" + eur(first.diff) : first.diff <= -0.005 ? "−" + eur(-first.diff) : "gleich"}</span>` : ""}</summary><table class="mini-t others">${rows}</table></details>`;
}
/* „Passt dazu“ (Kaufplan, Länderkarte, Korb): Was ein weiterer Wishlist-Titel hier zusätzlich kostet und was er spart.
   „spart“ rechnet mit heutigen Preisen; dahinter klein, wie weit der Titel hier über seinem Bestpreis liegt (0.77) */
function fillBest(f){
  if(f.champ === null || f.champ === undefined || f.eur === null || f.eur === undefined) return "";
  return ` <small>${atBest(f.eur, f.champ) ? `<span class="g-buy">am Bestpreis</span>` : `<span class="abv">+${eur(f.eur - f.champ)}</span> über Bestpreis`}</small>`;
}
function fillTip(f, cur, act){
  return `${f.titles.join(" + ")}: Mit ${f.titles.length === 1 ? "diesem Titel" : "diesen Titeln"} kostet der Kauf hier ${eur(f.extra)} mehr (Shop ${money(f.local, cur)}; die Guthabenkarten und der Rest decken einen Teil). ` +
    `Ohne Wechsel hierher kostet ${f.titles.length === 1 ? "er" : "sie"} ${eur(f.ref)}, im günstigsten zählenden Land gleicher oder leichterer Stufe oder in deinem Kontoland. Ersparnis: ${eur(f.ref)} − ${eur(f.extra)} = ${eur(f.gain)}.` +
    `${f.rest !== null && f.rest !== undefined ? ` Danach bleiben ${money(f.rest, cur)} Rest.` : ""}` +
    `${f.champ !== null && f.champ !== undefined ? ` Bestpreis der letzten 24 Monate: ${eur(f.champ)}, hier jetzt ${eur(f.eur)}.` : ""}${act ? " " + act : ""}`;
}
function altCell(i){
  if(i.alt === null || i.alt === undefined) return `<td class="mut c-alt">–</td>`;
  const tip = `Ohne diesen Wechsel: ${eur(i.alt)} in ${country(i.alt_code).name}` + (i.ref !== null && i.ref !== undefined ? ` · Deutschland ${eur(i.ref)}` : "");
  return `<td title="${esc(tip)}" class="mut c-alt" data-l="sonst">${num(i.alt)} <small style="display:inline">${esc(i.alt_code)}</small></td>`;
}
function restHtml(p, bare){
  const pre = bare ? "" : "Rest ";
  if(p.rest === null) return `<span class="warnc">${bare ? "unbekannt" : "Rest unbekannt"}</span>`;
  if(p.rest === 0) return `${pre}0`;
  const blocked = p.warnings.some(w => w.startsWith("Rest blockiert"));
  const rv = p.rest_value ?? p.rest_eur;
  return `<span class="${blocked ? "bad" : ""}">${pre}${money(p.rest, p.currency)}</span>${rv > 0.005 ? ` <small>${eur(rv)}</small>` : ""}`;
}
