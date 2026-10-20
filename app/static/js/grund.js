"use strict";
/* Grundlagen: Ansicht und Zustand im Browser, Zahlen, Zeiten, Links, Deal-Güte, Signale (Teil der Oberfläche, Reihenfolge in index.html) */
/* Ansicht je Browser: Reiter, Titelansicht, Filter, aufgeklappte Kästen */
function loadView(){ try{ return JSON.parse(localStorage.getItem("ek.view") || "{}") || {}; }catch(e){ return {}; } }
function saveView(){ try{ localStorage.setItem("ek.view", JSON.stringify({tab:S.tab, tview:S.tview, vf:S.vf, folds:S.folds, mDetails:S.mDetails, sorts:S.sorts, colOrder:S.colOrder, dense:S.dense, lsort:S.lsort})); }catch(e){} }
/* Hell, dunkel oder wie das Gerät. Gemerkt je Browser (ek.theme); das Skript im Kopf setzt es
   vor dem ersten Zeichnen, damit nichts aufblitzt. */
const ICO = d => `<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">${d}</svg>`;
const THEMES = [
  ["system", ICO(`<circle cx="8" cy="8" r="6"/><path d="M8 2a6 6 0 0 1 0 12z" fill="currentColor"/>`), "System", "wie dein Gerät"],
  ["light", ICO(`<circle cx="8" cy="8" r="3"/><path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M3 13l1-1M12 4l1-1"/>`), "Hell", ""],
  ["dark", ICO(`<path d="M13.5 10A6 6 0 0 1 6 2.5a6 6 0 1 0 7.5 7.5z"/>`), "Dunkel", ""]];
