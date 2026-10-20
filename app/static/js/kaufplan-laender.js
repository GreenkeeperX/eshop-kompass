"use strict";
/* Kaufplan und Länderkarten (Teil der Oberfläche, Reihenfolge in index.html) */
/* ---------- Kaufplan: was jetzt wo kaufen ---------- */
function planSums(steps){
  const opt = steps.reduce((a, p) => a + (p.optimum ?? 0), 0);
  const gap = steps.reduce((a, p) => a + (p.opt_gap ?? 0), 0);
  return {opt, gap};
}
function viewKauf(){
  const k = S.kauf;
  if(!k) return `<p class="hint">Kaufplan wird berechnet …</p>`;
  const sums = planSums(k.steps);
  const head = k.count
    ? `<b class="big">${eur(k.cost)}</b><span>${k.count} Titel in ${k.steps.length} ${k.steps.length === 1 ? "Land" : "Ländern"} · ${atBest(sums.opt + sums.gap, sums.opt) && k.steps.every(p => itemsAtBest(p.items)) ? `<span class="g-buy"${nearTip(sums.gap)}>am Bestpreis</span>` : `<span class="abv">+${eur(sums.gap)}</span> über Bestpreis-Summe ${eur(sums.opt)}`}${k.rest_lost ? ` · <span class="bad">${eur(k.rest_lost)} Rest verfällt beim Wechsel</span>` : ""}</span>`
    : `<span>Gerade steht kein Titel auf „kaufen“${!S.ui.plan_good && k.good_left ? `, aber ${k.good_left} auf „gut“: rechts „auch gute Angebote“ anhaken` : ""}.</span>`;
  let h = `<div class="bar on"><b>Jetzt kaufen</b>${head}<span class="sp"></span>
    <label title="Neben „kaufen“ auch Titel mit dem Urteil „gut“ einplanen"><input type="checkbox" data-act="plangood" ${S.ui.plan_good ? "checked" : ""}> auch gute Angebote${!S.ui.plan_good && k.good_left ? ` (${k.good_left})` : ""}</label>
    </div>`;
  if(k.lock) h += lockBox(k);
  if(k.steps.length) h += `<div class="grid steps">` + k.steps.map((p, n) => planCard(p, n + 1)).join("") + `</div>`;
  else h += emptyPlan();
  h += `<p class="restline">Jedes Land mit seinem eigenen Korb, zum Durchspielen: <button class="link" data-act="allland">alle Länderkarten</button></p>`;
  h += notPlanned(k) + boughtBox(k);
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
function notPlanned(k){
  const rows = [];
  for(const h of k.held || [])
    rows.push(`<tr><td>${esc(h.title)}</td><td class="l">kaufen in <b>${esc(h.name)}</b>, aber <span class="bad">Wechsel blockiert</span>: Guthaben in ${esc(k.lock.name)} muss erst aufgebraucht sein</td></tr>`);
  const open = k.dropped.filter(d => (d.open_titles || []).length);
  for(const d of open.filter(d => d.blocked_by))
    rows.push(`<tr><td>${d.open_titles.map(esc).join(", ")}</td><td class="l">kaufen in <b>${esc(d.name)}</b> ${tierTag(TIER_OF(d))}, aber <span class="bad">nur ein Land mit blockierendem Rest je Plan</span>: ${esc(d.blocked_by.join(", "))} bringt mehr</td></tr>`);
  for(const d of open.filter(d => !d.blocked_by))
    rows.push(`<tr><td>${d.open_titles.map(esc).join(", ")}</td><td class="l">kaufen in <b>${esc(d.name)}</b> ${tierTag(TIER_OF(d))}, aber <span class="bad">Wechsel lohnt nicht</span>: ${d.gain >= 0 ? `spart ${eur(d.gain)}` : `kostet ${eur(-d.gain)} mehr`} gegenüber ${esc(altNames(d.alt_codes))}, lohnt ab ${eur(d.threshold)}</td></tr>`);
  for(const x of k.s2_skip || []) rows.push(`<tr><td>${esc(x.title)}</td><td class="l">nur ein Weg zur Switch 2: ${esc(x.reason)}</td></tr>`);
  for(const x of k.packed || []) rows.push(`<tr><td>${esc(x.title)}</td><td class="l">steckt in <b>${esc(x.pack)}</b>, das ebenfalls zum Kauf ansteht: nicht doppelt kaufen</td></tr>`);
  // Kleinkram (0.92): wartet, bis ein Rest bleibt, statt eine Guthabenkarte größer zu machen
  // Je Land mit Summe; füllt er eine Karte fast ganz, ein Vorschlag zum Übernehmen, nie von selbst (0.93)
  const grouped = new Set();
  for(const g of k.small_groups || []){
    g.slugs.forEach(x => grouped.add(x));
    const faces = (g.cards || []).reduce((n, c) => n + c.face * c.count, 0);
    const card = (g.cards || []).map(c => `${c.count > 1 ? c.count + "× " : ""}${money(c.face, g.currency)}`).join(" + ");
    const of = g.smallest ? ` · zusammen ${money(g.local, g.currency)}${faces ? ` von ${card} (${Math.round(100 * g.local / faces)} %)` : ""}` : ` · zusammen ${money(g.local, g.currency)}`;
    const take = !g.full ? "" : g.step
      ? ` <b>Reicht für eine eigene Karte.</b> <button class="link" data-act="planfill" data-c="${g.code}" data-s="${esc(g.slugs.join(","))}" title="Nimmt den Kleinkram in den Schritt ${esc(g.name)}; der Plan kauft dafür ${esc(card)}">in den Schritt nehmen</button>`
      : ` <b>Reicht für eine eigene Karte.</b> <button class="link" data-act="add" data-c="${g.code}" data-s="${esc(g.slugs.join(","))}" title="Legt den Kleinkram in den Korb der Länderkarte ${esc(g.name)}">in die Länderkarte</button>`;
    rows.push(`<tr><td>${g.titles.map(esc).join(", ")}</td><td class="l">Kleinkram in <b>${esc(g.name)}</b>: wartet auf einen Rest, statt eine Guthabenkarte größer zu machen${of}.${take}</td></tr>`);
  }
  const loose = (k.small || []).filter(x => !grouped.has(x.slug));
  if(loose.length) rows.push(`<tr><td>${loose.map(x => esc(x.short)).join(", ")}</td><td class="l">Kleinkram: wartet auf einen Rest, statt eine Guthabenkarte größer zu machen; steht unter „Passt in den Rest“, sobald einer bleibt</td></tr>`);
  for(const l of k.later) rows.push(`<tr><td>${esc(l.title)}</td><td class="l">lieber warten: ${esc(l.reason)}; in den Ländern, deren Wechsel sich rechnet, kein Kauf</td></tr>`);
  if(k.nowhere.length) rows.push(`<tr><td>${k.nowhere.map(esc).join(", ")}</td><td class="l">nirgends kaufbar, wo es zählt</td></tr>`);
  if(k.bought_waiting.length) rows.push(`<tr><td>${k.bought_waiting.map(esc).join(", ")}</td><td class="l">schon gekauft oder in deiner Sammlung, steht noch auf der Wishlist</td></tr>`);
  if(!rows.length) return "";
  return `<details class="box fold" data-k="notplan" ${S.folds.notplan ? "open" : ""}><summary>Nicht im Plan (${rows.length})</summary><table class="mini-t">${rows.join("")}</table></details>`;
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
  h += `<div class="grid ${S.dense ? "" : "list"}">${cards.map(p => planCard(p)).join("")}</div>`;
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
    return g.length ? `<optgroup label="${l}">${g.map(r => `<option value="${esc(r.slug)}">${esc(r.title)}${(r.dlc_of || rowOf(r.slug).dlc_of) ? " (DLC)" : ""}${label ? " · " + label(r) : ""}</option>`).join("")}</optgroup>` : "";
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
  for(const w of p.warnings){
    // Im letzten Schritt des Kaufplans folgt kein Wechsel mehr: Der Rest bleibt, ein späterer Wechsel wartet auf ihn
    if(w.startsWith("Rest blockiert") && last) out.push(`<span class="warnc" title="Der Kaufplan wechselt danach nicht mehr. Ein späterer Wechsel geht erst, wenn das Guthaben aufgebraucht ist.">Rest bleibt, blockiert spätere Wechsel</span>`);
    else if(w.startsWith("Rest blockiert")) out.push(`<span class="bad" title="${esc(w)}, bis das Guthaben 0 ist">Rest blockiert Wechsel</span>`);
    else if(w.startsWith("Keine Guthabenkarten")) out.push(`<span class="warnc" title="${esc(w)}">Karten fehlen, geschätzt</span>`);
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
        const nm = `<span class="nm">${i.dlc_of ? `<span class="dlc ${need || (i.parent_owned ? "has" : "")}"${need ? ` title="${esc(needTip(p.code, need))}"` : ""}>DLC${need === "open" ? "?" : ""}</span>` : ""}${i.owned ? `<span class="dlc own">✓</span>` : ""}${i.dlc_of && i.short !== i.title ? `<small class="gm">${esc(i.dlc_of)}:</small> ` : ""}${esc(i.short)}${i.own ? " " + ownMark(i) : ""}${i.lang === "unknown" ? ` <span class="q" title="Sprache ungeprüft, zählt nicht">?</span>` : ""}${langTag(i, false)}</span>`;
        const filled = step && (p.fill_slugs || []).includes(i.slug)
          ? ` <button class="link" data-act="planunfill" data-c="${p.code}" data-s="${esc(i.slug)}" title="Von dir dazugenommen. Klick nimmt ihn wieder heraus.">dazugenommen ×</button>` : "";
        const first = step || p.ro ? `<td class="t" title="${esc(tip)}">${nm}${filled}</td>` : `<td class="t" title="${esc(tip)}"><label class="tt"><input type="checkbox" checked data-act="drop" data-c="${p.code}" data-s="${esc(i.slug)}">${nm}</label></td>`;
        // Klassen c-… ordnen die Zellen am Handy zu einer Karte je Titel (0.75)
        return `<tr>${first}${wide ? `<td class="c-loc" data-l="Shop">${priceLink(i.slug, p.code, num(i.local, cur), i, cur)}</td>` : ""}<td class="c-end"${i.sale ? ` data-l="bis"` : ""}>${i.sale ? endCell(i.end) : `<span class="mut">normal</span>`}</td>
          <td class="c-eur ${i.over ? "over" : ""}" ${i.over ? `title="hier teurer als ohne den Wechsel"` : ""}>${star(i)}${ax(i)}${buyLink(p.code, i, num(i.eur))}${i.sale ? ` <span class="pct">−${i.pct} %</span>` : ""}</td>
          <td class="c-best">${i.champ === null || i.champ === undefined ? `<span class="mut">–</span>` : atBest(i.eur, i.champ) ? `<span class="g-${i.grade || "buy"}" title="Bestpreis ${eur(i.champ)} in ${esc(country(i.champ_code).name)}${i.eur - i.champ >= 0.005 ? `, ${eur(i.eur - i.champ)} darüber zählt noch als Bestpreis (bis 2 %)` : ""}">am Bestpreis</span>` : `<span class="abv" title="Bestpreis ${eur(i.champ)} in ${esc(country(i.champ_code).name)}">+${num(i.eur - i.champ)}</span>`}</td>
          ${wide && !p.is_ref ? altCell(i) : ""}</tr>`;
      }).join("") + `</tbody></table></div>`;
  } else {
    h += `<p class="line"><small>Kein Wishlist-Titel im Angebot.</small></p>`;
  }
  if(!step && !p.ro){
    const sugg = p.trims.map(t =>
        `<button data-act="trim" data-c="${p.code}" data-s="${esc(t.slug)}" title="Ohne diesen Titel kostet das Paket ${eur(t.marginal)} weniger, ohne den Wechsel kostet er ${eur(t.ref)}">
          <span class="n">− ${esc(t.short)} weglassen</span><small>hier ${num(t.marginal)}, sonst ${num(t.ref)}${t.rest === null ? "" : ` · Rest ${num(t.rest, cur)}`}</small><b>spart ${eur(t.gain)}</b></button>`)
      .concat(p.fillers.map(f =>
        `<button data-act="add" data-c="${p.code}" data-s="${esc(f.slugs.join(","))}" title="${esc(f.titles.join(" + "))}: ${esc(money(f.local, cur))}, Aufpreis ${eur(f.extra)}, ohne den Wechsel ${eur(f.ref)}">
          <span class="n">+ ${f.shorts.map(esc).join(" + ")}</span><small>+${num(f.extra)}, sonst ${num(f.ref)}${f.rest === null || f.rest === undefined ? "" : ` · Rest ${num(f.rest, cur)}`}</small><b>spart ${eur(f.gain)}</b>${fillBest(f)}</button>`));
    if(sugg.length) h += `<div class="sugg">${sugg.slice(0, S.dense ? 3 : 99).join("")}</div>`;
  } else if((p.fill || []).length || (p.fill_nso || []).length){
    // Mitgliedschaft passt in den Rest: nur ein Hinweis, gekauft wird sie über ihren Kasten (0.57.1)
    const nsoFit = (p.fill_nso || []).map(f => `<button class="sm" data-act="planfill" data-c="${p.code}" data-s="nso-${esc(f.key)}" title="Online-Mitgliedschaft ${esc(f.label)} für ${esc(money(f.local, cur))}${f.at_best ? ", am Bestpreis" : ""}. Danach bleiben ${esc(money(f.left, cur))}. Sie verlängert deine laufende Mitgliedschaft. Klick nimmt sie in diesen Schritt.">${f.at_best ? `<span class="star">★</span>` : ""}Mitgliedschaft ${esc(f.label)} <small style="display:inline">${money(f.local, cur)}</small></button>`);
    // Die besten Treffer als Knöpfe, auch zwei Titel zusammen, wenn sie den Rest besser füllen;
    // alles andere, was passt, im Auswahlfeld daneben (0.70)
    const one = f => f.extra
      ? `<button class="sm" data-act="planfill" data-c="${p.code}" data-s="${esc(f.slug)}" title="Fehlender DLC zu ${esc(f.game)} aus deiner Sammlung, nicht auf der Wishlist: ${esc(money(f.local, cur))}${f.eur !== null ? `, umgerechnet ca. ${eur(f.eur)}` : ""}. Danach bleiben ${esc(money(f.left, cur))}. DLC gelten nur in der Region des Hauptspiels. Klick nimmt ihn in diesen Schritt.">+ ${esc(f.short)} <small style="display:inline">DLC · ${money(f.local, cur)}</small></button>`
      : `<button class="sm" data-act="planfill" data-c="${p.code}" data-s="${esc(f.slug)}" title="${esc(f.title)}${f.dlc ? " (DLC)" : ""}: ${esc(money(f.local, cur))}${f.eur !== null ? `, umgerechnet ca. ${eur(f.eur)}` : ""}. Danach bleiben ${esc(money(f.left, cur))}. Klick nimmt den Titel in diesen Schritt.">+ ${esc(f.short)} <small style="display:inline">${money(f.local, cur)}${f.sale ? " · Angebot" : ""}</small></button>`;
    const two = f => `<button class="sm" data-act="planfill" data-c="${p.code}" data-s="${esc(f.slugs.join(","))}" title="${esc(f.titles.join(" + "))}: zusammen ${esc(money(f.local, cur))}. Danach bleiben ${esc(money(f.left, cur))}. Klick nimmt beide in diesen Schritt.">+ ${f.shorts.map(esc).join(" + ")} <small style="display:inline">${money(f.local, cur)}</small></button>`;
    // Wishlist zuerst; fehlende DLC, die nicht auf der Wishlist stehen, dahinter: zwei als Knopf, alle im eigenen Auswahlfeld (0.77)
    const fill = p.fill || [], more = fill.filter(f => !f.extra), xs = fill.filter(f => f.extra);
    const top = more.map(f => ({left: f.left, h: one(f)})).concat((p.fill_pairs || []).map(f => ({left: f.left, h: two(f)})))
      .sort((x, y) => x.left - y.left).slice(0, 4)
      .concat(xs.slice(0, 2).map(f => ({h: one(f)})));
    // Ein Auswahlfeld für alles, was passt (0.78): oben die Wishlist, darunter die DLC deiner Spiele,
    // die nicht auf der Wishlist stehen, nach Spiel sortiert
    const optOf = (f, name) => `<option value="${esc(f.slug)}">${esc(name)} · ${esc(money(f.local, cur))} · bleiben ${esc(money(f.left, cur))}</option>`;
    const xsSorted = [...xs].sort((a, b) => (a.game || "").localeCompare(b.game || "", "de") || a.short.localeCompare(b.short, "de"));
    const sel = more.length + xs.length > 1 ? ` <select data-act="planpick" data-c="${p.code}" title="Alles, was in den Rest passt, mit dem, was danach bleibt: deine Wishlist und die DLC deiner Spiele, die nicht auf der Wishlist stehen"><option value="">alles, was passt (${more.length + xs.length}) …</option>` +
      (more.length ? `<optgroup label="Wishlist">${more.map(f => optOf(f, f.title + (f.dlc ? " (DLC)" : ""))).join("")}</optgroup>` : "") +
      (xs.length ? `<optgroup label="DLC deiner Spiele, nicht auf der Wishlist">${xsSorted.map(f => optOf(f, (f.game ? f.game + ": " : "") + f.short)).join("")}</optgroup>` : "") + `</select>` : "";
    h += `<div class="fillrow"><span class="mut">Passt in den Rest (${money(p.rest, cur)}):</span> ` + nsoFit.concat(top.map(x => x.h)).join(" ") + sel + `</div>`;
  } else if(p.rest > 0){
    // Nur wo ein Rest bleibt: Bei Kartenzahlung gibt es keinen Rest, der sich füllen ließe. Im Kaufplan
    // ein Knopf wie im Korb (0.76), ohne Titel, die schon in einem anderen Schritt stehen
    const planned = new Set(step && S.kauf ? S.kauf.steps.flatMap(x => x.items.map(i => i.slug)) : []);
    const f = p.fillers.find(f => !f.slugs.some(x => planned.has(x)));
    if(f) h += `<p class="restline" style="margin-top:6px">Passt dazu: ` + (step
      ? `<button class="fl" data-act="planfill" data-c="${p.code}" data-s="${esc(f.slugs.join(","))}" title="${esc(fillTip(f, cur, "Klick nimmt ihn in diesen Schritt."))}">+ ${f.shorts.map(esc).join(" + ")} <b>spart ${eur(f.gain)}</b>${fillBest(f)}</button>`
      : `<span title="${esc(fillTip(f, cur, ""))}">+ ${f.shorts.map(esc).join(" + ")} <b>spart ${eur(f.gain)}</b>${fillBest(f)}</span>`) + `</p>`;
  }
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
    foot += (has ? `<button data-act="share" data-c="${p.code}" data-step="1" title="Die Titel dieses Schritts als Korb übernehmen und in allen Ländern vergleichen (Wishlist, Ansicht Korb)">als Korb vergleichen</button>` : "") +
      (opts ? `<select data-act="planpick" data-c="${p.code}" title="Deine Wishlist-Titel und die Online-Mitgliedschaft, soweit es sie hier gibt und sie noch nicht in diesem Schritt sind. Sie kommen als Füllartikel dazu."><option value="">Titel dazunehmen …</option>${opts}</select>` : "");
  }
  if(foot) h += `<div class="foot">${foot}</div>`;
  return h + `</article>`;
}
/* Andere Länder an einem Schritt des Kaufplans (0.74): dieselben Titel dort, nach Mehrkosten.
   Ein Klick auf ein Land öffnet seine Karte. */
