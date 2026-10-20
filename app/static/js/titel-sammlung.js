"use strict";
/* Wishlist als Liste und Reiter Sammlung (Zusatzinhalte, Käufe) (Teil der Oberfläche, Reihenfolge in index.html) */
/* ---------- Titel: eine Zeile je Titel, Klick klappt die Einzelheiten auf ---------- */
function shownOffer(r){
  if(!r.shown) return null;
  return [r.easy, r.hard].find(b => b && b.code === r.shown.code) || null;
}
/* Steht ein Titel im Kaufplan, zählt dessen Preis: dort, mit diesen Karten, wird gekauft */
function planOffer(r){
  const p = S.kauf && S.kauf.steps.find(p => p.items.some(i => i.slug === r.slug));
  if(!p) return null;
  const i = p.items.find(i => i.slug === r.slug);
  return Object.assign({}, i, {code: p.code, name: p.name, currency: p.currency, tier: p.tier, plan: true,
                               reason: (p.reasons || {})[r.slug] || ""});
}
const cheapestOffer = r => [r.easy, r.hard].filter(Boolean).sort((a, b) => a.eur - b.eur)[0] || null;
function titleFilterBar(){
  const n = v => S.state.radar.filter(r => r.verdict === v).length;
  const f = S.vf || "all";
  const b = (v, l, c) => `<button class="fb ${f === v ? "on" : ""}" data-act="vf" data-v="${v}">${l} ${c}</button>`;
  return b("buy", "kaufen", n("buy")) + b("good", "gut", n("good")) + b("wait", "warten", n("wait")) + b("all", "alle", S.state.radar.length);
}
/* ---------- Sammlung: Zusatzinhalte zu Spielen, die du hast ---------- */
function collDlc(d){
  const tag = d.upgrade ? ` <span class="chip" title="Upgrade-Paket: macht die Switch-1-Fassung zur Nintendo Switch 2 Edition">Switch-2-Upgrade</span>` : "";
  const mk = (v, label, tip) => `<button class="link" data-act="dlcmark" data-s="${esc(d.slug)}" data-v="${v}" title="${tip}">${label}</button>`;
  let state;
  if(d.owned) state = `<span class="mut">✓ hast du${d.via ? `, im Paket ${esc(d.via)}` : ""}</span>` +
    (d.via ? ` · ${mk("missing", "stimmt nicht", "DekuDeals nennt diesen DLC im Paket, du hast ihn aber nicht: zählt wieder als fehlend")}` : "");
  else if(d.by_hand) state = `<span class="mut">✓ hast du (von dir abgehakt)</span> · ${mk("", "zurücksetzen", "Haken entfernen")}`;
  else if(d.ignored) state = `<span class="mut">ignoriert</span>${d.mark === "ignore" ? " · " + mk("", "zurücksetzen", "Wieder als fehlend zählen") : ""}`;
  else if(d.gone) state = `<span class="mut" title="Die ID-Suche fand ihn in keiner Region, mehrmals: meist nur im Spiel erhältlich oder aus dem eShop verschwunden">nicht mehr erhältlich</span> · ${mk("have", "habe ich", "Hast du schon")}`;
  else {
    if(d.wish) state = `${pill(d.verdict)} ${d.eur !== null && d.eur !== undefined ? `<a class="pl" href="${esc(deku(d.slug, d.code))}" target="_blank" rel="noopener" title="Preisverlauf bei DekuDeals für ${esc(d.name || "")}">${d.est ? "ca. " : ""}${eur(d.eur)}</a> in ${esc(d.name || "")}${needsRegion(true, d.code, d.slug) ? " " + needMark(d.code, needsRegion(true, d.code, d.slug)) : ""}` : `<span class="mut">${esc(d.reason || "kein Preis")}</span>`}${d.end ? ` <small class="mut">bis ${esc(dmy(d.end))}</small>` : ""} <button class="link" data-act="gotitle" data-s="${esc(d.slug)}">Einzelheiten</button>`;
    else state = `<span class="warnc">fehlt</span>${d.eur !== null && d.eur !== undefined ? ` · ${d.eur < 0.005 ? "kostenlos" : `<a class="pl" href="${esc(deku(d.slug, d.code))}" target="_blank" rel="noopener">${dlcPrice(d)}</a> in ${esc(d.name || "")}${needsRegion(true, d.code, d.slug) ? " " + needMark(d.code, needsRegion(true, d.code, d.slug)) : ""}`}${d.end ? ` <small class="mut">${endCell(d.end, "bis ")}</small>` : ""}` : ""}`;
    const p = d.pack;
    if(p && p.open && p.single !== null && d.eur !== null && d.eur !== undefined){
      const b = (on, t) => on ? `<b>${t}</b>` : t;
      state += ` · <span title="Was die ${p.open} fehlenden Teile einzeln kosten, gegen den Pass. In die Summe geht der günstigere Weg.">${b(p.cheaper === "single", `einzeln ${eur(p.single)}`)} · ${b(p.cheaper === "pass", `als Pass ${eur(d.eur)}`)}</span>`;
    }
    else if(p && p.open && d.eur !== null && d.eur !== undefined)
      state += ` · <span class="mut" title="Mindestens ein fehlender Teil ist einzeln nicht kaufbar oder hat noch keinen Preis; dann gibt es ihn nur über den Pass">einzeln nicht alle kaufbar</span>`;
    if(d.not_in_pack) state += ` · <span class="mut">laut dir nicht im Paket</span> ${mk("", "zurücksetzen", "Wieder als im Paket enthalten zählen")}`;
    state += ` · ${mk("have", "habe ich", "Hast du schon, etwa aus einem Paket, und die DekuDeals-Sammlung kennt es nicht")} · ${mk("ignore", "ignorieren", "Interessiert dich nicht: zählt nicht mehr als fehlend")}`;
  }
  const inner = d.pack ? ` <small class="mut" style="display:inline">enthält ${d.pack.n} DLC${d.pack.have ? `, ${d.pack.have} schon da` : ""}</small>` : "";
  // Noch unentschieden (0.72): fehlt, steht nicht auf der Wishlist und ist nicht ignoriert. Violetter Rand links
  // und Hinweis am Namen, damit diese DLC zwischen den entschiedenen auffallen
  const undec = !d.owned && !d.by_hand && !d.ignored && !d.gone && !d.wish;
  return `<tr class="${d.ignored ? "ign" : ""}${d.in_pack ? " part" : ""}${undec ? " undec" : ""}"><td class="l"${d.in_pack ? ` title="steckt in ${esc(d.in_pack)}"` : ""}>${d.in_pack ? "↳ " : ""}<a class="tl" href="${esc(deku(d.slug))}" target="_blank" rel="noopener" title="${d.wish || d.owned || d.by_hand || d.ignored ? "Bei DekuDeals ansehen" : "Bei DekuDeals ansehen; auf die Wishlist gesetzt rechnet das Tool auch Urteil und Bestpreis"}">${esc(d.title)}</a>${tag}${inner}${undec ? ` <span class="chip und" title="Fehlt, steht nicht auf deiner Wishlist und ist nicht ignoriert. Auf die Wishlist setzen, mit „habe ich“ abhaken oder ignorieren; in den Korb geht er auch über „Titel dazunehmen …“">nicht auf der Wishlist</span>` : ""}</td><td class="l">${state}</td></tr>`;
}
/* Preis eines fehlenden DLC wie in der Titelliste: Stern am Bestpreis, grün bei „kaufen“
   und „gut“, Rabatt blau (0.53.3). Ein Urteil gibt es nur auf der Wishlist. */
