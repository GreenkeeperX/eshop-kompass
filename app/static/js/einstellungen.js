"use strict";
/* Reiter Einstellungen mit Helfern und Lesezeichen (Teil der Oberfläche, Reihenfolge in index.html) */
/* ---------- Einstellungen: jede Änderung wird sofort gespeichert ---------- */
function cardInfo(text){
  let n = 0, out = 0;
  for(const line of (text || "").split(/[\n;]+/)){
    const t = line.trim();
    if(!t) continue;
    const off = /^(?:[x#!\-]\s+|\(aus\))/i.test(t);
    const body = t.replace(/^(?:[x#!\-]\s+|\(aus\)\s*)/i, "").replace(/https?:\/\/\S+/g, "").replace(/\s*=\s*/g, "=");
    const parts = (t.includes("|") || /https?:/i.test(t)) ? [body.split("|")[0]] : body.split(/\s+/);
    for(const p of parts) if(/\d/.test(p)){ n++; if(off) out++; }
  }
  return n ? `${n} ${n === 1 ? "Karte" : "Karten"} erkannt${out ? `, ${out} nicht vorrätig` : ""}` : "keine Karten eingetragen";
}
/* Spalte „Dein Faktor“: was 1 € Guthaben dort kostet, mit Zahlweg und Bewertung (0.53) */
function faktorCell(pi){
  const k = pi.card, est = pi.via === "giftcard" && !k && !pi.at_rate;
  const tip = pi.via === "card" ? `Kreditkarte: Mittelkurs plus ${pctTxt(pi.fee)} Gebühr` :
    k ? `Karte ${money(k.face, pi.currency)} (Wert ${eur(k.value)}) für ${eur(k.cost)}${k.live ? `, Shop-Preis vom ${stamp(k.live)}` : ", dein eingetragener Preis"}` :
    pi.via === "eur" ? "kein Guthaben unter Nennwert eingetragen" :
    pi.at_rate ? "Guthaben zum Kurs (Werte ohne Link)" : "geschätzt: kein Kartenpreis bekannt, entscheidet nichts";
  const how = pi.via === "card" ? "Kreditkarte" : pi.via === "eur" ? "Shop-Preis" : est ? "geschätzt" : "Guthaben";
  const r = pi.rating && pi.rating.level && !["cheaper", "same", "dearer"].includes(pi.rating.level) ? pi.rating.text.split(",")[0] : "";
  return `<span title="${esc(tip)} · 1 € = ${(1 / pi.unit).toLocaleString("de-DE", {maximumFractionDigits: 3})} ${esc(pi.currency)}" class="${pi.factor < 1 ? "lvl-neg" : "lvl-pos"}">${est ? "≈ " : ""}${fac(pi.factor)}</span> <small class="hint">${how}${r ? `, ${esc(r)}` : ""}</small>`;
}
function viewSettings(){
  const s = S.state.settings, lv = S.state.levels;
  const sel = (v, cur, l) => `<option value="${v}" ${String(cur) === String(v) ? "selected" : ""}>${l}</option>`;
  const on = c => c.code === "DE" || s.countries[c.code].enabled;
  const row = c => {
    const x = s.countries[c.code], ref = c.code === "DE", l = lv[c.code], pi = S.state.pay[c.code];
    const kurs = ref || !pi ? "" : faktorCell(pi);
    const level = ref ? "Basis" : !l ? "–" : `<span class="${l.level < 0 ? "lvl-neg" : "lvl-pos"}" title="gemessen an ${l.titles} gemeinsamen Titeln">${l.level > 0 ? "+" : ""}${l.level} %</span> <small class="hint">${l.cheaper} günstiger, ${l.sale} im Angebot</small>`;
    return `<tr data-code="${c.code}"><td>${esc(c.name)}<span class="code">${c.code}</span></td>
      <td><input type="checkbox" data-k="enabled" ${x.enabled ? "checked" : ""} ${ref ? "disabled" : ""}></td>
      <td>${ref ? "" : `<select data-k="tier">${sel(1, x.tier, "leicht")}${sel(2, x.tier, "mittel")}${sel(3, x.tier, "schwer")}</select>`}</td>
      <td>${ref ? "" : `<select data-k="pay">${sel("card", x.pay, "Karte")}${sel("giftcard", x.pay, "Guthabenkarte")}${sel("auto", x.pay, "das Günstigere")}</select>`}</td>
      <td>${ref ? "" : `<input class="sm" type="text" inputmode="decimal" data-k="tax_pct" value="${dc(x.tax_pct || 0)}">`}</td>
      <td>${ref ? "" : `<input type="text" inputmode="decimal" data-k="balance" value="${dc(x.balance || 0)}">`}</td>
      <td>${ref ? "" : `<input type="checkbox" data-k="rest_blocks" ${x.rest_blocks ? "checked" : ""}>`}</td>
      <td style="white-space:nowrap">${kurs}</td><td style="white-space:nowrap">${level}</td></tr>`;
  };
  // Guthabenkarten aufklappbar unter ihrem Land
  const cardRow = c => {
    const x = s.countries[c.code];
    if(c.code === "DE" || (x.pay === "card" && !x.cards)) return "";
    const old = x.cards_checked && (Date.now() - new Date(x.cards_checked)) > 30 * 86400000, k = "cards:" + c.code;
    const cs = cardTable(c.code, (S.state.pay[c.code] || {}).currency);
    return `<tr class="cardrow"><td colspan="10"><details data-k="${k}" ${S.folds[k] ? "open" : ""}><summary>Guthabenkarten: <span data-info="${c.code}">${cardInfo(x.cards)}</span>${cardSummary(c.code)}${x.cards_checked ? ` · <span class="${old ? "warnc" : ""}">Stand ${new Date(x.cards_checked).toLocaleDateString("de-DE")}${old ? ", bitte prüfen" : ""}</span>` : ""}</summary>
      ${c.code === "DG" ? `<small class="hint">Deutsches Konto: nur Karten unter Nennwert lohnen, ein Rest bleibt auf dem Konto und wird ab 5 € gewarnt; Deutschland zum Shop-Preis bleibt die Vergleichsbasis.</small>` : ""}
      ${cs}<textarea data-cards="${c.code}" spellcheck="false">${esc(x.cards)}</textarea></details></td></tr>`;
  };
  const table = list => `<div class="scroll"><table><thead><tr>${sth("laender", "name", "Land")}<th title="Land in Titeln, Kaufplan und Ländern zeigen. Preise holt das Tool für alle Länder, damit das Preisniveau stimmt.">Aktiv</th>${sth("laender", "tier", "Wechsel", "Wie mühsam der Wechsel des Nintendo-Kontos dorthin ist. leicht: Karte, kein Rest. mittel: Guthabenkarten, ein Rest verfällt beim nächsten Wechsel. schwer: Wechsel mit Guthaben nur über den Support. Je Stufe gilt unter Regeln eine eigene Mindestersparnis.")}${sth("laender", "pay", "Bezahlen", "Karte: Kreditkarte im eShop, Kosten sind Mittelkurs plus Fremdwährungsgebühr. Guthabenkarte: Preis der Karten, den das Tool über den Link liest; Werte ohne Link gelten als Guthaben zum Kurs (etwa Amazon Japan). Das Günstigere: nimmt Guthaben nur, wenn es weniger kostet als die Kreditkarte.")}<th title="Nur dort, wo der eShop Preise ohne Steuer zeigt (USA, Kanada). Wird auf den Shop-Preis aufgeschlagen.">Steuer %</th>${sth("laender", "balance", "Guthaben", "Was auf deinem Konto in diesem Land noch liegt, in Landeswährung. Wird vom Paket abgezogen.")}<th title="Angehakt: Ein Rest verhindert den Länderwechsel, bis er aufgebraucht oder über den Support gelöst ist. Ab Werk nirgends angehakt. Sonst bleibt ein Rest Guthaben, solange du im Land bleibst, und verfällt erst beim Wechsel.">Rest blockiert</th><th title="Was 1 € Guthaben dort kostet, gemessen am Mittelkurs. Karte: die Fremdwährungsgebühr. Guthabenkarte: Kartenpreis gegen Kurs. Ohne lesbaren Kartenpreis: die Schätzung unter Gebühren. Faktor 1,00 heißt zum Kurs, 1,08 heißt 8 % teurer, 0,98 heißt 2 % günstiger.">Dein Faktor</th>${sth("laender", "level", "Preisniveau", "Deine Wishlist-Titel dort gegenüber Deutschland, zum heutigen Preis mit allen Kosten. Negativ heißt günstiger.")}</tr></thead><tbody>${sortRows("laender", list, {name: c => c.name, tier: c => c.code === "DE" ? 0 : s.countries[c.code].tier,
    pay: c => c.code === "DE" ? "" : s.countries[c.code].pay, balance: c => c.code === "DE" ? null : +s.countries[c.code].balance || 0,
    level: c => c.code === "DE" ? 0 : lv[c.code] ? lv[c.code].level : null}).map(c => row(c) + cardRow(c)).join("")}</tbody></table></div>`;
  const act = S.state.countries.filter(on), off = S.state.countries.filter(c => !on(c));
  const t = s.tier_min_saving, de = s.deal_eur;
  const jump = [["set-laender", "Länder"], ["set-regeln", "Regeln"], ["set-gebuehren", "Gebühren"], ["sprachen", "Sprachen"], ["set-kaeufe", "Käufe"], ["set-quellen", "Quellen"], ["set-sicherung", "Sicherung und Protokoll"]];
  let h = `<div class="jump">${jump.map(([id, l]) => `<a href="#${id}">${l}</a>`).join("")}<span class="saved" id="saved"></span></div>
    <form class="set" id="setForm">
    <section class="setc"><h3 class="sec" id="set-laender">Länder</h3>
    <div class="fields" style="max-width:380px"><label class="f" title="Für dieses Land gilt keine Mindestersparnis, du bist ja schon dort.">Konto steht aktuell in<select name="current_country"><option value="">nicht angegeben</option>${
      [...S.state.countries].filter(c => c.shop === c.code).sort((x, y) => x.name.localeCompare(y.name, "de")).map(c => sel(c.code, s.current_country, esc(c.name))).join("")}</select></label></div>
    <details class="fold" data-k="setcountries" ${S.folds.setcountries ? "open" : ""}><summary class="hint">Länder, Zahlwege und Guthabenkarten <span class="mut">(${act.length} aktiv${off.length ? `, ${off.length} weitere` : ""})</span></summary>
    ${table(act)}
    <p class="hint">Das Preisniveau vergleicht deine Wishlist mit Deutschland. Eine Guthabenkarte je Zeile: <code>Wert = Preis in Euro | Link</code>, zum Beispiel <code>100 = 16,00 | https://…</code>; mehr unter „So trägst du Karten ein“.</p>
    <details class="hint" data-k="cardhelp" ${S.folds.cardhelp ? "open" : ""}><summary>So trägst du Karten ein</summary><p>Eine Karte je Zeile: <code>Wert = Preis in Euro | Link</code>, zum Beispiel <code>100 = 16,00 | https://…</code>. Preis und Link sind freiwillig, ein vorangestelltes <code>x</code> heißt nicht vorrätig. Nur Werte wie <code>500 1000 3000</code> ohne Link heißen: Guthaben zum Kurs, bezahlt mit deiner Karte wie im eShop (Amazon Japan), dann zählt auch der Rest. Hat eine Karte einen Link, liest das Tool den Preis einmal am Tag von der Shopseite, sofern die Seite ihn ohne Browser verrät. Sonst gilt dein Wert.</p></details>
    ${off.length ? `<details class="box fold" data-k="morecountries" ${S.folds.morecountries ? "open" : ""}><summary>weitere Länder (${off.length})</summary><p class="hint">Einschalten und aktualisieren; das Preisniveau zeigt, ob es sich lohnt.</p>${table(off)}</details>` : ""}
    </details>
    </section><section class="setc"><h3 class="sec" id="set-regeln">Regeln</h3>
    <p class="rule">„kaufen“ bis ${eur(de.buy)} oder 2 % über dem Bestpreis, „gut“ bis ${eur(de.good)} oder 15 %.${de.mini > 0 ? ` Kleinkram mit Bestpreis unter ${eur(de.mini)} ist nur bis 2 % „kaufen“ und macht im Kaufplan keine Guthabenkarte größer.` : ""} Ein Wechsel lohnt ab ${eur(t["1"])} Gewinn in einem leichten, ${eur(t["2"])} in einem mittleren und ${eur(t["3"])} in einem schweren Land. Regionen ohne deutsche Fassung ${({exclude: "fallen weg", warn: "bekommen einen Hinweis", off: "werden nicht geprüft"})[s.lang_rule] || "fallen weg"}.</p>
    <details class="fold" data-k="rulefields" ${S.folds.rulefields ? "open" : ""}><summary class="hint">Grenzen anpassen</summary>
    <div class="fields"><label class="f" title="Liegt der günstigste zählende Preis jetzt (in jedem Land, jeder Stufe, mit oder ohne Rabatt) höchstens so viel über dem Bestpreis, heißt das Urteil „kaufen“. Unabhängig davon gilt: bis 2 % über dem Bestpreis. Dieselbe Grenze färbt die Pakete.">Urteil „kaufen“ bis … € über Bestpreis<input name="deal_buy" type="text" inputmode="decimal" value="${dc(s.deal_eur.buy)}"></label><label class="f" title="Bis zu diesem Abstand heißt das Urteil „gutes Angebot“. Unabhängig davon gilt: bis 15 % über dem Bestpreis.">Urteil „gut“ bis … € über Bestpreis<input name="deal_good" type="text" inputmode="decimal" value="${dc(s.deal_eur.good)}"></label><label class="f" title="Titel mit Bestpreis unter diesem Betrag sind Kleinkram: „kaufen“ nur bis 2 % über dem Bestpreis, ohne die Euro-Grenze. Im Kaufplan machen sie keine Guthabenkarte größer, und kommen nie von selbst hinein: Lässt ein Schritt Rest, stehen sie unter „Passt in den Rest“ zur Auswahl. 0 schaltet das ab.">Kleinkram unter … €<input name="deal_mini" type="text" inputmode="decimal" value="${dc(s.deal_eur.mini ?? 2)}"></label><label class="f" title="Gibt es in Deutschland eine deutsche Fassung, fallen Regionen ohne sie weg (ausschließen) oder bekommen einen Hinweis (nur warnen). Europa gilt als dasselbe Produkt, Amerika wird bei Nintendo geprüft, Japan bestätigst du von Hand. Beim Ausschließen zählen ungeprüfte Angebote nicht für Bestpreis, Urteil und Kaufplan, beim Warnen zählen sie mit.">Regionen ohne deutsche Fassung<select name="lang_rule">${sel("exclude", s.lang_rule, "ausschließen")}${sel("warn", s.lang_rule, "nur warnen")}${sel("off", s.lang_rule, "nicht prüfen")}</select></label></div>
    <div class="fields" style="margin-top:12px"><label class="f" title="Kaufplan und Pakete: Ein Land lohnt sich erst, wenn es gegenüber dem, was dieselben Titel ohne diesen Wechsel kosten (günstigstes Land gleicher oder leichterer Stufe oder dein aktuelles Land), so viel spart. Stufe leicht: Kartenzahlung, kein Rest.">Wechsel lohnt ab Gewinn, Stufe leicht (€)<input name="tier1" type="text" inputmode="decimal" value="${dc(s.tier_min_saving["1"])}"></label><label class="f" title="Stufe mittel: Guthabenkarten, ein Rest verfällt beim Wechsel.">… Stufe mittel (€)<input name="tier2" type="text" inputmode="decimal" value="${dc(s.tier_min_saving["2"])}"></label><label class="f" title="Stufe schwer: Restguthaben blockiert den Wechsel und muss über den Support gelöst werden.">… Stufe schwer (€)<input name="tier3" type="text" inputmode="decimal" value="${dc(s.tier_min_saving["3"])}"></label></div>
    </details>
    </section><section class="setc"><h3 class="sec" id="set-gebuehren">Gebühren</h3>
    <div class="fields"><label class="f" title="Auslandseinsatzentgelt der Karte, mit der du im eShop zahlst. 0 bei Karten ohne Gebühr, zum Beispiel C24 oder Gebührenfrei/Eventim. Auch dann rechnet die Bank mit ihrem eigenen Kurs, der meist etwas über dem Mittelkurs liegt.">Fremdwährungsgebühr deiner Karte (%)<input name="card_fee_pct" type="text" inputmode="decimal" value="${dc(s.card_fee_pct)}"></label><label class="f" title="Gilt für Kartenpreise, die das Tool von einer Shopseite liest. Der Shop zeigt sie ohne seine Servicegebühr, die erst an der Kasse dazukommt. Bei Eneba waren es im Oktober 2026 genau 0,40 € plus 7,75 % je Bestellung. Von Hand eingetragene Kartenpreise bleiben, wie du sie einträgst.">Servicegebühr des Kartenshops (%)<input name="shop_fee_pct" type="text" inputmode="decimal" value="${dc(s.shop_fee_pct)}"></label><label class="f" title="Fester Teil der Servicegebühr je Bestellung. Kaufst du mehrere Karten in einer Bestellung, fällt er nur einmal an, und so rechnen Pakete und Kaufplan.">Servicegebühr, fester Teil (€)<input name="shop_fee_eur" type="text" inputmode="decimal" value="${dc(s.shop_fee_eur)}"></label><label class="f" title="Manche Kartenshops (Eneba) geben einen Teil des Kaufpreises als Guthaben zurück, aber nicht immer. Das Tool rechnet es nicht in die Preise, markiert aber in der Titelliste mit ✱, wo es ein Angebot zum Bestpreis machen könnte. 0 schaltet den Hinweis ab.">Mögliches Cashback des Kartenshops (%)<input name="cashback_pct" type="text" inputmode="decimal" value="${dc(s.cashback_pct ?? 0)}"></label></div>
    <details class="fold" data-k="feeadv" ${S.folds.feeadv ? "open" : ""}><summary class="hint">Erweitert</summary>
    <p class="hint">Nur ein Notbehelf: Zahlt ein Land mit Guthaben und ist kein Kartenpreis bekannt (kein Link mit lesbarem Preis in den letzten 14 Tagen, kein eigener Preis, keine Werte ohne Link), zeigt das Tool seine Preise geschätzt als Kurs plus diesen Wert, markiert mit ≈. Solche Preise entscheiden nichts: kein Urteil, kein Kaufplan, und „das Günstigere“ nimmt dann die Kreditkarte. Unter „Zu erledigen“ steht, wo Karten fehlen.</p>
    <div class="fields" style="max-width:300px"><label class="f">Schätzung ohne lesbaren Kartenpreis (%)<input name="gift_markup_pct" type="text" inputmode="decimal" value="${dc(s.gift_markup_pct)}"></label></div>
    <p class="hint" style="margin-top:10px">Euro-Guthaben (Deutschland mit Guthaben) bewertet das Tool nach festen Stufen für den Faktor: bis zu diesem Wert Top, gut, okay, darüber teuer. Andere Länder misst es an der Kreditkarte oder am besten Faktor der Karte in 90 Tagen.</p>
    <div class="fields" style="max-width:640px;grid-template-columns:repeat(3,1fr)"><label class="f">Top bis Faktor<input name="eur_top" type="text" inputmode="decimal" value="${dc(s.eur_card_steps.top)}"></label><label class="f">gut bis<input name="eur_good" type="text" inputmode="decimal" value="${dc(s.eur_card_steps.good)}"></label><label class="f">okay bis<input name="eur_ok" type="text" inputmode="decimal" value="${dc(s.eur_card_steps.ok)}"></label></div></details>
    </section></form><section class="setc">` + langSection() + `</section>
    <section class="setc" id="eshophist">` + eshopBox() + `</section>
    <section class="setc"><h3 class="sec" id="set-quellen">Quellen</h3>
    <div class="fields"><div class="pair"><label class="f">DekuDeals-Wishlist-Link<input form="setForm" name="wishlist_url" value="${esc(s.wishlist_url)}" placeholder="https://www.dekudeals.com/wishlist/…"></label><label class="f">DekuDeals-Sammlung <small>(leer: dieselbe Kennung wie die Wishlist; aktuell ${S.state.owned_count} Titel gelesen)</small><input form="setForm" name="collection_url" value="${esc(s.collection_url || "")}" placeholder="https://www.dekudeals.com/collection/…"></label></div><label class="f" title="Wie oft Wishlist und Preise neu geholt werden. Wechselkurse nur, wenn die Quelle neue hat (einmal am Tag); was sonst wie oft geholt wird, steht in docs/abrufe.md.">Abgleich alle … Stunden<input form="setForm" name="refresh_hours" type="number" step="1" min="1" value="${s.refresh_hours}"></label></div>
    <p class="hint" style="margin-top:8px">Wechselkurse vom ${esc(fxStamp())}. Die Quelle erneuert sie einmal am Tag, das Tool holt sie im ersten Abgleich danach ·
      <button class="link" type="button" data-act="diag">Verbindung testen</button><span id="diagCopy" ${S.diagText ? "" : "hidden"}> · <button class="link" type="button" data-act="copy" data-t="diag">Ergebnis kopieren</button></span></p>
    <pre class="log" id="diag" ${S.diagText ? "" : "hidden"}>${esc(S.diagText || "")}</pre>
    </section><section class="setc"><h3 class="sec" id="set-sicherung">Sicherung und Protokoll</h3>
    <p class="hint">Enthält Einstellungen, Guthabenkarten, Zielpreise, Körbe, Kaufprotokoll und die eigene Preisaufzeichnung. Beim Einlesen wird die Aufzeichnung ergänzt, nicht ersetzt. Preise, Sammlung und DekuDeals-Verläufe holt das Tool selbst neu.</p>
    <p style="margin-top:8px"><a class="btn" href="/api/abgleich" download="eshop-kompass-abgleich.json" title="Abgleichsdaten (IDs, Sprachen, Preise) und Protokoll zum Nachprüfen, ohne Einstellungen. Zum Einlesen nicht nötig.">Abgleichsdaten herunterladen</a>
      <a class="btn" style="margin-left:8px" href="/api/export" download="eshop-kompass-sicherung.json">Sicherung herunterladen</a>
      <label style="margin-left:8px"><button type="button" data-act="pickfile">Sicherung einlesen</button><input type="file" id="impFile" accept=".json,application/json" hidden></label></p>
    <p class="hint" style="margin-top:8px">Protokoll des letzten Abgleichs · <button class="link" type="button" data-act="copy" data-t="log">kopieren</button></p>
    <details class="fold" data-kc="logbox" ${S.folds.logbox ? "" : "open"}><summary class="hint">Protokoll anzeigen</summary>
    <pre class="log" id="log" style="margin-top:4px"></pre></details></section>`;
  return h;
}
function settingsBody(form){
  const body = {countries:{}, tier_min_saving:{}};
  const nv = el => el.value.trim().replace(",", ".");
  for(const k of ["wishlist_url","collection_url","current_country","card_fee_pct","gift_markup_pct","shop_fee_pct","shop_fee_eur","refresh_hours","lang_rule","cashback_pct"])
    body[k] = form.elements[k].inputMode === "decimal" ? nv(form.elements[k]) : form.elements[k].value;
  for(const t of ["1","2","3"]) body.tier_min_saving[t] = nv(form.elements["tier" + t]);
  body.deal_eur = {buy: nv(form.elements.deal_buy), good: nv(form.elements.deal_good), mini: nv(form.elements.deal_mini)};
  body.eur_card_steps = {top: nv(form.elements.eur_top), good: nv(form.elements.eur_good), ok: nv(form.elements.eur_ok)};
  form.querySelectorAll("tr[data-code]").forEach(tr => {
    const c = {};
    tr.querySelectorAll("[data-k]").forEach(el => { c[el.dataset.k] = el.type === "checkbox" ? el.checked : el.inputMode === "decimal" ? nv(el) : el.value; });
    body.countries[tr.dataset.code] = c;
  });
  form.querySelectorAll("textarea[data-cards]").forEach(el => {
    (body.countries[el.dataset.cards] = body.countries[el.dataset.cards] || {}).cards = el.value;
  });
  return body;
}
/* Sprachen von Hand bestätigen: einmal je Titel und Region */
/* Gelesene Sprachangaben auf Deutsch: Japan liefert japanische Wörter (ドイツ語), Amerika,
   Europa und titledb englische (german). Unbekanntes bleibt, wie es ist. */
const LANG_DE = {
  "日本語": "Japanisch", "英語": "Englisch", "ドイツ語": "Deutsch", "フランス語": "Französisch",
  "イタリア語": "Italienisch", "スペイン語": "Spanisch", "オランダ語": "Niederländisch",
  "ポルトガル語": "Portugiesisch", "ロシア語": "Russisch", "韓国語": "Koreanisch",
  "中国語": "Chinesisch", "簡体中国語": "Chinesisch (vereinfacht)", "繁体中国語": "Chinesisch (traditionell)",
  "ポーランド語": "Polnisch", "タイ語": "Thailändisch", "スウェーデン語": "Schwedisch",
  "デンマーク語": "Dänisch", "ノルウェー語": "Norwegisch", "フィンランド語": "Finnisch",
  "チェコ語": "Tschechisch", "ハンガリー語": "Ungarisch", "ギリシャ語": "Griechisch",
  "トルコ語": "Türkisch", "ウクライナ語": "Ukrainisch", "アラビア語": "Arabisch",
  english: "Englisch", french: "Französisch", german: "Deutsch", italian: "Italienisch",
  spanish: "Spanisch", dutch: "Niederländisch", portuguese: "Portugiesisch", russian: "Russisch",
  japanese: "Japanisch", korean: "Koreanisch", chinese: "Chinesisch", polish: "Polnisch",
  swedish: "Schwedisch", danish: "Dänisch", norwegian: "Norwegisch", finnish: "Finnisch",
  czech: "Tschechisch", hungarian: "Ungarisch", greek: "Griechisch", turkish: "Türkisch",
  ukrainian: "Ukrainisch", arabic: "Arabisch", thai: "Thailändisch"};
function langDe(text){
  if(!text) return "";
  // Zusätze wie ブラジルポルトガル語 (brasilianisches Portugiesisch): das Ende des Worts zählt
  const tail = w => Object.keys(LANG_DE).filter(k => k.endsWith("語") && w.endsWith(k)).sort((a, b) => b.length - a.length)[0];
  const out = text.split(/\s*[,、]\s*/).filter(Boolean)
    .map(w => LANG_DE[w] || LANG_DE[w.toLowerCase()] || (tail(w) ? LANG_DE[tail(w)] : w));
  return [...new Set(out)].join(", ");
}
/* Spalte „Deutsch?“: Ergebnis farbig mit Zeichen, Quelle und gelesene Sprachen im Tooltip,
   Korrektur als kleines Symbol. Die Quelle nennt die Gruppe, titledb zusätzlich gepunktet */
function langCell(t){
  const act = (v, sym, tip) => `<button class="ico" data-act="lang" data-s="${esc(t.slug)}" data-f="${t.family}" data-v="${v}" title="${tip}" aria-label="${tip}">${sym}</button>`;
  const what = t.state ? "Deutsch ✓" : "ohne Deutsch";
  if(t.manual){
    const nin = t.nintendo === null ? "Nintendo liefert keine Angabe" : `${t.src === "titledb" ? "titledb" : "Nintendo"} sagt: ${t.nintendo ? "mit" : "ohne"} Deutsch`;
    return `<span class="lg hand ${t.state ? "gn" : "bad"}" title="Von dir festgelegt. ${nin}">${what}</span>${act("", "↺", "Zurücksetzen: wieder die gelesene Angabe nehmen")}`;
  }
  if(t.state !== null){
    const src = t.src === "titledb" ? "Laut titledb (offene Titelliste, nicht von Nintendo)" : "Von Nintendo gelesen";
    // Farben wie in der Zahlenzeile (0.81): grün von Nintendo oder dir, violett nur laut titledb; ohne
    // Punktlinie, das Violett sagt es schon (0.81.2)
    return `<span class="lg ${t.state ? (t.src === "titledb" ? "warnc" : "gn") : "bad"}" title="${src}: ${esc(langDe(t.text) || "–")}">${what}</span>` +
      act(t.state ? 0 : 1, "✎", `Stimmt nicht? Klick setzt „${t.state ? "ohne Deutsch" : "Deutsch"}“, gilt dauerhaft und geht der gelesenen Angabe vor`);
  }
  return `<button data-act="lang" data-s="${esc(t.slug)}" data-f="${t.family}" data-v="1">Deutsch ja</button> <button data-act="lang" data-s="${esc(t.slug)}" data-f="${t.family}" data-v="0">nein</button>`;
}
function langSection(){
  const todo = S.state.lang_todo || [];
  // „ID fraglich“ steht oben, auch wenn schon eine Sprache gelesen ist: Sie kann zu einem anderen Titel gehören
  // Günstigere zuerst, was dort gerade nicht kaufbar ist, zuletzt
  // Was dort gerade nicht kaufbar ist, zählt nicht als offen (0.60): Der Store hat oft keine Seite dafür,
  // und die Antwort ändert nichts. Es steht eingeklappt darunter und kommt zurück, sobald es einen Preis gibt.
  const all = todo.filter(t => !t.manual && (t.state === null || t.doubt));
  const open = all.filter(t => t.here || t.doubt).sort((a, b) => b.matters - a.matters);
  const unbuyable = all.filter(t => !t.here && !t.doubt);
  const done = todo.filter(t => t.manual), auto = todo.filter(t => !t.manual && t.state !== null && !t.doubt);
  const now = open.filter(t => t.matters).length;
  let h = `<h3 class="sec" id="sprachen">Sprachen prüfen${open.length ? ` <span class="chip w">${open.length} offen</span>` : ""}</h3>
    <p class="hint">Gibt es einen Titel in Deutschland auf Deutsch, zählt eine Fassung aus einer anderen Region nur, wenn sie Deutsch enthält. Das Tool prüft jeden Titel einmal je Region und merkt sich das Ergebnis, unabhängig vom Preis: Wishlist-Titel und die fehlenden DLC deiner Spiele (ein Eintrag je Spiel gilt für alle seine DLC). Amerika liest es selbst von nintendo.com. Japan: Der Store zeigt dem Tool fast immer nur einen Warteraum. Die Angaben kommen dann aus titledb (eine offene Titelliste, nicht von Nintendo, deshalb so gekennzeichnet) oder vom Browser-Helfer unten, der die Seiten in deinem Browser liest. Ohne Angabe zählt die Fassung nicht. Deine Angabe gilt dauerhaft und geht der von Nintendo vor. Titel, die weder auf der Wishlist noch in der Sammlung stehen, räumt der Abgleich wieder ab.</p>`;
  if(!todo.length) return h + `<p class="hint">Keine Titel in Regionen außerhalb Europas.</p>`;
  h += jpHelper(todo);
  const row = t => `<tr><td>${esc(t.title)}${t.dlc ? ` <small>${t.dlc} fehlende DLC</small>` : ""}${t.doubt ? ` <span class="chip w" title="Die Programm-ID dieser ID passt laut titledb nicht zur europäischen Fassung, DekuDeals nennt aber diese ID. Bitte im Store nachsehen, ob die Seite zum Titel gehört.">ID fraglich</span>` : ""}</td><td>${esc(t.family_name)} <small>${t.codes.join(", ")}</small></td>
    <td><small>${t.here ? `${t.dlc ? "fehlende DLC dort ab" : "dort"} ${eur(t.here.eur)} (${t.here.code})` : "dort gerade nicht kaufbar"}${t.champ ? ` · sonst ${eur(t.champ.eur)} (${t.champ.code})` : ""}</small>${t.matters && t.state === null && !t.manual ? ` <span class="chip w" title="Dort wäre es gerade günstiger als in den zählenden Ländern">günstiger</span>` : ""}</td>
    <td>${t.url ? `<a href="${esc(t.url)}" target="_blank" rel="noopener">im Store nachsehen</a>` : ""}</td>
    <td class="lc">${langCell(t)}</td></tr>`;
  const group = (arr, label) => arr.length ? `<tr><th colspan="5" class="grp">${label} <span class="mut">${arr.length}</span></th></tr>${arr.map(row).join("")}` : "";
  const L = "sprachen", srt = arr => sortRows(L, arr, {title: t => t.title, region: t => t.family_name, price: t => t.here ? t.here.eur : null});
  const head = `<thead><tr>${sth(L, "title", "Titel")}${sth(L, "region", "Region")}${sth(L, "price", "Preis", "Günstigster Preis jetzt oder je in dieser Region, daneben der Bestpreis der zählenden Länder")}<th></th><th style="text-align:left">Deutsch?</th></tr></thead>`;
  h += open.length ? `${now ? `<p class="hint">Bei ${now} davon wäre die Fassung gerade günstiger, sie stehen oben.</p>` : ""}<div class="scroll"><table>${head}<tbody>${srt(open).map(row).join("")}</tbody></table></div>`
    : `<p class="hint">Alles geprüft ✓</p>`;
  if(unbuyable.length)
    h += `<details data-k="langna" ${S.folds.langna ? "open" : ""}><summary class="hint">Dort gerade nicht kaufbar, Sprache offen: <b>${unbuyable.length}</b></summary><p class="hint">Zählt nicht als offen, oft hat der Store gar keine Seite dafür. Gibt es dort wieder einen Preis, steht der Titel oben.</p><div class="scroll"><table>${head}<tbody>${srt(unbuyable).map(row).join("")}</tbody></table></div></details>`;
  if(done.length || auto.length)
  {
    const tdb = auto.filter(t => t.src === "titledb"), nin = auto.filter(t => t.src !== "titledb");
    h += `<details data-k="langdone" ${S.folds.langdone ? "open" : ""}><summary class="hint" title="Zusammen ${auto.length + done.length}">Geprüft: <b class="gn">${nin.length}</b> von Nintendo gelesen${tdb.length ? `, <b class="warnc">${tdb.length}</b> laut titledb` : ""}, <b class="gn">${done.length}</b> von dir bestätigt</summary><div class="scroll"><table>${head}<tbody>${group(srt(done), "Von dir bestätigt")}${group(srt(nin), "Von Nintendo gelesen")}${group(srt(tdb), "Laut titledb (nicht von Nintendo)")}</tbody></table></div></details>`;
  }
  return h;
}
/* Browser-Helfer „Käufe lesen“: liest in deinem Browser, angemeldet bei Nintendo, den
   Kaufverlauf so, wie ihn die Seite ec.nintendo.com/my/transactions selbst lädt, und gibt ihn an
   eShop-Kompass weiter (Knopf öffnet das Tool, die Daten stehen nur im Adressteil hinter #). */
function eshopHelper(tool){ return `(async()=>{
if(location.hostname!=="ec.nintendo.com"){alert("Bitte zuerst angemeldet die Kaufhistorie öffnen: ec.nintendo.com/my/transactions/1, dann das Lesezeichen anklicken.");return}
const box=document.createElement("div");box.style.cssText="position:fixed;z-index:2147483647;top:12px;right:12px;width:min(440px,90vw);background:#fff;color:#111;border:2px solid #333;border-radius:8px;padding:12px;font:14px sans-serif";box.textContent="eShop-Kompass: lese Kaufverlauf …";document.body.appendChild(box);
const look=(b,main)=>{b.style.cssText="margin:0 8px 6px 0;padding:6px 12px;border-radius:6px;font:600 13px sans-serif;cursor:pointer;"+(main?"background:#2f3b35;color:#fff;border:1px solid #2f3b35":"background:#f4f2ec;color:#1d2320;border:1px solid #9a9486");return b};
const fail=t=>{box.textContent="eShop-Kompass: "+t;const b=look(document.createElement("button"));b.textContent="Schließen";b.style.marginLeft="8px";b.onclick=()=>box.remove();box.append(b)};
try{
const s=await(await fetch("/api/auth/session",{credentials:"include"})).json();
if(!s.idToken)return fail("Nicht angemeldet. Bitte anmelden und die Kaufhistorie neu laden.");
const pe=performance.getEntriesByType("resource").map(e=>e.name).filter(u=>u.includes("operationName=TransactionsClientRootClient")).pop();
let ep="https://wb.lp1.savanna.srv.nintendo.net/graphql",v={country:s.country,language:"en",shopId:3},ext={persistedQuery:{sha256Hash:"aa2c23b02481e2c5caba64f6a52e81b2ddcbc311c299ee111dd28c41f245e1e6",version:1}};
if(pe){const u=new URL(pe);ep=u.origin+u.pathname;v=JSON.parse(u.searchParams.get("variables"));ext=JSON.parse(u.searchParams.get("extensions"))}
const H={"accept":"application/json","content-type":"application/json","x-nintendo-savanna-client-id":"042e4bd1f0eec144167dbc0c63f1d17876e7b9ec322713b613614214e3675df9"};
const get=async(off,lim)=>{const r=await fetch(ep+"?operationName=TransactionsClientRootClient&variables="+encodeURIComponent(JSON.stringify(Object.assign({},v,{idToken:s.idToken,limit:lim,offset:off})))+"&extensions="+encodeURIComponent(JSON.stringify(ext)),{headers:H});if(r.status===403||r.status===429)throw"gesperrt ("+r.status+")";const j=await r.json();if(!r.ok||j.errors)throw"Nintendo meldet "+r.status;return j.data.account.transactionHistories};
const wait=()=>new Promise(r=>setTimeout(r,1200));
let lim=100,page;try{page=await get(0,lim)}catch(e){if(String(e).startsWith("gesperrt"))throw e;lim=10;await wait();page=await get(0,lim)}
const seit=Number((location.hash.match(/ek-seit=(\\d+)/)||[])[1]||0),alt=t=>seit&&Number(t.transactionId)<=seit;
const all=[...page.transactionHistories],total=page.offsetInfo.total;
let err="",last=page.transactionHistories;while(all.length<total&&!(last.length&&last.every(alt))){box.textContent="eShop-Kompass: lese "+all.length+" von "+total+" …";await wait();let p;try{p=await get(all.length,lim)}catch(e){err=String(e);break}if(!p.transactionHistories.length)break;last=p.transactionHistories;all.push(...last)}
const complete=!err,newest=Math.max(0,...all.map(t=>Number(t.transactionId)||0));
const out=[];for(const t of all){const d=String(t.datetime||"").slice(0,10);
if(t.grantedItems)t.grantedItems.forEach((g,i)=>out.push({k:t.transactionId+"-"+i,title:g.title,date:d,type:"EXTERNAL",item:g.itemType,plat:g.labelPlatform}));
else if(t.title)out.push({k:String(t.transactionId),title:t.title,date:d,type:t.transactionType,item:t.itemType,plat:t.labelPlatform,amount:t.amount&&t.amount.formattedValue})}
const txt=JSON.stringify({hv:${HELPERS.eshop.v},region:v.country||s.country,complete,newest,entries:out});
box.textContent="";const p=document.createElement("p");p.textContent=(complete?"Fertig: ":"Unvollständig ("+err+"), das Tool merkt sich den alten Stand: ")+all.filter(t=>!alt(t)).length+" Vorgänge"+(seit?" seit dem letzten Lesen, dazu eine Seite bekannter zur Sicherheit":"")+" ("+(v.country||s.country)+").";
const go=look(document.createElement("button"),true);go.textContent="Im eShop-Kompass übernehmen";go.onclick=()=>window.open(${JSON.stringify(tool)}+"/#kaeufe="+encodeURIComponent(txt),"_blank");
const ta=document.createElement("textarea");ta.value=txt;ta.readOnly=true;ta.style.cssText="width:100%;height:80px;margin:8px 0";
const c=look(document.createElement("button"));c.textContent="Kopieren";c.onclick=async()=>{ta.select();try{await navigator.clipboard.writeText(txt)}catch(e){document.execCommand("copy")}c.textContent="Kopiert ✓"};
const b=look(document.createElement("button"));b.textContent="Schließen";b.onclick=()=>box.remove();
box.append(p,go,ta,c,b);
}catch(e){fail("Abgebrochen: "+e+". Bitte die Seite neu laden und noch einmal versuchen.")}
})();`; }
/* Lesezeichen: Ein Knopf, der selbst ein Lesezeichen anlegt, ist Webseiten nicht erlaubt. Darum
   ein Link zum Ziehen und „Code kopieren“ für ein von Hand angelegtes Lesezeichen (auch am Handy).
   v: Stand des Codes, need: ab welchem Stand ein altes Lesezeichen noch genügt. Ältere melden
   sich beim Übernehmen, damit niemand unbemerkt mit einem alten Lesezeichen weiterarbeitet. */
const HELPERS = {eshop: {v: 3, need: 1, label: "Käufe lesen"}, jp: {v: 7, need: 7, label: "JP-Sprachen lesen"}};
const BM_CODE = {};
function helpersOld(){ try{ return JSON.parse(localStorage.getItem("ek.helpers") || "{}") || {}; }catch(e){ return {}; } }
function helperSeen(k, hv){
  const old = helpersOld(), was = !!old[k];
  if((Number(hv) || 1) < HELPERS[k].need) old[k] = 1; else delete old[k];
  try{ localStorage.setItem("ek.helpers", JSON.stringify(old)); }catch(e){}
  return !!old[k] && !was;
}
function bmLink(k, code){
  const h = HELPERS[k];
  BM_CODE[k] = "javascript:" + encodeURIComponent(code);
  return `<span class="bm-w"><a class="bm" href="${BM_CODE[k]}" title="In die Lesezeichenleiste ziehen" onclick="event.preventDefault();toast('Bitte in die Lesezeichenleiste ziehen, nicht anklicken')">⠿ <b>${esc(h.label)}</b></a>
    <button data-act="bmcopy" data-k="${k}" title="Für ein von Hand angelegtes Lesezeichen">Code kopieren</button></span>
    ${helpersOld()[k] ? `<br><span class="warnc">Dein Lesezeichen „${esc(h.label)}“ ist veraltet. Bitte das alte löschen und neu anlegen.</span> <button class="sm" data-act="bmdone" data-k="${k}" title="Hast du das Lesezeichen schon neu angelegt? Dann blendet das den Hinweis aus. Sonst verschwindet er beim nächsten Übernehmen mit dem neuen Lesezeichen">Neu angelegt ✓</button>` : ""}
    <details class="fold" data-k="bmhow_${k}" ${S.folds["bmhow_" + k] ? "open" : ""}><summary class="hint">So legst du es an</summary><ul class="hint">
      <li>Am Computer: Lesezeichenleiste einblenden (Strg+Umschalt+B, am Mac ⌘+Umschalt+B) und den Knopf hineinziehen.</li>
      <li>Ohne Ziehen, auch am Handy: „Code kopieren“, ein beliebiges Lesezeichen anlegen, bearbeiten, „${esc(h.label)}“ als Namen und den Code als Adresse einfügen. Am Handy startet es aus den Lesezeichen oder über seinen Namen in der Adresszeile.</li>
      <li>Ein älteres Lesezeichen mit demselben Namen vorher löschen.</li>
    </ul></details>`;
}
async function jpImport(text){
  let send = text, fresh = false;
  try{ const o = JSON.parse(text); if(o && typeof o === "object" && !Array.isArray(o)){ fresh = helperSeen("jp", o.hv); delete o.hv; send = JSON.stringify(o); } }catch(e){}
  const r = await api("/api/jp_langs", {text: send});
  S.state.lang_todo = r.lang_todo; await refresh(); render();
  toast(`${r.read} Titel übernommen` + (r.empty ? `, ${r.empty} ohne Sprachangabe` : "") + (r.unknown ? `, ${r.unknown} unbekannte IDs` : "") + (r.gone ? `, bei ${r.gone} ohne Seite sucht der nächste Abgleich die ID neu` : ""));
  if(fresh) setTimeout(() => toast("Dein Lesezeichen „JP-Sprachen lesen“ ist veraltet. Bitte neu anlegen, siehe Browser-Helfer für Japan"), 4000);
}
/* Käufe aus dem eShop (Einstellungen, ab 0.71): Die DekuDeals-Sammlung bleibt die eine Wahrheit. Der Kaufverlauf
   hilft nur, wo er den Plan ändert (Gekauftes auf der Wishlist oder unter den fehlenden DLC) oder wo DekuDeals
   einen Kauf nicht kennt. Alles andere ordnet das Tool selbst ein; gefragt wird nur, was den Plan ändert. */
const ESHOP_GROUP = {ask: "offen", plan: "bei DekuDeals nachtragen", coll: "in der Sammlung",
  unknown: "nicht in der Sammlung", ticket: "Mitgliedschaft oder Gutschein", void: "erstattet"};
// Farbe je Gruppe, in der Zahlenzeile und der Spalte Einordnung gleich (0.78): grün erledigt,
// violett braucht dich, rot unbekannt, grau zählt nicht
const ESHOP_CLS = {ask: "warnc", plan: "warnc", coll: "gn", unknown: "bad", ticket: "mut", void: "mut"};
function eshopKnown(){
  // Suchtreffer für „anderer …“: Name, bei DLC mit Spiel davor; die Zuordnung zum Slug merkt sich S.eshopKnown
  const list = S.state.eshop_known || [], map = {};
  for(const x of list) map[x.game ? `${x.game}: ${x.title}` : x.title] = x.slug;
  S.eshopKnown = map;
  return "";
}
function eshopBox(){
  const rows = S.state.eshop || [], by = g => rows.filter(r => r.group === g);
  const ask = by("ask"), plan = by("plan");
  const how = {id: "über die Nintendo-ID", title: "Titel passt genau", eng: "englischer Name passt genau", pick: "von dir zugeordnet"};
  // Neuester bekannter Vorgang: Der Link zur Kaufhistorie gibt ihn mit, das Lesezeichen hört dort auf
  const seit = S.state.eshop_seit || 0, at = S.state.eshop_at || 0;
  const KIND = {APPLICATION: "Spiel", DLC: "DLC", BUNDLE: "Paket", TICKET: "Mitgliedschaft", CATALOG_TICKET: "Spielegutschein"};
  const PLAT = {HAC: "Switch", BEE: "Switch 2"};
  const what = r => [r.date ? dmy(r.date) : "", KIND[r.item] || "", PLAT[r.plat] || "", r.amount || ""].filter(Boolean).map(esc).join(" · ");
  const named = (slug, title, game) => `<a href="${esc(deku(slug))}" target="_blank" rel="noopener" title="Bei DekuDeals ansehen">${game && !String(title || "").toLowerCase().startsWith(game.toLowerCase()) ? `<span class="gm">${esc(game)}:</span> <b>${esc(title || slug)}</b>` : esc(title || slug)}</a>`;
  const kauf = r => `${esc(r.title)}${r.eng && r.eng !== r.title ? ` <small class="mut">(${esc(r.eng)})</small>` : ""}<br><small class="mut">${what(r)}</small>`;
  // „anderer …“ (ab 0.76): öffnet eine eigene Zeile unter dem Kauf, damit sich nichts seitlich verschiebt;
  // Treffer ohne Akzente wie in jedem Suchfeld, ein Klick ordnet zu
  const own = (r, label = "anderer …") => `<button class="link" data-act="eqopen" data-k="${esc(r.key)}" title="Einen anderen Titel suchen oder einen DekuDeals-Link einfügen">${S.eqOpen === r.key ? "schließen" : label}</button>`;
  const ownRow = (r, cols) => S.eqOpen !== r.key ? "" : `<tr class="eqrow"><td class="l" colspan="${cols}"><div class="eqin"><input type="text" class="eqq" data-k="${esc(r.key)}" placeholder="Name suchen oder DekuDeals-Link" aria-label="Gekauften Titel suchen oder DekuDeals-Link einfügen"> <button class="sm" data-act="eshopown" data-k="${esc(r.key)}">zuordnen</button></div><div class="eqhits"></div></td></tr>`;
  const undo = r => r.how === "pick"
    ? `<button class="link" data-act="eshoppick" data-k="${esc(r.key)}" data-v="" title="Deine Zuordnung zurücknehmen, wirkt sofort">zurücknehmen</button>`
    : `<button class="link" data-act="eshoppick" data-k="${esc(r.key)}" data-v="-" title="Falsch zugeordnet: zählt dann nicht als Besitz">stimmt nicht</button>`;
  const head = rows.length ? `${rows.length} Käufe${at ? `, gelesen am ${esc(dmy(new Date(at * 1000).toISOString()))}` : ""}` : "noch keine Käufe gelesen";
  let h = `<h3 class="sec" id="set-kaeufe">Käufe aus dem eShop <span class="mut">${head}</span></h3>
    <p class="hint">Deine Sammlung pflegst du bei DekuDeals. Der Kaufverlauf von Nintendo sorgt nur dafür, dass der Plan nichts vorschlägt, was du schon gekauft hast, und zeigt Käufe, die bei DekuDeals noch fehlen. Was schon in der Sammlung steht, ordnet das Tool selbst ein; fragen muss es nur, wenn die Antwort den Plan ändert.</p>
    <details class="box" data-k="eshophow" ${S.folds.eshophow || !rows.length ? "open" : ""}><summary><b>So liest du deine Käufe aus:</b> <span class="mut">Lesezeichen für deine Kaufhistorie bei Nintendo</span></summary>
    <ol class="hint">
      <li>Leg einmal dieses Lesezeichen an: ${bmLink("eshop", eshopHelper(location.origin))}</li>
      <li>Öffne angemeldet <a href="https://ec.nintendo.com/my/transactions/1${seit ? `#ek-seit=${seit}` : ""}" target="_blank" rel="noopener">deine Kaufhistorie bei Nintendo</a> über diesen Link, warte, bis die Liste da ist, und klick das Lesezeichen an.${seit ? ` Es liest nur, was seit dem letzten vollständigen Lesen dazugekommen ist; <a href="https://ec.nintendo.com/my/transactions/1" target="_blank" rel="noopener" title="Liest den ganzen Kaufverlauf noch einmal. Deine Zuordnungen bleiben, ältere Einträge bekommen fehlende Angaben.">alles neu lesen</a>.` : ""}</li>
      <li>Klick dort auf „Im eShop-Kompass übernehmen“.</li>
    </ol>
    <details class="fold" data-k="eshopfb" ${S.folds.eshopfb ? "open" : ""}><summary class="hint">Geht das nicht? Text von Hand einfügen</summary>
      <p class="hint">Kopiere im Fenster des Lesezeichens den Text und füge ihn hier ein: <textarea id="eshopimport" rows="2" style="width:100%"></textarea> <button data-act="eshopimport">Übernehmen</button></p>
    </details></details>`;
  if(!rows.length) return h;
  h += eshopKnown();
  // Offen: eine Zeile je Kauf, die Kandidaten als Knöpfe; ein Klick heißt „ja, dieser“
  // Zahlen wie bei „Geprüft“ in den Sprachen: violett, was dich braucht, grün, was erledigt ist (0.76)
  const N = (n, cls) => `<b class="${cls || "ink"}">${n}</b>`;
  // Nicht in der Sammlung rot: Diese Käufe kennt das Tool nicht, der Plan könnte sie vorschlagen (0.77)
  const counts = ["unknown", "plan", "ask", "coll", "ticket", "void"]
    .map(g => [g, ESHOP_CLS[g], by(g).length]).filter(x => x[2]).map(([g, cls, n]) => `${N(n, cls)} ${ESHOP_GROUP[g]}`).join(", ");
  h += `<p class="hint eqsum"><b class="ink">${rows.length} Käufe:</b> ${counts}</p>`;
  // Nicht in der Sammlung (0.81.3): eigene Klappzeile ganz oben, damit alles Offene über „Alle Käufe“ steht
  const unk = by("unknown");
  if(unk.length) h += `<details class="fold eqf" data-kc="eshopunk" ${S.folds.eshopunk ? "" : "open"}><summary>Nicht in der Sammlung: ${N(unk.length, "bad")}</summary><p class="hint">Diese Käufe kann das Tool keinem Titel zuordnen. Sie zählen nicht als Besitz, der Plan könnte sie also vorschlagen. „zuweisen“ ordnet einen Kauf von Hand zu.</p>
    <div class="scroll"><table class="mini-t eqt"><tbody>${unk.map(r => `<tr><td class="l">${kauf(r)}</td><td class="l">${r.how === "none" ? `<button class="link" data-act="eshoppick" data-k="${esc(r.key)}" data-v="" title="Wieder offen">zurücknehmen</button> · ${own(r, "zuweisen")}` : own(r, "zuweisen")}</td></tr>${ownRow(r, 2)}`).join("")}</tbody></table></div></details>`;
  if(ask.length) h += `<details class="fold eqf" data-kc="eshopask" ${S.folds.eshopask ? "" : "open"}><summary>Welcher Titel ist das? ${N(ask.length, "warnc")}</summary><p class="hint">Diese Käufe ähneln einem Titel deiner Wishlist oder einem fehlenden DLC. Ein Klick auf einen Namen ordnet den Kauf zu, er fällt dann aus dem Plan. „keiner“ lässt ihn im Plan.</p>
    <div class="scroll"><table class="mini-t eqt"><tbody>${ask.map(r => `<tr><td class="l">${kauf(r)}</td><td class="l eqa">${r.suggest.map(x =>
      `<button class="sm cand" data-act="eshoppick" data-k="${esc(r.key)}" data-v="${esc(x.slug)}" title="Ja, das ist ${esc(x.title)}: zählt als Besitz">${x.game && !String(x.title || "").toLowerCase().startsWith(x.game.toLowerCase()) ? `<span class="gm">${esc(x.game)}:</span> <b>${esc(x.title)}</b>` : esc(x.title)}</button>`).join("")}<button class="sm" data-act="eshoppick" data-k="${esc(r.key)}" data-v="-" title="Keiner davon: zählt nicht als Besitz">keiner</button>${own(r)}</td></tr>${ownRow(r, 2)}`).join("")}</tbody></table></div></details>`;
  // Gekauft, aber bei DekuDeals noch nicht in der Sammlung: zählt als Besitz, nachtragen
  if(plan.length) h += `<details class="fold eqf" data-kc="eshopplan" ${S.folds.eshopplan ? "" : "open"}><summary>Bei DekuDeals nachtragen: ${N(plan.length, "warnc")}</summary><p class="hint">Gekauft, aber nicht in deiner DekuDeals-Sammlung. Sie zählen schon als Besitz und fallen aus dem Plan. Trägst du sie bei DekuDeals ein, verschwinden sie hier nach dem nächsten Abgleich.</p>
    <div class="scroll"><table class="mini-t eqt"><thead><tr>${sth("eshop", "kauf", "Kauf", "", "l")}${sth("eshop", "name", "Zählt als", "", "l")}${sth("eshop", "how", "Woher", "", "l")}<th></th></tr></thead><tbody>${sortRows("eshop", plan, {
      kauf: r => r.title || "", name: r => (r.game ? r.game + " " : "") + (r.name || ""), how: r => how[r.how] || "", date: r => r.date || ""}).map(r =>
      `<tr><td class="l">${kauf(r)}</td><td class="l">${named(r.slug, r.name, r.game)}</td><td class="l"><small class="mut">${how[r.how] || ""}</small></td><td>${undo(r)}</td></tr>`).join("")}</tbody></table></div></details>`;
  // Alle Käufe zum Nachsehen, nach Gruppe; „zuweisen“ ordnet jeden von Hand zu, „neu zuweisen“, wenn das
  // Tool ihn schon einem Titel der Sammlung zugeordnet hat (0.77, vorher „anderer …“)
  // Einordnung nach Dringlichkeit, nicht nach Alphabet (0.81.2): Offenes oben, Erledigtes unten
  const ESHOP_RANK = ["unknown", "plan", "ask", "coll", "ticket", "void"];
  const allRows = sortRows("eshopall", rows, {kauf: r => r.title || "", group: r => ESHOP_RANK.indexOf(r.group), name: r => r.name || r.coll_name || "", date: r => r.date || ""});
  h += `<details class="fold eqf" data-k="eshopall" ${S.folds.eshopall ? "open" : ""}><summary>Alle Käufe: ${N(rows.length)} <span class="mut">(zum Nachsehen und Zuweisen)</span></summary>
    <div class="scroll"><table class="mini-t eqt"><thead><tr>${sth("eshopall", "kauf", "Kauf", "", "l")}${sth("eshopall", "group", "Einordnung", "", "l")}${sth("eshopall", "name", "Titel", "", "l")}${sth("eshopall", "date", "Datum", "", "num")}<th></th></tr></thead><tbody>${allRows.map(r =>
      `<tr class="${r.group === "coll" || r.group === "ticket" || r.group === "void" ? "mutr" : ""}"><td class="l">${esc(r.title)}${r.eng && r.eng !== r.title ? ` <small class="mut">(${esc(r.eng)})</small>` : ""}</td><td class="l"><small class="${ESHOP_CLS[r.group] || ""}">${ESHOP_GROUP[r.group] || ""}</small></td><td class="l">${r.slug ? named(r.slug, r.name, r.game) : r.coll ? named(r.coll, r.coll_name) : ""}</td><td class="num nw">${r.date ? esc(dmy(r.date)) : ""}</td><td class="l">${r.slug ? undo(r) : r.how === "none" ? `<button class="link" data-act="eshoppick" data-k="${esc(r.key)}" data-v="" title="Wieder offen">zurücknehmen</button> · ${own(r, "zuweisen")}` : r.group === "void" || r.group === "ticket" ? "" : own(r, r.coll ? "neu zuweisen" : "zuweisen")}</td></tr>${ownRow(r, 5)}`).join("")}</tbody></table></div></details>`;
  return h;
}
/* Browser-Helfer für Japan: Ein Lesezeichen liest die Shopseiten in deinem Browser, der durch
   den Warteraum von store-jp kommt, und gibt die Sprachen als Text zum Einfügen zurück. */
function jpHelperCode(tool){ return `(async()=>{
if(location.hostname!=="store-jp.nintendo.com"){alert("Bitte zuerst eine Seite von store-jp.nintendo.com öffnen und dann das Lesezeichen anklicken.");return}
const fromLink=decodeURIComponent(((location.search+location.hash).match(/ek-ids=([^&#]*)/)||[])[1]||"");
const box=document.createElement("div");box.style.cssText="position:fixed;z-index:2147483647;top:12px;right:12px;width:min(440px,90vw);background:#fff;color:#111;border:2px solid #333;border-radius:8px;padding:12px;font:14px sans-serif";document.body.appendChild(box);
const look=(b,main)=>{b.style.cssText="margin:0 8px 6px 0;padding:6px 12px;border-radius:6px;font:600 13px sans-serif;cursor:pointer;"+(main?"background:#2f3b35;color:#fff;border:1px solid #2f3b35":"background:#f4f2ec;color:#1d2320;border:1px solid #9a9486");return b};
const btn=(t,f,main)=>{const b=document.createElement("button");b.textContent=t;b.onclick=f;return look(b,main)};
let src=fromLink;
const TOOL=${JSON.stringify(tool)};
if(!/\\d{14}/.test(src))src=await new Promise(res=>{const p=document.createElement("p");p.textContent="eShop-Kompass: hole die Japan-IDs aus einem kleinen Fenster des Tools. Klappt das nicht, hier einfügen (Strg+V), dann „Lesen“.";p.style.margin="0 0 6px";
const t=document.createElement("textarea");t.style.cssText="width:100%;height:70px;margin:0 0 6px";
const ask=()=>window.open(TOOL+"/#ek-jpids","ekjp","popup,width=520,height=360");
window.addEventListener("message",ev=>{if(ev.origin===TOOL&&ev.data&&typeof ev.data.ekJpIds==="string"){t.value=ev.data.ekJpIds;if(/\\d{14}/.test(t.value))res(t.value)}});
box.append(p,t,btn("Lesen",()=>res(t.value),true),btn("Vom Tool holen",ask),btn("Abbrechen",()=>res("")));ask()});
const ids=[...new Set(src.match(/\\d{14}/g)||[])];
if(!ids.length){box.remove();return}
box.textContent="";
const wait=()=>new Promise(r=>setTimeout(r,2500));
const read=async path=>{try{const r=await fetch(path,{credentials:"include"});if(r.status===404)return{v:"",gone:true};if(!r.ok)return{v:null};
const d=new DOMParser().parseFromString(await r.text(),"text/html");
const th=[...d.querySelectorAll("th")].find(e=>e.textContent.trim()==="対応言語");
if(th){const td=th.parentElement.querySelector("td");return{v:((td&&td.querySelector("p"))||td||th).textContent.trim()}}
return{v:d.querySelector("[data-testid^=ProductDetail]")?"":null,d}}catch(e){return{v:null}}};
const out={};let bad=0,stop=false,viaGame=0;
for(let i=0;i<ids.length;i++){
box.textContent="eShop-Kompass: lese "+(i+1)+" von "+ids.length+" …";
let{v,d,gone}=await read("/item/software/D"+ids[i]);if(gone)out[ids[i]]="keine Seite";
if(v===""&&d){const a=[...d.querySelectorAll("a[href*='/item/software/D7001']")].map(e=>e.getAttribute("href").match(/D(7001\\d{10})/)).find(m=>m&&m[1]!==ids[i]);
if(a){await wait();const g=await read("/item/software/D"+a[1]);if(g.v){v=g.v;viaGame++}}}
if(v===null){if(++bad>=3){stop=true;break}}else{bad=0;if(v)out[ids[i]]=v}
await wait()}
const txt=JSON.stringify(Object.assign({hv:${HELPERS.jp.v}},out)),n=Object.values(out).filter(x=>x!=="keine Seite").length;
box.textContent="";const p=document.createElement("p");p.textContent=(stop?"Abgebrochen, der Store lässt gerade nicht durch. ":"Fertig. ")+n+" von "+ids.length+" Titeln mit Sprachen"+(viaGame?" ("+viaGame+" DLC über die Seite des Spiels)":"")+".";
const go=look(document.createElement("button"),true);go.textContent="Im eShop-Kompass übernehmen";go.onclick=()=>window.open(${JSON.stringify(tool)}+"/#jpsprachen="+encodeURIComponent(txt),"_blank");
const ta=document.createElement("textarea");ta.value=txt;ta.readOnly=true;ta.style.cssText="width:100%;height:110px;margin:8px 0";
const c=look(document.createElement("button"));c.textContent="Kopieren";
c.onclick=async()=>{ta.select();try{await navigator.clipboard.writeText(txt)}catch(e){document.execCommand("copy")}c.textContent="Kopiert ✓"};
const b=look(document.createElement("button"));b.textContent="Schließen";b.onclick=()=>box.remove();
box.append(p,go,ta,c,b);
})();`; }
// Japan-Titel, die der Browser-Helfer lesen soll: ohne Angabe von Nintendo und nicht von dir festgelegt.
// Angaben aus titledb immer (zur Bestätigung), offene Titel nur mit Preis in Japan oder Zweifel an der ID.
const jpOpenRows = (todo = S.state.lang_todo || []) =>
  todo.filter(t => t.family === "JP" && t.nsuid && !t.manual && (t.src === "titledb" || (t.state === null && (t.here || t.doubt))));
const jpOpenIds = (todo = S.state.lang_todo || []) => [...new Set(jpOpenRows(todo).map(t => t.nsuid))];
function jpHelper(todo){
  const jp = todo.filter(t => t.family === "JP");
  if(!jp.length) return "";
  const ids = jpOpenIds(todo), rows = jpOpenRows(todo);
  // Eine Seite je ID; DLC ohne eigene Seite lesen die ihres Spiels mit (0.81: alle Titel je Seite nennen)
  const pages = new Map();
  rows.forEach(t => pages.set(t.nsuid, (pages.get(t.nsuid) || []).concat(t)));
  const names = [...pages.entries()].map(([id, ts]) => `<li>${[...new Set(ts.map(t => t.title))].map(esc).join(", ")} <span class="mut">${ts.some(t => t.src !== "titledb") ? "ohne Angabe" : "laut titledb, zur Bestätigung"} · ${id}</span></li>`).join("");
  return `<details class="box" data-k="jphelper" ${S.folds.jphelper ? "open" : ""}><summary><b>Browser-Helfer für Japan:</b> <span class="mut">${ids.length ? `${rows.length} ${rows.length === 1 ? "Eintrag" : "Einträge"} ohne Angabe von Nintendo auf ${ids.length} ${ids.length === 1 ? "Seite" : "Seiten"}` : "alle Japan-Titel haben eine Angabe von Nintendo"}</span></summary>
    ${names ? `<p class="hint">Das Lesezeichen liest:</p><ul class="hint">${names}</ul>` : ""}
    <ol class="hint">
      <li>Leg einmal dieses Lesezeichen an: ${bmLink("jp", jpHelperCode(location.origin))}</li>
      <li>Öffne <a href="https://store-jp.nintendo.com/${ids.length ? `?ek-ids=${ids.join("+")}#ek-ids=${ids.join("+")}` : ""}" target="_blank" rel="noopener" data-act="jpopen">store-jp.nintendo.com</a> über diesen Link und klick das Lesezeichen an. Es liest ${ids.length ? "die offenen Titel" : "die Titel"}, eine Seite alle 2,5 Sekunden.${ids.length ? " Der Link gibt die IDs mit. Verliert der Store sie unterwegs, holt das Lesezeichen sie über ein kleines Fenster des Tools, das sich danach selbst schließt." : ""}</li>
      <li>Klick dort auf „Im eShop-Kompass übernehmen“.</li>
    </ol>
    <details class="fold" data-k="jpfb" ${S.folds.jpfb ? "open" : ""}><summary class="hint">Geht das nicht? IDs und Ergebnis von Hand</summary>
      <p class="hint">IDs zum Einfügen: <textarea id="jpids" readonly rows="2" style="width:100%">${ids.join(" ")}</textarea> <button data-act="jpcopy">IDs kopieren</button></p>
      <p class="hint">Ergebnis aus dem Fenster des Lesezeichens: <textarea id="jpimport" rows="3" style="width:100%" placeholder='{"70010000000000":"日本語, 英語, ドイツ語"}'></textarea> <button data-act="jpimport">Übernehmen</button></p>
    </details></details>`;
}
async function saveSettings(form, rerender){
  const active = () => JSON.stringify(Object.entries(S.state.settings.countries).filter(e => e[1].enabled).map(e => e[0]));
  const before = active();
  await api("/api/settings", settingsBody(form));
  const fresh = await api("/api/state");
  S.state = fresh; S.ui = fresh.ui;
  await loadPlans();
  if(rerender || before !== active()) render(); else renderHead();
  const el = $("saved");
  if(el){ el.textContent = before !== active() ? "Gespeichert. Für neue Länder bitte aktualisieren." : "Gespeichert ✓"; setTimeout(() => { if($("saved")) $("saved").textContent = ""; }, 3000); }
}