function othersHtml(p, step){
  const key = "ol:" + p.code, list = p.others.filter(o => !S.ui.hidden.includes(o.code));
  if(!list.length) return "";
  const amt = o => o.diff >= 0.005 ? `<span class="abv">+${eur(o.diff)}</span>` : o.diff <= -0.005 ? `<span class="gn">−${eur(-o.diff)}</span>` : `<span class="mut">gleich</span>`;
  const first = list.find(o => !o.missing.length);
  const tip = `Was die Titel dieses Schritts in anderen Ländern kosten, verglichen mit ${p.name}. Wie bei „Preis“ zählt, was die Spiele kosten; ein Rest bleibt als Guthaben. Grün heißt günstiger: Der Plan nimmt dann ${p.name}, weil der Wechsel dorthin sich nicht rechnet oder weil er jeden Titel einzeln dem günstigsten Land gibt.`;
  const rows = list.map(o => {
    const note = [o.current ? "Konto steht dort, kein Wechsel" : "", o.missing.length ? `ohne ${o.missing.map(esc).join(", ")}` : ""].filter(Boolean).join(" · ");
    return `<tr><td class="l"><span class="nw"><button class="link" data-act="goland" data-c="${o.code}" data-from="${p.code}" title="Diese Titel in ${esc(o.name)} ansehen, mit Preis, Wechsel und Rechnung">${esc(o.name)}</button> ${o.is_ref ? "" : tierTag(o.tier)}</span>${note ? `<br><small class="mut">${note}</small>` : ""}</td>` +
      `<td title="Die Spiele kosten dort ${o.estimated ? "ca. " : ""}${eur(o.games_cost)}">${o.estimated ? "ca. " : ""}${amt(o)}</td></tr>`;
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