function dlcPrice(d){
  const tip = [d.champ !== null && d.champ !== undefined ? `Bestpreis ${eur(d.champ)} (24 Monate, alle zählenden Länder)` : "Bestpreis noch nicht bekannt",
    d.grade === "buy" ? "am Bestpreis oder knapp darüber" : d.grade === "good" ? "gutes Angebot" : ""].filter(Boolean).join(" · ");
  const cls = d.grade === "buy" ? "g-buy" : d.grade === "good" ? "g-good" : "";
  return `${d.at_best ? `<span class="star" title="Am Bestpreis">★</span>` : ""}<span class="${cls}" title="${esc(tip)}">${d.est ? "ca. " : ""}${eur(d.eur)}</span>${d.sale && d.pct ? `<span class="pct">−${d.pct} %</span>` : ""}`;
}
function collGame(g){
  const shown = g.dlc.filter(d => !d.ignored && !d.gone), ign = g.dlc.filter(d => d.ignored), gone = g.dlc.filter(d => d.gone);
  const all = !g.missing && !g.ignore_all ? "" : `<button class="link" data-act="dlcmark" data-s="${esc(g.slug)}" data-v="${g.ignore_all ? "" : "ignore_all"}" title="${g.ignore_all ? "Die DLC dieses Spiels wieder zählen" : "Alle DLC dieses Spiels, die du nicht hast, ausblenden"}">${g.ignore_all ? "DLC wieder zählen" : "alle DLC ignorieren"}</button>`;
  // Je Art eine Zahl, ohne Gesamtzahl („10 von 17, 7 …“ las sich wie 17,7): „10 vorhanden und 7 ignoriert“.
  // Alles da: „5 von 5“ grün, „vorhanden“ grau; nichts mehr offen: die Zahl vorhandener grün, ignorierte rot,
  // Wörter grau (0.55.1, Wortlaut 0.56.2)
  const parts = [g.have === g.dlc.length ? `<span class="gn">${g.have} von ${g.dlc.length}</span> vorhanden` : g.have ? (!g.missing ? `<span class="gn">${g.have}</span> vorhanden` : `${g.have} vorhanden`) : "",
    g.missing ? `${g.missing} ${g.missing === 1 ? "fehlt" : "fehlen"}` : "", g.ignored ? `<span class="abv">${g.ignored}</span> ignoriert` : "", g.gone ? `${g.gone} nicht mehr erhältlich` : ""].filter(Boolean);
  // Wie ein Satz: „10 vorhanden und 7 ignoriert“, „3 vorhanden, 2 fehlen und 1 ignoriert“ (0.56.3)
  const sum = [parts.length > 1 ? parts.slice(0, -1).join(", ") + " und " + parts[parts.length - 1] : parts[0] || "",
    g.missing_eur !== null && g.missing_eur !== undefined ? `fehlende jetzt ${g.missing_eur < 0.005 && g.missing_priced === g.missing ? "kostenlos" : eur(g.missing_eur)}${g.missing_priced < g.missing ? ` (${g.missing_priced} mit Preis)` : ""}` : ""].filter(Boolean).join(" · ");
  const sumTip = `${g.dlc.length} DLC insgesamt`;
  const key = "ign:" + g.slug;
  const body = (shown.length ? `<table class="mini-t">${shown.map(collDlc).join("")}</table>` : "") +
    (ign.length ? `<details class="fold" data-k="${esc(key)}" ${S.folds[key] ? "open" : ""}><summary class="hint">${ign.length} ignoriert</summary><table class="mini-t">${ign.map(collDlc).join("")}</table></details>` : "") +
    (gone.length ? `<details class="fold" data-k="${esc("gone:" + g.slug)}" ${S.folds["gone:" + g.slug] ? "open" : ""}><summary class="hint">${gone.length} nicht mehr erhältlich</summary><table class="mini-t">${gone.map(collDlc).join("")}</table></details>` : "");
  const via = g.via ? ` <small class="mut">über ${esc(g.via)}</small>` : "";
  // Vollständig (nichts mehr offen): eine Zeile, die DLC aufklappbar wie bei „alle ignoriert“ (0.53.1)
  if(!g.missing) return `<details class="fold cgd" data-k="${esc("cg:" + g.slug)}" ${S.folds["cg:" + g.slug] || (S.rq && g.dlc.some(d => d.title.toLowerCase().includes(S.rq.toLowerCase()))) ? "open" : ""}><summary>${esc(g.title)}${via} <span class="mut" title="${sumTip}">${sum}</span></summary>${all ? `<div class="cga">${all}</div>` : ""}<table class="mini-t">${g.dlc.map(collDlc).join("")}</table></details>`;
  return `<section class="box cg"><h3>${esc(g.title)}${via} <span class="mut" title="${sumTip}">${sum}</span><span class="sp"></span>${all}</h3>${body}</section>`;
}
/* Suchen ohne Akzente, Satzzeichen und Leerzeichen: „pokemon“ findet „Pokémon“, „luigis“ „Luigi’s“
   (0.69 in der Sammlung, ab 0.76 in jedem Suchfeld) */
