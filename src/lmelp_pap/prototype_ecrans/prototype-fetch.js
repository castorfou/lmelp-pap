// PROTOTYPE jetable (#87) : chargé AVANT le script de la page. Les données
// (window.PROTO_DONNEES, lues une fois sur pap) vivent en mémoire ; GET
// /api/donnees les rend, les écritures sont simulées ici (rien n'est écrit).
const PROTO = window.PROTO_DONNEES;
const PROTO_JOUR = 86400000;
const ilYa = j => new Date(Date.now() - j * PROTO_JOUR).toISOString();
const dansJ = j => new Date(Date.now() + j * PROTO_JOUR).toISOString().slice(0, 10);
const dateJ = j => ilYa(j).slice(0, 10);
const brut = id => PROTO.emissions.find(e => e.id === id);
const enLmelp = e => e.dans_lmelp || e.attestations.some(a => a.source === "lmelp");

// --- Simulation : pistes de passionnés, journal d'échanges, ancienneté variée ---
(function semer() {
  const sans = PROTO.emissions.filter(e => !e.maturite && !enLmelp(e));
  const entre = (a, b) => sans.filter(e => e.date >= a && e.date <= b);
  const piste = (liste, source, note, journal, ancien) => liste.forEach(e => {
    e.maturite = "localise"; e.maturite_depuis = ilYa(ancien);
    e.localisations = [{ source, note, notice: null, depuis: ilYa(ancien), journal: journal.map(x => ({ ...x })), simule: true }];
  });
  piste(entre("1995-01-01", "1999-12-31").slice(0, 7), "Jean D. (passionné)",
    "Cassettes enregistrées sur France Inter, 1995-1999, d'après son message sur DVDClassik.",
    [{ date: dateJ(41), canal: "forum", interlocuteur: "Jean D.", texte: "Répond à l'appel sur DVDClassik : une quarantaine de cassettes du Masque, fin des années 90, étiquetées à la main." },
     { date: dateJ(33), canal: "courriel", interlocuteur: "Jean D.", texte: "Envoie la liste de ses étiquettes : 7 dates correspondent à des émissions littéraires de la liste.", relance: dateJ(5) }], 41);
  piste(entre("2001-01-01", "2003-12-31").slice(0, 3), "Comité d'histoire de la radiodiffusion",
    "Fonds d'un ancien technicien de France Inter, signalé par le Comité.",
    [{ date: dateJ(12), canal: "courriel", interlocuteur: "secrétariat du Comité", texte: "Le Comité transmet la demande au détenteur du fonds.", relance: dansJ(9) }], 12);
  // INA mediapro : un devis demandé pour 5 émissions (décision « Les sources d'intégraux à exploiter »)
  PROTO.emissions.filter(e => e.maturite === "localise" && e.localisations?.[0]?.source === "ina").slice(-5).forEach(e => {
    e.localisations[0].journal = [{ date: dateJ(18), canal: "courriel", interlocuteur: "INA mediapro", texte: "Demande de devis pour 5 émissions (offre pro, accès particulier ?).", relance: dateJ(4) }];
  });
  PROTO.emissions.filter(e => e.maturite === "localise").forEach((e, i) => {
    if (!e.localisations[0].simule) e.maturite_depuis = e.localisations[0].depuis = ilYa(20 + (i * 7) % 60);
  });
})();

// --- Écritures simulées, appelées par prototype.js ---
const PROTO_ECRIT = {
  piste(ids, source, note, echange) {
    ids.forEach(id => { const e = brut(id);
      e.localisations = e.localisations || [];
      e.localisations.push({ source, note: note || null, notice: null, depuis: new Date().toISOString(), journal: echange ? [{ ...echange }] : [], simule: true });
      if (!e.maturite) { e.maturite = "localise"; e.maturite_depuis = new Date().toISOString(); } });
  },
  echange(id, source, entree) {
    const l = brut(id).localisations.find(x => x.source === source);
    (l.journal ??= []).push({ ...entree });
  },
  url(id, url, note) { const e = brut(id); e.maturite = "telechargeable"; e.maturite_depuis = new Date().toISOString(); e.proto_url = { url, note }; },
  fichier(id, nom, provenance, datation, note) {
    const e = brut(id); e.maturite = "rapatrie"; e.maturite_depuis = new Date().toISOString();
    e.fichier_audio = `pap/audios/${e.date.slice(0, 4)}/${nom || "fichier-televerse.mp3"}`; e.proto_provenance = { provenance, datation, note };
  },
};

const PROTO_FETCH = window.fetch.bind(window);
window.fetch = async (url, options = {}) => {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "Content-Type": "application/json" } });
  if (url === "/api/donnees") return json(structuredClone(PROTO));
  if ((options.method || "GET") !== "GET") {
    if (url === "/api/localisations") { const b = JSON.parse(options.body); PROTO_ECRIT.piste([b.emission_id], b.source, b.note); return json(structuredClone(PROTO)); }
    return json({ erreur: "PROTOTYPE : écriture non simulée" }, 400);
  }
  return PROTO_FETCH(url, options);
};
