"use strict";
/* Sammlung, Ansicht „Spiele“ (1.6.1): jedes Spiel mit Genre, Spielern, Koop, Wertung, Spielzeit und Jahr;
   Filter, Sortierung, Mischungen und „Überrasch mich“ nach dem Vorbild von „Entdecken“ im VR-Navigator.
   Daten aus S.state.spiele (planner.game_infos). Filter laufen im Browser und stehen in der Adresse
   (#spiele?…), eine Mischung lässt sich so als Lesezeichen merken (Teil der Oberfläche, Reihenfolge in index.html) */
const G0 = {sys: "", g: [], gop: "", how: [], pl: 0, sc: 0, hr: 0, q: "", sort: "name", seed: 0, mix: "", n: 60};
S.g = Object.assign({}, G0, {g: [], how: []});
S.gOpen = null;
S.gMenu = null;
const G_SORTS = [["name", "Name"], ["score", "Wertung"], ["hours", "Spielzeit, kurz zuerst"], ["year", "Erscheinen, neu zuerst"],
  ["players", "Spieler, die meisten zuerst"], ["bought", "Zuletzt gekauft"], ["random", "Zufall"]];
// Spielweisen: mehrere gewählt heißt, alle müssen passen
const G_HOW = [["couch", "An einer Konsole (ab 2)", "Mehrere Spieler an einer Konsole: Couch, Splitscreen, geteilte Joy-Con"],
  ["local", "Lokal drahtlos", "Mehrere Konsolen im selben Raum"], ["online", "Online", "Über das Internet, mit Mitgliedschaft"],
  ["coop", "Koop", "Miteinander statt gegeneinander; bis IGDB dazukommt: laut HowLongToBeat gibt es eine Koop-Spielzeit"],
  ["handheld", "Handheld", "Unterwegs spielbar"], ["tv", "TV", "Am Fernseher spielbar"]];
// Mischungen: ein Klick setzt Filter und Sortierung (alles andere zurück), ein zweiter nimmt sie zurück
const G_MIXES = [
  ["surprise", "Überrasch mich", "Drei Spiele per Zufall aus dem, was die Filter gerade zeigen; gut bewertete kommen öfter", null],
  ["couch", "Couch-Abend", "Mindestens zwei an einer Konsole, die besten zuerst", {how: ["couch"], sort: "score"}],
  ["duo", "Koop zu zweit", "Koop für zwei, die besten zuerst", {how: ["coop"], pl: 2, sort: "score"}],
  ["big", "Große Runde", "Mindestens vier an einer Konsole", {how: ["couch"], pl: 4, sort: "score"}],
  ["online", "Online mit Freunden", "Mindestens zwei online", {how: ["online"], pl: 2, sort: "score"}],
  ["short", "Kurz und gut", "Höchstens fünf Stunden, Wertung ab 80", {hr: 5, sc: 80, sort: "score"}],
  ["go", "Für unterwegs", "Handheld, in zufälliger Folge", {how: ["handheld"], sort: "random"}]];
const gRand = a => () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
const gSeed = () => 1 + Math.floor(Math.random() * 2147483646);
const gNames = g => g.genre.map(x => x.n);
const gPl = (g, k) => (g.players[k] && g.players[k].v) ? g.players[k].v[1] : g.players[k] ? 2 : 0;   // online ohne Zahl: „ja“

/* Adresse: #spiele?… nur, solange die Ansicht offen ist */
function gHash(){
  const on = S.tab === "sammlung" && S.cview === "spiele";
  if(!on){ if(location.hash.startsWith("#spiele")) history.replaceState(null, "", location.pathname + location.search); return; }
  const p = new URLSearchParams();
  for(const [k, v] of Object.entries(S.g)) if(k !== "n" && String(v) !== String(G0[k])) p.set(k, Array.isArray(v) ? v.join(",") : v);
  const h = "#spiele" + (String(p) ? "?" + p : "");
  if(location.hash !== h) history.replaceState(null, "", location.pathname + location.search + h);
}
function gReadHash(){
  if(!location.hash.startsWith("#spiele")) return;
  S.tab = "sammlung"; S.cview = "spiele";
  const p = new URLSearchParams(location.hash.split("?")[1] || ""), d = Object.assign({}, G0, {g: [], how: []});
  for(const [k, v] of p){
    if(!(k in G0) || k === "n") continue;
    d[k] = Array.isArray(G0[k]) ? v.split(",").filter(Boolean) : typeof G0[k] === "number" ? (Number(v) || 0) : v;
  }
  S.g = d;
}
gReadHash();