function themeNow(){ const t = document.documentElement.dataset.theme; return t === "light" || t === "dark" ? t : "system"; }
function renderTheme(){
  const cur = THEMES.find(x => x[0] === themeNow()), b = $("thmBtn");
  b.innerHTML = cur[1];
  b.title = `Ansicht: ${cur[2]}${cur[3] ? ` (${cur[3]})` : ""}. Klick zum Ändern`;
  b.setAttribute("aria-label", b.title);
  $("thmMenu").innerHTML = THEMES.map(([k, ic, l, h]) =>
    `<button role="menuitemradio" aria-checked="${k === cur[0]}" class="${k === cur[0] ? "on" : ""}" data-act="thmset" data-v="${k}"><span class="ic">${ic}</span>${l}${h ? ` <small class="mut">${h}</small>` : ""}</button>`).join("");
}
function themeMenu(open){ $("thmMenu").hidden = !open; $("thmBtn").setAttribute("aria-expanded", open); }
function setTheme(k){
  if(k === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = k;
  try{ if(k === "system") localStorage.removeItem("ek.theme"); else localStorage.setItem("ek.theme", k); }catch(e){}
  renderTheme(); themeMenu(false);
}
/* Reihenfolge (0.61): erst was zu tun ist, dann Wunschliste, Korb und Länder (Einkauf), dann was du hast */
// Der Korb ist ab 0.73 eine Ansicht der Wishlist (Liste | Tabelle | Korb), kein eigener Reiter mehr
// Ab 0.74 vier Reiter: Die Länderkarten (intern weiter `laender`) öffnen sich aus dem Kaufplan, kein eigener Reiter
const TABS = [["jetzt","Jetzt"],["titel","Wishlist"],["sammlung","Sammlung"],["settings","Einstellungen"]];
const V0 = loadView();
if(V0.tab === "korb"){ V0.tab = "titel"; V0.tview = "korb"; }
if(V0.vf === "coll"){ V0.vf = "all"; if(V0.tab === "titel") V0.tab = "sammlung"; }   // bis 0.27 ein Filter im Reiter Titel
const S = {state:null, plans:[], ui:null, tab:TABS.some(t => t[0] === V0.tab) ? V0.tab : "jetzt",
           onlySale:false, collMissing:false, rq:"", vf:V0.vf || "all", tview:["table", "korb"].includes(V0.tview) ? V0.tview : "list",
           openTitle:null, folds:V0.folds || {}, mDetails:!!V0.mDetails,
           sorts:V0.sorts && typeof V0.sorts === "object" ? V0.sorts : {}, colOrder:V0.colOrder || "tierbest",
           // Ansicht und Sortierung der Länder merkt sich der Browser (0.65), früher der Server
           dense:typeof V0.dense === "boolean" ? V0.dense : null, lsort:V0.lsort || null,
           timer:null, step:"", lastSync:null};
const $ = id => document.getElementById(id);
/* Zahlen in Eingabefeldern mit Komma (0.65): dc zeigt, num0 liest beides */
const dc = v => v === null || v === undefined || v === "" ? "" : String(v).replace(".", ",");
const num0 = v => parseFloat(String(v ?? "").replace(",", "."));
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
/* Sortieren per Klick auf Spaltenköpfe: S.sorts[Tabelle] = {k, dir}. Erster Klick aufsteigend,
   zweiter absteigend, dritter zurück zur gewohnten Reihenfolge. Leere Werte stehen immer am Ende. */
function sth(t, k, label, title = "", cls = ""){
  const s = S.sorts[t], on = !!(s && s.k === k);
  return `<th class="sth ${on ? "on" : ""} ${cls}" tabindex="0" data-act="tsort" data-t="${t}" data-k="${esc(k)}" title="${esc(title ? title + " · " : "")}Klick sortiert"${on ? ` aria-sort="${s.dir > 0 ? "ascending" : "descending"}"` : ""}>${label}<span class="sa">${on ? (s.dir > 0 ? "▲" : "▼") : ""}</span></th>`;
}
function sortRows(t, arr, keys){
  const s = S.sorts[t], f = s && keys[s.k];
  if(!f) return arr;
  const empty = v => v === null || v === undefined || v === "" || (typeof v === "number" && !isFinite(v));
  return arr.map((x, i) => [x, f(x), i]).sort((a, b) => {
    const ea = empty(a[1]), eb = empty(b[1]);
    if(ea || eb) return (ea - eb) || (a[2] - b[2]);
    const c = typeof a[1] === "string" ? a[1].localeCompare(b[1], "de") : a[1] - b[1];
    return c * s.dir || (a[2] - b[2]);
  }).map(x => x[0]);
}

async function api(path, body){
  const r = await fetch(path, body === undefined ? {} :
    {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  const j = await r.json();
  if(!r.ok) throw new Error(j.error || r.status);
  return j;
}

/* ---------- Zahlen, Zeiten, Links ---------- */
const DIGITS = {};
function digits(cur){
  if(!(cur in DIGITS)){
    try{ DIGITS[cur] = new Intl.NumberFormat("de-DE",{style:"currency",currency:cur}).resolvedOptions().maximumFractionDigits; }
    catch(e){ DIGITS[cur] = 2; }
  }
  return DIGITS[cur];
}
function money(n, cur){
  if(n === null || n === undefined) return "–";
  try{ return new Intl.NumberFormat("de-DE",{style:"currency",currency:cur||"EUR"}).format(n); }
  catch(e){ return n.toFixed(2).replace(".",",") + " " + (cur||""); }
}
function num(n, cur){   // Landeswährung ohne Zeichen, für enge Spalten; Euro immer mit €
  if(n === null || n === undefined) return "–";
  if(!cur || cur === "EUR") return eur(n);
  const d = digits(cur);
  return n.toLocaleString("de-DE",{minimumFractionDigits:d, maximumFractionDigits:d});
}
const eur = n => money(n, "EUR");
const APPROX = `<span class="approx" title="geschätzt: Guthaben zum Kurs plus pauschalem Aufschlag, weil für das Land kein Kartenpreis lesbar ist">≈</span>`;
const ax = x => x && x.est ? APPROX : "";   // Kennzeichen für geschätzte Europreise
// Sprachfassung: DE✓ bestätigt (oder dasselbe Produkt wie im deutschen eShop), sonst Hinweis
function langTag(x, all){
  if(!x) return "";
  if(x.lang === "de") return `<span class="lgt de" title="Deutsche Fassung in dieser Region bestätigt">DE✓</span>`;
  if(x.lang === "same" && all) return `<span class="lgt de" title="Dieselbe Fassung wie im deutschen eShop">DE✓</span>`;
  if(x.lang === "no") return `<span class="lgt no" title="Andere Fassung als im deutschen eShop, ohne Deutsch">andere Fassung</span>`;
  return "";
}
function endCell(iso, prefix){
  if(!iso) return "";
  const d = new Date(iso);
  if(isNaN(d)) return "";
  const full = d.toLocaleString("de-DE",{weekday:"short",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"});
  const day = x => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(d) - day(new Date())) / 86400000);
  let text = d.toLocaleDateString("de-DE",{day:"2-digit",month:"2-digit"}), cls = "";
  if(diff <= 0){ text = "heute"; cls = "today"; }
  else if(diff === 1){ text = "morgen"; cls = "soon"; }
  else if(diff === 2){ cls = "soon"; }
  return `<span class="${cls}" title="Angebot endet ${esc(full)}">${diff <= 1 ? "" : (prefix || "")}${text}</span>`;
}
function ago(iso){
  if(!iso) return "noch nie";
  const min = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  if(min < 2) return "gerade eben";
  if(min < 90) return `vor ${min} Min.`;
  if(min < 48 * 60) return `vor ${Math.round(min / 60)} Std.`;
  return `vor ${Math.round(min / 1440)} Tagen`;
}
const clock = d => d.toLocaleTimeString("de-DE",{hour:"2-digit",minute:"2-digit"});
/* "morgen " oder "15.10. " vor einer Uhrzeit, die nicht mehr heute ist */
function whenDay(d){
  const day = x => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const n = Math.round((day(d) - day(new Date())) / 86400000);
  return n <= 0 ? "" : n === 1 ? "morgen " : d.toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit"}) + " ";
}
function toast(msg, undo){
  document.querySelectorAll(".toast").forEach(t => t.remove());
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  if(undo){
    const b = document.createElement("button");
    b.textContent = "Rückgängig";
    b.onclick = () => { t.remove(); undo(); };
    t.appendChild(b);
  }
  document.body.appendChild(t);
  setTimeout(() => t.remove(), undo ? 7000 : 2600);
}
const country = code => S.state.countries.find(c => c.code === code) || {name: code, lang: "en"};
const shopOf = code => code ? (country(code).shop || code) : "DE";   // DG nutzt den deutschen eShop
// Ohne Land (0.82.3) zeigt DekuDeals die dort eingestellte Länderansicht; mit Land (Preis in einer
// Länderspalte) die Ansicht dieses Shops
const deku = (slug, code) => `https://www.dekudeals.com/items/${encodeURIComponent(slug)}${code ? `?country=${shopOf(code).toLowerCase()}` : ""}`;
// Suche bei eShop-Prices nur mit Buchstaben und Ziffern: Zeichen wie & oder : finden dort nichts
const epSearch = title => `https://eshop-prices.com/games?q=${String(title).replace(/[^\p{L}\p{N}]+/gu, " ").trim().split(" ").map(encodeURIComponent).join("+")}&currency=EUR`;
function shopUrl(code, nsuid){   // Produktseite im eShop des Landes
  if(!nsuid) return null;
  const kind = String(nsuid).startsWith("7001") ? "titles" : String(nsuid).startsWith("7007") ? "bundles" : null;
  return kind ? `https://ec.nintendo.com/${shopOf(code)}/${country(code).lang}/${kind}/${nsuid}` : null;
}
/* Landespreis verlinkt den Verlauf bei DekuDeals, der Europreis die eShop-Seite */
function priceLink(slug, code, text, x, cur){
  const tip = (x && x.eur !== undefined && String(text).includes("€") ? compose(code, x) + " · " : "") +
    "Klick öffnet den Preisverlauf bei DekuDeals" + (x && x.low !== null && x.low !== undefined ? ` · Landestief ${money(x.low, cur)}` : "");
  return `<a class="pl" href="${deku(slug, code)}" target="_blank" rel="noopener" title="${esc(tip)}">${text}</a>`;
}
/* Woraus sich ein Europreis zusammensetzt: Shop-Preis, Steuer, Kurs, Zahlweg */
function compose(code, x){
  const p = S.state.pay[code];
  if(!p || x.eur === null || x.eur === undefined) return "";
  // Eigenes Angebot (ab 0.62): Code beim Händler, mit Kreditkarte bezahlt, im Konto des Landes eingelöst
  if(x.own) return `${x.own.src}-Code ${money(x.local, p.currency)} (${x.own.read ? `gelesen ${stamp(x.own.read)}` : "von dir eingetragen"}) · Kreditkarte zum Mittelkurs plus ${pctTxt(S.state.settings.card_fee_pct)} Gebühr = ${eur(x.eur)} · einlösen im Konto ${country(code).name}` +
    (x.own.eshop !== null && x.own.eshop !== undefined ? ` · im eShop ${eur(x.own.eshop)}` : " · im eShop dort nicht kaufbar");
  const cur = p.currency, parts = [];
  const net = x.net ?? x.local;
  parts.push(`eShop ${money(net, cur)}` + (p.tax ? ` + ${String(p.tax).replace(".", ",")} % Steuer = ${money(x.local, cur)}` : ""));
  if(p.via === "eur") return parts[0] + ", exakter Betrag";
  if(cur === "EUR" && x.alone && x.alone.cards.length){
    const a = x.alone, cards = a.cards.map(c => `${c.count}× ${eur(c.face)}`).join(" + ");
    return parts.concat(`Guthaben passend gekauft: ${cards} für ${eur(a.eur)}` + (a.rest ? `, ${eur(a.rest)} bleiben als Rest auf dem Konto` : "")).join(" · ") + ` · anteilig ${eur(x.eur)}`;
  }
  if(cur === "EUR" && p.card) return parts.concat(`Guthabenkarte ${eur(p.card.face)} für ${eur(p.card.cost)}${cardSrc(p.card)}, Faktor ${fac(p.card.factor)}, ein Rest bleibt auf dem Konto`).join(" · ") + ` · ergibt ${eur(x.eur)}`;
  parts.push(`Mittelkurs 1 € = ${p.rate.toLocaleString("de-DE", {maximumFractionDigits: p.rate > 20 ? 1 : 3})} ${cur}` +
    (S.state.fx_updated ? ` (Stand ${fxDate()})` : ""));
  if(p.via === "card") parts.push(`Kartenzahlung plus ${pctTxt(p.fee)} Fremdwährungsgebühr, die Bank rechnet mit eigenem Kurs`);
  else if(x.alone && x.alone.cards.length){
    // Guthaben passend zu diesem Titel gekauft; der Rest bleibt auf dem Konto und zählt nicht
    const a = x.alone, cards = a.cards.map(c => `${c.count}× ${money(c.face, cur)}`).join(" + ");
    return parts.concat(`Guthaben passend gekauft: ${cards} für ${eur(a.eur)}` +
      (a.rest ? `, davon ${money(x.local, cur)} für den Titel, ${money(a.rest, cur)} bleiben als Rest` : "")).join(" · ") +
      ` · anteilig ${x.est ? "ungefähr " : ""}${eur(x.eur)}`;
  }
  else if(p.card) parts.push(`Guthabenkarte ${money(p.card.face, cur)} (Wert ${eur(p.card.value)}) für ${eur(p.card.cost)}${cardSrc(p.card)}, Faktor ${fac(p.card.factor)}`);
  else if(p.at_rate) parts.push(`Guthaben in festen Werten zum Kurs${p.fee ? ` plus ${pctTxt(p.fee)} Gebühr deiner Karte` : ""}`);
  else parts.push(`Guthaben geschätzt mit Kurs ${p.markup >= 0 ? "+" : ""}${pctTxt(p.markup)}, weil kein Kartenpreis bekannt ist`);
  return parts.join(" · ") + ` · ergibt ${x.est ? "ungefähr " : ""}${eur(x.eur)}` + aloneTxt(x, cur);
}
/* Woher ein Kartenpreis stammt, für Tooltips */
const cardSrc = k => k.live ? ` (Shop-Preis vom ${stamp(k.live)}${feeTxt(k.fee, k.fee_eur)})` : "";
const feeTxt = (pct, fix) => pct || fix ? ` mit Servicegebühr ${[fix ? eur(fix) : "", pct ? pctTxt(pct) : ""].filter(Boolean).join(" + ")}` : "";
const stamp = sec => new Date(sec * 1000).toLocaleString("de-DE", {day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit"});
/* Faktor einer Guthabenkarte: Preis ÷ Wert zum Mittelkurs (0.53) */
const fac = f => f === null || f === undefined ? "–" : f.toLocaleString("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const RATE_CLS = {top: "gn", good: "gn", cheaper: "gn", ok: "", same: "", bad: "warnc", dearer: "abv"};
const rateCls = r => r && r.level ? RATE_CLS[r.level] ?? "" : "";
const rateHtml = r => r ? `<span class="${r.level ? RATE_CLS[r.level] ?? "" : "mut"}"${r.best ? ` title="Maßstab: ${r.level === "cheaper" || r.level === "dearer" || r.level === "same" ? "Faktor deiner Kreditkarte" : "bester Faktor dieser Karte in 90 Tagen"} ${fac(r.best)}"` : ""}>${esc(r.text)}</span>` : "";
/* Guthabenkarten eines Landes für die Einstellungen: Wert, Preis, Faktor, Bewertung */
function cardRows(code){ return (S.state.card_status || {})[code] || []; }
function cardSummary(code){
  const rows = cardRows(code).filter(r => r.stock && r.factor !== null), pi = S.state.pay[code] || {};
  if(!rows.length) return "";
  const best = rows.reduce((a, r) => r.factor < a.factor ? r : a);
  const x = S.state.settings.countries[code] || {};
  const verdict = x.pay === "auto" || x.pay === "card" ? (best.rating && best.rating.level === "cheaper" ? "Guthaben günstiger" : "Kreditkarte günstiger")
    : pi.rating && pi.rating.text ? pi.rating.text.split(",")[0] : "";
  const vc = verdict === "Guthaben günstiger" ? "gn" : verdict === "Kreditkarte günstiger" ? "" : pi.rating && pi.rating.level ? rateCls(pi.rating) : "mut";
  return ` · bester Faktor <span class="${rateCls(best.rating)}">${fac(best.factor)}</span>${verdict ? ` · <span class="${vc}">${esc(verdict)}</span>` : ""}`;
}
function cardTable(code, cur){
  const rows = cardRows(code);
  if(!rows.length) return "";
  const price = r => {
    if(r.live) return `<span title="Shop-Preis vom ${stamp(r.live)}${feeTxt(r.fee, r.fee_eur)}">${eur(r.cost)}</span> <small class="mut">Shop, ${new Date(r.live * 1000).toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit"})}${r.fee || r.fee_eur ? ", mit Gebühr" : ""}</small>` +
      (r.error ? ` <small class="warnc" title="Der letzte Abruf scheiterte. Der zuletzt gelesene Preis gilt bis zu 14 Tage weiter.">letzter Abruf: ${esc(r.error)}</small>` : "");
    if(r.url && r.checked) return `${r.manual === null ? "–" : `${eur(r.manual)} <small class="mut">eingetragen</small>`} <small class="warnc">${esc(r.error || "kein Preis")}</small>`;
    if(r.url && r.manual === null) return `<small class="mut">wird beim nächsten Abgleich gelesen</small>`;
    if(r.cost !== null) return `${eur(r.cost)} <small class="mut">eingetragen</small>`;
    return `<small class="mut">zum Kurs</small>`;
  };
  return `<table class="cards"><thead><tr><th>Karte</th><th title="Wert zum Mittelkurs">Wert</th><th>Preis</th><th title="Preis ÷ Wert. 1,00 heißt: Guthaben zum Kurs. 0,85 heißt: 100 € Guthaben kosten 85 €.">Faktor</th><th>Bewertung</th></tr></thead><tbody>${rows.map(r =>
    `<tr class="${r.stock ? "" : "mut"}"><td>${cur ? money(r.face, cur) : num(r.face)}</td><td>${r.value === null ? "–" : eur(r.value)}</td><td>${price(r)}</td>
      <td class="${r.stock ? rateCls(r.rating) : ""}">${fac(r.factor)}</td><td>${r.stock ? rateHtml(r.rating) : "nicht vorrätig"}${r.used ? ` <span class="chip" title="Diese Karte rechnet das Tool für die Preise dieses Landes">genutzt</span>` : ""}</td></tr>`).join("")}</tbody></table>`;
}
/* Einzelkauf: welche Karten ein Titel allein braucht und was übrig bleibt */
function aloneTxt(x, cur){
  const a = x.alone;
  if(!a) return "";
  const cards = a.cards.map(c => `${c.count}× ${money(c.face, cur)}`).join(" + ");
  return ` · allein gekauft: ${eur(a.eur)}${cards ? ` (${cards}${a.rest ? `, Rest ${money(a.rest, cur)}` : ""})` : ""}`;
}
const pctTxt = v => String(v ?? "").replace(".", ",") + " %";
function fxStamp(){
  const d = new Date(S.state.fx_updated);
  return isNaN(d) ? (S.state.fx_updated || "–") : d.toLocaleString("de-DE", {day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit"});
}
function fxDate(){
  const d = new Date(S.state.fx_updated);
  return isNaN(d) ? S.state.fx_updated : d.toLocaleDateString("de-DE");
}
function buyLink(code, x, text){
  if(x.own && x.own.url) return `<a class="pl" href="${esc(x.own.url)}" target="_blank" rel="noopener" title="${esc(compose(code, x))} · Klick öffnet ${esc(x.own.src)}">${text}</a>`;
  const url = shopUrl(code, x.nsuid), tip = esc(compose(code, x));
  return url ? `<a class="pl" href="${url}" target="_blank" rel="noopener" title="${tip} · Klick öffnet den eShop ${esc(country(code).name)}">${text}</a>`
             : `<span title="${tip}">${text}</span>`;
}
function costTip(p){
  const own = p.direct_n ? ` · dazu ${p.direct_n === 1 ? "ein eigenes Angebot" : `${p.direct_n} eigene Angebote`} (Codes) für ${eur(p.direct)}, mit Kreditkarte bezahlt` : "";
  return costTip0(p) + own;
}
function costTip0(p){
  if(p.is_ref){
    const c = (S.state.pay[p.code] || {}).card;
    return c ? `Kauf in Deutschland mit Guthabenkarten: ${eur(c.face)} für ${eur(c.cost)}, ein Rest bleibt auf dem Konto` : "Kauf in Deutschland, exakter Betrag";
  }
  const info = S.state.pay[p.code] || {};
  if(p.via === "card") return `Per Karte: ${money(p.total, p.currency)} zum Mittelkurs plus ${pctTxt(info.fee)} Gebühr. Die Abrechnung deiner Bank kann leicht abweichen.`;
  if(p.estimated) return `Geschätzt: ${money(p.total, p.currency)} zum Kurs ${info.markup >= 0 ? "+" : ""}${String(info.markup ?? "").replace(".", ",")} %, weil keine Guthabenkarten eingetragen sind`;
  const sum = p.cards.reduce((a, c) => a + c.count * c.face, 0);
  return `Guthabenkarten über ${money(sum, p.currency)} für ${eur(p.cost)}` + (p.rest ? `, davon bleiben ${money(p.rest, p.currency)} als Rest` : ", kein Rest");
}

/* ---------- Deal-Güte ---------- */
const MARK = {best:"Bestpreis über alle Länder", low:"Tiefstpreis dieses Landes", sale:"Angebot über dem Tiefstpreis"};
function markTip(x, cur){
  return [MARK[x.mark] || "kein Angebot",
    x.gap ? `${x.gap} % über Bestpreis` : "",
    x.champ !== null && x.champ !== undefined ? `Bestpreis ${eur(x.champ)} in ${country(x.champ_code).name}` : "",
    x.low !== null && x.low !== undefined ? `Landestief ${money(x.low, cur)}` : "Landestief noch nicht geladen"].filter(Boolean).join(" · ");
}

/* ---------- Zustand ---------- */
const planBody = (basket = []) => ({overrides:S.ui.overrides, must:[], basket});
function saveUi(){ return api("/api/ui", S.ui).catch(err => toast("Nicht gespeichert: " + err.message)); }
function migrateLocal(){   // frühere Versionen merkten sich den Korb im Browser
  try{
    const b = JSON.parse(localStorage.getItem("ek.basket") || "null");
    const o = JSON.parse(localStorage.getItem("ek.overrides") || "null");
    const empty = !S.ui.basket && !Object.keys(S.ui.overrides).length;
    if(empty && ((Array.isArray(b) && b.length) || (o && Object.keys(o).length))){
      if(Array.isArray(b) && b.length) S.ui.basket = b;
      if(o) S.ui.overrides = o;
      saveUi();
    }
    localStorage.removeItem("ek.basket"); localStorage.removeItem("ek.overrides"); localStorage.removeItem("ek.dense");
  }catch(e){}
}
async function loadPlans(){
  // Länder zeigen immer die Körbe je Land; der gemeinsame Korb (Wishlist, Ansicht Korb) rechnet extra (0.59).
  // Alle drei zugleich anfragen (0.77), nicht nacheinander
  const [r, b, k] = await Promise.all([api("/api/plans", planBody()),
    S.ui.basket ? api("/api/plans", planBody(S.ui.basket)) : null, api("/api/kaufplan")]);
  S.plans = r.plans;
  S.bplans = b ? b.plans : []; S.mix = b ? b.mix : null;
  S.kauf = k;
}
async function refresh(){
  S.state = await api("/api/state");
  S.ui = S.state.ui;
  if(S.dense === null) S.dense = S.ui.dense !== false;
  if(!S.lsort) S.lsort = S.ui.sort || "optimum";
  S.lastSync = S.state.last_sync;
  migrateLocal();
  if(S.ui.basket){   // Titel, die nicht mehr auf der Wishlist stehen, fallen aus dem Korb
    const known = new Set(S.state.matrix.rows.map(r => r.slug).concat((S.state.nso_items || []).map(x => x.slug)));
    S.ui.basket = S.ui.basket.filter(s => known.has(s));
    if(!S.ui.basket.length) S.ui.basket = null;
  }
  // Beim ersten Laden gleich zeichnen, was schon da ist; Kaufplan und Körbe folgen (0.77)
  if(!S.drawn){ S.drawn = true; render(); }
  await loadPlans();
  render();
  watch();
}
async function replan(){
  if(S.ui.basket && !S.ui.basket.length) S.ui.basket = null;
  saveUi();
  await loadPlans();
  render();
}
/* Änderung mit Rückweg: merkt sich den Stand davor */
async function change(label, fn){
  const before = JSON.stringify(S.ui);
  fn();
  await replan();
  toast(label, async () => { S.ui = JSON.parse(before); await replan(); });
}
function watch(){
  if(S.timer || !S.state.status.running) return;
  S.timer = setInterval(async () => {
    const st = await api("/api/status");
    const stepChanged = st.step !== S.step;
    S.step = st.step;
    S.state.status = st;
    if(!st.running){
      clearInterval(S.timer); S.timer = null;
      try{ await refresh(); }catch(e){ toast("Fehler beim Neuladen: " + e.message); }
      toast(st.ok ? "Abgleich fertig" : "Abgleich fehlgeschlagen");
    }
    else if(stepChanged && /^(Sprachen|Tiefstpreise)/.test(st.step)){ await refresh(); }   // Preise sind da
    else renderHead();
    showLog(st.log);
  }, 2000);
}
/* Offene Seite hält sich selbst aktuell */
setInterval(async () => {
  if(!S.state || S.timer || document.hidden) return;
  try{
    const st = await api("/api/status");
    if(st.running){ S.state.status = st; renderHead(); watch(); }
    else if(st.last_sync !== S.lastSync && S.tab !== "settings") await refresh();
    else renderHead();
  }catch(e){}
}, 60000);

/* Protokoll: neueste Zeile unten, die Box folgt ihr, solange du nicht hochgescrollt hast */
/* Der Server schreibt UTC, angezeigt wird die Uhrzeit deines Browsers */
function localStamp(line){
  const m = /^(\d\d):(\d\d):(\d\d)( .*)$/s.exec(line);
  if(!m) return line;
  const d = new Date(); d.setUTCHours(+m[1], +m[2], +m[3], 0);
  return d.toLocaleTimeString("de-DE") + m[4];
}
function showLog(lines){
  const l = $("log");
  if(!l) return;
  const atEnd = l.scrollHeight - l.scrollTop - l.clientHeight < 30;
  const st = S.state.status || {};
  const head = st.started ? `Abgleich vom ${new Date(st.started).toLocaleString("de-DE")}, v${S.state.version}${st.running ? ", läuft" : st.ok === false ? ", fehlgeschlagen" : ""}\n` : "";
  l.textContent = (lines || []).length ? head + lines.map(localStamp).join("\n") : "Noch kein Protokoll seit dem letzten Neustart.";
  if(atEnd || !l.dataset.seen){ l.scrollTop = l.scrollHeight; l.dataset.seen = "1"; }
}
function renderHead(){
  const st = S.state.status, hours = S.state.settings.refresh_hours || 6;
  const m = $("meta");
  if(st.running){
    m.textContent = `${st.step}${st.total ? ` (${st.done}/${st.total})` : ""} …`;
  } else {
    const last = S.state.last_sync ? new Date(S.state.last_sync) : null;
    const stale = last && Date.now() - last > 2 * hours * 3600000;
    let next = last ? new Date(+last + hours * 3600000) : null;
    if(st.boot_sync && (!next || new Date(st.boot_sync) < next)) next = new Date(st.boot_sync);   // einmal nach dem Start
    m.innerHTML = `<span class="${stale ? "warnc" : ""}" title="${last ? esc(last.toLocaleString("de-DE")) : ""}">Stand ${ago(S.state.last_sync)}</span>` +
      (next ? ` · nächster Abgleich ${next < new Date() ? "in Kürze" : "ca. " + whenDay(next) + clock(next)}` : "") +
      ` · ${S.state.item_count} Titel · v${esc(S.state.version)}`;
  }
  $("syncBtn").disabled = st.running;
  $("nav").innerHTML = TABS.map(([k,l]) =>
    `<button data-act="tab" data-tab="${k}" class="${S.tab===k?"on":""}">${l}</button>`).join("");
}
function banners(){
  let h = "";
  const st = S.state.status;
  if(!S.state.settings.wishlist_url)
    h += `<div class="banner">Trage unter Einstellungen deinen DekuDeals-Wishlist-Link ein und klicke auf Aktualisieren.</div>`;
  else if(!S.state.last_sync && !st.running)
    h += `<div class="banner">Noch kein Abgleich. Der erste Lauf sucht die Titel-IDs und dauert einige Minuten.</div>`;
  // Notbetrieb (0.84): DekuDeals gesperrt oder nicht lesbar, das Tool rechnet mit den zuletzt gelesenen Listen
  const fb = S.state.fallback;
  if(fb && !st.running){
    const when = fb.wishlist_at ? `vom ${esc(dmy(fb.wishlist_at))}` : "vom letzten Lesen";
    const why = fb.until ? `DekuDeals hat gesperrt und ruht bis ${esc(dmy(fb.until))}, ${esc(clock(new Date(fb.until)))}`
      : fb.error ? `DekuDeals ist gerade nicht lesbar (${esc(fb.error)})` : `Die Wishlist wurde seit ${when.replace("vom ", "dem ")} nicht mehr gelesen`;
    h += `<div class="banner"><b>Notbetrieb:</b> ${why}. Es gelten Wishlist und Sammlung ${when}, Tiefstpreise, DLC und Pakete vom letzten Lesen; Preise, Kurse und Kartenpreise sind aktuell.
      <button class="link" data-act="showlog">Protokoll öffnen</button></div>`;
  }
  const warn = ((S.state.checks || {}).warnings || []);
  if(warn.length && !st.running)
    h += `<div class="banner">Selbstprüfung nach dem letzten Abgleich: ${warn.map(esc).join(" · ")}.
      <button class="link" data-act="showlog">Protokoll öffnen</button></div>`;
  if(st.ok === false){
    const last = (st.log || []).filter(l => !/Abbruch|^\s/.test(l.slice(9))).pop() || "";
    const why = (st.log || []).filter(l => /Abbruch/.test(l)).pop() || last;
    h += `<div class="banner">Letzter Abgleich fehlgeschlagen: ${esc(why.replace(/^\S+ (Abbruch: )?/, ""))}.
      <button class="link" data-act="showlog">Protokoll öffnen</button></div>`;
  }
  return h;
}
let fitMatrix = () => {}, showStick = () => {};
/* Sofort kopieren, noch im Klick: Öffnet der Klick einen neuen Tab, verliert die Seite den Fokus,
   und navigator.clipboard lehnt danach ab (Firefox). execCommand kopiert synchron (0.57.1). */
function copyNow(text){
  const t = document.createElement("textarea");
  t.value = text; t.style.cssText = "position:fixed;top:0;left:0;opacity:0";
  const back = document.activeElement;
  document.body.appendChild(t); t.focus(); t.select();   // Firefox kopiert nur aus dem fokussierten Feld (0.58)
  let ok = false;
  try{ ok = document.execCommand("copy"); }catch(e){}
  t.remove();
  if(back && back.focus) back.focus();
  if(!ok) try{ navigator.clipboard.writeText(text); }catch(e){}
}
function render(){
  if(S.handover) return;          // Fenster für das JP-Lesezeichen, siehe jpHandOver
  renderHead();
  const m = $("main");
  // Seitlich und senkrecht gescrollte Tabellen bleiben, wo sie waren, etwa nach dem Sortieren (0.61)
  const keep = S.drawnTab === S.tab ? [...m.querySelectorAll(".scroll,.fitbox")].map(e => [e.scrollLeft, e.scrollTop]) : [];
  S.drawnTab = S.tab;
  m.className = "";     // Einstellungen ab 0.76 so breit wie der Bildschirm, alle Karten gleich (vorher 1280 px, nur Sprachen breiter)
  if(S.tab === "jetzt") m.innerHTML = banners() + viewJetzt();
  else if(S.tab === "titel") m.innerHTML = banners() + (S.tview === "table" ? viewMatrix() : S.tview === "korb" ? (S.ui.basket ? viewCompare() : viewKorbEmpty()) : viewTitles());
  else if(S.tab === "sammlung") m.innerHTML = banners() + viewCollection();
  else if(S.tab === "laender") m.innerHTML = banners() + viewCards();
  else { m.innerHTML = viewSettings(); showLog(S.state.status.log); }
  // Tabellen mit eigenem Scrollkasten, fensterhoch: Titel-Tabelle und Korb (0.61)
  document.body.classList.toggle("fit", (S.tab === "titel" && (S.tview === "table" || S.tview === "korb" && !!document.querySelector(".fitbox"))) && innerWidth > 700);
  if(!document.body.classList.contains("fit")) showStick();
  fitMatrix();
  m.querySelectorAll(".scroll,.fitbox").forEach((e, k) => { if(keep[k]){ e.scrollLeft = keep[k][0]; e.scrollTop = keep[k][1]; } });
  const grp = m.querySelector(".matrix tr.grp");
  if(grp) grp.closest(".matrix").style.setProperty("--grp", grp.getBoundingClientRect().height + "px");
  navFade();
}
/* Reiterleiste schmaler als ihre Reiter (Handy): rechts ausblenden, damit man sieht, dass es weitergeht (0.65) */
function navFade(){
  const n = $("nav");
  if(n) n.classList.toggle("more", n.scrollLeft + n.clientWidth < n.scrollWidth - 2);
}
addEventListener("resize", navFade);
const rowOf = slug => S.state.matrix.rows.find(r => r.slug === slug) || (S.state.nso_items || []).map(x => Object.assign({nso: true}, x)).find(r => r.slug === slug)
  || (S.state.extra_offers || []).filter(x => x.slug === slug).map(x => ({slug, title: x.title, dlc_of: x.game, extra: true}))[0] || {title:slug, slug};
const inBasket = slug => (S.ui.basket || []).includes(slug);

/* ---------- Signale: ein Urteil, ein Wechsel, feste Farben ---------- */
const VERDICT = {buy:"kaufen", good:"gut", wait:"warten", none:"kein Urteil"};
const TIER = {1:"leicht", 2:"mittel", 3:"schwer"};
const tierTag = t => t && TIER[t] ? `<span class="tier" title="Wechselstufe">${TIER[t]}</span>` : "";
const pill = v => v === "none" || !v ? `<span class="mut">kein Urteil</span>` : `<span class="vd ${v}">${VERDICT[v]}</span>`;
const star = x => x && x.mark === "best" ? `<span class="star" title="Einkaufspreis erreicht den Bestpreis">★</span>` : "";
/* Bis 2 % über dem Bestpreis gilt ein Preis als Bestpreis, wie im Urteil (BEST_TOLERANCE) */
const atBest = (eurNow, champ) => eurNow <= champ * 1.02 + 0.005;
/* Eine Bestpreis-Regel auf allen Ebenen (0.65): Eine Summe heißt nur „am Bestpreis“, wenn auch jeder
   Titel darin es ist. Sonst stünde oben grün „am Bestpreis“ und darunter rot „+0,86 €“. */
const itemsAtBest = items => items.every(i => i.champ === null || i.champ === undefined || atBest(i.eur, i.champ));
const nearTip = d => d >= 0.005 ? ` title="${eur(d)} über dem Bestpreis, das zählt noch als Bestpreis (bis 2 %)"` : "";
/* Abstand zum Bestpreis als Text: am Bestpreis in der Farbe des Urteils, +x € rot (teurer) */
function overBest(eurNow, champ, grade){
  if(eurNow === null || eurNow === undefined || !champ) return `<span class="mut">–</span>`;
  const d = eurNow - champ;
  const cls = grade ? "g-" + grade : "";
  return atBest(eurNow, champ) ? `<span class="${cls}"${nearTip(d)}>am Bestpreis</span>` : `<span class="abv">+${eur(d)}</span>`;
}
/* Wo ein Titel im Kaufplan steht: im Plan, Wechsel lohnt nicht, besser warten */
function planState(slug){
  const k = S.kauf;
  if(!k) return "";
  const n = k.steps.findIndex(p => p.items.some(i => i.slug === slug));
  if(n >= 0) return `im Plan, Schritt ${n + 1} (${esc(k.steps[n].name)})`;
  const d = k.dropped.find(x => (x.open_slugs || []).includes(slug));
  if(d && d.blocked_by) return `nicht im Plan: Rest in ${esc(d.name)} blockiert den Wechsel`;
  if(d) return `nicht im Plan: Wechsel nach ${esc(d.name)} lohnt nicht`;
  if(k.later.some(l => l.slug === slug)) return "nicht im Plan: lieber warten";
  if((k.held || []).some(h => h.slug === slug) && k.lock) return `nicht im Plan: Konto in ${esc(k.lock.name)} gesperrt, bis das Guthaben aufgebraucht ist`;
  const s2 = (k.s2_skip || []).find(x => x.slug === slug);
  if(s2) return `nicht im Plan: nur ein Weg zur Switch 2: ${esc(s2.reason)}`;
  const pk = (k.packed || []).find(x => x.slug === slug);
  if(pk) return `nicht einzeln im Plan: steckt in ${esc(pk.pack)}`;
  if((k.bought_slugs || []).includes(slug)){
    const b = (k.bought_how || []).find(x => x.slug === slug) || {};
    return b.how === "pack" ? `nicht im Plan: steckt in ${esc(b.via)}, das du schon hast` : b.how === "eshop" ? "nicht im Plan: laut eShop-Kaufverlauf gekauft"
      : b.how === "plan" ? "nicht im Plan: im Kaufplan als gekauft vermerkt"
      : (S.state.radar.find(r => r.slug === slug) || {}).owned ? "nicht im Plan: steht schon in deiner Sammlung" : "nicht im Plan: schon gekauft, steht noch auf der Wishlist";
  }
  return "";
}