const fold1 = t => String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
const hits = (q, t) => { const nq = fold1(q).replace(/ /g, ""); return !nq || fold1(t).replace(/ /g, "").includes(nq); };
function viewCollection(){
  const c = S.state.collection || {games: [], plain: [], waiting: []}, q = S.rq.toLowerCase();
  const hit = t => hits(q, t);
  const found = c.games.filter(g => hit(g.title) || g.dlc.some(d => hit(d.title)));
  const done = found.filter(g => !g.missing).sort((a, b) => a.title.localeCompare(b.title, "de"));
  const games = sortRows("sammlung", found.filter(g => g.missing),
    {title: g => g.title, missing: g => -g.missing, eur: g => g.missing_eur, sale: g => -g.missing_sale});
  const cs = S.sorts.sammlung, cv = cs ? cs.k : "";
  const co = (v, l) => `<option value="${v ? v + ":1" : ""}" ${cv === v ? "selected" : ""}>${l}</option>`;
  const plain = (c.plain || []).filter(g => hit(g.title)).sort((a, b) => a.title.localeCompare(b.title, "de"));
  const waiting = (c.waiting || []).filter(g => hit(g.title));
  const missing = c.games.reduce((n, g) => n + g.missing, 0);
  // Filter und Reihenfolge direkt über den Spielen, unter Zahlen und Erklärung (0.58)
  const tools = `<div class="tools">${searchBox("Spiel oder DLC filtern")}
    <select class="srt" data-act="tsortsel" data-t="sammlung" title="Reihenfolge der Spiele">${co("", "nach Name")}${co("missing", "nach Zahl fehlender DLC")}${co("eur", "nach Preis fehlender DLC")}${co("sale", "nach DLC im Angebot")}</select></div>`;
  let h = "";
  if(!c.owned) return h + `<p class="mut">Noch keine Sammlung gelesen. Trag unter Einstellungen den Link zu deiner DekuDeals-Sammlung ein und klicke auf Aktualisieren.</p>`;
  // Kopf der Sammlung: Zahlen in zwei kurzen Zeilen, die Erklärung eingeklappt (0.55.1)
  const nDone = c.games.filter(g => !g.missing).length;
  const priced = c.missing_eur !== null && c.missing_eur !== undefined;
  h += `<div class="box cstatb"><div class="cstat"><span><b>${c.owned}</b> Spiele in der Sammlung</span><span><b>${c.games.length}</b> mit DLC <span class="mut">(${c.games.length - nDone} mit offenen, ${nDone} ohne)</span></span><span><b>${(c.plain || []).length}</b> ohne DLC</span></div>
    ${missing ? `<div class="cstat"><span><b>${missing}</b> DLC fehlen</span>${priced ? `<span title="Summe im jeweils günstigsten zählenden Land">${c.missing_priced < missing ? `${c.missing_priced} mit Preis: ` : ""}zusammen <b>${eur(c.missing_eur)}</b></span>${c.missing_sale ? `<span><b>${c.missing_sale}</b> im Angebot</span>` : ""}` : ""}</div>` : ""}
    <details class="fold" data-k="collhow" ${S.folds.collhow ? "open" : ""}><summary class="hint">So funktioniert die Sammlung</summary><p class="hint" style="margin:2px 0 8px">Ob du einen DLC hast, steht in deiner Sammlung bei DekuDeals; was sie nicht kennt, hakst du mit „habe ich“ ab.
    „ignorieren“ blendet DLC aus, die dich nicht interessieren. Preise gelten im jeweils günstigsten zählenden Land; ein Urteil gibt es für DLC auf deiner Wishlist.</p></details></div>`;
  h += tools + games.map(collGame).join("");
  // Was nichts mehr braucht, steht zugeklappt darunter; die Suche klappt Treffer auf (0.53.1)
  const fold = (k, arr, head, note, inner) => arr.length ? `<details class="box cg fold" data-k="${k}" ${S.folds[k] || q ? "open" : ""}><summary><b>${head}</b> <span class="mut">${arr.length}</span></summary>${note ? `<p class="hint" style="margin:4px 0 6px">${note}</p>` : ""}${inner}</details>` : "";
  // Alle Spiele darin auf einmal auf- oder zuklappen, dezent hinter der Erklärung (0.91)
  const both = `<span class="foldall"><button class="link" data-act="foldall" data-v="1">alle aufklappen</button> · <button class="link" data-act="foldall" data-v="">alle zuklappen</button></span>`;
  h += fold("colldone", done, "Ohne offene DLC", `Alle DLC da, ignoriert oder nicht mehr erhältlich. Klick auf ein Spiel zeigt seine DLC. ${both}`, `<div class="cgl">${done.map(collGame).join("")}</div>`);
  h += fold("collplain", plain, "Ohne Zusatzinhalte", "", `<div class="cl">${plain.map(g => `<a class="tl" href="${esc(deku(g.slug))}" target="_blank" rel="noopener"${g.via ? ` title="über ${esc(g.via)}"` : ""}>${esc(g.title)}</a>`).join("")}</div>`);
  const list = (arr, head, note) => arr.length ? `<section class="box cg"><h3>${head} <span class="mut">${arr.length}</span></h3>${note ? `<p class="hint" style="margin:0 0 6px">${note}</p>` : ""}<div class="cl">${arr.map(g => `<a class="tl" href="${esc(deku(g.slug))}" target="_blank" rel="noopener"${g.via ? ` title="über ${esc(g.via)}"` : ""}>${esc(g.title)}</a>`).join("")}</div></section>` : "";
  h += list(waiting, "Noch nicht gelesen", "Das Tool liest je Abgleich höchstens 40 Artikelseiten, diese folgen bei den nächsten Abgleichen.");
  if(!games.length && !done.length && !plain.length && !waiting.length) h += `<p class="mut">${q ? "Kein Spiel passt zum Filter." : "Noch keine Spiele bekannt."}</p>`;
  return h;
}
function viewTitles(){
  const q = S.rq.toLowerCase(), f = S.vf || "all";
  const off = r => planOffer(r) || shownOffer(r) || cheapestOffer(r);
  const rows = sortRows("titel", S.state.radar.filter(r => hits(q, r.title) && (f === "all" || r.verdict === f)), {
    title: r => r.title, verdict: r => VORDER[r.verdict], price: r => off(r)?.eur,
    over: r => off(r) && r.champ ? off(r).eur - r.champ.eur : null, end: r => off(r)?.sale && off(r).end ? +new Date(off(r).end) : null,
    alt: r => { const x = shownOffer(r); return x && x.tier >= 3 && r.easy ? r.easy.eur : null; }});
  let h = `<div class="tools">${searchBox("Titel filtern")}${titleSortSel()}${titleFilterBar()}${viewSeg()}</div>
    <div class="radar"><table><thead><tr>${sth("titel", "title", "Titel")}${sth("titel", "verdict", "Urteil", "", "l")}${sth("titel", "price", "Einkaufspreis", "Was du zahlst, mit Steuer, Kurs, Guthabenkarten und Gebühr: im Land des Kaufplans, sonst im günstigsten zählenden Land")}
    ${sth("titel", "over", "über Bestpreis", "Einkaufspreis minus Bestpreis. Bestpreis: der niedrigste Einkaufspreis der letzten 24 Monate über alle zählenden Länder, mit deinem heutigen Einkaufsweg gerechnet")}
    ${sth("titel", "alt", "Alternative", "Liegt das beste Angebot in einem Land der Stufe schwer: das beste Angebot in einem leichten oder mittleren Land")}<th>Korb</th></tr></thead><tbody>`;
  h += titleGroups(rows).join("");
  if(!rows.length) h += `<tr><td colspan="6" class="mut">Kein Titel passt zum Filter.</td></tr>`;
  h += `</tbody></table></div>`;
  if(S.ui.basket) h += `<p class="restline">${S.ui.basket.length} Titel im Korb. <button class="link" data-act="gokorb">Korb in allen Ländern vergleichen</button></p>`;
  return h;
}
/* DLC beim Spiel (0.72): Steht das Spiel auf der Wishlist, folgen seine DLC direkt darunter; mehrere DLC
   eines Spiels, das nicht auf der Wishlist steht, bekommen eine Kopfzeile wie in der Sammlung. Die Gruppe
   steht dort, wo ihr erstes Mitglied in der gewählten Reihenfolge steht. Nach Preis, Abstand oder
   Angebotsende sortiert bleibt die Liste flach, sonst stimmt die Reihenfolge nicht mehr. */