function gFilter(d, games){
  const q = fold1(d.q);
  return games.filter(g => {
    if(d.sys === "s2" && !g.s2) return false;
    if(d.sys === "s1" && g.s2) return false;
    const names = gNames(g);
    if(d.g.length && !(d.gop === "and" ? d.g.every(x => names.includes(x)) : d.g.some(x => names.includes(x)))) return false;
    for(const h of d.how){
      if(h === "couch" && gPl(g, "offline") < Math.max(2, d.pl)) return false;
      if((h === "local" || h === "online") && gPl(g, h) < Math.max(2, d.pl || 0)) return false;
      if(h === "coop" && !g.coop) return false;
      if((h === "handheld" || h === "tv") && !g.modes.some(m => m.n === h)) return false;
    }
    if(d.pl && !d.how.some(h => ["couch", "local", "online"].includes(h)) && (g.max || 0) < d.pl) return false;
    if(d.sc && (g.score || 0) < d.sc) return false;
    if(d.hr > 0 && !(g.hours && g.hours <= d.hr)) return false;
    if(d.hr < 0 && !(g.hours && g.hours >= -d.hr)) return false;
    if(q && ![g.title, g.publisher, g.developer, ...names].some(t => t && fold1(t).includes(q))) return false;
    return true;
  });
}
function gSort(rows, d){
  if(d.sort === "random"){
    const r = gRand(d.seed || 1), a = rows.slice();
    for(let i = a.length - 1; i > 0; i--){ const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  }
  const by = {score: g => -(g.score ?? -1), hours: g => g.hours ?? 1e9, year: g => -(Number(g.released ? g.released.replace(/-/g, "") : 0)),
              players: g => -(g.max || 0), bought: g => -(g.bought ? Date.parse(g.bought) : 0)}[d.sort];
  return by ? rows.slice().sort((a, b) => by(a) - by(b) || a.title.localeCompare(b.title, "de")) : rows;
}
// Drei Vorschläge, gewichtet: jede Wertung über 60 macht ein Spiel wahrscheinlicher
function gPick(rows, seed, k = 3){
  const r = gRand(seed || 1), pool = rows.slice(), out = [], w = g => 1 + Math.max(0, (g.score ?? 65) - 60) / 8;
  while(out.length < k && pool.length){
    let x = r() * pool.reduce((s, g) => s + w(g), 0), i = 0;
    while(i < pool.length - 1 && (x -= w(pool[i])) > 0) i++;
    out.push(pool.splice(i, 1)[0]);
  }
  return out;
}
function gSetMix(k){
  const m = G_MIXES.find(x => x[0] === k);
  if(!m) return;
  if(m[3]) S.g = Object.assign({}, G0, {g: [], how: []}, JSON.parse(JSON.stringify(m[3])));
  S.g.mix = k; S.g.seed = gSeed(); S.g.n = G0.n;
}
const gLabel = d => [d.sys === "s2" ? "Switch 2" : d.sys === "s1" ? "nur Switch" : "", d.how.map(h => (G_HOW.find(x => x[0] === h) || [h, h])[1]).join(" + "),
  d.pl && `ab ${d.pl} Spieler`, d.g.join(d.gop === "and" ? " und " : " oder "), d.sc && `Wertung ab ${d.sc}`,
  d.hr > 0 ? `bis ${d.hr} Stunden` : d.hr < 0 ? `ab ${-d.hr} Stunden` : "", d.q && `„${d.q}“`].filter(Boolean).join(", ");

/* Zellen: ≈ heißt nur eine Quelle oder die Quellen sind sich nicht einig; der Tooltip sagt, welche */
const gApx = (tip, bad) => `<span class="approx gx${bad ? " bad" : ""}" title="${esc(tip)}">≈</span>`;   // grau; violett bei Widerspruch
const gHours = h => h === null || h === undefined ? "" : h < 1 ? "unter 1 h" : h < 10 ? `${String(Math.round(h * 2) / 2).replace(".", ",")} h` : `${Math.round(h)} h`;
const gRange = v => !v ? "ja" : v[0] === v[1] ? String(v[1]) : `${v[0]}–${v[1]}`;
function gPlayers(g, k){
  const p = g.players[k];
  if(!p) return "";
  const lab = {offline: "an einer Konsole", local: "lokal drahtlos", online: "online"}[k];
  const tip = p.ok ? `${lab}: DekuDeals und Nintendo einig` : p.alt ? `${lab}: DekuDeals ${gRange(p.v)}, Nintendo ${gRange(p.alt)}`
    : p.src === "Nintendo" ? `${lab}: nur laut Nintendo` : `${lab}: nur laut DekuDeals`;
  return `<span title="${esc(tip)}">${gRange(p.v)}</span>${p.ok ? "" : gApx(tip, !!p.alt)}`;
}
function gGenres(g){
  if(!g.genre.length) return g.read ? `<span class="mut">–</span>` : `<span class="mut" title="Die DekuDeals-Seite dieses Spiels ist noch nicht gelesen; je Abgleich höchstens 40 Seiten">folgt</span>`;
  return g.genre.map(x => esc(x.n) + (x.ok ? "" : gApx(x.src === "DekuDeals" ? "Nur laut DekuDeals" : "Nur laut Nintendo"))).join(", ");
}
function gScore(g){
  if(g.score === null || g.score === undefined) return "";
  const tip = [g.mc !== undefined && `Metacritic ${g.mc}`, g.mcu !== undefined && `Nutzer ${String(g.mcu).replace(".", ",")}`, g.oc !== undefined && `OpenCritic ${g.oc}`].filter(Boolean).join(", ");
  return `<span class="${g.score >= 85 ? "gn" : ""}" title="${esc(tip + " (über DekuDeals)")}">${g.score}</span>`;
}
function gYear(g){
  if(!g.year) return "";
  const tip = g.year_ok ? "DekuDeals und Nintendo einig" : g.year_alt ? `DekuDeals ${g.year}, Nintendo ${g.year_alt} (Erscheinen je Region verschieden)` : "Nur eine Quelle";
  return `<span title="${esc(tip)}">${esc(g.year)}</span>${g.year_ok ? "" : gApx(tip, !!g.year_alt)}`;
}
function gBadges(g){
  const b = [];
  if(g.s2) b.push(`<span class="chip s2c" title="${g.s2 === "edition" ? "Nintendo Switch 2 Edition" : g.s2 === "upgrade" ? "Mit Upgrade-Paket für die Switch 2" : "Spiel für die Switch 2"}">${g.s2 === "upgrade" ? "Switch-2-Upgrade" : g.s2 === "edition" ? "Switch 2 Edition" : "Switch 2"}</span>`);
  const ms = g.modes.map(m => m.n);
  if(ms.length && ms.length < 3) b.push(`<span class="chip" title="Spielmodi">nur ${ms.map(m => ({tv: "TV", tabletop: "Tisch", handheld: "Handheld"})[m]).join(", ")}</span>`);
  if(g.via) b.push(`<small class="mut">über ${esc(g.via)}</small>`);
  return b.join(" ");
}
function gRow(g, pick){
  const open = S.gOpen === g.slug && !pick;
  const coop = g.coop ? `<span title="Laut HowLongToBeat gibt es eine Koop-Spielzeit">ja</span>${gApx("Nur ein Hinweis: HowLongToBeat nennt eine Koop-Spielzeit. Genaue Koop-Angaben (lokal, online, wie viele) folgen mit IGDB")}` : "";
  const cells = [["c-gen", "Genre", gGenres(g)], ["c-pl", "Konsole", gPlayers(g, "offline")], ["c-pl", "Lokal", gPlayers(g, "local")],
    ["c-pl", "Online", gPlayers(g, "online")], ["c-pl", "Koop", coop], ["r", "Wertung", gScore(g)], ["r", "Spielzeit", g.hours ? `<span title="${esc(gHltbTip(g))}">${gHours(g.hours)}</span>` : ""], ["r", "Jahr", gYear(g)]];
  return `<div class="gr${open ? " open" : ""}"><span class="t"><button class="link g-n" data-act="gopen" data-s="${esc(g.slug)}" aria-expanded="${open}" title="Einzelheiten">${esc(g.title)}</button> ${gBadges(g)}</span>` +
    cells.map(([c, lab, v]) => `<span class="${c}${v ? "" : " nil"}" data-l="${lab}">${v}</span>`).join("") + `</div>` + (open ? gDetail(g) : "");
}
function gHltbTip(g){
  const h = g.hltb || {}, n = {main: "Hauptgeschichte", extra: "mit Nebenaufgaben", complete: "alles", solo: "allein", coop: "Koop", vs: "gegeneinander", all: "alle Spielweisen"};
  return "HowLongToBeat (über DekuDeals): " + Object.entries(h).map(([k, v]) => `${n[k] || k} ${gHours(v)}`).join(", ");
}
function gDetail(g){
  const c = ((S.state.collection || {}).games || []).find(x => x.slug === g.slug);
  const row = (l, v) => v ? `<span class="fl">${l}</span><span class="fv">${v}</span>` : "";
  const src = (ok, alt, one) => ok ? "" : alt ? gApx(`Nintendo: ${alt}`, true) : gApx(one || "Nur eine Quelle");
  const modes = g.modes.map(m => ({tv: "TV", tabletop: "Tisch", handheld: "Handheld"})[m.n] + (m.ok ? "" : gApx("Nur eine Quelle"))).join(", ");
  const h = g.hltb || {}, hn = {main: "Hauptgeschichte", extra: "mit Nebenaufgaben", complete: "alles", solo: "allein", coop: "Koop", vs: "gegeneinander", all: "alle Spielweisen"};
  const dlc = c ? `${c.have} von ${c.dlc.length} vorhanden${c.missing ? `, <span class="warnc">${c.missing}</span> ${c.missing === 1 ? "fehlt" : "fehlen"}` : ""} · <button class="link" data-act="gdlc" data-s="${esc(g.title)}">zu den DLC</button>` : "keine";
  return `<div class="gd facts">` +
    row("Spieler", ["offline", "local", "online"].filter(k => g.players[k]).map(k => `${gPlayers(g, k)} ${({offline: "an einer Konsole", local: "lokal drahtlos", online: "online"})[k]}`).join(", ")) +
    row("Spielmodi", modes) +
    row("Wertung", [g.mc !== undefined && `Metacritic ${g.mc}${g.mcu !== undefined ? ` (Nutzer ${String(g.mcu).replace(".", ",")})` : ""}`, g.oc !== undefined && `OpenCritic ${g.oc}`].filter(Boolean).join(" · ")) +
    row("Spielzeit", Object.entries(h).map(([k, v]) => `${hn[k] || k} ${gHours(v)}`).join(" · ")) +
    row("Erschienen", g.released ? `${esc(dmy(g.released.length > 4 ? g.released : g.released + "-01-01"))}${src(g.year_ok, g.year_alt)}` : "") +
    row("Entwickler", esc(g.developer || "")) +
    row("Verlag", g.publisher ? esc(g.publisher) + src(g.pub_ok, g.pub_alt) : "") +
    row("Alter", esc(g.age || "")) +
    row("Größe", g.size_gb ? `${String(g.size_gb).replace(".", ",")} GB` : "") +
    row("Gekauft", g.bought ? dmy(g.bought) : "") +
    row("DLC", dlc) +
    row("Quellen", `<a class="tl" href="${esc(deku(g.slug))}" target="_blank" rel="noopener">DekuDeals</a>${g.nin ? ", bestätigt von der Nintendo-Europa-Suche" : g.read ? ", noch nicht von Nintendo bestätigt" : ", Seite noch nicht gelesen"}`) +
    `</div>`;
}
function gMenu(k, head, n, body){
  return `<details class="gmenu" data-gm="${k}" ${S.gMenu === k ? "open" : ""}><summary>${head}${n ? ` <span class="cnt">${n}</span>` : ""}</summary><div class="pop">${body}</div></details>`;
}
function viewGames(){
  const sp = S.state.spiele || {games: [], genres: []}, all = sp.games, d = S.g;
  const rows = gSort(gFilter(d, all), d), pick = d.mix === "surprise" ? gPick(rows, d.seed) : [];
  const opt = (list, cur) => list.map(([v, l]) => `<option value="${esc(v)}"${String(v) === String(cur) ? " selected" : ""}>${esc(l)}</option>`).join("");
  const mixes = `<div class="chips gmix">${G_MIXES.map(([k, l, tip]) => `<button class="fb${d.mix === k ? " on" : ""}" data-act="${d.mix === k ? "gmixoff" : "gmix"}" data-v="${k}" title="${esc(d.mix === k ? "Zurücknehmen" : tip)}">${esc(l)}</button>`).join("")}</div>`;
  // Zahl hinter einem Genre: Spiele mit diesem Genre unter den übrigen Filtern
  const base = gFilter(Object.assign({}, d, {g: d.gop === "and" ? d.g : []}), all), gn = {};
  for(const g of base) for(const x of gNames(g)) gn[x] = (gn[x] || 0) + 1;
  const genres = gMenu("g", "Genre", d.g.length, `<span class="seg"><button data-act="ggop" data-v="" class="${d.gop !== "and" ? "on" : ""}" title="Spiele mit mindestens einem der Genres">eines davon</button><button data-act="ggop" data-v="and" class="${d.gop === "and" ? "on" : ""}" title="Nur Spiele mit allen gewählten Genres">alle</button></span>
    <div class="opts">${sp.genres.map(([x]) => `<label><input type="checkbox" data-gg="${esc(x)}"${d.g.includes(x) ? " checked" : ""}> ${esc(x)} <span class="mut">${gn[x] || 0}</span></label>`).join("")}</div>`);
  const hn = {};
  for(const [k] of G_HOW) hn[k] = gFilter(Object.assign({}, d, {how: d.how.includes(k) ? d.how : d.how.concat(k)}), all).length;
  const how = gMenu("how", "Spielweise", d.how.length, `<p class="hint">Mehrere gewählt: alle müssen passen.</p><div class="opts">${G_HOW.map(([k, l, tip]) => `<label title="${esc(tip)}"><input type="checkbox" data-gh="${k}"${d.how.includes(k) ? " checked" : ""}> ${esc(l)} <span class="mut">${hn[k]}</span></label>`).join("")}</div>`);
  const label = gLabel(d);
  const filters = `<div class="gfilter">
      <label>System <select data-gset="sys">${opt([["", "alle"], ["s2", "Switch 2"], ["s1", "nur Switch"]], d.sys)}</select></label>
      ${genres}${how}
      <label>Spieler <select data-gset="pl">${opt([[0, "egal"], [2, "ab 2"], [3, "ab 3"], [4, "ab 4"], [8, "ab 8"]], d.pl)}</select></label>
      <label>Wertung <select data-gset="sc">${opt([[0, "egal"], [70, "ab 70"], [80, "ab 80"], [90, "ab 90"]], d.sc)}</select></label>
      <label>Spielzeit <select data-gset="hr">${opt([[0, "egal"], [5, "bis 5 h"], [10, "bis 10 h"], [20, "bis 20 h"], [-40, "ab 40 h"]], d.hr)}</select></label></div>
    ${label ? `<div class="chips gact">${d.how.map(h => `<button class="fb" data-act="ghowoff" data-v="${h}" title="Filter entfernen">${esc((G_HOW.find(x => x[0] === h) || [h, h])[1])} ×</button>`).join("")}${d.g.map(x => `<button class="fb" data-act="ggoff" data-v="${esc(x)}" title="Filter entfernen">${esc(x)} ×</button>`).join("")}<button class="link" data-act="greset">alle Filter zurücksetzen</button></div>` : ""}`;
  const tools = `<div class="tools"><span class="sbox"><input type="search" id="gq" placeholder="Spiel, Genre oder Verlag" aria-label="Spiel, Genre oder Verlag suchen" value="${esc(d.q)}">${d.q ? `<button class="sx" data-act="gqclear" title="Suche leeren (Esc)">×</button>` : ""}</span>
    <label>Sortieren <select data-gset="sort">${opt(G_SORTS, d.sort)}</select></label>${d.sort === "random" ? `<button class="fb" data-act="gshuffle">Neu mischen</button>` : ""}${collSeg()}</div>`;
  const pickCard = d.mix === "surprise" ? `<section class="box gpick"><h3>Vorschlag${label ? ` <span class="mut">${esc(label)}</span>` : ""}</h3>
    ${pick.length ? `<div class="glist">${pick.map(g => gRow(g, true)).join("")}</div>` : `<p class="hint">Nichts passt zu den Filtern.</p>`}
    <p class="gpa"><button data-act="gmixoff" data-v="surprise">Schließen</button> <button class="primary" data-act="gmix" data-v="surprise">Noch mal</button></p></section>` : "";
  const head = `<div class="gr nph"><span>Spiel</span><span>Genre</span><span title="Spieler an einer Konsole (Couch, Splitscreen)">Konsole</span><span title="Spieler mit mehreren Konsolen im selben Raum">Lokal</span><span title="Spieler online">Online</span><span>Koop</span><span class="r" title="Metacritic, sonst OpenCritic">Wertung</span><span class="r" title="HowLongToBeat: Hauptgeschichte, sonst allein">Spielzeit</span><span class="r">Jahr</span></div>`;
  const note = `<p class="hint">${rows.length} von ${all.length} Spielen. Spielinfos von DekuDeals für ${sp.with_info}${sp.read < all.length ? ` (${all.length - sp.read} folgen bei den nächsten Abgleichen)` : ""}, bestätigt von Nintendo ${sp.confirmed}. ${gApx("Nur eine Quelle oder die Quellen sind sich nicht einig")} heißt: nur eine Quelle oder die Quellen sind sich nicht einig, der Tooltip sagt mehr. Wertung und Spielzeit von Metacritic, OpenCritic und HowLongToBeat über DekuDeals.</p>`;
  if(!all.length) return tools + `<p class="mut">Noch keine Spiele bekannt.</p>`;
  return tools + mixes + filters + pickCard + note +
    `<div class="glist box">${head}${rows.slice(0, d.n).map(g => gRow(g)).join("") || `<p class="mut">Kein Spiel passt zu den Filtern.</p>`}</div>` +
    (rows.length > d.n ? `<p class="gpa"><button data-act="gmore">weitere ${Math.min(G0.n, rows.length - d.n)} zeigen</button></p>` : "");
}
/* Umschalter der Sammlung: DLC | Spiele, gemerkt je Browser */
const collSeg = () => `<span class="seg">${[["dlc", "DLC", "Spiele mit ihren Zusatzinhalten: was du hast, was fehlt"], ["spiele", "Spiele", "Jedes Spiel mit Genre, Spielern, Koop, Wertung und Spielzeit, mit Filtern und Mischungen"]]
  .map(([v, l, tip]) => `<button data-act="cview" data-v="${v}" class="${(S.cview || "dlc") === v ? "on" : ""}" title="${tip}">${l}</button>`).join("")}</span>`;

/* Ereignisse der Ansicht */
document.addEventListener("click", e => {
  // Ein offenes Menü schließt bei einem Klick daneben
  if(S.gMenu && !e.target.closest(".gmenu")){ S.gMenu = null; document.querySelectorAll(".gmenu[open]").forEach(x => { x.open = false; }); }
  const el = e.target.closest("[data-act]");
  if(!el) return;
  const a = el.dataset.act, v = el.dataset.v, d = S.g;
  const done = () => { gHash(); render(); };
  if(a === "cview"){ S.cview = v; S.gOpen = null; saveView(); window.scrollTo(0, 0); done(); }
  else if(a === "gopen"){ S.gOpen = S.gOpen === el.dataset.s ? null : el.dataset.s; render(); }
  else if(a === "gdlc"){ S.cview = "dlc"; S.rq = el.dataset.s; saveView(); window.scrollTo(0, 0); done(); }
  else if(a === "gmix"){ gSetMix(v); done(); }
  else if(a === "gmixoff"){ if(v === "surprise"){ d.mix = ""; } else { S.g = Object.assign({}, G0, {g: [], how: []}); } done(); }
  else if(a === "gshuffle"){ d.seed = gSeed(); done(); }
  else if(a === "gmore"){ d.n += G0.n; render(); }
  else if(a === "ggop"){ d.gop = v; d.mix = ""; done(); }
  else if(a === "ggoff"){ d.g = d.g.filter(x => x !== v); d.mix = ""; done(); }
  else if(a === "ghowoff"){ d.how = d.how.filter(x => x !== v); d.mix = ""; done(); }
  else if(a === "greset"){ S.g = Object.assign({}, G0, {g: [], how: []}); done(); }
  else if(a === "gqclear"){ d.q = ""; done(); const q = $("gq"); if(q) q.focus(); }
});
document.addEventListener("toggle", e => {
  const k = e.target.dataset && e.target.dataset.gm;
  if(!k) return;
  if(e.target.open){ S.gMenu = k; document.querySelectorAll(".gmenu[open]").forEach(x => { if(x !== e.target) x.open = false; }); }
  else if(S.gMenu === k) S.gMenu = null;
}, true);
document.addEventListener("change", e => {
  const el = e.target, d = S.g;
  if(el.dataset.gset){ const k = el.dataset.gset; d[k] = typeof G0[k] === "number" ? Number(el.value) || 0 : el.value; if(k === "sort" && el.value === "random") d.seed = gSeed(); if(k !== "sort") d.mix = ""; d.n = G0.n; gHash(); render(); }
  else if(el.dataset.gg !== undefined){ const x = el.dataset.gg; d.g = el.checked ? d.g.concat(x) : d.g.filter(y => y !== x); d.mix = ""; d.n = G0.n; gHash(); render(); }
  else if(el.dataset.gh !== undefined){ const x = el.dataset.gh; d.how = el.checked ? d.how.concat(x) : d.how.filter(y => y !== x); d.mix = ""; d.n = G0.n; gHash(); render(); }
});
document.addEventListener("input", e => {
  if(e.target.id !== "gq") return;
  S.g.q = e.target.value; S.g.n = G0.n;
  const pos = e.target.selectionStart;
  gHash(); render();
  const q = $("gq"); if(q){ q.focus(); q.setSelectionRange(pos, pos); }
});
document.addEventListener("keydown", e => {
  if(e.key === "Escape" && S.gMenu){ S.gMenu = null; document.querySelectorAll(".gmenu[open]").forEach(x => { x.open = false; }); return; }
  if(e.key !== "Escape" || e.target.id !== "gq" || !S.g.q) return;
  e.preventDefault(); S.g.q = ""; gHash(); render(); const q = $("gq"); if(q) q.focus();
});
