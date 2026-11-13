/* Radar Infermiere P.IVA – web app. Nessuna libreria esterna.
   I testi degli annunci arrivano da siti esterni: si scrivono sempre con textContent, mai come HTML. */
(function () {
  "use strict";

  var DATI = { offerte: [], report: [], comuni: [], strutture: [], incontri: [], conti: {}, oggi: null, generato: null, casa: "Mezzolombardo", email_contatto: {} };
  var VISTA = "oggi";
  var FILTRI_BASE = { testo: "", contratto: "", distanza: "", stato: "attive", struttura: "", fonte: "", zona: "", ordine: "punteggio" };
  var FILTRI = copia(FILTRI_BASE);
  var CHIAVE = "radar-miei-stati";
  var MIEI = leggiMiei();
  var RADAR_GIA_ANIMATO = false;
  var MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
  var ETICHETTE = { interessante: "Interessante", contattato: "Contattato", scartato: "Scartato" };
  var NS = "http://www.w3.org/2000/svg";

  // ---------- memoria sul telefono (stati e note) ----------
  function leggiMiei() {
    try { return JSON.parse(localStorage.getItem(CHIAVE) || "{}"); } catch (e) { return {}; }
  }
  function salvaMiei() {
    try { localStorage.setItem(CHIAVE, JSON.stringify(MIEI)); } catch (e) { /* memoria non disponibile */ }
  }
  function mio(id) { return MIEI[id] || {}; }
  function copia(o) { var c = {}, k; for (k in o) c[k] = o[k]; return c; }

  // ---------- piccoli aiuti ----------
  function el(tag, attr) {
    var n = document.createElement(tag), i, k;
    attr = attr || {};
    for (k in attr) {
      if (k === "class") n.className = attr[k];
      else if (k === "text") n.textContent = attr[k];
      else if (k.indexOf("on") === 0) n.addEventListener(k.slice(2), attr[k]);
      else if (attr[k] !== null && attr[k] !== undefined && attr[k] !== false) n.setAttribute(k, attr[k]);
    }
    for (i = 2; i < arguments.length; i++) {
      var f = arguments[i];
      if (f === null || f === undefined || f === false) continue;
      n.appendChild(typeof f === "string" ? document.createTextNode(f) : f);
    }
    return n;
  }
  function sv(tag, attr) {
    var n = document.createElementNS(NS, tag), k;
    for (k in attr) n.setAttribute(k, attr[k]);
    return n;
  }
  function giorno(iso) {
    if (!iso) return "n.d.";
    var p = iso.split("-");
    return p[2] + "/" + p[1] + "/" + p[0];
  }
  function giornoBreve(iso) {
    var p = iso.split("-");
    return Number(p[2]) + " " + MESI[Number(p[1]) - 1];
  }
  function giorniDa(iso) {
    if (!iso || !DATI.oggi) return null;
    return Math.round((Date.parse(iso) - Date.parse(DATI.oggi)) / 86400000);
  }
  function plurale(n, uno, molti) { return n + " " + (n === 1 ? uno : molti); }
  function eNuovo(o) { var g = giorniDa(o.data_novita); return !!o.novita && g !== null && g >= -2; }
  function eAttiva(o) { return !o.scaduto && !o.sparito_dal && mio(o.id).stato !== "scartato"; }
  function linkSicuro(u) { return /^https?:\/\//i.test(u || "") ? u : "#"; }
  function comune(nome) { return DATI.comuni.filter(function (c) { return c.nome === nome; })[0]; }
  function trova(id) { return DATI.offerte.filter(function (z) { return z.id === id; })[0]; }
  function quando(o) {
    var g = giorniDa(o.scadenza);
    if (g === null) return null;
    if (g < 0) return "scaduta il " + giornoBreve(o.scadenza);
    if (g === 0) return "scade oggi";
    if (g === 1) return "scade domani";
    if (g <= 7) return "scade tra " + g + " giorni";
    return "scade il " + giornoBreve(o.scadenza);
  }
  function classePunti(p) { return p >= 60 ? "punti alto" : p >= 45 ? "punti medio" : "punti"; }

  // ---------- anello del punteggio ----------
  function anello(p) {
    var r = 20, giro = 2 * Math.PI * r;
    var svg = sv("svg", { viewBox: "0 0 46 46", "aria-hidden": "true" });
    svg.appendChild(sv("circle", { class: "binario", cx: 23, cy: 23, r: r }));
    svg.appendChild(sv("circle", { class: "arco", cx: 23, cy: 23, r: r, "stroke-dasharray": (giro * Math.max(0, Math.min(100, p)) / 100).toFixed(1) + " " + giro.toFixed(1) }));
    return el("span", { class: classePunti(p), role: "img", "aria-label": "Punteggio " + p + " su 100" }, svg, el("b", { text: String(p) }));
  }

  // ---------- riga di un'offerta ----------
  function riga(o, opzioni) {
    opzioni = opzioni || {};
    var m = mio(o.id), g = giorniDa(o.scadenza);
    var segni = el("span", { class: "segni" });
    if (eNuovo(o) && !o.scaduto) segni.appendChild(el("span", { class: "segno nuovo", text: o.novita === "nuovo" ? "Nuovo" : "Aggiornato" }));
    segni.appendChild(el("span", { class: "segno" + (o.piva ? " piva" : ""), text: o.etichetta || "Contratto non indicato" }));
    if (opzioni.conData) segni.appendChild(el("span", { class: "segno", text: o.punteggio + " punti" }));
    else if (o.scaduto) segni.appendChild(el("span", { class: "segno", text: o.datato ? "Datata" : "Scaduta" }));
    else if (g !== null && g <= 7) segni.appendChild(el("span", { class: "segno scade", text: quando(o) }));
    else if (g !== null) segni.appendChild(el("span", { class: "segno liscio", text: quando(o) }));
    if (o.sparito_dal) segni.appendChild(el("span", { class: "segno", text: "Non più in elenco" }));
    if (m.stato) segni.appendChild(el("span", { class: "segno mio", text: ETICHETTE[m.stato] }));

    var sinistra;
    if (opzioni.conData && o.scadenza) {
      sinistra = el("span", { class: "giorno" + (g !== null && g <= 3 ? " urgente" : "") },
        el("b", { text: String(Number(o.scadenza.split("-")[2])) }), el("small", { text: MESI[Number(o.scadenza.split("-")[1]) - 1] }));
    } else {
      sinistra = anello(o.punteggio);
    }
    var dove = o.zona
      ? el("span", { class: "dove" }, el("b", { text: o.minuti + "′" }), el("small", { text: o.zona }))
      : el("span", { class: "dove" }, el("small", { text: "zona n.d." }));
    return el("button", { class: "riga" + (o.scaduto || o.sparito_dal || m.stato === "scartato" ? " spenta" : ""), onclick: function () { apriScheda(o.id); } },
      sinistra,
      el("span", { class: "chi" },
        el("strong", { text: o.datore || o.titolo }),
        o.datore && o.titolo !== o.datore ? el("span", { class: "ruolo", text: o.titolo }) : null,
        segni),
      dove);
  }
  function elenco(v, offerte, opzioni, seVuoto) {
    if (!offerte.length) { v.appendChild(el("p", { class: "vuoto", text: seVuoto })); return; }
    var blocco = el("div");
    offerte.forEach(function (o) { blocco.appendChild(riga(o, opzioni)); });
    v.appendChild(blocco);
  }
  function titoloSezione(testo, nota) {
    return el("h2", { class: "sezione" }, testo, nota ? el("small", { text: nota }) : null);
  }

  // ---------- radar: casa al centro, distanza in minuti, direzione reale ----------
  function zoneAttive() {
    var z = {};
    DATI.offerte.forEach(function (o) {
      if (!o.zona || !eAttiva(o)) return;
      z[o.zona] = z[o.zona] || { n: 0, piva: 0, migliore: 0 };
      z[o.zona].n += 1;
      if (o.piva) z[o.zona].piva += 1;
      z[o.zona].migliore = Math.max(z[o.zona].migliore, o.punteggio);
    });
    return z;
  }
  function radar(animato) {
    var L = 360, C = 180, R = 146;
    function raggio(min) { return R * Math.sqrt(Math.min(min, 90) / 90); }
    var svg = sv("svg", { viewBox: "0 0 " + L + " " + L, role: "img", "aria-label": "Radar delle offerte attorno a " + DATI.casa + ": distanza in minuti d'auto" });
    svg.appendChild(sv("line", { class: "asse", x1: C, y1: C - R, x2: C, y2: C + R }));
    svg.appendChild(sv("line", { class: "asse", x1: C - R, y1: C, x2: C + R, y2: C }));
    [20, 45, 90].forEach(function (min) {
      var r = raggio(min);
      svg.appendChild(sv("circle", { class: "anello", cx: C, cy: C, r: r.toFixed(1) }));
      var t = sv("text", { class: "tacca", x: (C + 4).toFixed(1), y: (C - r - 4).toFixed(1) });
      t.textContent = min + "′";
      svg.appendChild(t);
    });
    var nord = sv("text", { class: "tacca", x: C - 12, y: C - R - 4, "text-anchor": "end" });
    nord.textContent = "N";
    svg.appendChild(nord);
    svg.appendChild(sv("line", { class: "spazzata", x1: C, y1: C, x2: C, y2: C - R }));

    var casa = comune(DATI.casa), zone = zoneAttive(), punti = [];
    Object.keys(zone).forEach(function (nome) {
      var c = comune(nome);
      if (!c || !casa) return;
      var f = Math.PI / 180;
      var a = Math.atan2((c.lon - casa.lon) * Math.cos(casa.lat * f), c.lat - casa.lat);  // 0 = nord, senso orario
      var r = c.minuti === 0 ? 0 : (c.minuti > 90 ? R + 14 : Math.max(20, raggio(c.minuti)));
      punti.push({ nome: nome, c: c, z: zone[nome], a: a, x: C + r * Math.sin(a), y: C - r * Math.cos(a),
        raggio: 7 + Math.min(7, 2.2 * Math.sqrt(zone[nome].n)) });
    });
    // Etichette: si prova a destra, a sinistra, sotto e sopra il punto; vince la prima posizione
    // che non copre altri punti né altre etichette e resta dentro il disegno.
    punti.sort(function (p, q) { return p.c.minuti - q.c.minuti; });
    var scatole = [];
    function libera(s) {
      if (s.x1 < 2 || s.x2 > L - 2 || s.y1 < 2 || s.y2 > L - 2) return false;
      var k;
      for (k = 0; k < punti.length; k++) {
        var q = punti[k];
        if (q.x + q.raggio > s.x1 && q.x - q.raggio < s.x2 && q.y + q.raggio > s.y1 && q.y - q.raggio < s.y2) return false;
      }
      for (k = 0; k < scatole.length; k++) {
        var t = scatole[k];
        if (t.x1 < s.x2 && t.x2 > s.x1 && t.y1 < s.y2 && t.y2 > s.y1) return false;
      }
      return true;
    }
    punti.forEach(function (p) {
      p.testo = p.nome.length <= 13 ? p.nome : p.nome.split(" ").slice(0, 2).join(" ");
      var w = p.testo.length * 5.9 + 4, d = p.raggio + 4, destraPrima = p.x >= C;
      var prove = [
        { x: p.x + d, y: p.y + 4, ancora: "start" }, { x: p.x - d, y: p.y + 4, ancora: "end" },
        { x: p.x, y: p.y + d + 9, ancora: "middle" }, { x: p.x, y: p.y - d - 2, ancora: "middle" },
        { x: p.x + d, y: p.y + 15, ancora: "start" }, { x: p.x - d, y: p.y + 15, ancora: "end" },
        { x: p.x + d, y: p.y - 8, ancora: "start" }, { x: p.x - d, y: p.y - 8, ancora: "end" }
      ];
      if (!destraPrima) prove = [prove[1], prove[0], prove[2], prove[3], prove[5], prove[4], prove[7], prove[6]];
      var scelta = null;
      prove.forEach(function (e) {
        if (scelta) return;
        var x1 = e.ancora === "start" ? e.x : e.ancora === "end" ? e.x - w : e.x - w / 2;
        var s = { x1: x1, x2: x1 + w, y1: e.y - 10, y2: e.y + 3 };
        if (libera(s)) { scelta = e; scatole.push(s); }
      });
      p.etichetta = scelta;  // se non c'è posto, il nome resta solo nell'elenco e nel titolo del punto
    });
    punti.forEach(function (p) {
      var gradi = ((p.a * 180 / Math.PI) + 360) % 360;
      var g = sv("g", { class: "eco" + (p.z.piva ? " piva" : ""), tabindex: "0", role: "button",
        "aria-label": p.nome + ": " + plurale(p.z.n, "offerta", "offerte") + ", " + p.c.minuti + " minuti" });
      g.style.setProperty("--ritardo", (gradi / 360 * 1.8).toFixed(2) + "s");
      g.appendChild(sv("circle", { cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: p.raggio.toFixed(1) }));
      var n = sv("text", { x: p.x.toFixed(1), y: (p.y + 3.7).toFixed(1) });
      n.textContent = p.z.n;
      g.appendChild(n);
      var titolo = sv("title", {});
      titolo.textContent = p.nome + ": " + plurale(p.z.n, "offerta", "offerte") + (p.z.piva ? " (" + p.z.piva + " in libera professione)" : "") + ", " + p.c.minuti + " min";
      g.appendChild(titolo);
      g.addEventListener("click", function () { vaiAZona(p.nome); });
      g.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); vaiAZona(p.nome); } });
      svg.appendChild(g);
      if (p.etichetta) {
        var nome = sv("text", { class: "nome", x: p.etichetta.x.toFixed(1), y: p.etichetta.y.toFixed(1), "text-anchor": p.etichetta.ancora });
        nome.textContent = p.testo;
        svg.appendChild(nome);
      }
    });
    if (casa && !zone[DATI.casa]) svg.appendChild(sv("circle", { class: "casa", cx: C, cy: C, r: 4.5 }));
    var scatola = el("div", { class: "radar" + (animato ? " vivo" : "") });
    scatola.appendChild(svg);
    return scatola;
  }
  function legendaRadar() {
    return el("p", { class: "legenda" },
      el("span", {}, el("i", { class: "piva" }), "con libera professione"),
      el("span", {}, el("i", {}), "solo altri contratti"),
      el("span", { text: "Anelli: 20, 45 e 90 minuti d'auto da " + DATI.casa }));
  }

  // ---------- vista: oggi ----------
  function vistaOggi(v) {
    var attive = DATI.offerte.filter(eAttiva);
    var ultimo = DATI.report[0];
    var novita = [];
    if (ultimo) {
      (ultimo.nuovi || []).concat(ultimo.aggiornati || []).forEach(function (r) {
        var o = trova(r.id);
        if (o && eAttiva(o) && novita.indexOf(o) < 0) novita.push(o);
      });
    }
    var scadono = attive.filter(function (o) { var g = giorniDa(o.scadenza); return g !== null && g >= 0 && g <= 7; })
      .sort(function (a, b) { return a.scadenza < b.scadenza ? -1 : 1; });
    var piva = attive.filter(function (o) { return o.piva; });

    v.appendChild(el("h1", { class: "titolo", text: "Consegne" }));
    v.appendChild(el("p", { class: "sotto-titolo", text: (DATI.oggi_lungo || "") + (DATI.ora ? ", aggiornate alle " + DATI.ora : "") }));
    if (!DATI.offerte.length) {
      v.appendChild(el("p", { class: "vuoto", text: "Ancora nessun dato. Il primo giro del Radar li porterà qui." }));
      return;
    }
    var frase = el("p", { class: "sommario" });
    frase.appendChild(el("b", { text: novita.length ? plurale(novita.length, "novità", "novità") : "Nessuna novità" }));
    frase.appendChild(document.createTextNode(novita.length ? " dall'ultimo giro, " : " dall'ultimo giro. "));
    frase.appendChild(el("b", { text: scadono.length ? plurale(scadono.length, "scadenza", "scadenze") : "nessuna scadenza" }));
    frase.appendChild(document.createTextNode(" entro una settimana. In tutto " + plurale(attive.length, "offerta attiva", "offerte attive") +
      ", di cui " + piva.length + " in libera professione."));
    v.appendChild(frase);

    v.appendChild(radar(!RADAR_GIA_ANIMATO));
    RADAR_GIA_ANIMATO = true;
    v.appendChild(legendaRadar());

    var incontri = (DATI.incontri || []).filter(function (x) { return x.data >= DATI.oggi; });
    if (incontri.length) {
      v.appendChild(titoloSezione("Incontri"));
      incontri.forEach(function (x) {
        v.appendChild(el("div", { class: "pannello" }, el("p", { text: x.nome + ", " + giorno(x.data) + (x.ora ? " alle " + x.ora : "") }),
          el("div", { class: "azioni" }, el("a", { class: "azione principale", href: x.ics, text: "Aggiungi al calendario" }))));
      });
    }
    var conRisposta = DATI.offerte.filter(function (o) { return o.contatto && o.contatto.risposte.length; });
    if (conRisposta.length) { v.appendChild(titoloSezione("Hanno risposto")); elenco(v, conRisposta, {}, ""); }
    var daScrivere = attive.filter(function (o) { return o.da_contattare && !mio(o.id).inviata; });
    if (daScrivere.length) {
      v.appendChild(titoloSezione("Da contattare oggi", plurale(daScrivere.length, "email pronta", "email pronte")));
      elenco(v, daScrivere, {}, "");
      v.appendChild(el("p", { class: "nota", text: "Apri l'offerta e tocca «Prepara l'email»: la invii tu. A ogni struttura si scrive una volta sola." }));
    }

    v.appendChild(titoloSezione("Novità", ultimo && ultimo.data !== DATI.oggi ? "giro del " + giornoBreve(ultimo.data) : null));
    elenco(v, novita.slice(0, 8), {}, "Niente di nuovo dall'ultimo giro.");
    if (novita.length > 8) v.appendChild(el("button", { class: "collegamento", text: "Vedi tutte le novità", onclick: function () { FILTRI = copia(FILTRI_BASE); FILTRI.stato = "nuove"; cambiaVista("offerte"); } }));

    v.appendChild(titoloSezione("Scadono entro 7 giorni"));
    elenco(v, scadono, { conData: true }, "Nessuna scadenza nei prossimi 7 giorni.");

    var migliori = piva.filter(function (o) { return novita.indexOf(o) < 0; }).slice(0, 3);
    v.appendChild(titoloSezione("Libera professione, le più adatte"));
    elenco(v, migliori, {}, "Nessuna offerta in libera professione attiva al momento.");
    v.appendChild(el("button", { class: "collegamento", text: "Vedi tutte le offerte in libera professione", onclick: function () { FILTRI = copia(FILTRI_BASE); FILTRI.contratto = "piva"; cambiaVista("offerte"); } }));

    if (ultimo) {
      v.appendChild(titoloSezione("Fonti"));
      v.appendChild(el("p", { class: "vuoto", text: ultimo.fonti_lette + " fonti lette su " + ultimo.fonti_totali + " nell'ultimo giro." }));
      (ultimo.problemi || []).forEach(function (p) { v.appendChild(el("p", { class: "avviso", text: p })); });
    }
  }

  // ---------- vista: offerte ----------
  function filtra() {
    var t = FILTRI.testo.toLowerCase();
    var r = DATI.offerte.filter(function (o) {
      var m = mio(o.id).stato || "";
      if (t && ((o.titolo || "") + " " + (o.datore || "") + " " + (o.zona || "") + " " + (o.fonte || "") + " " + (o.struttura || "")).toLowerCase().indexOf(t) < 0) return false;
      if (FILTRI.contratto === "piva" && !o.piva) return false;
      if (FILTRI.contratto === "dip" && !o.dipendente) return false;
      if (FILTRI.contratto === "nd" && o.contratto) return false;
      if (FILTRI.distanza && !(o.minuti !== null && o.minuti <= Number(FILTRI.distanza))) return false;
      if (FILTRI.struttura && o.struttura !== FILTRI.struttura) return false;
      if (FILTRI.fonte && o.fonte !== FILTRI.fonte) return false;
      if (FILTRI.zona && o.zona !== FILTRI.zona) return false;
      switch (FILTRI.stato) {
        case "attive": return eAttiva(o);
        case "nuove": return eNuovo(o) && eAttiva(o);
        case "valutare": return !m && eAttiva(o);
        case "interessante": case "contattato": case "scartato": return m === FILTRI.stato;
        case "chiuse": return o.scaduto || !!o.sparito_dal;
        default: return true;
      }
    });
    var lontano = "9999-99-99";
    r.sort(function (a, b) {
      if (FILTRI.ordine === "recenti") return (b.primo_visto || "").localeCompare(a.primo_visto || "") || (b.pubblicato || "").localeCompare(a.pubblicato || "") || b.punteggio - a.punteggio;
      if (FILTRI.ordine === "scadenza") return (a.scadenza || lontano).localeCompare(b.scadenza || lontano) || b.punteggio - a.punteggio;
      if (FILTRI.ordine === "distanza") return (a.minuti === null ? 999 : a.minuti) - (b.minuti === null ? 999 : b.minuti) || b.punteggio - a.punteggio;
      return b.punteggio - a.punteggio;
    });
    return r;
  }
  function scelta(nome, voci) {
    var predefinito = FILTRI_BASE[nome];
    var s = el("select", { "aria-label": nome, class: FILTRI[nome] !== predefinito ? "scelto" : "",
      onchange: function () { FILTRI[nome] = s.value; disegna(); } });
    voci.forEach(function (v) { var o = el("option", { value: v[0], text: v[1] }); if (FILTRI[nome] === v[0]) o.selected = true; s.appendChild(o); });
    return s;
  }
  function distinti(campo) {
    var visti = {};
    DATI.offerte.forEach(function (o) { if (o[campo]) visti[o[campo]] = 1; });
    return Object.keys(visti).sort().map(function (x) { return [x, x]; });
  }
  function vistaOfferte(v) {
    v.appendChild(el("h1", { class: "titolo", text: "Offerte" }));
    var cerca = el("input", { class: "cerca", type: "search", placeholder: "Cerca struttura, zona, ruolo", value: FILTRI.testo, "aria-label": "Cerca tra le offerte" });
    cerca.addEventListener("input", function () { FILTRI.testo = cerca.value; lista(); });
    var barra = el("div", { class: "filtri" },
      scelta("ordine", [["punteggio", "Per punteggio"], ["recenti", "Più recenti"], ["scadenza", "Per scadenza"], ["distanza", "Più vicine"]]),
      scelta("stato", [["attive", "Attive"], ["nuove", "Novità"], ["valutare", "Da valutare"], ["interessante", "Interessanti"], ["contattato", "Contattate"], ["scartato", "Scartate"], ["chiuse", "Scadute o datate"], ["tutte", "Tutte"]]),
      scelta("contratto", [["", "Ogni contratto"], ["piva", "Libera professione"], ["dip", "Dipendente"], ["nd", "Non indicato"]]),
      scelta("distanza", [["", "Ogni distanza"], ["20", "Entro 20 min"], ["45", "Entro 45 min"], ["90", "Entro 90 min"]]),
      scelta("struttura", [["", "Ogni struttura"]].concat(distinti("struttura"))),
      scelta("fonte", [["", "Ogni fonte"]].concat(distinti("fonte"))));
    if (FILTRI.zona) barra.insertBefore(el("button", { class: "pastiglia", text: FILTRI.zona + "  ✕", "aria-label": "Togli il filtro sulla zona " + FILTRI.zona, onclick: function () { FILTRI.zona = ""; disegna(); } }), barra.firstChild);
    var conta = el("p", { class: "conta" }), contenitore = el("div");
    function lista() {
      var r = filtra();
      conta.textContent = plurale(r.length, "offerta", "offerte");
      contenitore.textContent = "";
      if (!r.length) contenitore.appendChild(el("p", { class: "vuoto", text: DATI.offerte.length ? "Nessuna offerta con questi filtri. Prova a toglierne uno." : "Ancora nessun dato. Il primo giro del Radar li porterà qui." }));
      r.forEach(function (o) { contenitore.appendChild(riga(o, { conData: FILTRI.ordine === "scadenza" && !!o.scadenza && !o.scaduto })); });
    }
    v.appendChild(cerca); v.appendChild(barra); v.appendChild(conta); v.appendChild(contenitore);
    lista();
  }

  // ---------- vista: scadenze ----------
  function vistaScadenze(v) {
    v.appendChild(el("h1", { class: "titolo", text: "Scadenze" }));
    var conData = DATI.offerte.filter(function (o) { var g = giorniDa(o.scadenza); return g !== null && g >= 0 && eAttiva(o); })
      .sort(function (a, b) { return a.scadenza < b.scadenza ? -1 : 1; });
    function tra(da, a) { return conData.filter(function (o) { var g = giorniDa(o.scadenza); return g >= da && g <= a; }); }
    v.appendChild(titoloSezione("Entro 7 giorni"));
    elenco(v, tra(0, 7), { conData: true }, "Nessuna scadenza nei prossimi 7 giorni.");
    v.appendChild(titoloSezione("Entro 30 giorni"));
    elenco(v, tra(8, 30), { conData: true }, "Nessun'altra scadenza entro 30 giorni.");
    var dopo = tra(31, 100000);
    if (dopo.length) {
      v.appendChild(titoloSezione("Più avanti"));
      elenco(v, dopo, { conData: true }, "");
    }
    v.appendChild(el("p", { class: "nota", text: "Molti annunci non dichiarano una scadenza: qui compaiono solo quelli che la indicano. Dalla scheda puoi aggiungerla al calendario." }));
  }

  // ---------- vista: zone ----------
  function vaiAZona(z) { FILTRI = copia(FILTRI_BASE); FILTRI.zona = z; cambiaVista("offerte"); }
  function vistaZone(v) {
    v.appendChild(el("h1", { class: "titolo", text: "Zone" }));
    v.appendChild(el("p", { class: "sotto-titolo", text: "Dove sono le offerte attive, per minuti d'auto da " + DATI.casa }));
    v.appendChild(radar(false));
    v.appendChild(legendaRadar());
    var zone = zoneAttive();
    var righe = Object.keys(zone).map(comune).filter(Boolean).sort(function (a, b) { return a.minuti - b.minuti; });
    v.appendChild(titoloSezione("Dalla più vicina"));
    if (!righe.length) v.appendChild(el("p", { class: "vuoto", text: "Nessuna offerta attiva con una zona riconosciuta." }));
    var blocco = el("div");
    righe.forEach(function (c) {
      var z = zone[c.nome];
      blocco.appendChild(el("button", { class: "zona-riga", onclick: function () { vaiAZona(c.nome); } },
        el("b", { text: c.minuti + "′" }),
        el("span", { text: c.nome }),
        el("small", { class: z.piva ? "piva" : "", text: plurale(z.n, "offerta", "offerte") + (z.piva ? ", " + z.piva + " in libera professione" : "") })));
    });
    v.appendChild(blocco);
    var senza = DATI.offerte.filter(function (o) { return !o.zona && eAttiva(o); }).length;
    v.appendChild(el("p", { class: "nota", text: (senza ? plurale(senza, "offerta attiva non ha", "offerte attive non hanno") + " una zona riconosciuta. " : "") +
      "Minuti e chilometri sono stime: la tabella si può correggere nel file data/comuni.csv." }));
  }

  // ---------- vista: report e andamento ----------
  function graficoContratti(v) {
    var conteggi = {};
    DATI.offerte.filter(eAttiva).forEach(function (o) { var k = o.etichetta || "Contratto non indicato"; conteggi[k] = (conteggi[k] || 0) + 1; });
    var voci = Object.keys(conteggi).map(function (k) { return [k, conteggi[k]]; }).sort(function (a, b) { return b[1] - a[1]; });
    if (!voci.length) { v.appendChild(el("p", { class: "vuoto", text: "Nessuna offerta attiva." })); return; }
    var massimo = voci[0][1], blocco = el("div", { class: "barre", role: "list" });
    voci.forEach(function (x) {
      var barra = el("i");
      barra.style.width = Math.max(2, Math.round(x[1] / massimo * 100)) + "%";
      blocco.appendChild(el("div", { class: "barra", role: "listitem" }, el("span", { text: x[0] }), el("span", { class: "pista" }, barra, el("b", { text: String(x[1]) }))));
    });
    v.appendChild(blocco);
  }
  function graficoNovita(v) {
    var perGiorno = {};
    DATI.report.forEach(function (r) { perGiorno[r.data] = (r.nuovi || []).length; });
    var giorni = [], i, base = Date.parse(DATI.oggi);
    for (i = 13; i >= 0; i--) giorni.push(new Date(base - i * 86400000).toISOString().slice(0, 10));
    var valori = giorni.map(function (g) { return perGiorno[g] === undefined ? null : perGiorno[g]; });
    var massimo = Math.max.apply(null, valori.map(function (x) { return x || 0; }));
    if (!massimo) { v.appendChild(el("p", { class: "vuoto", text: "Nessuna novità registrata negli ultimi 14 giorni." })); return; }
    var lettura = el("p", { class: "lettura", "aria-live": "polite", text: "Tocca una colonna per leggere il giorno." });
    var colonne = el("div", { class: "colonne" }), assi = el("div", { class: "assi", "aria-hidden": "true" });
    var indiceMassimo = valori.indexOf(massimo);
    giorni.forEach(function (g, k) {
      var val = valori[k] || 0, barra = el("i");
      barra.style.height = (massimo ? Math.round(val / massimo * 100) : 0) + "%";
      var testo = giornoBreve(g) + ": " + (valori[k] === null ? "nessun giro" : plurale(val, "novità", "novità"));
      var col = el("button", { class: "colonna" + (val ? "" : " zero"), "aria-label": testo, title: testo, onclick: function () {
        Array.prototype.forEach.call(colonne.children, function (c) { c.classList.remove("scelta"); });
        col.classList.add("scelta"); lettura.textContent = testo;
      } }, (val && (k === indiceMassimo || k === giorni.length - 1)) ? el("b", { text: String(val) }) : null, barra);
      colonne.appendChild(col);
      assi.appendChild(el("span", { text: (k % 2 === 1 || k === giorni.length - 1) ? String(Number(g.slice(8))) : "" }));
    });
    v.appendChild(colonne); v.appendChild(assi); v.appendChild(lettura);
  }
  function voceReport(r) {
    var testo = (r.datore || r.titolo) + (r.zona ? ", " + r.zona : "") + (r.scadenza ? ", scade il " + giornoBreve(r.scadenza) : "");
    return el("button", { class: "voce", onclick: function () { apriScheda(r.id); } }, el("b", { text: String(r.punteggio) }), el("span", { text: testo }));
  }
  function vistaReport(v) {
    v.appendChild(el("h1", { class: "titolo", text: "Report" }));
    if (!DATI.report.length) { v.appendChild(el("p", { class: "vuoto", text: "Ancora nessun report. Arriva dopo il primo giro del Radar." })); return; }
    v.appendChild(titoloSezione("Offerte attive per contratto"));
    graficoContratti(v);
    v.appendChild(titoloSezione("Novità al giorno", "ultimi 14 giorni"));
    graficoNovita(v);
    v.appendChild(titoloSezione("Archivio dei giri"));
    DATI.report.forEach(function (rep, i) {
      var parti = [];
      if (rep.nuovi.length) parti.push(plurale(rep.nuovi.length, "novità", "novità"));
      if (rep.aggiornati.length) parti.push(rep.aggiornati.length + " aggiornate");
      if (rep.scadenze7.length) parti.push(plurale(rep.scadenze7.length, "scadenza", "scadenze"));
      if (rep.problemi.length) parti.push(plurale(rep.problemi.length, "fonte da controllare", "fonti da controllare"));
      var d = el("details", { class: "rep" }, el("summary", {}, giornoBreve(rep.data), el("small", { text: parti.join(", ") || "niente di nuovo" })));
      if (i === 0) d.open = true;
      [["Novità", rep.nuovi], ["Aggiornate", rep.aggiornati], ["Scadenze entro 7 giorni", rep.scadenze7], ["Le 5 migliori", rep.top5]].forEach(function (s) {
        if (!s[1].length) return;
        d.appendChild(el("h4", { text: s[0] }));
        s[1].forEach(function (r) {
          d.appendChild(voceReport(r));
          if (r.cambi && r.cambi.length && s[0] === "Aggiornate") d.appendChild(el("p", { class: "nota", text: "Cambiato: " + r.cambi.join("; ") }));
        });
      });
      if (rep.problemi.length) {
        d.appendChild(el("h4", { text: "Fonti da controllare" }));
        rep.problemi.forEach(function (p) { d.appendChild(el("p", { class: "prob", text: p })); });
      }
      d.appendChild(el("p", { class: "nota", text: plurale(rep.attivi, "offerta attiva", "offerte attive") + ", " + rep.fonti_lette + " fonti lette su " + rep.fonti_totali }));
      v.appendChild(d);
    });
  }

  // ---------- scheda offerta ----------
  function dato(nome, valore) {
    return el("div", { class: "dato" }, el("span", { text: nome }), el("span", { class: valore ? "" : "nd", text: valore || "n.d." }));
  }
  function testoEmail(o) {
    var modello = DATI.email_contatto || {};
    function riempi(s) {
      return (s || "").replace(/\{titolo\}/g, o.titolo || "").replace(/\{datore\}/g, o.datore || "").replace(/\{fonte\}/g, o.fonte || "").replace(/\{rif\}/g, o.rif || "");
    }
    return { oggetto: riempi(modello.oggetto || "Richiesta di informazioni – {titolo}"), testo: riempi(modello.testo || "") };
  }
  function copiaTesto(testo, bottone) {
    function fatto() { var prima = bottone.textContent; bottone.textContent = "Copiato"; setTimeout(function () { bottone.textContent = prima; }, 1600); }
    if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(testo).then(fatto, function () {}); return; }
    var area = el("textarea"); area.value = testo; document.body.appendChild(area); area.select();
    try { document.execCommand("copy"); fatto(); } catch (e) { /* copia non disponibile */ }
    document.body.removeChild(area);
  }
  function apriScheda(id) {
    var o = trova(id);
    var box = document.getElementById("scheda");
    box.textContent = "";
    var corpo = el("div");
    corpo.appendChild(el("button", { class: "chiudi", text: "‹ Indietro", onclick: chiudiScheda }));
    if (!o) {
      corpo.appendChild(el("p", { class: "vuoto", text: "Questa offerta non è più in elenco." }));
      box.appendChild(corpo); box.hidden = false; document.body.style.overflow = "hidden"; return;
    }
    var m = mio(o.id), g = giorniDa(o.scadenza);
    corpo.appendChild(el("div", { class: "capo" },
      el("div", {}, el("h2", { text: o.datore || o.titolo }), o.datore && o.titolo !== o.datore ? el("p", { class: "ruolo", text: o.titolo }) : null),
      anello(o.punteggio)));
    if (o.datato) corpo.appendChild(el("p", { class: "avviso rosso", text: "Annuncio datato: pubblicato il " + giorno(o.pubblicato) + ". Probabilmente non è più aperto." }));
    else if (o.scaduto) corpo.appendChild(el("p", { class: "avviso rosso", text: "Scadenza passata (" + giorno(o.scadenza) + ")." }));
    else if (g !== null && g <= 7) corpo.appendChild(el("p", { class: "avviso rosso", text: "Attenzione: " + quando(o) + " (" + giorno(o.scadenza) + ")." }));
    if (o.sparito_dal) corpo.appendChild(el("p", { class: "avviso", text: "Dal " + giorno(o.sparito_dal) + " non compare più nell'elenco della fonte: potrebbe essere chiuso." }));
    if (o.cambi && o.cambi.length && eNuovo(o)) corpo.appendChild(el("p", { class: "avviso", text: "Aggiornato il " + giorno(o.data_novita) + ": " + o.cambi.join("; ") }));
    (o.avvisi || []).forEach(function (a) { corpo.appendChild(el("p", { class: "avviso", text: a })); });
    if (o.nota_manuale) corpo.appendChild(el("p", { class: "avviso", text: o.nota_manuale }));

    var azioni = el("div", { class: "azioni" });
    azioni.appendChild(el("a", { class: "azione principale", href: linkSicuro(o.url), target: "_blank", rel: "noopener noreferrer", text: "Apri l'annuncio originale" }));
    if (o.zona) azioni.appendChild(el("a", { class: "azione", href: "https://maps.apple.com/?dirflg=d&daddr=" + encodeURIComponent(o.zona + ", Trentino-Alto Adige, Italia"), target: "_blank", rel: "noopener noreferrer", text: "Indicazioni stradali" }));
    if (o.pdf_letti && o.pdf_letti.length && o.pdf_letti[0] !== o.url) azioni.appendChild(el("a", { class: "azione", href: linkSicuro(o.pdf_letti[0]), target: "_blank", rel: "noopener noreferrer", text: "Apri l'avviso in PDF" }));
    if (o.calendario) azioni.appendChild(el("a", { class: "azione", href: "ics/" + o.id + ".ics", text: "Scadenza nel calendario" }));
    if (o.excel) azioni.appendChild(el("a", { class: "azione", href: o.excel, download: "", text: "Excel costi-benefici" }));
    corpo.appendChild(azioni);
    if (o.conti) corpo.appendChild(el("p", { class: "avviso neutro", text: "In tasca circa " + o.conti.netto_ora.toLocaleString("it-IT") + " € netti all'ora (" + o.conti.netto_ora_porta_a_porta.toLocaleString("it-IT") + " contando il viaggio)" +
      (o.conti.turni_per_obiettivo ? ". Servirebbero " + o.conti.turni_per_obiettivo + " turni al mese per l'obiettivo" : "") + (o.conti.tariffa_stimata ? ". Compenso non dichiarato: stimo " + o.conti.tariffa + " €/h." : ".") }));
    if (o.email || o.pec) {
      corpo.appendChild(titoloSezione("Primo contatto"));
      bottoniPosta(corpo, o.id, o.email, o.pec, testoEmail(o), o.contatto);
      corpo.appendChild(el("p", { class: "nota", text: "È una richiesta di informazioni, non una candidatura. Parte dal tuo telefono solo quando tocchi Invia." }));
    }
    bloccoRisposte(corpo, o.contatto);

    corpo.appendChild(el("div", { class: "dati" },
      dato("Contratto", o.contratto), dato("Compenso", o.compenso), dato("Ore e turni", o.turni),
      dato("Zona", o.zona ? o.zona + ", circa " + o.minuti + " min e " + o.km + " km da " + DATI.casa : null),
      dato("Scadenza", o.scadenza ? giorno(o.scadenza) + (o.scadenza_frase ? " («" + o.scadenza_frase + "»)" : "") : null), dato("Pubblicato", o.pubblicato ? giorno(o.pubblicato) : null),
      dato("Struttura", o.struttura), dato("Contatti", [o.email, o.pec ? o.pec + " (PEC)" : null].filter(Boolean).join(", ") || null),
      dato("Fonte", o.fonte), dato("Visto dal", giorno(o.primo_visto) + (o.ultimo_visto ? ", ultimo controllo il " + giornoBreve(o.ultimo_visto) : ""))));

    corpo.appendChild(titoloSezione("Perché " + o.punteggio + " punti su 100"));
    var misure = el("div", { class: "dati" });
    (o.dettaglio_punteggio || []).forEach(function (d) {
      var r = el("div", { class: "misura" },
        el("div", { class: "sopra" }, el("span", { text: d.voce }), el("b", { text: d.max ? d.punti + " su " + d.max : String(d.punti) })));
      if (d.max) { var bin = el("div", { class: "binario" }), pieno = el("i"); pieno.style.width = Math.max(0, Math.round(d.punti / d.max * 100)) + "%"; bin.appendChild(pieno); r.appendChild(bin); }
      r.appendChild(el("small", { text: d.motivo }));
      misure.appendChild(r);
    });
    corpo.appendChild(misure);

    corpo.appendChild(titoloSezione("Il mio stato"));
    var stati = el("div", { class: "stati" });
    Object.keys(ETICHETTE).forEach(function (s) {
      stati.appendChild(el("button", { class: m.stato === s ? "scelto" : "", text: ETICHETTE[s], "aria-pressed": String(m.stato === s), onclick: function () {
        MIEI[o.id] = MIEI[o.id] || {};
        MIEI[o.id].stato = MIEI[o.id].stato === s ? "" : s;
        salvaMiei(); var y = box.scrollTop; apriScheda(o.id); box.scrollTop = y; disegna();
      } }));
    });
    corpo.appendChild(stati);
    var appunto = el("textarea", { class: "appunto", placeholder: "Appunti (restano su questo telefono)", "aria-label": "Appunti personali" });
    appunto.value = m.nota || "";
    appunto.addEventListener("input", function () { MIEI[o.id] = MIEI[o.id] || {}; MIEI[o.id].nota = appunto.value; salvaMiei(); });
    corpo.appendChild(appunto);

    if (o.estratto) {
      corpo.appendChild(titoloSezione("Dall'annuncio"));
      corpo.appendChild(el("p", { class: "estratto", text: o.estratto }));
    }
    corpo.appendChild(el("p", { class: "nota", text: "Dati estratti in automatico: possono contenere errori. Controlla sempre l'annuncio originale." }));
    box.appendChild(corpo);
    box.hidden = false; box.scrollTop = 0;
    document.body.style.overflow = "hidden";
    if (location.hash !== "#o=" + o.id) history.pushState({ scheda: o.id }, "", "#o=" + o.id);
  }
  function chiudiScheda() {
    var box = document.getElementById("scheda");
    if (box.hidden) return;
    box.hidden = true; document.body.style.overflow = "";
    if (location.hash.indexOf("#o=") === 0) history.replaceState(null, "", location.pathname + location.search);
  }
  window.addEventListener("popstate", function () { document.getElementById("scheda").hidden = true; document.body.style.overflow = ""; });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") chiudiScheda(); });

  // ---------- memoria sul telefono: agenda e conti ----------
  function leggiChiave(k, base) { try { return JSON.parse(localStorage.getItem(k) || "null") || base; } catch (e) { return base; } }
  function salvaChiave(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* memoria non disponibile */ } }
  var AGENDA = leggiChiave("radar-agenda", { giorni: {} });
  var CONTI_MIEI = leggiChiave("radar-conti", {});
  var MESE_AGENDA = null, GIORNO_SCELTO = null, AVVISO_AGENDA = "", ALTRO = "strutture";
  var GIORNI_SETT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"];
  var MESI_LUNGHI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"];
  var TIPI_TURNO = { M: ["Mattina", 7], P: ["Pomeriggio", 7], N: ["Notte", 10], G: ["Giornata", 12], X: ["Impegno personale", 0] };

  function isoDi(d) { return d.getUTCFullYear() + "-" + ("0" + (d.getUTCMonth() + 1)).slice(-2) + "-" + ("0" + d.getUTCDate()).slice(-2); }
  function dataDi(iso) { var p = iso.split("-"); return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])); }
  function piu(iso, n) { var d = dataDi(iso); d.setUTCDate(d.getUTCDate() + n); return isoDi(d); }
  function giornoSett(iso) { return (dataDi(iso).getUTCDay() + 6) % 7; }   // 0 = lunedì
  function lunedi(iso) { return piu(iso, -giornoSett(iso)); }
  function nomeGiorno(iso) { return GIORNI_SETT[giornoSett(iso)] + " " + Number(iso.slice(8)); }
  function euro(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".") + " €"; }
  function conti() {
    var c = copia(DATI.conti || {}), k;
    for (k in CONTI_MIEI) if (CONTI_MIEI[k] !== null && CONTI_MIEI[k] !== "") c[k] = Number(CONTI_MIEI[k]);
    var contributi = c.coefficiente * c.enpapi;
    c.quota = 1 - contributi - (c.coefficiente - contributi) * c.imposta;
    return c;
  }

  // Due giorni liberi per ogni settimana (lun-dom). Non sono fissi: si spostano da soli quando aggiungi un turno,
  // preferendo sabato e domenica, poi due giorni vicini. Il giorno dopo una notte è smonto, non riposo.
  function settimana(lun) {
    var giorni = [], i, g;
    for (i = 0; i < 7; i++) {
      g = piu(lun, i);
      var t = AGENDA.giorni[g], ieri = AGENDA.giorni[piu(g, -1)];
      giorni.push({ iso: g, turno: t && t.tipo !== "X" ? t : null, impegno: t && t.tipo === "X" ? t : null, smonto: !!(ieri && ieri.tipo === "N") && !(t && t.tipo !== "X") });
    }
    var liberi = giorni.filter(function (x) { return !x.turno && !x.smonto; }).map(function (x) { return giornoSett(x.iso); });
    var migliore = null, a, b, punti;
    for (a = 0; a < liberi.length; a++) for (b = a + 1; b < liberi.length; b++) {
      punti = (liberi[a] >= 5 ? 3 : 1) + (liberi[b] >= 5 ? 3 : 1) + (liberi[b] - liberi[a] === 1 ? 2 : 0) + (liberi[b] === 6 && liberi[a] === 4 ? 1 : 0) + (liberi[b] === 5 && liberi[a] === 4 ? 1 : 0);
      if (!migliore || punti > migliore.punti) migliore = { punti: punti, giorni: [liberi[a], liberi[b]] };
    }
    var riposi = migliore ? migliore.giorni : liberi.slice(0, 1);
    giorni.forEach(function (x) { x.riposo = riposi.indexOf(giornoSett(x.iso)) >= 0; x.offribile = !x.turno && !x.smonto && !x.riposo && !x.impegno; });
    return { lun: lun, giorni: giorni, mancano: Math.max(0, 2 - liberi.length), weekendLibero: riposi.indexOf(5) >= 0 && riposi.indexOf(6) >= 0 };
  }
  function riposiDi(lun) { return settimana(lun).giorni.filter(function (x) { return x.riposo; }).map(function (x) { return x.iso; }); }
  function mettiTurno(iso, turno) {
    var lun = lunedi(iso), prima = riposiDi(lun);
    if (turno) AGENDA.giorni[iso] = turno; else delete AGENDA.giorni[iso];
    salvaChiave("radar-agenda", AGENDA);
    var s = settimana(lun), dopo = riposiDi(lun);
    var persi = prima.filter(function (x) { return dopo.indexOf(x) < 0; }), nuovi = dopo.filter(function (x) { return prima.indexOf(x) < 0; });
    AVVISO_AGENDA = s.mancano ? "Attenzione: in questa settimana " + (s.mancano === 2 ? "non resta nessun giorno libero" : "resta un solo giorno libero") + ". Sposta o rifiuta un turno."
      : (persi.length && nuovi.length ? "Giorno libero spostato da " + persi.map(nomeGiorno).join(" e ") + " a " + nuovi.map(nomeGiorno).join(" e ") + "." : "");
  }
  function turniDelMese(mese) {
    return Object.keys(AGENDA.giorni).filter(function (g) { return g.slice(0, 7) === mese && AGENDA.giorni[g].tipo !== "X"; }).sort()
      .map(function (g) { var t = copia(AGENDA.giorni[g]); t.iso = g; return t; });
  }
  function contoMese(mese) {
    var c = conti(), turni = turniDelMese(mese), fatturato = 0, ore = 0, viaggi = 0;
    turni.forEach(function (t) { fatturato += (t.ore || 0) * (t.tariffa || 0); ore += t.ore || 0; viaggi += 2 * (t.km || 0) * c.costo_km; });
    return { turni: turni.length, ore: ore, fatturato: fatturato, netto: fatturato * c.quota - viaggi - c.spese_fisse_mese - c.fondo_pensione_mese };
  }
  function luoghi() {
    var visti = {}, elenco = [];
    (DATI.strutture || []).forEach(function (s) { if (!visti[s.nome]) { visti[s.nome] = 1; elenco.push({ nome: s.nome, km: s.km || 0, tariffa: null }); } });
    DATI.offerte.forEach(function (o) { var n = o.datore || o.titolo; if (o.piva && !visti[n]) { visti[n] = 1; elenco.push({ nome: n, km: o.km || 0, tariffa: o.euro_ora }); } });
    return elenco;
  }
  function campoNumero(etichetta, valore, alCambio, passo) {
    var i = el("input", { type: "number", inputmode: "decimal", step: passo || "1", value: valore === null || valore === undefined ? "" : String(valore), "aria-label": etichetta });
    i.addEventListener("change", function () { alCambio(i.value === "" ? null : Number(i.value)); });
    return el("label", { class: "campo" }, el("span", { text: etichetta }), i);
  }

  // ---------- vista: agenda ----------
  function vistaAgenda(v) {
    if (!MESE_AGENDA) MESE_AGENDA = (DATI.oggi || isoDi(new Date())).slice(0, 7);
    var primo = MESE_AGENDA + "-01", anno = +MESE_AGENDA.slice(0, 4), mese = +MESE_AGENDA.slice(5, 7);
    function sposta(n) { var d = dataDi(primo); d.setUTCMonth(d.getUTCMonth() + n); MESE_AGENDA = isoDi(d).slice(0, 7); GIORNO_SCELTO = null; AVVISO_AGENDA = ""; disegna(); }
    v.appendChild(el("h1", { class: "titolo", text: "Agenda" }));
    v.appendChild(el("p", { class: "sotto-titolo", text: "Due giorni liberi a settimana, sempre. Si spostano da soli quando aggiungi un turno." }));
    v.appendChild(el("div", { class: "mese-nav" },
      el("button", { "aria-label": "Mese precedente", text: "‹", onclick: function () { sposta(-1); } }),
      el("b", { text: MESI_LUNGHI[mese - 1] + " " + anno }),
      el("button", { "aria-label": "Mese successivo", text: "›", onclick: function () { sposta(1); } })));
    if (AVVISO_AGENDA) v.appendChild(el("p", { class: "avviso" + (AVVISO_AGENDA.indexOf("Attenzione") === 0 ? " rosso" : ""), role: "status", text: AVVISO_AGENDA }));

    var griglia = el("div", { class: "calendario" });
    GIORNI_SETT.forEach(function (g) { griglia.appendChild(el("span", { class: "capo-giorno", text: g })); });
    var lun = lunedi(primo), settimane = [], scadenze = {}, incontri = {};
    DATI.offerte.forEach(function (o) { if (o.scadenza && eAttiva(o)) scadenze[o.scadenza] = (scadenze[o.scadenza] || 0) + 1; });
    (DATI.incontri || []).forEach(function (x) { incontri[x.data] = x; });
    while (lun.slice(0, 7) <= MESE_AGENDA) { settimane.push(settimana(lun)); lun = piu(lun, 7); if (settimane.length > 5) break; }
    settimane.forEach(function (s) {
      s.giorni.forEach(function (x) {
        var fuori = x.iso.slice(0, 7) !== MESE_AGENDA, classi = "giorno-cal";
        if (fuori) classi += " fuori";
        if (x.turno) classi += " turno"; else if (x.riposo) classi += " riposo"; else if (x.smonto) classi += " smonto";
        if (x.iso === DATI.oggi) classi += " oggi";
        if (x.iso === GIORNO_SCELTO) classi += " scelto";
        var sigla = x.turno ? x.turno.tipo : (x.impegno ? "•" : (x.smonto ? "sm" : (x.riposo ? "lib" : "")));
        var voce = nomeGiorno(x.iso) + (x.turno ? ", turno " + TIPI_TURNO[x.turno.tipo][0] : x.riposo ? ", giorno libero" : x.smonto ? ", smonto notte" : "");
        griglia.appendChild(el("button", { class: classi, "aria-label": voce, onclick: function () { GIORNO_SCELTO = x.iso; AVVISO_AGENDA = ""; disegna(); } },
          el("b", { text: String(Number(x.iso.slice(8))) }), el("small", { text: sigla }),
          (scadenze[x.iso] || incontri[x.iso]) ? el("i", { class: incontri[x.iso] ? "punto incontro" : "punto" }) : null));
      });
    });
    v.appendChild(griglia);
    v.appendChild(el("div", { class: "legenda" }, el("span", {}, el("i", { class: "piva" }), "Turno"), el("span", {}, el("i", { class: "lib" }), "Giorno libero"), el("span", {}, el("i", {}), "Scadenza o incontro")));

    if (GIORNO_SCELTO) v.appendChild(schedaGiorno(GIORNO_SCELTO, scadenze, incontri));

    var cm = contoMese(MESE_AGENDA), c = conti();
    var weekendLiberi = settimane.filter(function (s) { return s.weekendLibero; }).length;
    v.appendChild(titoloSezione("Il mese"));
    v.appendChild(el("div", { class: "dati" },
      dato("Turni", cm.turni ? cm.turni + " (" + cm.ore + " ore)" : "nessuno"),
      dato("Fatturato", cm.turni ? euro(cm.fatturato) : null),
      dato("Netto stimato", cm.turni ? euro(cm.netto) + " su " + euro(c.obiettivo_netto_mese) + " di obiettivo" : null),
      dato("Weekend liberi", weekendLiberi + " su " + settimane.length)));
    settimane.forEach(function (s) { if (s.mancano) v.appendChild(el("p", { class: "avviso rosso", text: "Settimana del " + Number(s.lun.slice(8)) + " " + MESI[+s.lun.slice(5, 7) - 1] + ": " + (s.mancano === 2 ? "nessun giorno libero" : "un solo giorno libero") + "." })); });
    if (cm.turni && weekendLiberi < 2) v.appendChild(el("p", { class: "avviso", text: "Meno di due weekend liberi questo mese: se puoi, sposta un turno del sabato o della domenica in settimana." }));

    var offribili = [];
    settimane.forEach(function (s) { s.giorni.forEach(function (x) { if (x.offribile && x.iso.slice(0, 7) === MESE_AGENDA && x.iso >= (DATI.oggi || "")) offribili.push(x.iso); }); });
    v.appendChild(titoloSezione("Giorni che puoi offrire", offribili.length ? String(offribili.length) : null));
    if (offribili.length) {
      var testo = "Disponibilità di " + MESI_LUNGHI[mese - 1] + ": " + offribili.map(nomeGiorno).join(", ") + ".";
      v.appendChild(el("p", { class: "vuoto", text: offribili.map(nomeGiorno).join(", ") }));
      var bCopia = el("button", { class: "azione", text: "Copia le disponibilità" });
      bCopia.addEventListener("click", function () { copiaTesto(testo, bCopia); });
      var turni = turniDelMese(MESE_AGENDA);
      var az = el("div", { class: "azioni" }, bCopia);
      if (turni.length) az.appendChild(el("a", { class: "azione", href: "data:text/calendar;charset=utf-8," + encodeURIComponent(icsTurni(turni)), download: "turni-" + MESE_AGENDA + ".ics", text: "Turni nel calendario" }));
      v.appendChild(az);
      v.appendChild(el("p", { class: "nota", text: "Sono i giorni senza turni che non servono come giorni liberi. Se ne dai via uno, i giorni liberi restano due." }));
    } else v.appendChild(el("p", { class: "vuoto", text: "Nessun giorno da offrire in questo mese senza toccare i giorni liberi." }));
    v.appendChild(el("button", { class: "collegamento", text: "Scadenze degli annunci", onclick: function () { cambiaVista("scadenze"); } }));
  }
  function icsTurni(turni) {
    var orari = { M: ["070000", "140000"], P: ["140000", "210000"], N: ["210000", "070000"], G: ["070000", "190000"] };
    var r = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Radar Infermiere//IT"];
    turni.forEach(function (t) {
      var g = t.iso.replace(/-/g, ""), fine = (t.tipo === "N" ? piu(t.iso, 1) : t.iso).replace(/-/g, ""), o = orari[t.tipo] || orari.M;
      r.push("BEGIN:VEVENT", "UID:turno-" + t.iso + "@radar-infermiere", "DTSTAMP:" + g + "T000000Z", "DTSTART;TZID=Europe/Rome:" + g + "T" + o[0], "DTEND;TZID=Europe/Rome:" + fine + "T" + o[1],
        "SUMMARY:Turno " + TIPI_TURNO[t.tipo][0] + (t.dove ? " - " + String(t.dove).replace(/[,;\\\n]/g, " ") : ""), "END:VEVENT");
    });
    r.push("END:VCALENDAR");
    return r.join("\r\n");
  }
  function schedaGiorno(iso, scadenze, incontri) {
    var t = AGENDA.giorni[iso] || {}, c = conti(), box = el("div", { class: "pannello" });
    box.appendChild(el("h3", { text: nomeGiorno(iso) + " " + MESI_LUNGHI[+iso.slice(5, 7) - 1] }));
    if (incontri[iso]) box.appendChild(el("p", { class: "avviso", text: "Incontro con " + incontri[iso].nome + (incontri[iso].ora ? " alle " + incontri[iso].ora : "") }));
    if (scadenze[iso]) box.appendChild(el("p", { class: "nota", text: plurale(scadenze[iso], "annuncio scade", "annunci scadono") + " in questo giorno." }));
    var tipo = el("select", { "aria-label": "Tipo di turno" });
    Object.keys(TIPI_TURNO).forEach(function (k) { var o = el("option", { value: k, text: TIPI_TURNO[k][0] }); if ((t.tipo || "M") === k) o.selected = true; tipo.appendChild(o); });
    var dove = el("input", { type: "text", list: "luoghi", placeholder: "Dove (struttura)", value: t.dove || "", "aria-label": "Struttura" });
    var lista = el("datalist", { id: "luoghi" });
    var noti = luoghi(); noti.forEach(function (l) { lista.appendChild(el("option", { value: l.nome })); });
    var ore = el("input", { type: "number", inputmode: "decimal", value: String(t.ore || TIPI_TURNO[t.tipo || "M"][1]), "aria-label": "Ore" });
    var tariffa = el("input", { type: "number", inputmode: "decimal", value: String(t.tariffa || c.tariffa_predefinita), "aria-label": "Euro all'ora" });
    tipo.addEventListener("change", function () { ore.value = String(TIPI_TURNO[tipo.value][1]); });
    dove.addEventListener("change", function () { var l = noti.filter(function (x) { return x.nome === dove.value; })[0]; if (l && l.tariffa) tariffa.value = String(l.tariffa); });
    box.appendChild(el("div", { class: "modulo" }, el("label", { class: "campo largo" }, el("span", { text: "Turno" }), tipo), el("label", { class: "campo largo" }, el("span", { text: "Dove" }), dove, lista),
      el("label", { class: "campo" }, el("span", { text: "Ore" }), ore), el("label", { class: "campo" }, el("span", { text: "€ all'ora" }), tariffa)));
    var az = el("div", { class: "azioni" });
    az.appendChild(el("button", { class: "azione principale", text: AGENDA.giorni[iso] ? "Aggiorna" : "Aggiungi", onclick: function () {
      var l = noti.filter(function (x) { return x.nome === dove.value; })[0];
      mettiTurno(iso, { tipo: tipo.value, dove: dove.value.trim(), ore: tipo.value === "X" ? 0 : Number(ore.value) || 0, tariffa: tipo.value === "X" ? 0 : Number(tariffa.value) || 0, km: l ? l.km : 0 });
      disegna();
    } }));
    if (AGENDA.giorni[iso]) az.appendChild(el("button", { class: "azione", text: "Togli", onclick: function () { mettiTurno(iso, null); disegna(); } }));
    az.appendChild(el("button", { class: "azione", text: "Chiudi", onclick: function () { GIORNO_SCELTO = null; disegna(); } }));
    box.appendChild(az);
    return box;
  }

  // ---------- vista: conti ----------
  function vistaConti(v) {
    var c = conti(), mese = (DATI.oggi || isoDi(new Date())).slice(0, 7);
    function cambia(k) { return function (val) { CONTI_MIEI[k] = val; salvaChiave("radar-conti", CONTI_MIEI); disegna(); }; }
    var nettoTurno = c.tariffa_predefinita * c.ore_turno * c.quota;
    var serve = c.obiettivo_netto_mese + c.fondo_pensione_mese + c.spese_fisse_mese;
    var turni = nettoTurno > 0 ? Math.ceil(serve / nettoTurno) : 0, fatturato = serve / c.quota;
    v.appendChild(el("h1", { class: "titolo", text: "Conti" }));
    v.appendChild(el("p", { class: "sotto-titolo", text: "Quanto serve lavorare per avere " + euro(c.obiettivo_netto_mese) + " netti al mese, dopo tasse, contributi, spese e fondo pensione." }));
    v.appendChild(el("div", { class: "cifra" }, el("b", { text: String(turni) }), el("span", { text: "turni al mese da " + c.ore_turno + " ore a " + c.tariffa_predefinita + " €/h, circa " + (Math.round(turni / 4.33 * 10) / 10).toLocaleString("it-IT") + " a settimana" })));
    v.appendChild(el("div", { class: "dati" },
      dato("Da fatturare", euro(fatturato) + " al mese, " + euro(fatturato * 12) + " l'anno"),
      dato("Di cui ENPAPI", euro(fatturato * c.coefficiente * c.enpapi) + " al mese"),
      dato("Di cui imposta", euro(fatturato * (c.coefficiente - c.coefficiente * c.enpapi) * c.imposta) + " al mese"),
      dato("Resta di ogni euro", Math.round(c.quota * 100) + " centesimi, prima di spese e fondo"),
      dato("Limite forfettario", fatturato * 12 > c.limite_forfettario ? "superato: " + euro(fatturato * 12) + " su " + euro(c.limite_forfettario) : "margine di " + euro(c.limite_forfettario - fatturato * 12))));

    var cm = contoMese(mese);
    v.appendChild(titoloSezione("Questo mese in agenda"));
    if (cm.turni) {
      var manca = c.obiettivo_netto_mese - cm.netto;
      v.appendChild(el("div", { class: "dati" }, dato("Turni segnati", cm.turni + " (" + cm.ore + " ore)"), dato("Fatturato", euro(cm.fatturato)), dato("Netto stimato", euro(cm.netto)),
        dato("Per l'obiettivo", manca <= 0 ? "raggiunto, con " + euro(-manca) + " di margine" : "mancano " + euro(manca) + ", circa " + Math.ceil(manca / nettoTurno) + " turni")));
    } else v.appendChild(el("p", { class: "vuoto", text: "Segna i turni nell'Agenda, anche di strutture diverse: qui li sommo e ti dico quanto manca all'obiettivo." }));

    v.appendChild(titoloSezione("I tuoi numeri"));
    v.appendChild(el("div", { class: "modulo" },
      campoNumero("Obiettivo netto al mese", c.obiettivo_netto_mese, cambia("obiettivo_netto_mese"), "50"),
      campoNumero("Fondo pensione al mese", c.fondo_pensione_mese, cambia("fondo_pensione_mese"), "50"),
      campoNumero("Spese fisse al mese", c.spese_fisse_mese, cambia("spese_fisse_mese"), "10"),
      campoNumero("Compenso medio €/h", c.tariffa_predefinita, cambia("tariffa_predefinita"), "1"),
      campoNumero("Ore per turno", c.ore_turno, cambia("ore_turno"), "1"),
      campoNumero("Imposta (0,05 o 0,15)", c.imposta, cambia("imposta"), "0.01")));
    v.appendChild(el("p", { class: "nota", text: "Stima per il regime forfettario: reddito al 78% del fatturato, ENPAPI 16% del reddito, imposta sul reddito tolti i contributi. Il 4% integrativo lo paga il cliente. Fai controllare i numeri al commercialista prima di decidere." }));

    var conConti = DATI.offerte.filter(function (o) { return o.conti && eAttiva(o); })
      .sort(function (a, b) { return b.conti.netto_ora_porta_a_porta - a.conti.netto_ora_porta_a_porta; });
    v.appendChild(titoloSezione("Offerte a confronto", "netto all'ora, viaggio compreso"));
    if (!conConti.length) v.appendChild(el("p", { class: "vuoto", text: "Nessuna offerta in libera professione attiva." }));
    conConti.forEach(function (o) {
      v.appendChild(el("button", { class: "zona-riga conto", onclick: function () { apriScheda(o.id); } },
        el("b", { text: o.conti.netto_ora_porta_a_porta.toLocaleString("it-IT", { maximumFractionDigits: 0 }) + " €" }),
        el("span", { text: (o.datore || o.titolo) + (o.zona ? ", " + o.zona : "") }),
        el("small", { text: (o.conti.tariffa_stimata ? "compenso non dichiarato, stimo " : "") + o.conti.tariffa + " €/h, " + (o.conti.turni_per_obiettivo || "n.d.") + " turni" })));
    });
  }

  // ---------- vista: altro (strutture, zone, report, dati) ----------
  function testoStruttura(s) {
    return { oggetto: "Disponibilità come infermiere in libera professione (Rif. " + s.rif + ")",
      testo: "Buongiorno,\n\nsono un infermiere iscritto all'OPI e sto valutando collaborazioni in libera professione in Trentino-Alto Adige.\nVi chiedo se avete bisogno, ora o nei prossimi mesi, di infermieri a partita IVA (turni, sostituzioni, prestazioni), e a quali condizioni: impegno orario e compenso orario.\n\nGrazie e cordiali saluti\nMichael Panico" };
  }
  function linkPosta(indirizzo, posta) { return "mailto:" + encodeURIComponent(indirizzo) + "?subject=" + encodeURIComponent(posta.oggetto) + "&body=" + encodeURIComponent(posta.testo); }
  function segnaInviata(id) { var m = copia(mio(id)); m.inviata = DATI.oggi || isoDi(new Date()); MIEI[id] = m; salvaMiei(); }
  function bottoniPosta(contenitore, chiave, email, pec, posta, contatto) {
    var inviata = (contatto && contatto.inviata_il) || mio(chiave).inviata;
    if (inviata) { contenitore.appendChild(el("p", { class: "nota", text: "Email di primo contatto già inviata il " + giorno(inviata) + ": non la rimando." })); return; }
    var az = el("div", { class: "azioni" });
    if (email) az.appendChild(el("a", { class: "azione principale", href: linkPosta(email, posta), text: "Prepara l'email", onclick: function () { segnaInviata(chiave); } }));
    if (pec) az.appendChild(el("a", { class: "azione" + (email ? "" : " principale"), href: linkPosta(pec, posta), text: "Scrivi alla PEC", onclick: function () { segnaInviata(chiave); } }));
    var b = el("button", { class: "azione", text: "Copia il testo" });
    b.addEventListener("click", function () { copiaTesto(posta.oggetto + "\n\n" + posta.testo, b); });
    az.appendChild(b);
    contenitore.appendChild(az);
    if (pec) contenitore.appendChild(el("p", { class: "nota", text: "Per la PEC: nell'app Mail scegli la tua casella PEC come mittente prima di inviare." }));
  }
  function bloccoRisposte(contenitore, contatto) {
    if (!contatto) return;
    (contatto.risposte || []).forEach(function (r) {
      contenitore.appendChild(titoloSezione("Risposta del " + giorno(r.data)));
      var fatti = [r.compenso, r.turni, r.incontro ? "incontro proposto il " + giorno(r.incontro.data) + (r.incontro.ora ? " alle " + r.incontro.ora : "") : null].filter(Boolean);
      if (fatti.length) contenitore.appendChild(el("p", { class: "avviso", text: "Ho letto: " + fatti.join(", ") + ". Controlla nel testo." }));
      contenitore.appendChild(el("p", { class: "estratto", text: r.testo }));
    });
  }
  function vistaAltro(v) {
    v.appendChild(el("h1", { class: "titolo", text: "Altro" }));
    var barra = el("div", { class: "filtri" });
    [["strutture", "Strutture"], ["zone", "Zone"], ["report", "Report"], ["dati", "I miei dati"]].forEach(function (x) {
      barra.appendChild(el("button", { class: ALTRO === x[0] ? "pastiglia" : "pastiglia spenta", text: x[1], onclick: function () { ALTRO = x[0]; disegna(); } }));
    });
    v.appendChild(barra);
    var dentro = el("div", { class: "dentro" });
    v.appendChild(dentro);
    if (ALTRO === "zone") return vistaZone(dentro);
    if (ALTRO === "report") return vistaReport(dentro);
    if (ALTRO === "dati") return vistaDati(dentro);
    dentro.appendChild(el("p", { class: "sotto-titolo", text: "Posti che cercano infermieri quasi sempre, anche senza un annuncio aperto. Dal più vicino." }));
    (DATI.strutture || []).forEach(function (s) {
      var d = el("details", { class: "rep" });
      d.appendChild(el("summary", {}, el("span", { text: s.nome }), el("small", { text: [s.comune, s.minuti !== null ? s.minuti + " min" : null].filter(Boolean).join(", ") })));
      d.appendChild(el("p", { class: "nota", text: [s.tipo, s.note].filter(Boolean).join(". ") }));
      if (s.email || s.pec) bottoniPosta(d, s.chiave, s.email, s.pec, testoStruttura(s), s.contatto);
      var az = el("div", { class: "azioni" });
      if (s.sito) az.appendChild(el("a", { class: "azione", href: linkSicuro(s.sito), target: "_blank", rel: "noopener noreferrer", text: "Apri il sito" }));
      if (!s.email && !s.pec) az.appendChild(el("a", { class: "azione", href: "https://www.google.com/search?q=" + encodeURIComponent(s.nome + " " + (s.comune || "") + " contatti email PEC"), target: "_blank", rel: "noopener noreferrer", text: "Cerca i contatti" }));
      d.appendChild(az);
      bloccoRisposte(d, s.contatto);
      dentro.appendChild(d);
    });
    dentro.appendChild(el("p", { class: "nota", text: "L'elenco è nel file data/strutture.csv del progetto: lì si aggiungono strutture e indirizzi email." }));
  }
  function vistaDati(v) {
    v.appendChild(el("p", { class: "sotto-titolo", text: "Stati, appunti, turni e numeri dei conti vivono solo su questo telefono. Fanne una copia ogni tanto." }));
    var area = el("textarea", { class: "appunto", "aria-label": "Copia dei dati", placeholder: "Per ripristinare, incolla qui la copia e tocca Ripristina" });
    var bCopia = el("button", { class: "azione", text: "Copia i miei dati" });
    bCopia.addEventListener("click", function () { copiaTesto(JSON.stringify({ stati: MIEI, agenda: AGENDA, conti: CONTI_MIEI }), bCopia); });
    var bRipristina = el("button", { class: "azione", text: "Ripristina", onclick: function () {
      try {
        var d = JSON.parse(area.value);
        if (d.stati) { MIEI = d.stati; salvaMiei(); }
        if (d.agenda && d.agenda.giorni) { AGENDA = d.agenda; salvaChiave("radar-agenda", AGENDA); }
        if (d.conti) { CONTI_MIEI = d.conti; salvaChiave("radar-conti", CONTI_MIEI); }
        area.value = ""; area.placeholder = "Dati ripristinati.";
      } catch (e) { area.value = ""; area.placeholder = "La copia incollata non è valida: copiala di nuovo per intero."; }
    } });
    v.appendChild(el("div", { class: "azioni" }, bCopia, bRipristina));
    v.appendChild(area);
  }

  // ---------- navigazione ----------
  var VISTE = { oggi: vistaOggi, offerte: vistaOfferte, agenda: vistaAgenda, conti: vistaConti, altro: vistaAltro, scadenze: vistaScadenze, zone: vistaZone, report: vistaReport };
  function disegna() {
    var v = document.getElementById("vista");
    v.textContent = "";
    VISTE[VISTA](v);
  }
  function cambiaVista(nome) {
    VISTA = nome;
    Array.prototype.forEach.call(document.querySelectorAll(".schede button"), function (b) {
      var att = b.getAttribute("data-vista") === (nome === "scadenze" ? "agenda" : nome);
      b.className = att ? "attiva" : "";
      if (att) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    });
    disegna(); window.scrollTo(0, 0);
  }
  Array.prototype.forEach.call(document.querySelectorAll(".schede button"), function (b) {
    b.addEventListener("click", function () { if (b.getAttribute("data-vista") === "offerte" && VISTA !== "offerte") FILTRI.zona = ""; cambiaVista(b.getAttribute("data-vista")); });
  });

  // ---------- avvio ----------
  function mostraDati(d) {
    DATI = d;
    var s = document.getElementById("aggiornato");
    var vecchi = d.oggi && (Date.now() - Date.parse(d.oggi)) / 86400000 > 2.2;
    s.textContent = vecchi ? "Dati del " + giornoBreve(d.oggi) + ": riapri l'app con la rete attiva" : "Aggiornato il " + d.generato;
    s.className = "stato-dati" + (vecchi ? " vecchi" : "");
    var m = /^#o=([0-9a-f]+)$/.exec(location.hash);
    if (/^#(offerte|agenda|conti|altro|scadenze)$/.test(location.hash)) cambiaVista(location.hash.slice(1)); else disegna();
    if (m) apriScheda(m[1]);
  }
  fetch("dati.json", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(mostraDati)
    .catch(function () {
      document.getElementById("aggiornato").textContent = "Dati non disponibili";
      var v = document.getElementById("vista");
      v.textContent = "";
      v.appendChild(el("p", { class: "vuoto", text: "Non riesco a caricare i dati. Apri l'app una volta con la connessione attiva; se chiede l'accesso, inserisci la tua email." }));
    });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () { navigator.serviceWorker.register("sw.js").catch(function () {}); });
  }
})();
