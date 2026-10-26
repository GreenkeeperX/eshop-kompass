"use strict";
/* Reiter Jetzt und die Legende (Teil der Oberfläche, Reihenfolge in index.html) */
/* ---------- Jetzt: Startseite mit Konto, Aufgaben und Kaufplan ---------- */
function accountLine(){
  const s = S.state.settings, cur = s.current_country, pi = cur ? S.state.pay[cur] : null;
  // Nur Länder mit eigenem Shop: „Deutschland (Guthaben)“ ist dasselbe deutsche Konto (0.63)
  const opts = [...S.state.countries].filter(c => c.shop === c.code && ((s.countries[c.code] || {}).enabled || c.code === cur))
    .sort((x, y) => x.name.localeCompare(y.name, "de"))
    .map(c => `<option value="${c.code}" ${c.code === cur ? "selected" : ""}>${esc(c.name)}</option>`).join("");
  const bal = cur && s.countries[cur] ? s.countries[cur].balance || 0 : 0;
  return `<div class="acct"><span>Konto steht in: <select data-act="acct"><option value="">nicht angegeben</option>${opts}</select></span>` +
    (cur && cur !== "DE" ? `<span>Guthaben dort: <input type="text" inputmode="decimal" data-act="bal" value="${dc(bal)}"> ${esc((pi || {}).currency || "")}</span>` : "") +
    ` <span class="hint">„gekauft“ stellt beides selbst um.</span></div>`;
}
function todos(){
  const out = [], s = S.state.settings;
  // Nur was gerade Geld kostet: offene Sprachen, wo die Fassung günstiger wäre. Die übrigen
  // offenen Titel stehen unter Einstellungen, Sprachen prüfen.
  const open = (S.state.lang_todo || []).filter(t => !t.manual && t.state === null && t.here), need = open.filter(t => t.matters);
  // Je Aufgabe ein fetter Kern, Einzelheiten klein dahinter (0.65)
  if(need.length) out.push([`<b>${need.length} ${need.length === 1 ? "Sprache" : "Sprachen"} prüfen</b> <small>in ${[...new Set(need.map(t => t.family_name))].join(", ")} wäre es günstiger (${need.slice(0, 3).map(t => esc(t.title)).join(", ")}${need.length > 3 ? " …" : ""})${open.length > need.length ? `; insgesamt ${open.length} offen` : ""}</small>`, `<button class="link" data-act="gosprachen">prüfen</button>`]);
  for(const p of S.plans){
    if(p.is_ref || p.code === "DG" || !(s.countries[p.code] || {}).enabled) continue;
    // Nach Ursache (0.95): keine Karte, keine vorrätig, keine mit Preis
    const w = p.warnings.find(w => w.startsWith("Keine Guthabenkarte"));
    if(w){
      const [what, why] = w.startsWith("Keine Guthabenkarten") ? ["Guthabenkarte eintragen", "ohne Karte mit Preis sind die Preise dort geschätzt"]
        : w.startsWith("Keine Guthabenkarte vorrätig") ? ["keine Karte vorrätig", "alle eingetragenen Karten sind als nicht vorrätig markiert, die Preise dort sind geschätzt"]
        : ["kein Kartenpreis", "für keine vorrätige Karte ist ein Preis gelesen oder eingetragen, die Preise dort sind geschätzt"];
      out.push([`<b>${esc(p.name)}: ${what}</b> <small>${why}</small>`, `<button class="link" data-act="gocards" data-c="${p.code}">Karten ${w.startsWith("Keine Guthabenkarten") ? "eintragen" : "ansehen"}</button>`]);
    }
  }
  const coll = S.state.collection || {};
  // Kostenlose DLC deiner Spiele: holen kostet nichts (0.52)
  const free = coll.free || [];
  if(free.length) out.push([`<b>${free.length === 1 ? "Einen fehlenden DLC" : `${free.length} fehlende DLC`} kostenlos holen</b> <details class="inl" data-k="todofree" ${S.folds.todofree ? "open" : ""}><summary>welche</summary>${free.map(f =>
    `<a class="tl" href="${esc(deku(f.slug))}" target="_blank" rel="noopener" title="${f.end ? `kostenlos bis ${esc(dmy(f.end))}` : "bei DekuDeals ansehen"}">${esc(f.game)}: ${esc(f.title)}</a>`).join("<br>")}</details>`,
    `<button class="link" data-act="gotab" data-v="sammlung">Sammlung</button>`]);
  // Pass statt Teile: Teile stehen auf der Wishlist, der Pass ist günstiger als alle fehlenden Teile
  for(const x of coll.pass_hints || [])
    out.push([`<b>${esc(x.game)}: Pass statt Teile</b> <small>${x.wished.map(w => esc(w.title)).join(", ")} ${x.wished.length === 1 ? "steht" : "stehen"} auf der Wishlist. <a class="tl" href="${esc(deku(x.slug))}" target="_blank" rel="noopener">${esc(x.title)}</a> enthält ${x.open} fehlende DLC, einzeln ${eur(x.single)}, als Pass ${x.est ? "ca. " : ""}${eur(x.eur)} (spart ${eur(x.saving)}). Auf die Wishlist gesetzt, plant ihn der Kaufplan statt der Teile.</small>`, ""]);
  // Erinnerung an „Käufe lesen“: älter als 30 Tage und seitdem gekauft
  const at = S.state.eshop_at || 0, k = S.kauf;
  if(at && Date.now() / 1000 - at > 30 * 86400 &&
     ((S.state.eshop_owned_n !== null && S.state.eshop_owned_n !== undefined && S.state.owned_count > S.state.eshop_owned_n) ||
      (k && (k.bought || []).some(b => new Date(b.at) / 1000 > at))))
    out.push([`<b>Käufe lesen</b> <small>zuletzt am ${esc(dmy(new Date(at * 1000).toISOString()))}, seitdem hast du gekauft</small>`, `<button class="link" data-act="gokaeufe" data-v="how">Käufe lesen</button>`]);
  // Käufe (0.71): nur, was den Plan ändert oder bei DekuDeals fehlt
  const er = S.state.eshop || [], ask = er.filter(r => r.group === "ask"), add = er.filter(r => r.group === "plan");
  if(ask.length) out.push([`<b>${ask.length === 1 ? "Einen Kauf" : `${ask.length} Käufe`} zuordnen</b> <small>ähnlich zu ${ask.slice(0, 3).map(r => esc(r.suggest[0].title)).join(", ")}${ask.length > 3 ? " …" : ""}</small>`, `<button class="link" data-act="gokaeufe">zuordnen</button>`]);
  if(add.length) out.push([`<b>${add.length === 1 ? "Einen Kauf" : `${add.length} Käufe`} bei DekuDeals nachtragen</b> <small>${add.slice(0, 3).map(r => esc(r.name || r.title)).join(", ")}${add.length > 3 ? " …" : ""}; ${add.length === 1 ? "zählt" : "zählen"} schon als Besitz</small>`, `<button class="link" data-act="gokaeufe">ansehen</button>`]);
  // Online-Mitgliedschaft: 30 Tage vor Ablauf (0.56)
  const nso = S.state.nso;
  // Nach einem vermerkten Kauf mit Mitgliedschaft (0.88): neues Ablaufdatum vorschlagen, statt zu erinnern
  if(nso && nso.suggest) out.push([nsoSuggest(nso), ""]);
  else if(nso && nso.due){
    const b = (nso.rows || []).find(r => r.counts);
    out.push([`<b><button class="link" data-act="gonso" title="Zum Kasten Online-Mitgliedschaft">Online-Mitgliedschaft</button> ${nso.days_left < 0 ? "ist abgelaufen" : `läuft ${nso.days_left === 0 ? "heute" : `in ${nso.days_left} ${nso.days_left === 1 ? "Tag" : "Tagen"}`} ab`}</b>${b ? ` <small>am günstigsten in ${esc(b.name)} für ${eur(b.eur)}</small>` : ""}`, `<button class="link" data-act="gonso">ansehen</button>`]);
  }
  for(const [code, c] of Object.entries(s.countries)){
    if(c.enabled && c.cards && c.cards_checked && Date.now() - new Date(c.cards_checked) > 30 * 86400000)
      out.push([`<b>${esc(country(code).name)}: Kartenpreise prüfen</b> <small>älter als 30 Tage</small>`, `<button class="link" data-act="gocards" data-c="${code}">prüfen</button>`]);
  }
  if(!out.length) return "";
  return `<div class="todo"><b>Zu erledigen</b>` + out.map(([t, a]) => `<div><span>${t}</span>${a}</div>`).join("") + `</div>`;
}
function viewJetzt(){
  return accountLine() + todos() + viewKauf() + nsoBox();
}
/* Online-Mitgliedschaft, 12 Monate, einzeln (0.56): Einkaufspreis je aktivem Land mit deinem
   Zahlweg, klein und zugeklappt, solange die Verlängerung nicht ansteht. */