function titleGroups(rows){
  const s = S.sorts.titel;
  if(s && ["price", "over", "end", "alt"].includes(s.k)) return rows.map(r => titleRow(r));
  // Eine Ausgabe des Spiels gilt als das Spiel (0.76): „Sparks of Hope + Rayman Edition“ nimmt den Season Pass zu sich
  const parents = [...new Set(rows.filter(r => r.dlc_of).map(r => r.dlc_of))].sort((a, b) => b.length - a.length);
  const gameKey = t => parents.find(p => t === p || (t.toLowerCase().startsWith(p.toLowerCase()) && /^[\s:–\-+]/.test(t.slice(p.length)))) || t;
  const units = new Map();
  for(const r of rows){
    const k = r.dlc_of || gameKey(r.title);
    if(!units.has(k)) units.set(k, {games: [], dlc: []});
    const u = units.get(k);
    (r.dlc_of ? u.dlc : u.games).push(r);
  }
  const out = [];
  for(const [k, u] of units){
    // DLC stehen immer eingerückt unter ihrem Spiel; steht das Spiel nicht auf der Wishlist, unter
    // einer Kopfzeile mit seinem Namen, auch bei nur einem DLC (0.77; 0.76 zeigte einen einzelnen grau davor)
    const sub = u.dlc.length > 0;
    for(const g of u.games) out.push(titleRow(g));
    if(!u.games.length && sub) out.push(`<tr class="tgrp"><td colspan="6"><b>${esc(k)}</b> <small class="mut">${u.dlc.length} DLC${u.dlc[0].parent_owned ? ", das Spiel hast du" : ""}</small></td></tr>`);
    for(const d of u.dlc) out.push(titleRow(d, k));
  }
  return out;
}
const VORDER = {buy: 0, good: 1, wait: 2, none: 3};
// Angebotsende hat keine eigene Spalte: Auswahl neben dem Filter, gemeinsam mit den Spaltenköpfen
function titleSortSel(){
  const s = S.sorts.titel, v = s ? `${s.k}:${s.dir}` : "";
  const o = (val, l) => `<option value="${val}" ${v === val ? "selected" : ""}>${l}</option>`;
  return `<select class="srt" data-act="tsortsel" data-t="titel" title="Reihenfolge der Titel">${o("", "nach Urteil und Nähe zum Bestpreis")}${o("title:1", "nach Titel")}${o("price:1", "nach Einkaufspreis")}${o("over:1", "nach Abstand zum Bestpreis")}${o("end:1", "nach Angebotsende")}${!["", "title:1", "price:1", "over:1", "end:1"].includes(v) ? o(v, "eigene Sortierung") : ""}</select>`;
}
function titleRow(r, group){
  const x = shownOffer(r), open = S.openTitle === r.slug, ce = r.champ;
  const cheapest = cheapestOffer(r), pl = planOffer(r);
  const off = pl || x || cheapest;
  const hit = r.target !== null && cheapest && cheapest.eur <= r.target + 0.005;
  const ps = r.verdict === "buy" || r.verdict === "good" ? planState(r.slug) : "";
  const why = r.verdict === "none" ? esc(r.reason) : "";
  const price = off ? `${star(off)}${ax(off)}<b>${buyLink(off.code, off, eur(off.eur))}</b> ${off.sale ? `<span class="pct" title="${esc(markTip(off, off.currency))}">−${off.pct} %</span>` : `<span class="pct np">Normalpreis</span>`}
      <small>${esc(off.name)} ${ownMark(off)}${needMark(off.code, needsRegion(r.dlc_of, off.code, r.slug))} ${tierTag(off.tier)}${off.currency === "EUR" ? "" : " · " + priceLink(r.slug, off.code, money(off.local, off.currency), off, off.currency)}${off.sale && off.end ? " · " + endCell(off.end, "bis ") : ""}</small>` : `<span class="mut">–</span>`;
  const over = off && ce ? `${overBest(off.eur, ce.eur, r.verdict === "none" ? null : r.verdict)}<small>${(pl ? pl.gap : r.gap) && !atBest(off.eur, ce.eur) ? (pl ? pl.gap : r.gap) + " % · " : ""}Bestpreis ${ce.est ? APPROX : ""}${eur(ce.eur)} ${esc(ce.code)}</small>` : `<span class="mut">–</span>`;
  let alt = "";
  if(pl && cheapest && cheapest.code !== pl.code && cheapest.eur < pl.eur - 0.005)
    alt = `<span title="${esc(`Günstigstes Land. Der Plan kauft in ${pl.name}${pl.reason ? ": " + pl.reason : ""}`)}">${eur(cheapest.eur)} ${esc(cheapest.name)}</span><small>${TIER[cheapest.tier]} · ${eur(pl.eur - cheapest.eur)} günstiger</small>`;
  else if(!pl && x && x.tier >= 3 && r.easy) alt = `${eur(r.easy.eur)} ${esc(r.easy.name)}<small>${TIER[r.easy.tier]}${ce ? ` · <span class="abv">+${eur(Math.max(0, r.easy.eur - ce.eur))}</span>` : ""}</small>`;
  const marks = (r.cashback ? ` <span class="cb" title="Mit ${String(r.cashback.pct).replace(".", ",")} % Cashback des Kartenshops wären es in ${esc(country(r.cashback.code).name)} etwa ${eur(r.cashback.eur)}, also Bestpreis. Cashback gibt es nicht immer, bitte beim Kauf prüfen.">✱</span>` : "") +
    (r.nohist ? ` <span class="nohist" title="DekuDeals hat für diesen Titel noch keinen Tiefstpreis geliefert: Der Bestpreis stützt sich nur auf heutige Preise und die eigene Aufzeichnung">ohne Verlauf</span>` : "") +
    (r.target !== null ? ` <span class="tgtm ${hit ? "hit" : ""}" title="Dein Zielpreis">Ziel ${eur(r.target)}${hit ? " ✓" : ""}</span>` : "");
  const dlc = r.dlc_of ? `<span class="dlc ${r.parent_owned ? "has" : ""}" title="DLC zu ${esc(r.dlc_of)}${r.parent_owned ? ", das Hauptspiel steht in deiner Sammlung" : r.parent_owned === false ? ", das Hauptspiel steht nicht in deiner Sammlung" : ""}">DLC</span>` : "";
  // In der Gruppe ohne den Namen des Spiels davor („Vampire Survivors: Operation Guns“ → „Operation Guns“)
  const name = group && r.title.toLowerCase().startsWith(group.toLowerCase()) ? r.title.slice(group.length).replace(/^[\s:–\-+]+/, "") || r.title : r.title;
  let h = `<tr class="v-${r.verdict} ${open ? "open" : ""} ${group ? "sub" : ""}" data-s="${esc(r.slug)}"><td class="tn"><button class="tbtn" data-act="topen" data-s="${esc(r.slug)}" title="Einzelheiten ${open ? "zuklappen" : "aufklappen"}"><span class="chev">${open ? "▾" : "▸"}</span>${dlc}${esc(name)}</button>${r.owned ? ` <span class="chip w" title="Der Titel steht schon in deiner DekuDeals-Sammlung">schon in Sammlung</span>` : ""}${packChip(r.slug)}${((S.state.s2 || {})[r.slug] || {}).base_owned ? ` <span class="chip" title="Du hast die Switch-1-Fassung: Das Upgrade-Paket genügt, Einzelheiten aufklappen">Upgrade genügt</span>` : ""}${r.no_ids ? `<small>nicht im eShop gefunden</small>` : ""}</td>
    <td class="l vdc">${pill(r.verdict)}${marks}${ps ? `<small>${ps}</small>` : why ? `<small>${why}</small>` : ""}</td>
    <td class="pr">${price}</td><td class="ob">${over}</td><td class="al">${alt}</td>
    <td class="kb-c"><button class="kb ${inBasket(r.slug) ? "on" : ""}" data-act="star" data-s="${esc(r.slug)}" title="in den gemeinsamen Korb">${inBasket(r.slug) ? "✓" : "+"}</button></td></tr>`;
  if(open) h += `<tr class="det"><td colspan="6">${titleDetail(r)}</td></tr>`;
  return h;
}
// Ersparnis gegen den nächstbesten zählenden Preis, wie bei der Kaufentscheidung; Deutschland mit und ohne Guthaben gilt als ein Land
function nextBest(x, list){
  if(!x) return "";
  const de = k => k === "DE" || k === "DG";
  const own = (list.find(e => e.code === x.code) || {}).c;
  const base = own && own.eur !== null && own.eur !== undefined ? own.eur : x.eur;
  const nb = list.find(e => e.code !== x.code && !(de(e.code) && de(x.code)) && e.c.lang !== "unknown" && !e.c.nocard && e.c.eur !== null && e.c.eur !== undefined);
  if(!nb) return ` · <span class="mut">kein zweites zählendes Land</span>`;
  const d = nb.c.eur - base;
  return d >= 0.005 ? ` · <span class="gn">${esc(x.name)} spart ${eur(d)} gegenüber ${esc(country(nb.code).name)}</span>`
    : ` · nächstbester Preis ${eur(nb.c.eur)} in ${esc(country(nb.code).name)}`;
}
function titleDetail(r){
  const mr = S.state.matrix.rows.find(x => x.slug === r.slug) || {cells:{}};
  const x = shownOffer(r) || [r.easy, r.hard].filter(Boolean).sort((a, b) => a.eur - b.eur)[0];
  const ce = r.champ, todo = S.state.lang_todo || [];
  let h = `<div class="dh"><b>${esc(r.title)}</b><span class="sp"></span>
    <a class="btn sm" href="${deku(r.slug)}" target="_blank" rel="noopener">DekuDeals</a>
    <a class="btn sm" href="${epSearch(r.title)}" target="_blank" rel="noopener">eShop-Prices</a>
    <button class="sm" data-act="verlauf" data-s="${esc(r.slug)}">Verlauf</button></div><div class="dg">`;
  if(x) h += `<span>Rechnung</span><span>${esc(x.name)}: ${esc(compose(x.code, x))}</span>`;
  const list = Object.entries(mr.cells).filter(([, c]) => !c.na).map(([code, c]) => ({code, c}))
    .sort((a, b) => (a.c.eur ?? 1e9) - (b.c.eur ?? 1e9));
  const na = Object.entries(mr.cells).filter(([, c]) => c.na);
  h += `<span>Alle Länder</span><div class="al-list">` + list.map(({code, c}) => {
    const co = country(code), counts = c.lang !== "unknown" && !c.nocard;
    const t = c.lang === "unknown" ? todo.find(t => t.slug === r.slug && t.codes.includes(code)) : null;
    const extra = c.nocard ? `<span class="warnc">ohne Karte, zählt nicht</span>`
      : c.lang === "unknown" ? `<span class="warnc">Sprache ungeprüft</span>${t ? ` <button class="sm" data-act="lang" data-s="${esc(r.slug)}" data-f="${t.family}" data-v="1">Deutsch ja</button> <button class="sm" data-act="lang" data-s="${esc(r.slug)}" data-f="${t.family}" data-v="0">nein</button>` : ""}`
      : langTag(c, true);
    // ★ steht direkt vor den Angaben, ? vor dem Grund, warum ein Land nicht zählt (0.55.1)
    return `<div class="${counts ? "" : "nc"}"><b>${ax(c)}${buyLink(code, c, eur(c.eur))}</b>
      <span>${esc(co.name)} ${ownMark(c)}${needMark(code, needsRegion(r.dlc_of, code, r.slug))} ${tierTag((S.state.matrix.cols.find(k => k.code === code) || {}).tier)}</span>
      <span class="mut">${star(c) ? star(c) + " " : ""}${counts && ce && !atBest(c.eur, ce.eur) ? `<span title="über dem Bestpreis ${eur(ce.eur)} (${esc(ce.name)})"><span class="abv">+${eur(c.eur - ce.eur)}</span> über Bestpreis</span> · ` : ""}${c.sale ? `<span class="pct" style="margin:0">−${c.pct} %</span>${c.end ? " · " + endCell(c.end, "bis ") : ""}` : "normal"}${lowTxt(c)}</span><span>${counts ? "" : `<span class="q">?</span> `}${extra}</span></div>`;
  }).join("") + (na.length ? `<div class="mut nc"><span></span><span>${na.map(([code, c]) => esc(country(code).name) + (c.nolang ? " (ohne Deutsch)" : "")).join(", ")}</span><span>nicht kaufbar</span></div>` : "") + `</div>`;
  h += ownOffersRow(r, mr);
  h += `<span>Werte</span><span>${ce ? `Bestpreis ${eur(ce.eur)} in ${esc(ce.name)} (24 Monate)` : "Bestpreis noch nicht bekannt"}${r.typical ? ` · typischer Angebotspreis ${eur(r.typical.eur)} in ${esc(r.typical.name)}` : ""}${r.de !== null ? ` · in Deutschland jetzt ${eur(r.de)}` : ""}${nextBest(x, list)}</span>`;
  const rh = rhythmLines(r.rhythm || []);
  if(rh) h += `<span>Angebote</span><span>${rh}</span>`;
  const now = Math.min(...[r.easy, r.hard].filter(Boolean).map(b => b.eur));
  const sug = r.target === null && ce && (!isFinite(now) || ce.eur < now - 0.005) ? ce.eur : null;
  h += `<span>Zielpreis</span><span><input class="tgt" type="text" inputmode="decimal" data-act="target" data-s="${esc(r.slug)}" value="${dc(r.target ?? "")}" placeholder="–">
    ${sug !== null ? `<button class="sm" data-act="tgtfill" data-s="${esc(r.slug)}" data-v="${sug}">Bestpreis ${eur(sug)} übernehmen</button>` : ""}
    <small class="mut" style="display:inline">${r.target !== null ? "Ist er erreicht, heißt das Urteil „kaufen“." : "leer: Das Urteil misst am Bestpreis."}</small></span>`;
  h += `<span>Urteil</span><span>${pill(r.verdict)} ${esc(r.reason)}${r.nohist ? ` <span class="nohist">noch ohne Verlauf</span> <small class="mut">DekuDeals hat noch keinen Tiefstpreis geliefert, der Bestpreis stützt sich nur auf heutige Preise und die eigene Aufzeichnung</small>` : ""}</span>`;
  const s2 = s2Line(r.slug);
  if(s2) h += `<span>Switch 2</span><span>${s2}</span>`;
  const pk = packLine(r.slug);
  if(pk) h += `<span>Pakete</span><span>${pk}</span>`;
  return h + `</div>`;
}
/* Suchfeld mit eigenem ×, das in jedem Browser gleich aussieht (0.62.1); Esc leert ebenfalls */
const searchBox = ph => `<span class="sbox"><input type="search" id="rq" placeholder="${esc(ph)}" value="${esc(S.rq)}">${S.rq ? `<button class="sx" data-act="rqclear" title="Suche leeren (Esc)">×</button>` : ""}</span>`;
/* Prüfstand eines eigenen Angebots mit Link (ab 0.62.1): Gilt der gelesene Preis oder der eingetragene?
   Die Plausibilität prüft der Server (planner.read_offer): Währung des Landes, höchstens 40 % Abstand. */
