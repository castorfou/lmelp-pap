// PROTOTYPE jetable (#87) : trois variantes des pages « sans enregistrement » et
// « localisé », ?variant=A|B|C. Chargé APRÈS le script de la page : remplace
// pageEtat pour ces deux états, garde la vraie page pour les autres.
// Écritures simulées en mémoire (prototype-fetch.js).
(function () {
  const css = document.createElement("style");
  css.textContent = `
  #bascule { position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%); background: #b3261e; color: #fff; border-radius: 999px; padding: 6px 8px; display: flex; gap: 10px; align-items: center; box-shadow: 0 4px 14px #0005; z-index: 60; font-weight: 600; font-size: 13px; }
  #bascule button { background: #fff2; color: #fff; border: 0; border-radius: 999px; width: 30px; height: 30px; padding: 0; }
  body { padding-bottom: 70px; }
  .p-journal { list-style: none; margin: 4px 0; padding: 0; border-left: 2px solid var(--trait); }
  .p-journal li { padding: 3px 0 5px 10px; position: relative; font-size: 13px; }
  .p-journal li::before { content: ""; position: absolute; left: -5px; top: 8px; width: 8px; height: 8px; border-radius: 50%; background: var(--localise); }
  .p-journal .meta { color: var(--doux); font-size: 12px; }
  .p-relance { font-size: 12px; font-weight: 600; white-space: nowrap; }
  .p-relance.due { color: #b3261e; } .p-relance.bientot { color: #9a6700; } .p-relance.loin { color: var(--doux); font-weight: 400; }
  .p-form { display: grid; gap: 6px; font-size: 13px; }
  .p-form label { display: grid; gap: 2px; } .p-form .ligne { display: flex; gap: 8px; flex-wrap: wrap; align-items: end; }
  .p-form input, .p-form textarea, .p-form select { font: inherit; padding: 4px 8px; border: 1px solid var(--trait); border-radius: 6px; background: var(--carte); color: var(--texte); }
  .p-form .oblig::after { content: " *"; color: #b3261e; }
  .p-seg { display: inline-flex; border: 1px solid var(--trait); border-radius: 6px; overflow: hidden; margin-bottom: 8px; }
  .p-seg button { border: 0; border-radius: 0; border-right: 1px solid var(--trait); } .p-seg button:last-child { border-right: 0; }
  .p-seg button.actif { background: var(--entete); color: var(--entete-texte); }
  .p-deplie td { background: var(--ligne); }
  .p-deux { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .p-deux h4, .p-fiche h4, .p-det h4 { margin: 2px 0 6px; font-size: 13px; }
  tr.p-ligne { cursor: pointer; } tr.p-ligne:hover td, tr.p-ligne.choisie td { background: var(--ligne); }
  .p-fiche { position: fixed; top: 0; right: 0; bottom: 0; width: 460px; max-width: 100vw; background: var(--carte); box-shadow: -4px 0 18px #0004; padding: 16px 18px 80px; overflow: auto; z-index: 40; }
  .p-fiche .tete { display: flex; gap: 6px; align-items: start; } .p-fiche .tete h3 { flex: 1; margin: 0; font-size: 15px; }
  .p-fiche section { border-top: 1px solid var(--trait); padding: 10px 0; }
  .p-sorties { display: grid; gap: 6px; } .p-sorties > button { text-align: left; padding: 8px 10px; }
  .p-sorties > button b { display: block; } .p-sorties > button span { color: var(--doux); font-size: 12px; }
  .p-avec-fiche main { margin-right: 470px; }
  .p-det { margin-top: 10px; } .p-det .tete { display: flex; gap: 10px; align-items: center; cursor: pointer; }
  .p-det .tete b { font-size: 14px; } .p-det .corps { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 8px; }
  .p-mini { padding: 1px 8px; font-size: 12px; }
  .p-tag { font-size: 10px; color: var(--doux); border: 1px dashed var(--doux); border-radius: 4px; padding: 0 4px; margin-left: 4px; }
  `;
  document.head.append(css);

  const ICI = new URLSearchParams(location.search);
  const NOMS = { A: "Ligne dépliée pleine largeur", B: "Fiche latérale de l'émission", C: "Par détenteur (pistes groupées)" };
  let variante = NOMS[ICI.get("variant")] ? ICI.get("variant") : "A";
  const aujourdhui = () => new Date().toISOString().slice(0, 10);
  const CANAUX = ["courriel", "téléphone", "forum", "courrier", "sur place", "autre"];
  const DATATIONS = ["étiquette de la cassette ou du fichier", "annonce à l'antenne", "déduite du contenu (livres, invités)", "inconnue"];
  const P = { ouverte: null, onglet: {}, choix: new Set(), detOuvert: new Set() };

  // ----- Lecture du modèle -----
  const brutDe = id => PROTO.emissions.find(e => e.id === id);
  const journal = e => e.localisations.flatMap(l => (l.journal || []).map(x => ({ ...x, source: l.source }))).sort((a, b) => b.date.localeCompare(a.date));
  const dernier = e => journal(e)[0] || null;
  const relanceDe = e => { const d = e.localisations.map(l => (l.journal || []).at(-1)?.relance).filter(Boolean).sort()[0]; return d || null; };
  const jours = d => Math.round((Date.parse(d) - Date.parse(aujourdhui())) / 86400000);
  const relanceHtml = d => { if (!d) return `<span class="doux">—</span>`; const j = jours(d);
    return `<span class="p-relance ${j <= 0 ? "due" : j <= 7 ? "bientot" : "loin"}" title="relance prévue le ${d}">${j < 0 ? `due depuis ${-j} j` : j === 0 ? "aujourd'hui" : `dans ${j} j`}</span>`; };
  const dernierHtml = e => { const x = dernier(e); return x ? `${-jours(x.date)} j <span class="doux">· ${esc(x.canal)}</span>` : `<span class="doux">aucun</span>`; };
  const fmt = d => new Date(d).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });

  function recharger(message, avant) {
    preparer(structuredClone(PROTO)); rendre();
    if (message) notifier(message + " (simulé)", avant);
  }

  // ----- Formulaires partagés (le contenu ; chaque variante choisit où il vit) -----
  function formEchange(e, source, fini) {
    const f = document.createElement("div"); f.className = "p-form";
    const sources = e.localisations.map(l => l.source);
    f.innerHTML = `<div class="ligne">
        <label>Date<input type="date" name="date" value="${aujourdhui()}"></label>
        <label>Canal<select name="canal">${CANAUX.map(c => `<option>${c}</option>`).join("")}</select></label>
        ${sources.length > 1 && !source ? `<label>Piste<select name="source">${sources.map(s => `<option>${esc(s)}</option>`).join("")}</select></label>` : ""}
        <label>Interlocuteur<input name="interlocuteur" value="${esc((source || sources[0] || "").replace(/ \(.*/, ""))}"></label></div>
      <label><span class="oblig">Ce qui s'est passé</span><textarea name="texte" rows="2" placeholder="ex. Relancé par courriel, il cherche la cassette du 12 mars"></textarea></label>
      <div class="ligne"><label>Prochaine relance<input type="date" name="relance"></label>
        <span class="doux">${[7, 15, 30].map(j => `<button type="button" class="p-mini" data-j="${j}">+${j} j</button>`).join(" ")}</span>
        <button class="primaire" name="ok" disabled style="margin-left:auto">Noter l'échange</button></div>`;
    const v = n => f.querySelector(`[name=${n}]`);
    f.querySelectorAll("[data-j]").forEach(b => b.onclick = () => { v("relance").value = new Date(Date.now() + b.dataset.j * 864e5).toISOString().slice(0, 10); });
    v("texte").oninput = () => { v("ok").disabled = !v("texte").value.trim(); };
    v("ok").onclick = () => {
      const entree = { date: v("date").value, canal: v("canal").value, interlocuteur: v("interlocuteur").value.trim(), texte: v("texte").value.trim(), relance: v("relance").value || null };
      const ids = Array.isArray(e.ids) ? e.ids : [e.id];
      ids.forEach(id => PROTO_ECRIT.echange(id, source || v("source")?.value || sources[0], entree));
      fini && fini(); recharger(`Échange noté${ids.length > 1 ? ` pour ${ids.length} émissions` : ""}`);
    };
    return f;
  }
  function formPiste(ids, fini) {
    const f = document.createElement("div"); f.className = "p-form";
    const connues = [...new Set(PROTO.emissions.flatMap(e => (e.localisations || []).filter(l => l.simule).map(l => l.source)))];
    f.innerHTML = `<label><span class="oblig">Qui détient l'enregistrement</span><input name="source" list="p-connues" placeholder="ex. Jean D. (passionné), cassettes 1978-1982">
        <datalist id="p-connues">${connues.map(s => `<option value="${esc(s)}">`).join("")}</datalist></label>
      <label>Note<textarea name="note" rows="2" placeholder="ce qu'on sait de son fonds"></textarea></label>
      <label><input type="checkbox" name="premier" checked style="width:auto"> noter aussi le premier échange (aujourd'hui)</label>
      <div class="ligne"><select name="canal">${CANAUX.map(c => `<option>${c}</option>`).join("")}</select><input name="texte" placeholder="ex. message reçu sur le forum" style="flex:1"></div>
      <div class="ligne"><span class="doux">${ids.length > 1 ? `${ids.length} émissions : ${ids.slice(0, 6).join(", ")}${ids.length > 6 ? "…" : ""}` : "sans enregistrement → localisé"}</span>
      <button class="primaire" name="ok" disabled style="margin-left:auto">${ids.length > 1 ? `Localiser les ${ids.length} émissions` : "Localiser"}</button></div>`;
    const v = n => f.querySelector(`[name=${n}]`);
    v("source").oninput = () => { v("ok").disabled = !v("source").value.trim(); };
    v("ok").onclick = () => {
      const avant = compter(EMISSIONS), s = v("source").value.trim();
      const ech = v("premier").checked ? { date: aujourdhui(), canal: v("canal").value, interlocuteur: s.replace(/ \(.*/, ""), texte: v("texte").value.trim() || "piste notée", relance: null } : null;
      PROTO_ECRIT.piste(ids, s, v("note").value.trim(), ech); P.choix.clear();
      fini && fini(); recharger(`${ids.length} émission(s) localisée(s) : ${s}`, avant);
    };
    return f;
  }
  function formUrl(e, fini) {
    const f = document.createElement("div"); f.className = "p-form";
    f.innerHTML = `<label><span class="oblig">URL de l'intégral</span><input name="url" placeholder="https://…/fichier.mp3"></label>
      <label>Note<input name="note" placeholder="d'où vient ce lien"></label>
      <div class="ligne"><span class="doux">→ téléchargeable : il partira avec le prochain lot de téléchargement</span><button class="primaire" name="ok" disabled style="margin-left:auto">Enregistrer l'URL</button></div>`;
    const v = n => f.querySelector(`[name=${n}]`);
    v("url").oninput = () => { v("ok").disabled = !/^https?:\/\/\S+$/.test(v("url").value.trim()); };
    v("ok").onclick = () => { const avant = compter(EMISSIONS); PROTO_ECRIT.url(e.id, v("url").value.trim(), v("note").value.trim()); fini && fini(); recharger(`${e.id} téléchargeable`, avant); };
    return f;
  }
  function formFichier(e, fini) {
    const f = document.createElement("div"); f.className = "p-form";
    const prov = e.localisations.filter(l => l.source !== "ina").map(l => l.source)[0] || "";
    f.innerHTML = `<label><span class="oblig">Fichier audio</span><input type="file" name="fichier" accept="audio/*"></label>
      <label><span class="oblig">Provenance</span><input name="prov" value="${esc(prov)}" placeholder="qui l'a fourni, sous quelle forme (cassette numérisée, fichier…)"></label>
      <label>La date est établie par<select name="datation">${DATATIONS.map(d => `<option>${d}</option>`).join("")}</select></label>
      <label>Note<input name="note" placeholder="ex. face B, coupure à 38 min"></label>
      <div class="ligne"><span class="doux">→ rapatrié : à écouter et qualifier (intégral ? bonne émission ?)</span><button class="primaire" name="ok" disabled style="margin-left:auto">Téléverser</button></div>`;
    const v = n => f.querySelector(`[name=${n}]`);
    const maj = () => { v("ok").disabled = !(v("fichier").files.length && v("prov").value.trim()); };
    v("fichier").onchange = maj; v("prov").oninput = maj;
    v("ok").onclick = () => { const avant = compter(EMISSIONS); PROTO_ECRIT.fichier(e.id, v("fichier").files[0]?.name, v("prov").value.trim(), v("datation").value, v("note").value.trim()); fini && fini(); recharger(`${e.id} rapatrié`, avant); };
    return f;
  }
  const SORTIES = e => [
    ...(e.etat === "sans" ? [["piste", "Une piste", "quelqu'un ou un fonds détient l'enregistrement → localisé", () => formPiste([e.id])]] :
      [["piste", "Une autre piste", "un second détenteur (reste localisé)", () => formPiste([e.id])]]),
    ["url", "Une URL", "un lien vers le fichier intégral → téléchargeable", () => formUrl(e)],
    ["fichier", "Le fichier", "on l'a reçu (cassette numérisée, envoi…) → rapatrié", () => formFichier(e)],
  ];
  function journalHtml(liste, vide) {
    return liste.length ? `<ul class="p-journal">${liste.map(x => `<li><div class="meta">${fmt(x.date)} · ${esc(x.canal)}${x.interlocuteur ? ` · ${esc(x.interlocuteur)}` : ""}${x.relance ? ` · relance ${relanceHtml(x.relance)}` : ""}</div>${esc(x.texte)}</li>`).join("")}</ul>` : `<p class="doux">${vide}</p>`;
  }
  const detenteursHtml = e => e.localisations.map(l => `<div>${l.notice ? `<a href="${esc(l.notice)}" target="_blank" rel="noopener">${esc(l.source === "ina" ? "INA mediapro" : l.source)}</a>` : esc(l.source)}${l.simule ? '<span class="p-tag">simulé</span>' : ""}${l.note ? `<div class="doux">${esc(l.note)}</div>` : ""}</div>`).join("") || `<span class="doux">${esc(e.sources.join(", "))}</span>`;

  // ----- En-tête commun d'une page d'état (comme la vraie page) -----
  function entete(racine, s, tous, liste, extra = "") {
    racine.innerHTML = `<button class="retour">← Accueil</button>
      <div class="carte"><h2 style="margin-top:0"><span class="pastille" style="background:${couleur(s.cle)}"></span>${s.nom} : ${liste.length} émission(s) ${vue.annee ? `en ${vue.annee} <button id="effacer-annee">× toutes les années</button>` : ""}</h2><div id="h"></div>
      <div class="doux">Cliquer une année filtre la liste.</div></div>${extra}<div id="p-corps"></div>`;
    racine.querySelector(".retour").onclick = () => { vue.etat = null; P.ouverte = null; document.body.classList.remove("p-avec-fiche"); rendre(); scrollTo(0, 0); };
    $("effacer-annee")?.addEventListener("click", () => { vue.annee = null; rendre(); });
    $("h").append(histogramme({ liste: tous, hauteur: 90, empile: false, surligne: vue.etat, annee: vue.annee, clic: a => { vue.annee = vue.annee === a ? null : a; rendre(); } }));
    return $("p-corps");
  }
  // Colonnes : localisé ajoute le dernier échange et la relance ; tri par défaut : relance due d'abord
  function cols(cle) {
    const c = [
      { k: "date", t: "Date", v: e => e.date, h: e => e.date },
      { k: "titre", t: "Titre", v: e => e.titre.toLowerCase(), h: e => esc(e.titre) + themesMixtes(e) },
      { k: "sources", t: cle === "localise" ? "Détenteur" : "Attestée par", v: e => e.localisations.map(l => l.source).join() || e.sources.join(), h: e => cle === "localise" ? detenteursHtml(e) : `<span class="doux">${esc(e.sources.join(", "))}</span>` },
    ];
    if (cle === "localise") c.push(
      { k: "relance", t: "Relance", v: e => relanceDe(e) || "9999", h: e => relanceHtml(relanceDe(e)) },
      { k: "echange", t: "Dernier échange", v: e => dernier(e)?.date || "", h: dernierHtml });
    c.push({ k: "depuis", t: "Depuis", v: e => e.depuis ?? -1, h: depuis });
    return c;
  }
  function trier(liste, c) {
    if (!P.tri || P.tri.etat !== vue.etat) P.tri = { etat: vue.etat, k: vue.etat === "localise" ? "relance" : "depuis", sens: vue.etat === "localise" ? 1 : -1 };
    const col = c.find(x => x.k === P.tri.k) || c[0];
    return liste.sort((a, b) => { const x = col.v(a), y = col.v(b); return (x < y ? -1 : x > y ? 1 : 0) * P.tri.sens; });
  }
  function tableau(corps, liste, c, { cases, ligne, apres }) {
    corps.innerHTML += `<div class="carte" style="margin-top:8px"><table><thead><tr>${cases ? `<th><input type="checkbox" id="p-tous"></th>` : ""}${c.map(x => `<th class="triable" data-k="${x.k}">${x.t}${P.tri.k === x.k ? (P.tri.sens > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}${apres ? "<th></th>" : ""}</tr></thead><tbody></tbody></table></div>`;
    corps.querySelectorAll("th.triable").forEach(th => th.onclick = () => { P.tri.sens = P.tri.k === th.dataset.k ? -P.tri.sens : 1; P.tri.k = th.dataset.k; rendre(); });
    const tb = corps.querySelector("tbody");
    liste.slice(0, 300).forEach(e => {
      const tr = document.createElement("tr"); tr.className = "p-ligne" + (P.ouverte === e.id ? " choisie" : ""); tr.dataset.id = e.id;
      tr.innerHTML = `${cases ? `<td><input type="checkbox" ${P.choix.has(e.id) ? "checked" : ""}></td>` : ""}${c.map(x => `<td>${x.h(e)}</td>`).join("")}${apres ? `<td>${apres(e)}</td>` : ""}`;
      if (cases) { const cb = tr.querySelector("input"); cb.onclick = ev => ev.stopPropagation(); cb.onchange = () => { cb.checked ? P.choix.add(e.id) : P.choix.delete(e.id); majLot(); }; }
      tr.onclick = ev => { if (!ev.target.closest("a, button, input")) ligne(e, tr); };
      tb.append(tr);
    });
    if (liste.length > 300) tb.insertAdjacentHTML("beforeend", `<tr><td colspan="8" class="doux">… ${liste.length - 300} de plus</td></tr>`);
    $("p-tous")?.addEventListener("change", ev => { liste.forEach(e => ev.target.checked ? P.choix.add(e.id) : P.choix.delete(e.id)); rendre(); });
    return tb;
  }
  // Barre de lot de « sans enregistrement » : une piste pour plusieurs émissions
  const barreLot = () => `<div class="lot"><button class="primaire" id="p-lot">Une piste pour la sélection (${P.choix.size})</button><span class="doux">un passionné qui détient plusieurs dates : cocher les émissions, puis une seule saisie</span></div>`;
  function majLot() { const b = $("p-lot"); if (b) b.textContent = `Une piste pour la sélection (${P.choix.size})`; }
  function dialogue(titre, contenu) {
    const d = $("boite"); d.innerHTML = `<h3 id="boite-titre">${titre}</h3>`; d.append(contenu);
    const x = document.createElement("div"); x.className = "choix"; x.innerHTML = `<button>Fermer</button>`; x.firstChild.onclick = () => d.close(); d.append(x);
    d.showModal(); contenu.querySelector("input, textarea")?.focus();
    return () => d.close();
  }
  function brancherLot() { $("p-lot")?.addEventListener("click", () => { const ids = [...P.choix].sort(); if (!ids.length) return toast("Cocher d'abord des émissions");
    let fermer; fermer = dialogue(`Une piste pour ${ids.length} émission(s)`, formPiste(ids, () => fermer())); }); }

  // ===== Variante A : la ligne se déplie en pleine largeur sous elle =====
  function pageA(racine, s, tous, liste) {
    const corps = entete(racine, s, tous, liste, s.cle === "sans" ? barreLot() : "");
    const c = cols(s.cle);
    const tb = tableau(corps, trier(liste, c), c, { cases: s.cle === "sans", ligne: e => { P.ouverte = P.ouverte === e.id ? null : e.id; rendre(); } });
    brancherLot();
    const e = liste.find(x => x.id === P.ouverte); if (!e) return;
    const tr = tb.querySelector(`tr[data-id="${CSS.escape(e.id)}"]`);
    const dep = document.createElement("tr"); dep.className = "p-deplie";
    const td = document.createElement("td"); td.colSpan = tr.children.length; dep.append(td);
    td.innerHTML = `<div class="p-deux"><div class="gauche"></div><div class="droite"></div></div>`;
    const g = td.querySelector(".gauche"), d = td.querySelector(".droite");
    if (s.cle === "localise") {
      g.innerHTML = `<h4>Journal des échanges</h4>${journalHtml(journal(e), "Aucun échange noté. L'ancienneté compte depuis l'entrée dans l'état.")}<h4 style="margin-top:10px">Noter un échange</h4>`;
      g.append(formEchange(e));
    } else {
      g.innerHTML = `<h4>Ce qu'on sait</h4><div class="doux">Attestée par : ${esc(e.sources.join(", "))}</div><p class="doux">Aucun enregistrement connu.</p>`;
    }
    const sorties = SORTIES(e), cle = P.onglet[e.id] || sorties[0][0];
    d.innerHTML = `<h4>Faire avancer</h4><div class="p-seg">${sorties.map(([k, t]) => `<button data-k="${k}" class="${k === cle ? "actif" : ""}">${t}</button>`).join("")}</div><div class="doux" style="margin-bottom:6px">${sorties.find(x => x[0] === cle)[2]}</div>`;
    d.querySelectorAll(".p-seg button").forEach(b => b.onclick = () => { P.onglet[e.id] = b.dataset.k; rendre(); });
    d.append(sorties.find(x => x[0] === cle)[3]());
    tr.after(dep);
  }

  // ===== Variante B : fiche latérale de l'émission, la liste reste visible =====
  function pageB(racine, s, tous, liste) {
    const corps = entete(racine, s, tous, liste, s.cle === "sans" ? barreLot() : "");
    const c = cols(s.cle), triee = trier(liste, c);
    tableau(corps, triee, c, { cases: s.cle === "sans", ligne: e => { P.ouverte = e.id; P.onglet[e.id] = null; rendre(); } });
    brancherLot();
    document.querySelector(".p-fiche")?.remove();
    const e = triee.find(x => x.id === P.ouverte);
    document.body.classList.toggle("p-avec-fiche", !!e);
    if (!e) return;
    const i = triee.indexOf(e), f = document.createElement("aside"); f.className = "p-fiche";
    f.innerHTML = `<div class="tete"><h3>${esc(e.date)} · ${esc(e.titre)}</h3><button id="p-prec" title="précédente (↑)">↑</button><button id="p-suiv" title="suivante (↓)">↓</button><button id="p-fermer" title="fermer (Échap)">✕</button></div>
      <div class="doux">${s.nom} depuis ${e.depuis ?? "?"} j · ${i + 1}/${triee.length} dans la file</div>
      <section><h4>Attestée par</h4><div class="doux">${esc(e.sources.join(", "))}</div></section>
      ${s.cle === "localise" ? `<section><h4>Détenteur(s)</h4>${detenteursHtml(e)}<div style="margin-top:6px">Relance : ${relanceHtml(relanceDe(e))}</div></section>
        <section><h4>Journal des échanges</h4>${journalHtml(journal(e), "Aucun échange noté.")}<details id="p-ech"><summary>Noter un échange</summary></details></section>` : ""}
      <section><h4>Faire avancer</h4><div class="p-sorties"></div></section>`;
    f.querySelector("#p-ech")?.append(formEchange(e));
    const zone = f.querySelector(".p-sorties");
    SORTIES(e).forEach(([k, t, aide, form]) => {
      const b = document.createElement("button"); b.innerHTML = `<b>${t}</b><span>${aide}</span>`;
      if (P.onglet[e.id] === k) b.classList.add("primaire");
      b.onclick = () => { P.onglet[e.id] = P.onglet[e.id] === k ? null : k; rendre(); };
      zone.append(b);
      if (P.onglet[e.id] === k) { const ff = form(); ff.style.margin = "0 0 8px 10px"; zone.append(ff); }
    });
    document.body.append(f);
    const aller = d => { const n = triee[i + d]; if (n) { P.ouverte = n.id; rendre(); } };
    f.querySelector("#p-prec").onclick = () => aller(-1); f.querySelector("#p-suiv").onclick = () => aller(1);
    f.querySelector("#p-fermer").onclick = () => { P.ouverte = null; rendre(); };
    pageB.aller = aller;
  }

  // ===== Variante C : localisé groupé par détenteur ; sans = sélection puis piste =====
  function pageC(racine, s, tous, liste) {
    if (s.cle === "sans") {
      const corps = entete(racine, s, tous, liste, barreLot());
      const c = cols(s.cle);
      tableau(corps, trier(liste, c), c, { cases: true, ligne: e => { P.choix.has(e.id) ? P.choix.delete(e.id) : P.choix.add(e.id); rendre(); },
        apres: () => `<button class="p-mini" data-x="url">URL</button> <button class="p-mini" data-x="fichier">Fichier</button>` });
      brancherLot(); brancherSorties(corps, liste);
      return;
    }
    const corps = entete(racine, s, tous, liste);
    const groupes = {};
    liste.forEach(e => e.localisations.forEach(l => (groupes[l.source] ??= []).push(e)));
    const cles = Object.keys(groupes).sort((a, b) => {
      const ra = groupes[a].map(relanceDe).filter(Boolean).sort()[0] || "9999", rb = groupes[b].map(relanceDe).filter(Boolean).sort()[0] || "9999";
      return ra.localeCompare(rb) || groupes[b].length - groupes[a].length; });
    cles.forEach(src => {
      const l = groupes[src], ouvert = P.detOuvert.has(src) || cles.length === 1;
      const ent = []; const vus = new Set();
      l.forEach(e => e.localisations.filter(x => x.source === src).forEach(x => (x.journal || []).forEach(j => { const k = j.date + j.texte; if (vus.has(k)) { ent.find(z => z.k === k).n++; return; } vus.add(k); ent.push({ ...j, k, n: 1 }); })));
      ent.sort((a, b) => b.date.localeCompare(a.date));
      const relance = l.map(relanceDe).filter(Boolean).sort()[0];
      const nom = src === "ina" ? "INA mediapro (notices Archives Radio Pro)" : src;
      const det = document.createElement("div"); det.className = "carte p-det";
      det.innerHTML = `<div class="tete"><span>${ouvert ? "▾" : "▸"}</span><b>${esc(nom)}</b><span class="doux">${l.length} émission(s) · ${l[0].annee === l.at(-1).annee ? l[0].annee : `${Math.min(...l.map(e => e.annee))}-${Math.max(...l.map(e => e.annee))}`}</span>
        <span class="doux">dernier échange : ${ent[0] ? `${-jours(ent[0].date)} j` : "aucun"}</span><span>relance : ${relanceHtml(relance)}</span></div>`;
      det.querySelector(".tete").onclick = () => { P.detOuvert.has(src) ? P.detOuvert.delete(src) : P.detOuvert.add(src); rendre(); };
      if (ouvert) {
        const b = document.createElement("div"); b.className = "corps";
        b.innerHTML = `<div><h4>Journal du détenteur</h4>${journalHtml(ent.map(x => ({ ...x, texte: x.texte + (x.n < l.length ? ` (${x.n} émission${x.n > 1 ? "s" : ""})` : "") })), "Aucun échange noté.")}<h4 style="margin-top:10px">Noter un échange pour ses ${l.length} émission(s)</h4></div>
          <div><h4>Ses émissions</h4><table><tbody>${l.slice(0, 40).map(e => `<tr data-id="${esc(e.id)}"><td>${e.date}</td><td>${esc(e.titre)}</td><td style="white-space:nowrap"><button class="p-mini" data-x="url">URL</button> <button class="p-mini" data-x="fichier">Fichier</button></td></tr>`).join("")}</tbody></table>${l.length > 40 ? `<div class="doux">… ${l.length - 40} de plus</div>` : ""}</div>`;
        b.firstElementChild.append(formEchange({ ids: l.map(e => e.id), localisations: [{ source: src }] }, src));
        det.append(b);
        brancherSorties(b, l);
      }
      corps.append(det);
    });
  }
  function brancherSorties(zone, liste) {
    zone.querySelectorAll("button[data-x]").forEach(b => b.onclick = ev => { ev.stopPropagation();
      const e = liste.find(x => x.id === b.closest("tr").dataset.id); let fermer;
      fermer = b.dataset.x === "url" ? dialogue(`${e.date} : une URL`, formUrl(e, () => fermer())) : dialogue(`${e.date} : le fichier`, formFichier(e, () => fermer())); });
  }

  // ----- Branchement sur la vraie page -----
  const PAGES = { A: pageA, B: pageB, C: pageC };
  const pageReelle = pageEtat;
  pageEtat = function (racine) {
    if (vue.etat !== "sans" && vue.etat !== "localise") { document.querySelector(".p-fiche")?.remove(); document.body.classList.remove("p-avec-fiche"); return pageReelle(racine); }
    const s = ETAT[vue.etat], tous = EMISSIONS.filter(e => e.etat === vue.etat), liste = tous.filter(e => !vue.annee || e.annee === vue.annee);
    PAGES[variante](racine, s, tous, liste);
  };
  const barre = document.createElement("div"); barre.id = "bascule";
  barre.innerHTML = `<button id="p-g" title="variante précédente (←)">◀</button><span id="p-nom"></span><button id="p-d" title="variante suivante (→)">▶</button>`;
  document.body.append(barre);
  const CLES = Object.keys(NOMS);
  const nommer = () => { $("p-nom").textContent = `PROTOTYPE ${variante} · ${NOMS[variante]}`; };
  function basculer(d) {
    variante = CLES[(CLES.indexOf(variante) + d + CLES.length) % CLES.length];
    const u = new URL(location); u.searchParams.set("variant", variante); history.replaceState(null, "", u);
    P.ouverte = null; nommer(); rendre();
  }
  $("p-g").onclick = () => basculer(-1); $("p-d").onclick = () => basculer(1); nommer();
  // ce script arrive après le premier rendu de la page : on la redessine
  if (EMISSIONS.length) rendre();
  addEventListener("keydown", ev => {
    if (ev.target.closest("input, textarea, select, [contenteditable]") || $("boite").open) return;
    if (ev.key === "ArrowLeft") basculer(-1); if (ev.key === "ArrowRight") basculer(1);
    if (variante === "B" && P.ouverte && pageB.aller) { if (ev.key === "ArrowUp") { ev.preventDefault(); pageB.aller(-1); } if (ev.key === "ArrowDown") { ev.preventDefault(); pageB.aller(1); } if (ev.key === "Escape") { P.ouverte = null; rendre(); } }
  });
})();
