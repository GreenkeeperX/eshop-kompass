"use strict";
/* Sammlung, Ansicht „Spiele“ (1.6.1): jedes Spiel mit Genre, Spielern, Koop, Wertung, Spielzeit und Jahr;
   Filter, Sortierung, Mischungen und „Überrasch mich“ nach dem Vorbild von „Entdecken“ im VR-Navigator.
   Daten aus S.state.spiele (planner.game_infos). Filter laufen im Browser und stehen in der Adresse
   (#spiele?…), eine Mischung lässt sich so als Lesezeichen merken (Teil der Oberfläche, Reihenfolge in index.html) */
const G0 = {sys: "", g: [], gop: "", how: [], pl: 0, sc: 0, hr: 0, st: "", q: "", sort: "name", seed: 0, mix: ""};
S.g = Object.assign({}, G0, {g: [], how: []});
S.gOpen = null;
S.gMenu = null;
const G_SORTS = [["name", "Name"], ["score", "Wertung"], ["hours", "Spielzeit, kurz zuerst"], ["year", "Erscheinen, neu zuerst"],
  ["players", "Spieler, die meisten zuerst"], ["random", "Zufall"]];
// Spielweisen: mehrere gewählt heißt, alle müssen passen
const G_HOW = [["couch", "An einer Konsole (ab 2)", "Mehrere Spieler an einer Konsole: Couch, Splitscreen, geteilte Joy-Con"],
  ["local", "Lokal drahtlos", "Mehrere Konsolen im selben Raum"], ["online", "Online", "Über das Internet, mit Mitgliedschaft"],
  ["coop", "Koop", "Miteinander statt gegeneinander: laut IGDB, sonst kennt HowLongToBeat eine Koop-Spielzeit"],
  ["coopl", "Koop an einer Konsole", "Laut IGDB Koop lokal"], ["coopo", "Koop online", "Laut IGDB Koop online"],
  ["gs", "GameShare", "Laut Nintendos Liste mit GameShare: Freunde spielen mit, ohne das Spiel zu haben"],
  ["handheld", "Handheld", "Unterwegs spielbar"], ["tv", "TV", "Am Fernseher spielbar"]];
// Mischungen: ein Klick setzt Filter und Sortierung (alles andere zurück), ein zweiter nimmt sie zurück
const G_MIXES = [
  ["surprise", "Überrasch mich", "Drei Spiele per Zufall aus dem, was die Filter gerade zeigen; gut bewertete kommen öfter", null],
  ["couch", "Couch-Abend", "Mindestens zwei an einer Konsole, die besten zuerst", {how: ["couch"], sort: "score"}],
  ["duo", "Koop zu zweit", "Koop für zwei, die besten zuerst", {how: ["coop"], pl: 2, sort: "score"}],
  ["big", "Große Runde", "Mindestens vier an einer Konsole", {how: ["couch"], pl: 4, sort: "score"}],
  ["online", "Online mit Freunden", "Mindestens zwei online", {how: ["online"], pl: 2, sort: "score"}],
  ["short", "Kurz und gut", "Höchstens fünf Stunden, Wertung ab 80", {hr: 5, sc: 80, sort: "score"}],
  ["go", "Für unterwegs", "Handheld, in zufälliger Folge", {how: ["handheld"], sort: "random"}],
  ["backlog", "Aus dem Backlog", "Was du dir zum Spielen vorgenommen hast, die besten zuerst; „Überrasch mich“ wählt dann daraus", {st: "backlog", sort: "score"}]];
// Mein Stand (1.7.1): von Hand je Spiel, in den Einstellungen gespeichert (game_marks) und damit in der Sicherung
const G_ST = [["backlog", "Backlog", "○", "Willst du spielen, noch nicht angefangen"], ["started", "angefangen", "▶", "Angefangen"],
  ["done", "durchgespielt", "✓", "Durchgespielt"]];
const G_STF = [["", "egal"], ["open", "nicht durchgespielt"], ["backlog", "Backlog"], ["started", "angefangen"], ["done", "durchgespielt"],
  ["fav", "Favoriten"], ["none", "ohne Stand"]];