/* Online-Mitgliedschaft (ab 0.57): oben die Varianten im Vergleich, je im besten Land; ein Klick wählt,
   welche Variante die Ländertabelle darunter zeigt. „deine“ stellst du darüber ein, sie bestimmt
   Kopfzeile und Erinnerung. Farben wie bei Titeln: ★ gold am Bestpreis, grün fürs Urteil, rot der Betrag darüber. */
/* Bausteine einer Zeile der Mitgliedschaft, oben je Variante wie unten je Land (0.69) */
function nsoPrice(r, v){
  const g = r.grade === "buy" ? "g-buy" : r.grade === "good" ? "g-good" : "";
  const tip = `${r.est ? "geschätzt, ohne gelesenen Kartenpreis · " : ""}${r.low_eur !== null && r.low_eur !== undefined ? `Tiefstpreis 24 Monate hier ${eur(r.low_eur)}${r.low_since ? ` (eigene Aufzeichnung seit ${dmy(r.low_since)})` : ""}` : "kein Tiefstpreis bekannt"}${v.champ ? ` · Bestpreis ${eur(v.champ)} in ${r.champ_name || ""}` : ""}`;
  const price = `<span class="${g}" title="${esc(tip)}">${r.est ? "ca. " : ""}${eur(r.eur)}</span>`;
  return r.url ? `<a class="pl" href="${esc(r.url)}" target="_blank" rel="noopener" title="${esc(tip)} · Klick öffnet ${r.src ? esc(r.src) : `den eShop ${esc(r.name)}`}">${price}</a>` : price;
}
function nsoTags(r, planned){
  return [r.src ? ` <span class="chip" title="Bezahlt mit Kreditkarte zum Kurs plus Gebühr; den Code löst du im Konto dieses Landes ein.">${esc(r.src)}-Code</span>` : "",
    r.current ? ` <span class="chip" title="Dein Konto steht gerade in diesem Land: Hier kaufst du ohne Wechsel">Konto</span>` : "",
    planned.has(r.code) ? ` <span class="chip" title="Der Kaufplan kauft gerade in diesem Land: Die Mitgliedschaft ließe sich im selben Schritt mitkaufen">im Plan</span>` : ""].join("");
}
function nsoChips(r, v){
  return [r.sale && r.pct ? `<span class="pct">−${r.pct} %</span>${r.end ? " " + endCell(r.end, "bis ") : ""}` : "",
    !r.counts ? `<span class="warnc">ohne Guthabenkarte, zählt nicht</span>` : !r.at_best && r.over > 0.005 ? `<span class="abv" title="über dem Bestpreis: ${eur(v.champ)} in ${esc(r.champ_name || "")}">+${eur(r.over)}</span>` : "",
    v.slug && !r.src ? `<a class="tl" href="${esc(deku(v.slug, r.code))}" target="_blank" rel="noopener" title="Preisverlauf bei DekuDeals">DekuDeals</a>` : ""].filter(Boolean).join(" ");
}
function nsoSuggest(m){
  const s = m.suggest, by = s.from.map(f => `${esc(f.label)} am ${esc(dmy(f.date))}`).join(", ");
  return `<b>Mitgliedschaft gekauft</b> <small>läuft damit bis ${esc(dmy(s.until))} (${by})</small> ` +
    `<button class="link" data-act="nsotake" data-v="${esc(s.until)}" title="Gerechnet ab Ablauf, sonst ab dem Kauftag; 1 Monat zählt 30 Tage, 3 Monate 90, 12 Monate 365">übernehmen</button> · <button class="link" data-act="nsotake" data-v="${esc(m.until)}" title="Das eingetragene Datum bleibt">verwerfen</button>`;
}
function nsoBox(){
  const m = S.state.nso;
  if(!m) return "";
  const vs = m.variants || [];
  const mineV = vs.find(v => v.key === m.mine);
  // Eine Auswahl (0.61): Die gewählte Variante ist deine, sie bestimmt Kopfzeile, Erinnerung und Länderliste
  const sel = mineV || {key: m.mine, label: "12 Monate", months: 12, accounts: 1, rows: m.rows || [], champ: m.champ, slug: "nintendo-switch-online-12-month-membership"};
  const rows = sel.rows || [], best = rows.find(r => r.counts), myBest = ((mineV || sel).rows || []).find(r => r.counts);
  const planned = new Set(((S.kauf || {}).steps || []).map(p => p.code));
  const grade = r => r.grade === "buy" ? "g-buy" : r.grade === "good" ? "g-good" : "";
  const starOf = r => r.at_best ? `<span class="star" title="Am Bestpreis">★</span>` : "";
  const until = m.until ? `läuft bis ${esc(dmy(m.until))}${m.days_left !== null && m.days_left >= 0 ? ` (noch ${m.days_left} ${m.days_left === 1 ? "Tag" : "Tage"})` : m.days_left < 0 ? " (abgelaufen)" : ""}` : "Ablaufdatum offen";
  const myLabel = mineV ? mineV.label : "12 Monate";
  const head = myBest ? `am günstigsten ${esc(myBest.name)} ${starOf(myBest)}${myBest.est ? "ca. " : ""}<b class="${grade(myBest)}">${eur(myBest.eur)}</b> (${eur(myBest.month)} je Monat)`
    : m.ids_known ? "Preise kommen mit dem nächsten Abgleich" : "die eShop-IDs sucht der nächste Abgleich";
  let h = `<details class="box" id="nsobox" data-k="nso" ${S.folds.nso || m.due ? "open" : ""}><summary><b>Online-Mitgliedschaft</b> <span class="mut">ausgewählt: ${esc(myLabel)} · ${head} · ${until}</span></summary>
    <p class="hint">Deine Mitgliedschaft (die markierte Variante, ein Klick wählt eine andere) läuft bis <input type="date" data-act="nsountil" value="${esc(m.until)}">${m.suggest ? ` · ${nsoSuggest(m)}` : ""} · 30 Tage vorher erinnert dich der Kasten „Zu erledigen“ oben im Reiter Jetzt an die Verlängerung (er erscheint nur, wenn etwas ansteht). Bezahlt wie bei Spielen: Kreditkarte oder deine Guthabenkarten. Kaufen kannst du nur im Land, in dem dein Konto gerade steht.</p>`;
  // Vergleich der Varianten: günstigster Preis je Monat (bei Familie je Konto) fett
  const priced = vs.filter(v => v.best);
  if(priced.length > 1){
    const cheapest = Math.min(...priced.filter(v => !v.family).map(v => v.best.per_account));   // Familie kaufst du nicht selbst
    h += `<table class="mini-t nsov"><tr>${sth("nsov", "label", "Variante", "", "l")}${sth("nsov", "land", "bestes Land", "", "l")}${sth("nsov", "eur", "Einkaufspreis", "", "num")}${sth("nsov", "month", "je Monat", "Bei der Familie je Konto", "num")}<th class="num">im Shop</th><th class="l"></th></tr>` + sortRows("nsov", vs, {
      label: v => v.label, land: v => v.best ? v.best.name : null, eur: v => v.best ? v.best.eur : null, month: v => v.best ? v.best.per_account : null}).map(v => {
      const b = v.best;
      // Nur der Name ist Link, die Laufzeit in Klammern steht grau daneben (0.58)
      const [main, paren] = v.label.split(" (");
      const name = v.key === sel.key ? `<b title="Deine Mitgliedschaft: Kopfzeile, Erinnerung und Länder unten gelten ihr">${esc(main)}</b>${paren ? ` <span class="mut">(${esc(paren)}</span>` : ""}`
        : `<button class="link" data-act="nsov" data-v="${v.key}" title="Als deine Mitgliedschaft wählen und ihre Länder zeigen">${esc(main)}</button>${paren ? ` <span class="mut">(${esc(paren)}</span>` : ""}`;
      const tags = [v.family ? `<span class="chip" title="Kaufen kann nur, wer die Familiengruppe verwaltet; der Preis gilt für bis zu ${v.accounts} Konten">kauft der Verwalter</span>` : ""].filter(Boolean).join(" ");
      if(!b) return `<tr class="${v.key === sel.key ? "on" : ""}"><td class="l">${name} ${tags}</td><td class="l mut" colspan="5">noch kein Preis</td></tr>`;
      const month = v.family ? `<span title="${eur(b.month)} je Monat für die ganze Gruppe">${eur(b.per_account)} je Konto</span>` : eur(b.month);
      // Wie die Ländertabelle (0.69): Preis führt in den Shop, Tooltip mit Tiefst- und Bestpreis, Shop-Preis,
      // Chips; so reicht die obere Tabelle, die Länder darunter sind zugeklappt
      return `<tr class="${v.key === sel.key ? "on" : ""}"><td class="l">${name} ${tags}</td><td class="l">${esc(b.name)}${nsoTags(b, planned)}</td><td class="num">${starOf(b)}${nsoPrice(b, v)}</td><td class="num">${!v.family && b.per_account <= cheapest + 0.005 ? `<b>${month}</b>` : month}</td><td class="num mut">${money(b.local, b.currency)}</td><td class="l">${nsoChips(b, v)}</td></tr>`;
    }).join("") + `</table>`;
  }
  // Alle Länder der ausgewählten Variante zugeklappt (0.69): Die obere Tabelle trägt Link, Tooltip und Chips
  const landOpen = S.folds.nsoland || priced.length <= 1;
  if(vs.length){
    const atBestNow = rows.some(r => r.at_best);
    h += `<details class="fold" data-k="nsoland" ${landOpen ? "open" : ""}><summary class="hint" style="margin:8px 0 2px">Alle Länder für <b>${esc(sel.label)}</b>${rows.length ? ` (${rows.length})` : ""}${sel.champ ? ` · Bestpreis der letzten 24 Monate ${eur(sel.champ)} in ${esc((rows[0] || {}).champ_name || "")}${atBestNow ? "" : ", gerade nirgends zu haben"}` : ""}</summary>`;
  }
  if(rows.length){
    h += `<table class="mini-t"><tr>${sth("nso", "name", "Land", "", "l")}${sth("nso", "tier", "Wechsel", "Wie mühsam der Wechsel des Kontos dorthin ist", "l")}${sth("nso", "eur", "Einkaufspreis", "", "num")}${sth("nso", "month", "je Monat", "", "num")}<th class="num">im Shop</th><th class="l"></th></tr>` + sortRows("nso", rows, {
      name: r => r.name, tier: r => r.tier, eur: r => r.eur, month: r => r.month}).map(r => {
      const price = nsoPrice(r, sel);
      // Eigene Angebote: Preis vom Link gelesen (ab 0.61) oder wie eingetragen
      const xstate = !r.src ? "" : r.url ? offerNote(r.url, r.currency) : `<small class="mut">eingetragen${r.date ? " " + esc(dmy(r.date)) : ""}</small>`;
      const tags = [r.src ? `<span class="chip" title="Bezahlt mit Kreditkarte zum Kurs plus Gebühr; den Code löst du im Konto dieses Landes ein.">${esc(r.src)}-Code</span> ${xstate} <button class="x" data-act="nsoxdel" data-i="${r.extra}" title="Angebot entfernen">×</button>` : "",
        r.current ? `<span class="chip" title="Dein Konto steht gerade in diesem Land: Hier kaufst du ohne Wechsel">Konto</span>` : "",
        planned.has(r.code) ? `<span class="chip" title="Der Kaufplan kauft gerade in diesem Land: Die Mitgliedschaft ließe sich im selben Schritt mitkaufen">im Plan</span>` : ""].filter(Boolean).join(" ");
      const chips = nsoChips(r, sel);
      return `<tr class="${r.counts ? "" : "nc"}"><td class="l">${r === best ? `<b>${esc(r.name)}</b>` : esc(r.name)} ${tags}</td><td class="l">${tierTag(r.tier)}</td><td class="num">${starOf(r)}${price}</td><td class="num mut">${eur(r.month)}</td><td class="num mut">${money(r.local, r.currency)}</td><td class="l">${chips}</td></tr>`;
    }).join("") + `</table>`;
  } else if(vs.length) h += `<p class="hint">Für ${esc(sel.label)} gibt es noch keine Preise. Die eShop-IDs liest der nächste Abgleich von Nintendos Mitgliedschaftsseite und von DekuDeals.</p>`;
  if(vs.length) h += `</details>`;
  // Weitere Angebote von Hand, etwa Codes bei Amazon Japan (0.60)
  const act = S.state.countries.filter(c => (S.state.settings.countries[c.code] || {}).enabled && c.shop === c.code);
  h += `<details class="fold" data-k="nsox" ${S.folds.nsox ? "open" : ""}><summary class="hint">Weiteres Angebot eintragen, etwa einen Code bei Amazon Japan</summary>
    <p class="hint">Gilt, bis du es entfernst; bezahlt mit Kreditkarte zum Kurs plus deiner Gebühr. Preis in der Landeswährung. Mit Link liest der Abgleich den Preis einmal am Tag selbst, etwa bei Amazon; zeigt der Shop eine Prüfseite, gilt dein Preis.</p>
    <p class="nsox"><select id="nsoxk" aria-label="Variante der Mitgliedschaft">${vs.map(v => `<option value="${v.key}" ${v.key === sel.key ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select>
    <select id="nsoxc" aria-label="Land des Angebots">${act.map(c => `<option value="${c.code}" ${c.code === "JP" ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
    <input id="nsoxp" type="text" inputmode="decimal" placeholder="Preis" style="width:90px">
    <input id="nsoxs" type="text" value="Amazon" style="width:90px" title="Quelle">
    <input id="nsoxu" type="url" placeholder="Link (optional)" style="width:220px">
    <button class="sm" data-act="nsoxadd">Eintragen</button></p></details>`;
  return h + `</details>`;
}

/* ---------- Legende: eine für alle Ansichten ---------- */
function openLegend(){
  const d = $("legend");
  d.innerHTML = `<header><h2>Legende</h2><button data-act="lgclose" autofocus>Schließen</button></header><div class="lgd">
    <div><span class="vd buy">kaufen</span> Einkaufspreis höchstens ${eur(S.state.settings.deal_eur.buy)} oder höchstens 2 % über dem Bestpreis, oder dein Zielpreis ist erreicht.${S.state.settings.deal_eur.mini > 0 ? ` Kleinkram (Bestpreis unter ${eur(S.state.settings.deal_eur.mini)}) nur bis 2 %.` : ""}</div>
    <div><span class="vd good">gut</span> höchstens ${eur(S.state.settings.deal_eur.good)} oder höchstens 15 % über dem Bestpreis.</div>
    <div><span class="vd wait">warten</span> weiter weg vom Bestpreis. Das Urteil gilt dem günstigsten Preis jetzt, mit oder ohne Rabatt: Ein dauerhaft günstiger Normalpreis am Bestpreis ist „kaufen“.</div>
    <div><span class="nohist">ohne Verlauf</span> DekuDeals hat noch keinen Tiefstpreis geliefert: Der Bestpreis stützt sich nur auf heutige Preise und die eigene Aufzeichnung. <span class="warnc">Preise vom 18.10.2026</span> am Schritt: Der letzte Preisabruf dort scheiterte, es gelten die alten Preise.</div>
    <div><b>Bestpreis</b>: der niedrigste Einkaufspreis der letzten 24 Monate über alle zählenden Länder, mit deinem heutigen Einkaufsweg gerechnet. <b>Einkaufspreis</b>: was du zahlst, mit Steuer, Kurs, Guthabenkarten und Gebühr.</div>
    <div><span class="star">★</span> am Bestpreis. In der Tabelle: <span class="sw c-buy">9,99</span> „kaufen“, <span class="sw c-good">9,99</span> „gut“, <span class="sw champ">9,99</span> hier gab es den Bestpreis.</div>
    <div><b>Wechsel</b>: ob sich der Weg in ein Land lohnt, am Schritt <b>✓ lohnt</b> oder <b class="bad">lohnt nicht</b>. Gerechnet gegen das, was dieselben Titel ohne diesen Wechsel kosten („sonst“: günstigstes Land gleicher oder leichterer Stufe oder dein aktuelles Land), mit deiner Schwelle je Stufe. <b>Rest</b>: Guthaben, das nach dem Kauf auf dem Konto bleibt; vor einem weiteren Wechsel verfällt er und zählt als Kosten.</div>
    <div><span class="tier">leicht</span> Kartenzahlung, kein Rest · <span class="tier">mittel</span> Guthabenkarten, ein Rest verfällt beim Wechsel · <span class="tier">schwer</span> Guthabenkarten, ein Wechsel mit Guthaben geht nur über den Support.</div>
    <div><span class="pct">−60 %</span> Rabatt im Shop (blau). <span class="approx">≈</span> geschätzt (ohne gelesenen Kartenpreis); in der Sammlung unter „Spiele“ grau: nur eine Quelle, violett: die Quellen widersprechen sich. <span class="cb">✱</span> mit Cashback des Kartenshops wäre es der Bestpreis. <span class="q">?</span> zählt nicht: Sprache ungeprüft oder ohne Guthabenkarte. <span class="asm">1,15 €</span> <small class="asm">angenommen</small> Was wäre, wenn: ein Preis, den du im Kaufplan mit ✎ angenommen hast.</div>
    <div><span class="lgt de">DE✓</span> deutsche Fassung bestätigt oder dieselbe wie im deutschen eShop · <span class="lgt no">andere Fassung</span> ohne Deutsch · <span class="lg warnc">Deutsch</span> violett: laut titledb, nicht von Nintendo.</div>
    <div>Chips: <span class="chip">Konto</span> dein Konto steht dort, <span class="chip">im Plan</span> der Kaufplan kauft dort, <span class="tagwin">günstigstes</span> günstigstes Land im Korb, <span class="chip">Switch-2-Upgrade</span> Upgrade-Paket, <span class="chip">Upgrade genügt</span> du hast die Switch-1-Fassung, <span class="chip w">schon in Sammlung</span> steht schon in deiner Sammlung, <span class="chip">Paket spart …</span> oder <span class="chip w">einzeln günstiger</span> Paket gegen seine Teile, <span class="chip w">Teil schon da</span> ein Teil des Pakets ist schon in deiner Sammlung. <b>ca.</b> vor einem Betrag: geschätzt oder aus anderen Angaben errechnet, etwa ein Pass aus seinen Teilen.</div>
    <div>Marken: <span class="dlc">DLC</span> Zusatzinhalt · <span class="dlc need">DLC</span> braucht das Spiel aus dieser Region · <span class="dlc open">DLC?</span> Fassung ungeprüft · <span class="dlc ownm">Amazon</span> eigenes Angebot, mit Kreditkarte bezahlt. <span class="dlc own">✓</span> im Kaufplan: schon in deiner Sammlung. In der Sammlung: <span class="warnc">fehlt</span> noch nicht in deiner Sammlung, <span class="chip und">nicht auf der Wishlist</span> fehlt, und du hast noch nicht entschieden, ↳ steckt im Pass oder Paket darüber.</div>
    <div>Farben: <span class="g-buy">grün</span> nur fürs Urteil, <span class="star">gold</span> nur für den Bestpreis, <span class="warnc">violett</span> heißt prüfen, <span class="bad">rot</span> heißt nein oder teurer, etwa der Betrag über dem Bestpreis; ein roter Preis in einem Schritt kostet dort mehr als ohne den Wechsel („sonst“). Rot ist immer nur der Betrag. Jede Rechnung steht unter „Rechnung“ oder im Tooltip.</div>
  </div>`;
  if(!d.open) d.showModal();
}
