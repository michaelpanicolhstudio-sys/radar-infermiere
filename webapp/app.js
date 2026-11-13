/* Radar Infermiere P.IVA – web app. Nessuna libreria esterna.
   I testi degli annunci arrivano da siti esterni: si scrivono sempre con textContent, mai come HTML. */
(function () {
  "use strict";

  var DATI = { offerte: [], report: [], comuni: [], oggi: null, generato: null, casa: "Mezzolombardo", email_contatto: {} };
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
      return (s || "").replace(/\{titolo\}/g, o.titolo || "").replace(/\{datore\}/g, o.datore || "").replace(/\{fonte\}/g, o.fonte || "");
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
    if (o.calendario) azioni.appendChild(el("a", { class: "azione", href: "ics/" + o.id + ".ics", text: "Scadenza nel calendario" }));
    var posta = testoEmail(o);
    if (o.email) azioni.appendChild(el("a", { class: "azione", href: "mailto:" + encodeURIComponent(o.email) + "?subject=" + encodeURIComponent(posta.oggetto) + "&body=" + encodeURIComponent(posta.testo), text: "Scrivi alla struttura" }));
    var copiaBottone = el("button", { class: "azione", text: "Copia testo dell'email" });
    copiaBottone.addEventListener("click", function () { copiaTesto(posta.oggetto + "\n\n" + posta.testo, copiaBottone); });
    azioni.appendChild(copiaBottone);
    corpo.appendChild(azioni);
    corpo.appendChild(el("p", { class: "nota", text: "L'email preparata è una richiesta di informazioni, non una candidatura." }));

    corpo.appendChild(el("div", { class: "dati" },
      dato("Contratto", o.contratto), dato("Compenso", o.compenso), dato("Ore e turni", o.turni),
      dato("Zona", o.zona ? o.zona + ", circa " + o.minuti + " min e " + o.km + " km da " + DATI.casa : null),
      dato("Scadenza", o.scadenza ? giorno(o.scadenza) : null), dato("Pubblicato", o.pubblicato ? giorno(o.pubblicato) : null),
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

  // ---------- navigazione ----------
  var VISTE = { oggi: vistaOggi, offerte: vistaOfferte, scadenze: vistaScadenze, zone: vistaZone, report: vistaReport };
  function disegna() {
    var v = document.getElementById("vista");
    v.textContent = "";
    VISTE[VISTA](v);
  }
  function cambiaVista(nome) {
    VISTA = nome;
    Array.prototype.forEach.call(document.querySelectorAll(".schede button"), function (b) {
      var att = b.getAttribute("data-vista") === nome;
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
    if (/^#(offerte|scadenze|zone|report)$/.test(location.hash)) cambiaVista(location.hash.slice(1)); else disegna();
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
