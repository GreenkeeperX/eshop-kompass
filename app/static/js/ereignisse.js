"use strict";
/* Klicks und Eingaben, Kopfleiste, Start der Seite (Teil der Oberfläche, Reihenfolge in index.html) */
/* ---------- Ereignisse ---------- */
function goKorb(){ S.tview = "korb"; go("titel"); }
function go(tab, top = true){ S.tab = tab; saveView(); if(top) window.scrollTo(0, 0); render(); if(top) window.scrollTo(0, 0); }   // erst nach oben, sonst misst fitMatrix die alte Lage
/* Länderkarten: Steht ein Land im Kaufplan, zeigt seine Karte den Korb des Plans, damit
   Preise und Summen mit „Jetzt“ übereinstimmen (die Kartenkosten hängen am ganzen Korb).
   Eigene Änderungen an der Karte gehen vor. */
function planStepFor(code){
  if(!S.kauf) return null;
  const n = S.kauf.steps.findIndex(st => st.code === code);
  if(n < 0) return null;
  const st = S.kauf.steps[n], slugs = new Set(st.items.map(i => i.slug)), o = S.ui.overrides[code];
  if(o && ((o.add || []).length || (o.remove || []).some(x => slugs.has(x)))) return null;
  return {st, n};
}
function cardPlans(){
  return S.plans.map(own => {
    const f = !own.is_ref && planStepFor(own.code);
    return f ? Object.assign({}, f.st, {from_step: f.n + 1, own_slugs: own.items.map(i => i.slug), current: own.current}) : own;
  });
}
function ov(code){
  const p = cardPlans().find(x => x.code === code);
  if(p && p.from_step){
    // Erste Änderung an einer Karte mit Plan-Korb: vom Plan-Korb ausgehen, nicht vom eigenen
    const own = new Set(p.own_slugs), plan = p.items.map(i => i.slug), prev = S.ui.overrides[code] || {add:[], remove:[]};
    S.ui.overrides[code] = {add: plan.filter(x => !own.has(x)),
                            remove: [...new Set([...(prev.remove || []), ...[...own].filter(x => !plan.includes(x))])]};
  }
  return S.ui.overrides[code] || (S.ui.overrides[code] = {add:[], remove:[]});
}
// Ohne Land: der gemeinsame Korb; mit Land: der Korb dieses Landes (ab 0.59 getrennt)
function addTo(code, slugs){
  if(!code){ S.ui.basket = S.ui.basket || []; for(const s of slugs) if(!S.ui.basket.includes(s)) S.ui.basket.push(s); return; }
  const o = ov(code);
  for(const s of slugs){
    o.remove = o.remove.filter(x => x !== s);
    if(!o.add.includes(s)) o.add.push(s);
  }
}
function dropFrom(code, s){
  if(!code){ S.ui.basket = (S.ui.basket || []).filter(x => x !== s); return; }
  const o = ov(code);
  o.add = o.add.filter(x => x !== s);
  if(!o.remove.includes(s)) o.remove.push(s);
}
document.addEventListener("click", async e => {
  if(!e.target.closest(".thm")) themeMenu(false);
  const el = e.target.closest("[data-act]");
  if(!el) return;
  const a = el.dataset.act, d = el.dataset;
  try{
    if(a === "tab"){ go(d.tab); }
    else if(a === "legend"){ openLegend(); }
    else if(a === "thm"){ themeMenu($("thmMenu").hidden); }
    else if(a === "thmset"){ setTheme(d.v); }
    else if(a === "lgclose"){ $("legend").close(); }
    else if(a === "vf"){ S.vf = d.v; saveView(); render(); }
    else if(a === "tview"){ S.tview = d.v; saveView(); render(); }
    else if(a === "mdet"){ S.mDetails = !S.mDetails; saveView(); render(); }
    else if(a === "tsort"){
      const cur = S.sorts[d.t];
      if(!cur || cur.k !== d.k) S.sorts[d.t] = {k: d.k, dir: 1};
      else if(cur.dir > 0) cur.dir = -1;
      else delete S.sorts[d.t];
      saveView();
      if(d.t === "verlauf") drawVerlauf(); else render();
    }
    else if(a === "topen"){ S.openTitle = S.openTitle === d.s ? null : d.s; render(); }
    else if(a === "gotitle"){
      S.openTitle = d.s; S.tview = "list"; S.vf = "all"; S.rq = ""; go("titel", false);
      const r = document.querySelector(`tr[data-s="${CSS.escape(d.s)}"]`); if(r) r.scrollIntoView({block:"center"});
    }
    else if(a === "gokorb"){ goKorb(); }
    else if(a === "gobasket"){
      if(!S.ui.basket){
        const p = S.plans.find(x => !x.is_ref && x.items.length);
        if(!p){ toast("Noch kein Titel im Angebot, den du vergleichen könntest"); return; }
        await change("Korb übernommen", () => { S.ui.basket = p.items.map(i => i.slug); });
      }
      goKorb();
    }
    else if(a === "gocards"){
      S.folds["cards:" + d.c] = 1;
      go("settings", false);
      const t = document.querySelector(`textarea[data-cards="${CSS.escape(d.c || "")}"]`);
      if(t){ t.scrollIntoView({block:"center"}); t.focus(); }
    }
    else if(a === "verlauf"){ await openVerlauf(d.s); }
    else if(a === "gotab"){ go(d.v); }
    else if(a === "goland"){
      // Andere Länder (0.74): die Titel des Schritts in diesem Land, nur zum Ansehen
      const st = d.from && S.kauf ? S.kauf.steps.findIndex(x => x.code === d.from) : -1;
      S.landStep = null;
      if(st >= 0){
        const r = await api("/api/plans", {overrides: {}, must: [], basket: S.kauf.steps[st].items.map(i => i.slug)});
        const p = r.plans.find(x => x.code === d.c);
        if(p) S.landStep = {code: d.c, step: st + 1, from: S.kauf.steps[st].name, p: Object.assign(p, {ro: true})};
      }
      S.landFocus = d.c; go("laender");
    }
    else if(a === "allland"){ S.landFocus = null; S.landStep = null; go("laender"); }
    else if(a === "nsov"){
      // Gleich umschalten (0.68): Alle Varianten sind schon geladen, die Wahl ändert sonst nichts
      // auf dem Server. Bis 0.67 lud der Knopf den ganzen Stand neu und brauchte Sekunden.
      const m = S.state.nso, v = (m.variants || []).find(x => x.key === d.v);
      S.folds.nso = 1;
      if(v){ m.mine = v.key; m.rows = v.rows; m.champ = v.champ; S.state.settings.nso_variant = v.key; render(); }
      await api("/api/settings", {nso_variant: d.v});
      if(!v) await refresh();
    }
    else if(a === "nsoxadd"){
      const price = num0($("nsoxp").value);
      if(!(price > 0)){ toast("Bitte einen Preis eintragen"); return; }
      const list = (S.state.settings.nso_extra || []).concat({key: $("nsoxk").value, code: $("nsoxc").value, price,
        src: $("nsoxs").value, url: $("nsoxu").value, date: new Date().toISOString().slice(0, 10)});
      await api("/api/settings", {nso_extra: list}); S.folds.nso = 1; S.folds.nsox = 0; await refresh(); toast("Angebot eingetragen");
    }
    else if(a === "ownadd"){
      const k = d.s, price = num0($("ownp-" + k).value);
      if(!(price > 0)){ toast("Bitte einen Preis eintragen"); return; }
      const list = (S.state.settings.own_offers || []).concat({slug: k, code: $("ownc-" + k).value, price,
        src: $("owns-" + k).value, url: $("ownu-" + k).value, date: new Date().toISOString().slice(0, 10)});
      await api("/api/settings", {own_offers: list}); delete S.folds["own-" + k]; await refresh(); toast("Angebot eingetragen");
    }
    else if(a === "owndel"){
      const list = (S.state.settings.own_offers || []).filter((x, i) => i !== +d.i);
      await api("/api/settings", {own_offers: list}); await refresh(); toast("Angebot entfernt");
    }
    else if(a === "nsoxdel"){
      const list = (S.state.settings.nso_extra || []).filter((x, i) => i !== +d.i);
      await api("/api/settings", {nso_extra: list}); S.folds.nso = 1; await refresh(); toast("Angebot entfernt");
    }
    else if(a === "nsotake"){ await api("/api/settings", {nso_until: el.dataset.v}); toast(el.dataset.v === (S.state.nso || {}).until ? "Ablaufdatum bleibt" : "Ablaufdatum übernommen"); await refresh(); }
    else if(a === "gonso"){ S.folds.nso = 1; saveView(); go("jetzt", false); const t = $("nsobox"); if(t){ t.open = true; t.scrollIntoView({block:"start", behavior:"smooth"}); } }
    else if(a === "gokaeufe"){ if(d.v === "how") S.folds.eshophow = 1; go("settings", false); const t = $("set-kaeufe"); if(t) t.scrollIntoView(); }
    else if(a === "gosprachen"){ go("settings", false); const t = $("sprachen"); if(t) t.scrollIntoView(); }
    else if(a === "dlcmark"){
      await api("/api/settings", {dlc_marks: {[d.s]: d.v || null}});
      S.state = await api("/api/state"); S.ui = S.state.ui; render();
      toast({have: "Als vorhanden abgehakt", ignore: "DLC ignoriert", ignore_all: "Alle DLC des Spiels ignoriert", missing: "Zählt wieder als fehlend"}[d.v] || "Zurückgesetzt");
    }
    else if(a === "bmdone"){ const o = helpersOld(); delete o[d.k]; try{ localStorage.setItem("ek.helpers", JSON.stringify(o)); }catch(e){} render(); }
    else if(a === "jpopen"){ const ta = $("jpids"); if(ta && ta.value) copyNow(ta.value); }
    else if(a === "jpcopy"){
      copyNow($("jpids").value);
      toast("IDs kopiert");
    }
    else if(a === "eshopimport"){ await eshopImport($("eshopimport").value); }
    else if(a === "eshoppick"){
      await api("/api/eshop_history/pick", {key: d.k, slug: d.v});
      S.eqOpen = null;
      await refresh();
      toast(d.v === "-" ? "Zählt nicht als Besitz" : d.v ? "Zugeordnet, zählt als Besitz" : "Zurückgenommen");
    }
    else if(a === "eqopen"){
      S.eqOpen = S.eqOpen === d.k ? null : d.k; render();
      const q = document.querySelector(`input.eqq[data-k="${CSS.escape(d.k)}"]`); if(q) q.focus();
    }
    else if(a === "eshopown"){
      const raw = (el.parentElement.querySelector("input").value || "").trim(), v = raw.toLowerCase();
      const slug = (S.eshopKnown || {})[raw] || (v.match(/\/items\/([a-z0-9-]+)/) || [])[1] || v.replace(/[?#].*$/, "");
      if(!/^[a-z0-9][a-z0-9-]*$/.test(slug)){ toast("Bitte einen Namen aus der Liste wählen oder einen DekuDeals-Link einfügen"); return; }
      await api("/api/eshop_history/pick", {key: d.k, slug});
      S.eqOpen = null;
      await refresh();
      toast("Zugeordnet, zählt als Besitz");
    }
    else if(a === "jpimport"){ await jpImport($("jpimport").value); }
    else if(a === "bmcopy"){
      try{ await navigator.clipboard.writeText(BM_CODE[d.k]); toast("Code kopiert. Jetzt ein Lesezeichen anlegen und den Code als Adresse einfügen"); }
      catch(e){ toast("Kopieren ging nicht. Bitte den Knopf in die Lesezeichenleiste ziehen"); }
    }
    else if(a === "lang"){
      await api("/api/settings", {lang_confirm: {[d.s]: {[d.f]: d.v === "" ? null : d.v === "1"}}});
      S.state = await api("/api/state"); S.ui = S.state.ui; await loadPlans(); render();
      toast(d.v === "" ? "Angabe zurückgesetzt" : "Sprache bestätigt");
    }
    else if(a === "tgtfill"){ S.ui.targets[d.s] = parseFloat(d.v); await saveUi(); await refresh(); toast("Zielpreis übernommen"); }
    else if(a === "bought"){
      const p = S.kauf.steps.find(x => x.code === d.c);
      if(!confirm(`Kauf in ${p.name} vermerken? Dein Konto steht danach dort${p.rest ? `, Rest ${money(p.rest, p.currency)}` : ""}.`)) return;
      await api("/api/bought", {code: p.code, slugs: p.items.map(i => i.slug), titles: p.items.map(i => i.short),
        cost: p.cost, games: p.games_paid, de: p.de_now, rest: p.rest, currency: p.currency});
      if(S.ui.plan_fill && S.ui.plan_fill[p.code]){ delete S.ui.plan_fill[p.code]; await saveUi(); }
      toast(`Kauf in ${p.name} vermerkt`); await refresh(); S.kauf = await api("/api/kaufplan"); render();
    }
    else if(a === "planfill" || a === "planunfill"){
      const f = S.ui.plan_fill = S.ui.plan_fill || {}, list = f[d.c] || [];
      f[d.c] = a === "planfill" ? list.concat(d.s.split(",")) : list.filter(x => x !== d.s);
      if(!f[d.c].length) delete f[d.c];
      await saveUi(); S.kauf = await api("/api/kaufplan"); render();
      toast(a === "planfill" ? "Füllartikel im Plan" : "Füllartikel herausgenommen");
    }
    else if(a === "unbought"){ await api("/api/bought/undo", {}); toast("Letzter Kauf zurückgenommen"); await refresh(); S.kauf = await api("/api/kaufplan"); render(); }
    else if(a === "vlclose"){ $("verlauf").close(); }
    else if(a === "vltoggle"){ const sh = S.vl.show; sh.has(d.c) ? sh.delete(d.c) : sh.add(d.c); drawVerlauf(); }
    else if(a === "showlog"){ go("settings", false); const l = $("log"); if(l){ l.closest("details").open = true; l.scrollIntoView({block:"center"}); } }
    else if(a === "sync"){
      const r = await api("/api/sync", {});
      if(!r.started) toast("Ein Abgleich läuft schon, sein Protokoll steht unter Einstellungen");
      S.state.status.running = true; S.state.status.ok = null; S.state.status.step = "Abgleich startet"; render(); watch(); }
    else if(a === "dense"){ S.dense = d.v === "1"; saveView(); render(); }
    else if(a === "add"){ addTo(d.c, d.s.split(",")); await replan(); }
    else if(a === "trim"){ const name = rowOf(d.s).title; await change(`${name} entfernt`, () => dropFrom(d.c, d.s)); }
    else if(a === "resetall"){ await change("Alle Warenkörbe zurückgesetzt", () => { S.ui.overrides = {}; }); }
    else if(a === "reset"){ await change("Auswahl zurückgesetzt", () => { delete S.ui.overrides[d.c]; }); }
    else if(a === "hide"){ await change(`${country(d.c).name} ausgeblendet`, () => { if(!S.ui.hidden.includes(d.c)) S.ui.hidden.push(d.c); }); }
    else if(a === "unhide"){ S.ui.hidden = S.ui.hidden.filter(c => c !== d.c); await replan(); }
    else if(a === "share"){
      const slugs = (d.step ? S.kauf.steps : cardPlans()).find(p => p.code === d.c).items.map(i => i.slug);
      await change(`Korb von ${country(d.c).name} übernommen`, () => { S.ui.basket = slugs; });
      goKorb();
    }
    else if(a === "rqclear"){ S.rq = ""; render(); $("rq").focus(); }
    else if(a === "unshare"){ await change("Korb geleert", () => { S.ui.basket = null; }); }
    else if(a === "bdrop"){ const name = rowOf(d.s).title; await change(`${name} entfernt`, () => dropFrom(null, d.s)); }
    else if(a === "star"){
      const b = S.ui.basket || [];
      S.ui.basket = b.includes(d.s) ? b.filter(x => x !== d.s) : b.concat(d.s);
      await replan();
    }
    else if(a === "plan2basket"){
      const slugs = S.kauf.steps.flatMap(p => p.items.map(i => i.slug));
      await change("Kaufplan als Korb übernommen", () => { S.ui.basket = slugs; });
      goKorb();
    }
    else if(a === "pickfile"){ $("impFile").click(); }
    else if(a === "copy"){
      // Ohne HTTPS (Heimnetz) gibt es keine Zwischenablage-Schnittstelle, dann über ein Textfeld
      const txt = ($(el.dataset.t) || {}).textContent || "";
      let ok = false;
      try{ await navigator.clipboard.writeText(txt); ok = true; }catch(e){}
      if(!ok){ const ta = document.createElement("textarea"); ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select(); try{ ok = document.execCommand("copy"); }catch(e){} ta.remove(); }
      toast(ok ? "Kopiert" : "Kopieren nicht möglich, bitte markieren");
    }
    else if(a === "diag"){
      // Eigene Box: Das Protokoll des Abgleichs läuft daneben weiter
      const l = $("diag");
      l.hidden = false;
      l.textContent = "Teste DekuDeals, Nintendo, Wechselkurse und Guthabenkarten …";
      const r = await api("/api/diag");
      S.diagText = r.lines.join("\n");   // bleibt stehen, auch wenn die Seite neu zeichnet
      l.textContent = S.diagText;
      l.scrollTop = 0;
      if($("diagCopy")) $("diagCopy").hidden = false;
    }
  }catch(err){ toast("Fehler: " + err.message); }
});
document.addEventListener("change", async e => {
  const el = e.target, a = el.dataset.act;
  try{
    if(el.id === "impFile" && el.files[0]){
      const data = JSON.parse(await el.files[0].text());
      await api("/api/import", data);
      await refresh();
      toast("Sicherung eingelesen");
    }
    else if(el.closest("#setForm") || (el.form && el.form.id === "setForm")){
      await saveSettings($("setForm"), !!el.dataset.cards || ["pay", "tax_pct"].includes(el.dataset.k) ||
        ["deal_buy", "deal_good", "tier1", "tier2", "tier3"].includes(el.name));
    }
    else if(a === "drop"){ const name = rowOf(el.dataset.s).title; await change(`${name} entfernt`, () => dropFrom(el.dataset.c, el.dataset.s)); }
    else if(a === "planpick" && el.value){
      const nm = el.selectedOptions[0].textContent.split(" · ")[0];
      const f = S.ui.plan_fill = S.ui.plan_fill || {};
      f[el.dataset.c] = (f[el.dataset.c] || []).concat(el.value);
      await saveUi(); S.kauf = await api("/api/kaufplan"); render();
      toast(`${nm} im Plan`);
    }
    else if((a === "pick" || a === "bpick") && el.value){ addTo(el.dataset.c, [el.value]); await replan(); }
    else if(a === "korbland"){ S.korbLand = el.value; render(); }
    else if(a === "sort"){ S.lsort = el.value; saveView(); render(); }
    else if(a === "tsortsel"){ if(el.value){ const [k, dir] = el.value.split(":"); S.sorts[el.dataset.t] = {k, dir: +dir}; } else delete S.sorts[el.dataset.t]; saveView(); render(); }
    else if(a === "colorder"){ S.colOrder = el.value; saveView(); render(); }
    else if(a === "onlysale"){ S.onlySale = el.checked; render(); }
    else if(a === "nsountil"){
      await api("/api/settings", {nso_until: el.value || ""}); await refresh();
      toast(el.value ? `Mitgliedschaft läuft bis ${dmy(el.value)}` : "Ablaufdatum entfernt");
    }
    else if(a === "acct" || a === "bal"){
      const s = S.state.settings, cur = s.current_country;
      const body = a === "acct" ? {current_country: el.value}
        : {countries: {[cur]: {balance: Math.max(0, num0(el.value) || 0)}}};
      const back = a === "acct" ? {current_country: cur}
        : {countries: {[cur]: {balance: (s.countries[cur] || {}).balance || 0}}};
      await api("/api/settings", body); await refresh();
      toast(a === "acct" ? (el.value ? `Konto steht in ${country(el.value).name}` : "Konto ohne Land") : "Guthaben gespeichert",
        async () => { await api("/api/settings", back); await refresh(); });
    }
    else if(a === "plangood"){ S.ui.plan_good = el.checked; await saveUi(); S.kauf = await api("/api/kaufplan"); render(); }
    else if(a === "target"){
      const v = num0(el.value);
      if(v > 0) S.ui.targets[el.dataset.s] = v; else delete S.ui.targets[el.dataset.s];
      await saveUi();
      await refresh();
    }
  }catch(err){ toast("Fehler: " + err.message); }
});
document.addEventListener("input", e => {
  const el = e.target;
  if(el.dataset.cards){ const i = document.querySelector(`[data-info="${el.dataset.cards}"]`); if(i) i.textContent = cardInfo(el.value); return; }
  if(el.classList.contains("eqq")){
    // Treffer für „anderer …“: höchstens zwölf, ohne neu zu zeichnen
    const box = el.closest("td").querySelector(".eqhits"), q = el.value.trim();
    const found = q.length < 2 || /\/items\//.test(q) ? [] : Object.entries(S.eshopKnown || {}).filter(([n]) => hits(q, n)).slice(0, 12);
    box.innerHTML = found.map(([n, slug]) => `<button class="sm" data-act="eshoppick" data-k="${esc(el.dataset.k)}" data-v="${esc(slug)}" title="Ja, das ist ${esc(n)}: zählt als Besitz">${esc(n)}</button>`).join("") +
      (q.length >= 2 && !found.length && !/\/items\//.test(q) ? `<small class="mut">Nichts gefunden. Ein DekuDeals-Link geht immer: Titel dort suchen, Adresse hier einfügen.</small>` : "");
    return;
  }
  if(el.id !== "rq") return;
  S.rq = el.value;
  const pos = el.selectionStart, id = el.id;
  render();
  const q = $(id); q.focus(); q.setSelectionRange(pos, pos);
});
document.addEventListener("keydown", e => {
  if(e.key !== "Escape" || e.target.id !== "rq" || !S.rq) return;
  e.preventDefault(); S.rq = ""; render(); $("rq").focus();
});
$("verlauf").addEventListener("click", e => {   // Klick neben das Fenster schließt es
  const d = e.currentTarget, r = d.getBoundingClientRect();
  if(e.target === d && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) d.close();
});
$("legend").addEventListener("click", e => { if(e.target === e.currentTarget) e.currentTarget.close(); });
// Aufgeklappte Kästen (Rechnung, Nicht im Plan, Gekauft) bleiben beim Neuzeichnen offen
document.addEventListener("toggle", e => {
  // data-kc: von Haus aus offen, gemerkt wird das Zuklappen (0.76)
  const kc = e.target.dataset && e.target.dataset.kc;
  if(kc === "logbox" && e.target.open){ const l = $("log"); if(l) l.scrollTop = l.scrollHeight; }
  if(kc){ if(e.target.open) delete S.folds[kc]; else S.folds[kc] = 1; saveView(); return; }
  const k = e.target.dataset && e.target.dataset.k;
  if(!k) return;
  if(e.target.open) S.folds[k] = 1; else delete S.folds[k];
  saveView();
}, true);
/* Kopfleiste beim Scrollen: nach unten erst 300 px mitkommen, dann ausblenden; 40 px nach oben
   zeigen sie wieder. Kleine Gegenbewegungen (Touchpad) unter 8 px zählen nicht als Richtungswechsel. --stick sagt Tabellenköpfen und Sprungleiste, wie viel Platz sie gerade belegt. */
(function(){
  let lastY = scrollY, turn = scrollY, dir = 0, hidden = false;
  const set = hid => {
    hidden = hid; const el = $("stick");
    el.classList.toggle("hid", hid);
    document.documentElement.style.setProperty("--stick", hid ? "0px" : el.offsetHeight + "px");
    document.documentElement.style.setProperty("--sh", el.offsetHeight + "px");
    fitMatrix();
  };
  // Titel-Tabelle: genau so hoch, dass nur sie scrollt, nicht das Fenster. Ausgeblendet klappt die
  // Leiste weg (body.fit) und die Tabelle wächst um ihre Höhe, so verdeckt nichts die Filterzeile (0.56.3).
  fitMatrix = () => {
    const box = document.querySelector("body.fit .fitbox");
    if(!box) return;
    const st = $("stick"), sh = st.offsetHeight, r = box.getBoundingClientRect();
    // Alles unter der Tabelle (Hinweis, Abstände) und ihr Platz mit sichtbarer Leiste; der Rand der
    // Leiste kann gerade mitten in der Bewegung stecken, deshalb der aktuelle Wert
    const bodyEnd = document.body.getBoundingClientRect().bottom + (parseFloat(getComputedStyle(document.body).marginBottom) || 0);
    const after = bodyEnd - r.bottom;
    const topShown = r.top - (parseFloat(getComputedStyle(st).marginTop) || 0);
    const base = Math.max(240, Math.floor(innerHeight - topShown - after - 2));
    box.style.height = (base + (hidden ? sh : 0)) + "px";
  };
  // Die Titel-Tabelle scrollt in einem eigenen Kasten: ihr Scrollen zählt mit (0.56.2)
  document.addEventListener("scroll", () => {
    const box = document.querySelector(".fitbox");
    const y = scrollY + (box ? box.scrollTop : 0);
    if(Math.abs(y - lastY) < 8 && y > 60) return;
    const d = Math.sign(y - lastY);
    if(d !== dir){ dir = d; turn = lastY; }          // Richtung gewechselt: ab hier messen
    if(dir > 0 && !hidden && y > 300 && y - turn > 300 && $("thmMenu").hidden) requestAnimationFrame(() => set(true));
    else if(dir < 0 && hidden && (turn - y > 40 || y < 60)) requestAnimationFrame(() => set(false));
    lastY = y;
  }, {passive: true, capture: true});
  addEventListener("resize", () => set(hidden));
  showStick = () => { if(hidden) set(false); };
  set(false);
})();
document.addEventListener("keydown", e => { if(e.key === "Escape") themeMenu(false); });
document.addEventListener("submit", e => { if(e.target.id === "setForm") e.preventDefault(); });

async function eshopImport(text){
  let fresh = false;
  try{ const o = JSON.parse(text); if(o && !Array.isArray(o)) fresh = helperSeen("eshop", o.hv); }catch(e){}
  if(fresh) setTimeout(() => toast("Dein Lesezeichen „Käufe lesen“ ist veraltet. Bitte neu anlegen, siehe Käufe aus dem eShop"), 4000);
  const r = await api("/api/eshop_history", {text});
  await refresh();
  toast(`${r.read} Einträge gelesen, ${r.new} neu. ${r.matched} zählen als Besitz` + (r.open ? `, ${r.open} ohne Zuordnung` : "") + (r.complete ? "" : ". Unvollständig gelesen: Beim nächsten Mal liest das Lesezeichen wieder ab dem alten Stand"));
}
renderTheme();
// Vom Lesezeichen „Käufe lesen“: Daten im Adressteil hinter #, gehen nicht übers Netz
// Ebenso „JP-Sprachen lesen“ mit #jpsprachen=
const KAEUFE = location.hash.startsWith("#kaeufe=") ? decodeURIComponent(location.hash.slice(8)) : null;
const JPSPR = location.hash.startsWith("#jpsprachen=") ? decodeURIComponent(location.hash.slice(12)) : null;
// Vom JP-Lesezeichen im Store geöffnet (ab 0.58): die offenen Japan-IDs per postMessage zurück an den Store-Tab,
// ohne Zwischenablage. Ist die Verbindung zum Store-Tab weg, zeigt das Fenster die IDs zum Kopieren.
const JPASK = location.hash === "#ek-jpids";
if(KAEUFE || JPSPR || JPASK) history.replaceState(null, "", location.pathname + location.search);
function jpHandOver(){
  const ids = jpOpenIds().join(" ");
  let sent = false;
  render(); S.handover = true;
  if(window.opener) try{ window.opener.postMessage({ekJpIds: ids}, "https://store-jp.nintendo.com"); sent = true; }catch(e){}
  document.title = "Japan-IDs";
  $("main").innerHTML = sent && ids ? `<div class="box"><p>${ids.split(" ").length} Japan-IDs an den Store übergeben. Dieses Fenster schließt sich.</p></div>`
    : `<div class="box"><p>${ids ? "Die IDs kopieren und im Store-Tab ins Feld des Lesezeichens einfügen:" : "Gerade sind keine Japan-Titel offen."}</p>${ids ? `<textarea id="jpids" readonly rows="4" style="width:100%">${esc(ids)}</textarea> <button data-act="jpcopy">IDs kopieren</button>` : ""}</div>`;
  if(sent && ids) setTimeout(() => window.close(), 1500);
}
refresh().then(() => JPASK ? jpHandOver() : KAEUFE ? (S.tab = "sammlung", saveView(), eshopImport(KAEUFE).catch(err => toast("Fehler: " + err.message)))
  : JPSPR && (S.tab = "settings", saveView(), render(), jpImport(JPSPR).then(() => { const t = $("sprachen"); if(t) t.scrollIntoView(); }, err => toast("Fehler: " + err.message)))).catch(err => { $("main").innerHTML = `<div class="banner">Server nicht erreichbar: ${esc(err.message)}</div>`; });