const gRand = a => () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
const gSeed = () => 1 + Math.floor(Math.random() * 2147483646);
const gNames = g => g.genre.map(x => x.n);
const gPl = (g, k) => (g.players[k] && g.players[k].v) ? g.players[k].v[1] : g.players[k] ? 2 : 0;   // online ohne Zahl: „ja“

/* Adresse: #spiele?… nur, solange die Ansicht offen ist */
function gHash(){
  const on = S.tab === "sammlung" && S.cview === "spiele";
  if(!on){ if(location.hash.startsWith("#spiele")) history.replaceState(null, "", location.pathname + location.search); return; }
  const p = new URLSearchParams();
  for(const [k, v] of Object.entries(S.g)) if(String(v) !== String(G0[k])) p.set(k, Array.isArray(v) ? v.join(",") : v);
  const h = "#spiele" + (String(p) ? "?" + p : "");
  if(location.hash !== h) history.replaceState(null, "", location.pathname + location.search + h);
}
function gReadHash(){
  if(!location.hash.startsWith("#spiele")) return;
  S.tab = "sammlung"; S.cview = "spiele";
  const p = new URLSearchParams(location.hash.split("?")[1] || ""), d = Object.assign({}, G0, {g: [], how: []});
  for(const [k, v] of p){
    if(!(k in G0)) continue;
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
      if(h === "coopl" && !(g.coop && g.coop.local)) return false;
      if(h === "coopo" && !(g.coop && g.coop.online)) return false;
      if(h === "gs" && !g.gs) return false;
      if((h === "handheld" || h === "tv") && !g.modes.some(m => m.n === h)) return false;
    }
    if(d.pl && !d.how.some(h => ["couch", "local", "online"].includes(h)) && (g.max || 0) < d.pl) return false;
    const m = g.mine || {};
    if(d.st && !(d.st === "open" ? m.s !== "done" : d.st === "fav" ? m.fav : d.st === "none" ? !m.s && !m.fav : m.s === d.st)) return false;
    if(d.sc && (g.score || 0) < d.sc) return false;
    if(d.hr > 0 && !(g.hours && g.hours <= d.hr)) return false;
    if(d.hr < 0 && !(g.hours && g.hours >= -d.hr)) return false;
    if(q && ![g.title, g.publisher, g.developer, ...names].some(t => t && fold1(t).includes(q))) return false;
    return true;
  });
}
function gSort(rows, d){
  if(d.sort === "random" && !S.sorts.spiele){
    const r = gRand(d.seed || 1), a = rows.slice();
    for(let i = a.length - 1; i > 0; i--){ const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  }
  const by = {score: g => -(g.score ?? -1), hours: g => g.hours ?? 1e9, year: g => -(Number(g.released ? g.released.replace(/-/g, "") : 0)),
              players: g => -(g.max || 0)}[d.sort];
  const out = by ? rows.slice().sort((a, b) => by(a) - by(b) || a.title.localeCompare(b.title, "de")) : rows;
  return sortRows("spiele", out, G_COLS);
}
// Spaltenköpfe (1.7.0): Klick sortiert wie in der Wishlist; Zahlen, bei denen mehr besser ist, zuerst absteigend
const G_COLS = {title: g => g.title, offline: g => gPl(g, "offline") || null, local: g => gPl(g, "local") || null,
  online: g => gPl(g, "online") || null, coop: g => !g.coop ? null : Math.max(+g.coop.local || 0, +g.coop.online || 0, 1), genre: g => g.genre.length ? g.genre[0].n : null,
  mc: g => g.score ?? null, hours: g => g.hours ?? null, year: g => g.released || null};
function gTh(k, label, tip, cls = "", d0 = 1){
  const s = S.sorts.spiele, on = !!(s && s.k === k);
  return `<span class="sth ${on ? "on" : ""} ${cls}" role="columnheader" tabindex="0" data-act="tsort" data-t="spiele" data-k="${k}"${d0 < 0 ? ` data-d0="-1"` : ""} title="${esc(tip ? tip + " · " : "")}Klick sortiert"${on ? ` aria-sort="${s.dir > 0 ? "ascending" : "descending"}"` : ""}>${label}<span class="sa">${on ? (s.dir > 0 ? "▲" : "▼") : ""}</span></span>`;
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
  S.g.mix = k; S.g.seed = gSeed(); delete S.sorts.spiele;
}
const gLabel = d => [d.sys === "s2" ? "Switch 2" : d.sys === "s1" ? "nur Switch" : "", d.how.map(h => (G_HOW.find(x => x[0] === h) || [h, h])[1]).join(" + "),
  d.pl && `ab ${d.pl} Spieler`, d.g.join(d.gop === "and" ? " und " : " oder "), d.sc && `Wertung ab ${d.sc}`,
  d.hr > 0 ? `bis ${d.hr} Stunden` : d.hr < 0 ? `ab ${-d.hr} Stunden` : "", d.st && (G_STF.find(x => x[0] === d.st) || ["", ""])[1], d.q && `„${d.q}“`].filter(Boolean).join(", ");

/* Herkunft (1.6.2, Entscheidung 27.10.2026): kein Zeichen. DekuDeals gilt; nennt Nintendo etwas anderes,
   ist der Wert dezent violett, beide Werte stehen im Tooltip. Leer heißt grauer Strich (1.7.0) */
const G_NIL = `<span class="mut">–</span>`;
const gVal = (v, tip, bad) => `<span class="${bad ? "gxc" : ""}" title="${esc(tip)}">${v}</span>`;
const gHours = h => h === null || h === undefined ? "" : h < 1 ? "unter 1 h" : h < 10 ? `${String(Math.round(h * 2) / 2).replace(".", ",")} h` : `${Math.round(h)} h`;
const gRange = v => !v ? "ja" : v[0] === v[1] ? String(v[1]) : `${v[0]}–${v[1]}`;
function gPlayers(g, k){
  const p = g.players[k];
  if(!p) return "";
  const lab = {offline: "an einer Konsole", local: "lokal drahtlos", online: "online"}[k];
  const tip = (p.ok ? `${lab}: DekuDeals und Nintendo einig` : p.alt ? `${lab}: DekuDeals ${gRange(p.v)}, Nintendo ${gRange(p.alt)}`
    : p.src === "Nintendo" ? `${lab}: nur laut Nintendo` : `${lab}: nur laut DekuDeals`) +
    (k === "online" && g.paid_online ? ". Braucht die Online-Mitgliedschaft (Nintendo)" : "");
  return gVal(gRange(p.v), tip, !!p.alt);
}
/* Genres als Blasen (1.7.0): höchstens zwei, der Rest als „+n“ mit Tooltip. Die Reihenfolge ist in jeder
   Zeile dieselbe (planner.game_infos: seltenere zuerst), so steht ein Genre immer gleich zu den anderen */
function gGenres(g){
  if(!g.genre.length) return g.read ? "" : `<span class="mut" title="Die DekuDeals-Seite dieses Spiels ist noch nicht gelesen; je Abgleich höchstens 40 Seiten">folgt</span>`;
  const src = g.genre[0].src === "Nintendo" ? "Genre laut Nintendo" : "Genre laut DekuDeals (Nintendo nennt keines)";
  const rest = g.genre.slice(2).map(x => x.n);
  return `<span class="gtags" title="${esc(src + ": " + g.genre.map(x => x.n).join(", "))}">${g.genre.slice(0, 2).map(x => `<span class="chip">${esc(x.n)}</span>`).join("")}${rest.length ? `<span class="chip more">+${rest.length}</span>` : ""}</span>`;
}
/* Wertung (1.7.0, Entscheidung 27.10.2026): Metacritic. Fehlt sie, steht OpenCritic grau und kursiv da */
function gScore(g){
  const more = [g.mcu !== undefined && `Metacritic-Nutzer ${String(g.mcu).replace(".", ",")}`, g.oc !== undefined && `OpenCritic ${g.oc}`].filter(Boolean).join(", ");
  if(g.mc !== undefined) return `<span class="${g.mc >= 85 ? "gn" : ""}" title="${esc(`Metacritic ${g.mc}${more ? `; ${more}` : ""} (über DekuDeals)`)}">${g.mc}</span>`;
  if(g.oc !== undefined) return `<span class="galt" title="${esc(`Keine Metacritic-Wertung. OpenCritic ${g.oc} (über DekuDeals)`)}">${g.oc}</span>`;
  return "";
}
function gYear(g){
  if(!g.year) return "";
  const tip = g.year_ok ? "DekuDeals und Nintendo einig" : g.year_alt ? `DekuDeals ${g.year}, Nintendo ${g.year_alt} (Erscheinen je Region verschieden)` : "Nur eine Quelle";
  return gVal(esc(g.year), tip, !!g.year_alt);
}
/* Marken hinter dem Titel (1.7.0), knapp wie DE✓: Switch 2, abweichende Spielmodi, Paket */
const G_MODE = {tv: "TV", tabletop: "Tisch", handheld: "Handheld"};
function gBadges(g){
  const b = [], m = g.mine || {}, st = G_ST.find(x => x[0] === m.s);
  if(st || m.fav) b.push(`<span class="gme">${st ? `<span class="gst ${m.s}" title="Mein Stand: ${st[1]}">${st[2]}</span>` : ""}${m.fav ? `<span class="gfav" title="Favorit">★</span>` : ""}</span>`);
  // Die Switch 2 Edition steht schon im Namen
  if(g.s2 && g.s2 !== "edition") b.push(`<span class="lgt de" title="${g.s2 === "upgrade" ? "Mit Upgrade-Paket für die Switch 2, das du hast" : "Spiel für die Switch 2"}">${g.s2 === "upgrade" ? "S2-Upgrade" : "Switch 2"}</span>`);
  const ms = g.modes.map(m => m.n), miss = ["tv", "tabletop", "handheld"].filter(m => !ms.includes(m));
  if(ms.length && miss.length){
    const lab = miss.length === 1 ? `ohne ${G_MODE[miss[0]]}` : `nur ${ms.map(m => G_MODE[m]).join(", ")}`;
    b.push(`<span class="lgt de" title="${esc(`Spielbar: ${ms.map(m => G_MODE[m]).join(", ")}. Nicht: ${miss.map(m => G_MODE[m]).join(", ")}`)}">${lab}</span>`);
  }
  // GameShare (1.7.2): laut Nintendos Liste der hervorgehobenen Spiele
  if(g.gs) b.push(`<span class="lgt de" title="${esc(`GameShare laut Nintendo: ${[g.gs.local && "lokal", g.gs.online && "online über GameChat"].filter(Boolean).join(" und ")}. Freunde spielen mit, ohne das Spiel zu haben`)}">GameShare</span>`);
  // Sprachen (1.7.1): markiert wird nur die Ausnahme, ein Spiel ohne Deutsch
  if(g.langs && g.langs.length && !g.langs.includes("german")) b.push(`<span class="lgt no" title="${esc("Laut Nintendo Europa ohne Deutsch. Sprachen: " + langDe(g.langs.join(", ")))}">ohne Deutsch</span>`);
  return b.join("");
}
function gRow(g, pick){
  const open = S.gOpen === g.slug && !pick;
  const coop = gCoop(g);
  const cells = [["c-pl", "Konsole", gPlayers(g, "offline")], ["c-pl", "Lokal", gPlayers(g, "local")], ["c-pl", "Online", gPlayers(g, "online")],
    ["c-pl", "Koop", coop], ["c-gen", "Genre", gGenres(g)], ["r", "Metacritic", gScore(g)],
    ["r", "Spielzeit", g.hours ? `<span title="${esc(gHltbTip(g))}">${gHours(g.hours)}</span>` : ""], ["r", "Jahr", gYear(g)]];
  const tip = g.title + (g.via ? ` · aus: ${g.via}` : "") + " · Einzelheiten";
  return `<div class="gr${open ? " open" : ""}"><span class="t"><button class="link g-n" data-act="gopen" data-s="${esc(g.slug)}" aria-expanded="${open}" title="${esc(tip)}">${esc(g.title)}</button>${gBadges(g)}${g.via ? `<small class="mut gvia" title="${esc("Hast du im Paket " + g.via)}">aus: ${esc(g.via)}</small>` : ""}</span>` +
    cells.map(([c, lab, v]) => `<span class="${c}${v ? "" : " nil"}" data-l="${lab}">${v || G_NIL}</span>`).join("") + `</div>` + (open ? gDetail(g) : "");
}
const G_FILLED = {genre: "Genre", players: "Spieler", modes: "Spielmodi", mc: "Wertung", mcu: "Wertung", oc: "Wertung", hltb: "Spielzeit",
  released: "Erscheinen", developer: "Entwickler", publisher: "Verlag", age: "Alter", size_gb: "Größe", platform: "System"};
const G_HLTB = {main: "Story", extra: "mit Nebenaufgaben", complete: "insgesamt", solo: "allein", coop: "Koop", vs: "gegeneinander", all: "alle Spielweisen"};
/* Koop (1.7.2): von IGDB lokal, online oder beides, Höchstzahl im Tooltip; sonst „ja“ als Hinweis von HowLongToBeat */
function gCoopTip(c){
  if(!c) return "";
  if(c.src !== "IGDB") return "Nur ein Hinweis: HowLongToBeat kennt eine Koop-Spielzeit";
  const n = v => v === true ? "" : ` bis ${v}`;
  return "Koop laut IGDB: " + ([c.local && `an einer Konsole${n(c.local)}`, c.online && `online${n(c.online)}`, c.split && "geteilter Bildschirm"].filter(Boolean).join(", ") || "ja, ohne Einzelheiten");
}
function gCoop(g){
  const c = g.coop;
  if(!c) return "";
  const lab = c.local && c.online ? "beides" : c.local ? "lokal" : c.online ? "online" : "ja";
  return `<span title="${esc(gCoopTip(c))}">${lab}</span>`;
}
function gHltbTip(g){
  return "HowLongToBeat (über DekuDeals): " + Object.entries(g.hltb || {}).map(([k, v]) => `${G_HLTB[k] || k} ${gHours(v)}`).join(", ");
}
/* Einzelheiten (1.7.0): oben, was beim Aussuchen hilft (Wertung, Spielzeit, DLC, Erscheinen, USK), darunter
   klein der Rest. Was schon in der Zeile steht (Spieler, Genre), kommt nur bei Mehrwert wieder: wenn
   Nintendo etwas anderes nennt */
function gDetail(g){
  const c = ((S.state.collection || {}).games || []).find(x => x.slug === g.slug);
  const item = (l, v, tip) => v ? `<span class="gdi"${tip ? ` title="${esc(tip)}"` : ""}><span class="fl">${l}</span><span class="fv">${v}</span></span>` : "";
  const num = v => String(v).replace(".", ",");
  const score = [g.mc !== undefined && `Metacritic <b>${g.mc}</b>`, g.mcu !== undefined && `Nutzer ${num(g.mcu)}`, g.oc !== undefined && `OpenCritic ${g.oc}`].filter(Boolean).join(" · ");
  const hltb = Object.entries(g.hltb || {}).map(([k, v]) => `${G_HLTB[k] || k} ${gHours(v)}`).join(" · ");
  const dlc = c && c.dlc.length ? `${collSum(c)} · <button class="link" data-act="gdlc" data-s="${esc(g.title)}">zu den DLC</button>` : "";
  const who = [g.developer && `Entwickler: ${g.developer}`, g.publisher && `Verlag: ${g.publisher}${g.pub_alt ? ` (Nintendo: ${g.pub_alt})` : ""}`].filter(Boolean).join("\n");
  const rel = g.released ? `${esc(g.released.length > 4 ? dmy(g.released) : g.released)}${g.year_alt ? ` <span class="gxc">(Nintendo: ${esc(g.year_alt)})</span>` : ""}` : "";
  const age = g.usk ? `${esc(g.usk)}` : g.pegi ? `<span title="Keine USK-Angabe">PEGI ${esc(g.pegi)}</span>` : "";
  const ageTip = [g.usk && `USK ${g.usk}`, g.pegi && `PEGI ${g.pegi}`].filter(Boolean).join(", ");
  const odd = ["offline", "local", "online"].filter(k => g.players[k] && g.players[k].alt)
    .map(k => `${({offline: "an einer Konsole", local: "lokal drahtlos", online: "online"})[k]} <span class="gxc">DekuDeals ${gRange(g.players[k].v)}, Nintendo ${gRange(g.players[k].alt)}</span>`).join(" · ");
  const m = g.mine || {};
  const mine = `<span class="seg gmark">${G_ST.map(([k, l, ic, tip]) => `<button data-act="gmark" data-s="${esc(g.slug)}" data-k="s" data-v="${m.s === k ? "" : k}" class="${m.s === k ? "on" : ""}" title="${esc(m.s === k ? "Zurücknehmen" : tip)}">${ic} ${l}</button>`).join("")}</span> <button class="fb gfavb${m.fav ? " on" : ""}" data-act="gmark" data-s="${esc(g.slug)}" data-k="fav" data-v="${m.fav ? "" : "1"}" title="${m.fav ? "Kein Favorit mehr" : "Als Favorit merken"}">${m.fav ? "★" : "☆"} Favorit</button>`;
  const top = item("Mein Stand", mine) + item("Wertung", score) + item("Spielzeit", hltb, "HowLongToBeat, über DekuDeals") + item("DLC", dlc) +
    item("Erschienen", rel, who || "") + item("USK", age, ageTip) + (odd ? item("Spieler", odd, "DekuDeals und Nintendo nennen verschiedene Zahlen") : "") +
    (g.coop && g.coop.src === "IGDB" ? item("Koop", esc(gCoopTip(g.coop).replace("Koop laut IGDB: ", "")), "IGDB") : "") +
    (g.gs ? item("GameShare", [g.gs.local && "lokal", g.gs.online && "online"].filter(Boolean).join(", "), "Laut Nintendos Liste der hervorgehobenen GameShare-Spiele") : "") +
    (g.paid_online ? item("Online", "mit Mitgliedschaft", "Laut Nintendo braucht das Online-Spiel die Nintendo Switch Online-Mitgliedschaft") : "");
  const pk = g.pack ? `aus ${esc(g.pack.title)}${g.pack.filled && g.pack.filled.length ? ` <span title="${esc("Von der Seite des Pakets, weil die Seite des Spiels sie nicht nennt: " + g.pack.filled.map(k => G_FILLED[k] || k).filter((x, i, a) => a.indexOf(x) === i).join(", "))}">(Angaben teils vom Paket)</span>` : ""}` : "";
  const langs = g.langs && g.langs.length ? `<span title="${esc("Sprachen laut Nintendo Europa: " + langDe(g.langs.join(", ")))}">${g.langs.includes("german") ? `Deutsch${g.langs.length > 1 ? ` und ${g.langs.length - 1} weitere Sprachen` : ""}` : `<span class="gno">ohne Deutsch</span>`}</span>` : "";
  const small = [langs, g.size_gb && `${num(g.size_gb)} GB`, g.bought && `gekauft am ${dmy(g.bought)}`, pk,
    `<a class="tl" href="${esc(deku(g.slug))}" target="_blank" rel="noopener">DekuDeals</a>${g.nin ? ", von Nintendo geprüft" : g.read ? ", noch nicht von Nintendo geprüft" : ", Seite noch nicht gelesen"}`].filter(Boolean).join(" · ");
  return `<div class="gd">${top ? `<div class="gdt">${top}</div>` : ""}<p class="hint gds">${small}</p></div>`;
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
      <label>Spielzeit <select data-gset="hr">${opt([[0, "egal"], [5, "bis 5 h"], [10, "bis 10 h"], [20, "bis 20 h"], [-40, "ab 40 h"]], d.hr)}</select></label>
      <label title="Dein Stand je Spiel, setzt du in den Einzelheiten">Mein Stand <select data-gset="st">${opt(G_STF, d.st)}</select></label></div>
    ${label ? `<div class="chips gact">${d.how.map(h => `<button class="fb" data-act="ghowoff" data-v="${h}" title="Filter entfernen">${esc((G_HOW.find(x => x[0] === h) || [h, h])[1])} ×</button>`).join("")}${d.g.map(x => `<button class="fb" data-act="ggoff" data-v="${esc(x)}" title="Filter entfernen">${esc(x)} ×</button>`).join("")}<button class="link" data-act="greset">alle Filter zurücksetzen</button></div>` : ""}`;
  const tools = `<div class="tools"><span class="sbox"><input type="search" id="gq" placeholder="Spiel, Genre oder Verlag" aria-label="Spiel, Genre oder Verlag suchen" value="${esc(d.q)}">${d.q ? `<button class="sx" data-act="gqclear" title="Suche leeren (Esc)">×</button>` : ""}</span>
    <label>Sortieren <select data-gset="sort">${S.sorts.spiele ? `<option value="" selected>nach Spalte</option>` : ""}${opt(G_SORTS, S.sorts.spiele ? "" : d.sort)}</select></label>${d.sort === "random" && !S.sorts.spiele ? `<button class="fb" data-act="gshuffle">Neu mischen</button>` : ""}</div>`;
  const pickCard = d.mix === "surprise" ? `<section class="box gpick"><h3>Vorschlag${label ? ` <span class="mut">${esc(label)}</span>` : ""}</h3>
    ${pick.length ? `<div class="glist">${pick.map(g => gRow(g, true)).join("")}</div>` : `<p class="hint">Nichts passt zu den Filtern.</p>`}
    <p class="gpa"><button data-act="gmixoff" data-v="surprise">Schließen</button> <button class="primary" data-act="gmix" data-v="surprise">Noch mal</button></p></section>` : "";
  const head = `<div class="gr nph" role="row"><span class="gh-sp" aria-hidden="true">Spieler</span>${gTh("title", "Spiel", "", "gh-t")}${gTh("offline", "Konsole", "Spieler an einer Konsole (Couch, Splitscreen)", "", -1)}${gTh("local", "Lokal", "Spieler mit mehreren Konsolen im selben Raum", "", -1)}${gTh("online", "Online", "Spieler online", "", -1)}${gTh("coop", "Koop", "Laut IGDB: lokal, online oder beides; „ja“: nur ein Hinweis von HowLongToBeat", "", -1)}${gTh("genre", "Genre", "Von Nintendo, sonst DekuDeals")}${gTh("mc", "Metacritic", "Grau und kursiv: keine Metacritic-Wertung, dafür OpenCritic", "r", -1)}${gTh("hours", "Spielzeit", "HowLongToBeat: Story, sonst allein", "r")}${gTh("year", "Jahr", "", "r", -1)}</div>`;
  const note = `<p class="hint">${rows.length === all.length ? `Alle ${all.length} Spiele` : `${rows.length} von ${all.length} Spielen`}. Angaben von DekuDeals, Nintendo prüft gegen: violett heißt, Nintendo nennt etwas anderes (Tooltip). Genre von Nintendo.</p>`;
  if(!all.length) return collTop() + tools + `<p class="mut">Noch keine Spiele bekannt.</p>`;
  return collTop() + tools + mixes + filters + pickCard + note +
    `<div class="glist box">${head}${rows.map(g => gRow(g)).join("") || `<p class="mut">Kein Spiel passt zu den Filtern.</p>`}</div>` +
    "";
}
/* Kopfzeile beider Ansichten der Sammlung (1.6.2): was in der Sammlung steht, rechts der Umschalter. Steht
   in beiden Ansichten an derselben Stelle, damit er beim Wechseln nicht springt */
function collTop(){
  const sp = S.state.spiele || {};
  if(!sp.entries) return `<div class="ctop"><span></span>${collSeg()}</div>`;
  // 1.7.0: Pakete sind keine eigene Zeile mehr, gezählt werden ihre Spiele
  const pk = sp.packs ? `${sp.packs} ${sp.packs === 1 ? "Paket" : "Pakete"} mit ${sp.via_packs} ${sp.via_packs === 1 ? "Spiel" : "Spielen"}` : "";
  const why = [`${sp.entries} Einträge bei DekuDeals`, [sp.dlc_entries ? `davon ${sp.dlc_entries} DLC` : "", pk].filter(Boolean).join(" und ")].filter(Boolean).join(", ");
  return `<div class="ctop"><span><b>${sp.games.length}</b> Spiele <span class="mut">(${why})</span></span>${collSeg()}</div>`;
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
  else if(a === "gmark"){
    // Sofort zeigen, dann speichern; ein Fehler lädt den Stand des Servers neu
    const g = ((S.state.spiele || {}).games || []).find(x => x.slug === el.dataset.s), k = el.dataset.k;
    if(!g) return;
    const val = k === "fav" ? (v ? true : null) : (v || null);
    g.mine = Object.assign({}, g.mine); if(val) g.mine[k] = val; else delete g.mine[k];
    render();
    api("/api/settings", {game_marks: {[g.slug]: {[k]: val}}}).catch(() => refresh());
  }
  else if(a === "gdlc"){ S.cview = "dlc"; S.rq = el.dataset.s; saveView(); window.scrollTo(0, 0); done(); }
  else if(a === "gmix"){ gSetMix(v); done(); }
  else if(a === "gmixoff"){ if(v === "surprise"){ d.mix = ""; } else { S.g = Object.assign({}, G0, {g: [], how: []}); } done(); }
  else if(a === "gshuffle"){ d.seed = gSeed(); done(); }
  else if(a === "ggop"){ d.gop = v; d.mix = ""; done(); }
  else if(a === "ggoff"){ d.g = d.g.filter(x => x !== v); d.mix = ""; done(); }
  else if(a === "ghowoff"){ d.how = d.how.filter(x => x !== v); d.mix = ""; done(); }
  else if(a === "greset"){ S.g = Object.assign({}, G0, {g: [], how: []}); delete S.sorts.spiele; saveView(); done(); }
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
  if(el.dataset.gset){ const k = el.dataset.gset; if(k === "sort"){ delete S.sorts.spiele; saveView(); if(!el.value) return; } d[k] = typeof G0[k] === "number" ? Number(el.value) || 0 : el.value; if(k === "sort" && el.value === "random") d.seed = gSeed(); if(k !== "sort") d.mix = ""; gHash(); render(); }
  else if(el.dataset.gg !== undefined){ const x = el.dataset.gg; d.g = el.checked ? d.g.concat(x) : d.g.filter(y => y !== x); d.mix = ""; gHash(); render(); }
  else if(el.dataset.gh !== undefined){ const x = el.dataset.gh; d.how = el.checked ? d.how.concat(x) : d.how.filter(y => y !== x); d.mix = ""; gHash(); render(); }
});
document.addEventListener("input", e => {
  if(e.target.id !== "gq") return;
  S.g.q = e.target.value;
  const pos = e.target.selectionStart;
  gHash(); render();
  const q = $("gq"); if(q){ q.focus(); q.setSelectionRange(pos, pos); }
});
document.addEventListener("keydown", e => {
  if(e.key === "Escape" && S.gMenu){ S.gMenu = null; document.querySelectorAll(".gmenu[open]").forEach(x => { x.open = false; }); return; }
  if(e.key !== "Escape" || e.target.id !== "gq" || !S.g.q) return;
  e.preventDefault(); S.g.q = ""; gHash(); render(); const q = $("gq"); if(q) q.focus();
});