function offerNote(url, cur){
  const k = (S.state.offer_checks || {})[url];
  if(!url || !k) return "";
  const day = t => new Date(t * 1000).toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit"});
  if(!k.check) return `<small class="mut" title="Vom Link gelesen am ${stamp(k.read)}">gelesen ${day(k.read)}</small>`;
  const seen = k.seen !== null && k.seen !== undefined ? money(k.seen, k.seen_cur || cur) : "";
  const keep = " Es gilt dein eingetragener Preis.";
  const why = {
    cur: [`Link zeigt ${seen}`, `Die Seite nennt den Preis in ${k.seen_cur || "anderer Währung"} statt in ${cur}.` + keep],
    off: [`Link liest ${seen}, passt nicht`, "Der gelesene Preis weicht um mehr als 40 % von deinem ab: falscher Link oder Tippfehler?" + keep],
    err: ["Link nicht lesbar", `Der letzte Abruf scheiterte: ${k.error || "unbekannt"}.` + keep],
    old: ["Link länger nicht gelesen", "Der zuletzt gelesene Preis ist älter als 14 Tage." + keep],
    wait: ["wird gelesen", "Der nächste Abgleich liest den Preis vom Link."]}[k.check];
  // „Link“ führt zur Seite, zum Nachsehen, was dort steht (0.68)
  const text = why[0].startsWith("Link ") ? `<a href="${esc(url)}" target="_blank" rel="noopener">Link</a>${esc(why[0].slice(4))}` : esc(why[0]);
  return `<small class="${k.check === "wait" ? "mut" : "warnc"}" title="${esc(why[1])}">${text}</small>`;
}
/* Eigene Angebote für einen Titel (ab 0.62), etwa Codes bei Amazon Japan: Liste und Eintragen */
function ownOffersRow(r, mr){
  const all = S.state.settings.own_offers || [];
  const mine = all.map((x, i) => ({x, i})).filter(e => e.x.slug === r.slug);
  const act = S.state.countries.filter(c => (S.state.settings.countries[c.code] || {}).enabled && c.shop === c.code);
  const rows = mine.map(({x, i}) => {
    const cell = mr.cells[x.code] || {};
    const used = cell.own && cell.own.idx === i;
    const state = (used ? `<span class="gn">zählt</span>`
      : cell.na ? `<span class="mut">zählt nicht: dort keine deutsche Fassung</span>` : `<span class="mut">zählt nicht: der eShop ist dort günstiger</span>`)
      + (x.url ? " " + offerNote(x.url, (S.state.pay[x.code] || {}).currency || "") : "");
    // × gleich hinter dem Preis, damit er nicht allein in die nächste Zeile rutscht (0.68)
    return `<span class="nw">${esc(x.src)} ${esc(country(x.code).name)} ${x.url ? `<a class="tl" href="${esc(x.url)}" target="_blank" rel="noopener">${money(x.price, (S.state.pay[x.code] || {}).currency || "")}</a>` : money(x.price, (S.state.pay[x.code] || {}).currency || "")} <button class="x" data-act="owndel" data-i="${i}" title="Angebot entfernen">×</button></span> · ${state}`;
  });
  const form = `<details class="fold" data-k="own-${esc(r.slug)}" ${S.folds["own-" + r.slug] ? "open" : ""}><summary class="hint">${mine.length ? "Weiteres " : ""}Angebot außerhalb des eShops eintragen, etwa einen Code bei Amazon Japan</summary>
    <p class="hint">Bezahlt mit Kreditkarte zum Kurs plus deiner Gebühr, eingelöst im Konto des Landes. Ist es günstiger als der eShop dort, zählt es für Bestpreis, Urteil und Kaufplan. Mit Link liest der Abgleich den Preis einmal am Tag selbst.</p>
    <p class="nsox"><select id="ownc-${esc(r.slug)}">${act.map(c => `<option value="${c.code}" ${c.code === "JP" ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
    <input id="ownp-${esc(r.slug)}" type="text" inputmode="decimal" placeholder="Preis" style="width:90px">
    <input id="owns-${esc(r.slug)}" type="text" value="Amazon" style="width:90px" title="Quelle">
    <input id="ownu-${esc(r.slug)}" type="url" placeholder="Link (optional)" style="width:220px">
    <button class="sm" data-act="ownadd" data-s="${esc(r.slug)}">Eintragen</button></p></details>`;
  return `<span>Eigene Angebote</span><span>${rows.length ? rows.join("<br>") : ""}${form}</span>`;
}
/* Landestief neben dem Preis eines Landes: erreicht (grün) oder wie viel darüber (rot), 0.53.3 */
/* Landestief nur als Auskunft, grau: Maßstab der Kaufentscheidung ist der Bestpreis aller Länder (0.53.5) */
function lowTxt(c){
  if(c.low_eur === null || c.low_eur === undefined) return "";
  // Normalpreis am Landestief: nie im Angebot gewesen, nichts Besonderes
  if(c.eur <= c.low_eur * 1.02 + 0.005) return c.sale ? ` · am Landestief` : "";
  return ` · Landestief ${eur(c.low_eur)}`;
}
/* Angebotsrhythmus je Land aus den DekuDeals-Verläufen, ohne Vorhersage */
const MONTHS = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"];
function rhythmLines(list){
  const join = a => a.length > 1 ? a.slice(0, -1).join(", ") + " und " + a[a.length - 1] : a.join("");
  return list.map(x => {
    let t = `<b>${esc(x.name)}</b>: ${x.count === 1 ? "1 Angebot" : `${x.count} Angebote`} seit ${esc(x.since.slice(5, 7) + "." + x.since.slice(0, 4))}`;
    if(x.gap !== null) t += `, im Schnitt alle ${x.gap} Wochen${x.gap_min !== x.gap_max ? ` (${x.gap_min} bis ${x.gap_max})` : ""}`;
    t += x.running ? `. Das letzte läuft seit ${dm(x.last_start)}`
      : x.last_end ? `. Das letzte lief vom ${dm(x.last_start)} bis ${dm(x.last_end)}, Beginn vor ${x.weeks_ago} Wochen`
      : `. Das letzte begann am ${dmy(x.last_start)}, vor ${x.weeks_ago} Wochen`;
    if(x.months.length) t += `. Meist im ${join(x.months.map(m => MONTHS[m - 1]))}`;
    if(x.next) t += `. ${new Date(x.next) < new Date() ? "Nach diesem Muster wäre das nächste schon fällig" : `Nach diesem Muster wäre das nächste ab etwa ${dmy(x.next)} üblich`} <span class="mut">(Schätzung)</span>`;
    return (t + ".").replace(/\.\.$/, ".");
  }).join("<br>");
}
function packChip(slug){
  const p = ((S.state.bundles || {}).packs || {})[slug];
  if(!p) return "";
  if(p.have.length) return ` <span class="chip w" title="${esc(p.have.join(", "))} steht schon in deiner Sammlung">Teil schon da</span>`;
  if(!p.partial && p.saving > 0.005) return ` <span class="chip" title="Das Paket kostet weniger als die Teile einzeln">Paket spart ${eur(p.saving)}</span>`;
  if(!p.partial && p.saving < -0.005) return ` <span class="chip w" title="Die Teile einzeln kosten weniger als das Paket">einzeln günstiger</span>`;
  return "";
}
/* Komplett-Edition gegen Einzelkauf, und in welchen Paketen ein Titel steckt */
function packLine(slug){
  const b = S.state.bundles || {}, p = (b.packs || {})[slug], ins = (b.in || {})[slug] || [];
  const out = [];
  if(p){
    const parts = p.parts.map(k => `${esc(k.title)}${k.owned ? ` <span class="mut">✓ hast du</span>` : k.eur !== null && k.eur !== undefined ? ` ${eur(k.eur)}` : ` <span class="mut">ohne Preis</span>`}`).join(", ");
    let cmp = "";
    if(p.partial) cmp = ` <span class="mut">DekuDeals nennt nicht alle Teile, deshalb kein Vergleich.</span>`;
    else if(p.saving !== null && p.saving !== undefined)
      cmp = ` · einzeln ${eur(p.alone)}${p.have.length ? " (ohne, was du hast)" : ""}, als Paket ${p.est ? "ca. " : ""}${eur(p.eur)}: ` +
        (p.saving > 0.005 ? `<b>Paket spart ${eur(p.saving)}</b>` : p.saving < -0.005 ? `<span class="warnc">einzeln ${eur(-p.saving)} günstiger</span>` : "gleich teuer");
    else if(p.unpriced.length) cmp = ` <span class="mut">Für den Vergleich fehlt der Preis von ${p.unpriced.map(esc).join(", ")} (nicht auf der Wishlist).</span>`;
    out.push(`Enthält, soweit bekannt: ${parts}${cmp}${p.have.length ? `. <span class="warnc">${p.have.map(esc).join(", ")} hättest du doppelt.</span>` : ""}`);
  }
  if(ins.length) out.push(`Auch enthalten in: ${ins.map(i => i.wish ? `<button class="link" data-act="gotitle" data-s="${esc(i.slug)}">${esc(i.title)}</button>` : `<a class="tl" href="${esc(deku(i.slug))}" target="_blank" rel="noopener">${esc(i.title)}</a>`).join(", ")}`);
  return out.join("<br>");
}
/* Switch-2-Edition: reicht das Upgrade-Paket zum Spiel, das du schon hast? */
function s2Line(slug){
  const p = (S.state.s2 || {})[slug];
  if(!p) return "";
  const ap = p.est ? "ca. " : "";
  const up = "das Upgrade-Paket";
  const cmp = p.path_saving !== null && p.path_saving !== undefined
    ? (p.path_saving > 0.005 ? ` · <b>spart ${eur(p.path_saving)}</b> gegenüber der Edition (${eur(p.edition_eur)})`
       : ` · die Edition (${eur(p.edition_eur)}) ist ${p.path_saving < -0.005 ? `${eur(-p.path_saving)} günstiger` : "gleich teuer"}`) : "";
  if(p.base_owned && p.upgrade_owned) return `Die Switch-1-Fassung (${esc(p.base_title)}) und das Upgrade-Paket stehen in deiner Sammlung. Die Edition brauchst du nicht.`;
  if(p.base_owned) return `Die Switch-1-Fassung (${esc(p.base_title)}) steht in deiner Sammlung. Das Upgrade-Paket genügt` +
    (p.upgrade_eur !== null && p.upgrade_eur !== undefined ? `: jetzt ${ap}${eur(p.upgrade_eur)} in ${esc(p.upgrade_name)}${cmp}`
     : `. Setz es auf die Wishlist${p.upgrade ? ` (<a class="tl" href="${esc(deku(p.upgrade))}" target="_blank" rel="noopener">DekuDeals</a>)` : ""}, dann rechnet das Tool den Preis.`);
  if(p.path_eur !== null && p.path_eur !== undefined)
    return `Statt der Edition: Switch-1-Fassung (${eur(p.base_eur)} in ${esc(p.base_name)}) plus ${up} (${eur(p.upgrade_eur)}), zusammen ${ap}${eur(p.path_eur)}${cmp}`;
  return `Es gibt auch die Switch-1-Fassung (${esc(p.base_title)}) plus ${up}. Stehen beide auf der Wishlist, vergleicht das Tool diesen Weg mit der Edition.`;
}
