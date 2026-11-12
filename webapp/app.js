/* Radar Infermiere P.IVA – web app. Nessuna libreria esterna.
   I testi degli annunci arrivano da siti esterni: si scrivono sempre con textContent, mai come HTML. */
(function () {
  "use strict";

  var DATI = { offerte: [], report: [], comuni: [], oggi: null, generato: null, casa: "Mezzolombardo" };
  var VISTA = "offerte";
  var FILTRI = { testo: "", contratto: "", distanza: "", stato: "attive", fonte: "", zona: "" };
  var CHIAVE = "radar-miei-stati";
  var MIEI = leggiMiei();

  // ---------- memoria sul telefono (stati e note) ----------
  function leggiMiei() {
    try { return JSON.parse(localStorage.getItem(CHIAVE) || "{}"); } catch (e) { return {}; }
  }
  function salvaMiei() {
    try { localStorage.setItem(CHIAVE, JSON.stringify(MIEI)); } catch (e) { /* memoria non disponibile */ }
  }
  function mio(id) { return MIEI[id] || {}; }

  // ---------- piccoli aiuti ----------
  function el(tag, attr) {
    var n = document.createElement(tag), i, k;
    attr = attr || {};
    for (k in attr) {
      if (k === "class") n.className = attr[k];
      else if (k === "text") n.textContent = attr[k];
      else if (k.indexOf("on") === 0) n.addEventListener(k.slice(2), attr[k]);
      else if (attr[k] !== null && attr[k] !== undefined) n.setAttribute(k, attr[k]);
    }
    for (i = 2; i < arguments.length; i++) {
      var f = arguments[i];
      if (f === null || f === undefined || f === false) continue;
      n.appendChild(typeof f === "string" ? document.createTextNode(f) : f);
    }
    return n;
  }
  function giorno(iso) {
    if (!iso) return "n.d.";
    var p = iso.split("-");
    return p[2] + "/" + p[1] + "/" + p[0];
  }
  function giorniDa(iso) {
    if (!iso || !DATI.oggi) return null;
    return Math.round((Date.parse(iso) - Date.parse(DATI.oggi)) / 86400000);
  }
  function classeVoto(p) { return p >= 60 ? "voto alto" : p >= 45 ? "voto medio" : "voto"; }
  function ePiva(o) { return /P\.IVA|Collaborazione/.test(o.contratto || ""); }
  function eNuovo(o) { var g = giorniDa(o.data_novita); return o.novita && g !== null && g >= -2; }
  function linkSicuro(u) { return /^https?:\/\//i.test(u || "") ? u : "#"; }
  function quando(o) {
    var g = giorniDa(o.scadenza);
    if (g === null) return null;
    if (g < 0) return "scaduta il " + giorno(o.scadenza);
    if (g === 0) return "scade oggi";
    if (g === 1) return "scade domani";
    return "scade tra " + g + " giorni (" + giorno(o.scadenza).slice(0, 5) + ")";
  }

  // ---------- card ----------
  function card(o) {
    var m = mio(o.id), g = giorniDa(o.scadenza);
    var righe = el("div", { class: "righe" });
    if (eNuovo(o)) righe.appendChild(el("span", { class: "pill nuovo", text: o.novita === "nuovo" ? "Nuovo" : "Aggiornato" }));
    righe.appendChild(el("span", { class: "pill" + (ePiva(o) ? " piva" : ""), text: o.contratto || "Contratto n.d." }));
    if (g !== null && g >= 0 && g <= 7) righe.appendChild(el("span", { class: "pill scade", text: quando(o) }));
    if (o.scaduto) righe.appendChild(el("span", { class: "pill", text: "Scaduta" }));
    if (m.stato) righe.appendChild(el("span", { class: "pill mio", text: ETICHETTE[m.stato] }));
    var meta = [o.zona ? o.zona + " · " + o.minuti + " min" : "Zona n.d.", o.compenso || "Compenso n.d."];
    if (g !== null && g > 7) meta.push("scade il " + giorno(o.scadenza));
    return el("button", { class: "offerta" + (o.scaduto || m.stato === "scartato" ? " spenta" : ""), onclick: function () { apriScheda(o.id); } },
      el("div", { class: classeVoto(o.punteggio), text: String(o.punteggio), "aria-label": "Punteggio " + o.punteggio }),
      el("div", {},
        el("h3", { text: o.datore || o.titolo }),
        o.datore && o.titolo !== o.datore ? el("p", { class: "ruolo", text: o.titolo }) : null,
        righe,
        el("p", { class: "meta", text: meta.join("  ·  ") })));
  }
  var ETICHETTE = { interessante: "Interessante", contattato: "Contattato", scartato: "Scartato" };

  // ---------- vista: offerte ----------
  function filtra() {
    var t = FILTRI.testo.toLowerCase();
    return DATI.offerte.filter(function (o) {
      var m = mio(o.id).stato || "";
      if (t && ((o.titolo || "") + " " + (o.datore || "") + " " + (o.zona || "") + " " + (o.fonte || "")).toLowerCase().indexOf(t) < 0) return false;
      if (FILTRI.contratto === "piva" && !ePiva(o)) return false;
      if (FILTRI.contratto === "dip" && !o.dipendente) return false;
      if (FILTRI.contratto === "nd" && o.contratto) return false;
      if (FILTRI.distanza && !(o.minuti !== null && o.minuti <= Number(FILTRI.distanza))) return false;
      if (FILTRI.fonte && o.fonte !== FILTRI.fonte) return false;
      if (FILTRI.zona && o.zona !== FILTRI.zona) return false;
      switch (FILTRI.stato) {
        case "attive": return !o.scaduto && m !== "scartato";
        case "nuove": return eNuovo(o) && !o.scaduto;
        case "valutare": return !m && !o.scaduto;
        case "interessante": case "contattato": case "scartato": return m === FILTRI.stato;
        case "scadute": return o.scaduto;
        default: return true;
      }
    });
  }
  function scelta(nome, voci) {
    var s = el("select", { "aria-label": nome, class: FILTRI[nome] && !(nome === "stato" && FILTRI.stato === "attive") ? "scelto" : "",
      onchange: function () { FILTRI[nome] = s.value; disegna(); } });
    voci.forEach(function (v) { var o = el("option", { value: v[0], text: v[1] }); if (FILTRI[nome] === v[0]) o.selected = true; s.appendChild(o); });
    return s;
  }
  function vistaOfferte(v) {
    var cerca = el("input", { class: "cerca", type: "search", placeholder: "Cerca struttura, zona, ruolo…", value: FILTRI.testo, "aria-label": "Cerca" });
    cerca.addEventListener("input", function () { FILTRI.testo = cerca.value; lista(); });
    var fonti = {};
    DATI.offerte.forEach(function (o) { fonti[o.fonte] = 1; });
    var barra = el("div", { class: "filtri" },
      scelta("stato", [["attive", "Attive"], ["nuove", "Novità"], ["valutare", "Da valutare"], ["interessante", "Interessanti"], ["contattato", "Contattate"], ["scartato", "Scartate"], ["scadute", "Scadute"], ["tutte", "Tutte"]]),
      scelta("contratto", [["", "Ogni contratto"], ["piva", "P.IVA e collaborazioni"], ["dip", "Dipendente"], ["nd", "Non indicato"]]),
      scelta("distanza", [["", "Ogni distanza"], ["20", "Entro 20 min"], ["45", "Entro 45 min"], ["90", "Entro 90 min"]]),
      scelta("fonte", [["", "Ogni fonte"]].concat(Object.keys(fonti).sort().map(function (f) { return [f, f]; }))));
    if (FILTRI.zona) barra.insertBefore(el("button", { class: "pastiglia-zona", text: FILTRI.zona + "  ✕", onclick: function () { FILTRI.zona = ""; disegna(); } }), barra.firstChild);
    var conta = el("p", { class: "conta" }), contenitore = el("div");
    function lista() {
      var r = filtra();
      conta.textContent = r.length + (r.length === 1 ? " offerta" : " offerte") + ", dalla più adatta";
      contenitore.textContent = "";
      if (!r.length) contenitore.appendChild(el("p", { class: "vuoto", text: DATI.offerte.length ? "Nessuna offerta con questi filtri." : "Ancora nessun dato. Il primo giro del Radar li porterà qui." }));
      r.forEach(function (o) { contenitore.appendChild(card(o)); });
    }
    v.appendChild(cerca); v.appendChild(barra); v.appendChild(conta); v.appendChild(contenitore);
    lista();
  }

  // ---------- vista: scadenze ----------
  function vistaScadenze(v) {
    var conData = DATI.offerte.filter(function (o) { var g = giorniDa(o.scadenza); return g !== null && g >= 0 && g <= 30 && mio(o.id).stato !== "scartato"; })
      .sort(function (a, b) { return a.scadenza < b.scadenza ? -1 : 1; });
    var sette = conData.filter(function (o) { return giorniDa(o.scadenza) <= 7; });
    var trenta = conData.filter(function (o) { return giorniDa(o.scadenza) > 7; });
    v.appendChild(el("h2", { class: "sezione", text: "Entro 7 giorni" }));
    if (!sette.length) v.appendChild(el("p", { class: "vuoto", text: "Nessuna scadenza nei prossimi 7 giorni." }));
    sette.forEach(function (o) { v.appendChild(card(o)); });
    v.appendChild(el("h2", { class: "sezione", text: "Entro 30 giorni" }));
    if (!trenta.length) v.appendChild(el("p", { class: "vuoto", text: "Nessun'altra scadenza entro 30 giorni." }));
    trenta.forEach(function (o) { v.appendChild(card(o)); });
    v.appendChild(el("p", { class: "piccolo", text: "Molti annunci non indicano una scadenza: qui compaiono solo quelli che la dichiarano." }));
  }

  // ---------- vista: report ----------
  function voceReport(r) {
    var testo = (r.datore || r.titolo) + (r.zona ? " · " + r.zona : "") + (r.scadenza ? " · scade il " + giorno(r.scadenza).slice(0, 5) : "");
    return el("button", { class: "voce", onclick: function () { apriScheda(r.id); } }, el("b", { text: String(r.punteggio) }), testo);
  }
  function vistaReport(v) {
    if (!DATI.report.length) { v.appendChild(el("p", { class: "vuoto", text: "Ancora nessun report. Arriva dopo il primo giro del Radar." })); return; }
    DATI.report.forEach(function (rep, i) {
      var parti = [];
      if (rep.nuovi.length) parti.push(rep.nuovi.length + (rep.nuovi.length === 1 ? " nuova" : " nuove"));
      if (rep.aggiornati.length) parti.push(rep.aggiornati.length + " aggiorn.");
      if (rep.scadenze7.length) parti.push(rep.scadenze7.length + " scad.");
      if (rep.problemi.length) parti.push(rep.problemi.length + " fonti ⚠");
      var d = el("details", { class: "rep" }, el("summary", {}, giorno(rep.data), el("small", { text: parti.join(" · ") || "niente di nuovo" })));
      if (i === 0) d.open = true;
      [["Novità", rep.nuovi], ["Aggiornati", rep.aggiornati], ["Scadenze entro 7 giorni", rep.scadenze7], ["Le 5 migliori", rep.top5]].forEach(function (s) {
        if (!s[1].length) return;
        d.appendChild(el("h4", { text: s[0] }));
        s[1].forEach(function (r) {
          d.appendChild(voceReport(r));
          if (r.cambi && r.cambi.length && s[0] === "Aggiornati") d.appendChild(el("p", { class: "piccolo", text: "Cambiato: " + r.cambi.join("; ") }));
        });
      });
      if (rep.problemi.length) {
        d.appendChild(el("h4", { text: "Fonti non lette o da controllare" }));
        rep.problemi.forEach(function (p) { d.appendChild(el("p", { class: "prob", text: p })); });
      }
      d.appendChild(el("p", { class: "piccolo", text: rep.attivi + " offerte attive · " + rep.fonti_lette + " fonti lette su " + rep.fonti_totali }));
      v.appendChild(d);
    });
  }

  // ---------- vista: mappa ----------
  function vistaMappa(v) {
    var NS = "http://www.w3.org/2000/svg", L = 340, A = 330;
    function sv(tag, attr) { var n = document.createElementNS(NS, tag); for (var k in attr) n.setAttribute(k, attr[k]); return n; }
    function x(lon) { return 14 + (lon - 10.6) / (12.05 - 10.6) * (L - 28); }
    function y(lat) { return 14 + (47.0 - lat) / (47.0 - 45.65) * (A - 28); }
    var conteggi = {};
    DATI.offerte.forEach(function (o) { if (o.zona && !o.scaduto && mio(o.id).stato !== "scartato") conteggi[o.zona] = (conteggi[o.zona] || 0) + 1; });
    var svg = sv("svg", { viewBox: "0 0 " + L + " " + A, role: "img", "aria-label": "Mappa delle offerte attorno a " + DATI.casa });
    var casa = DATI.comuni.filter(function (c) { return c.nome === DATI.casa; })[0];
    if (casa) {
      [45, 90].forEach(function (min, i) { svg.appendChild(sv("circle", { class: "anello", cx: x(casa.lon), cy: y(casa.lat), r: i ? 118 : 62 })); });
    }
    DATI.comuni.forEach(function (c) {
      var n = conteggi[c.nome] || 0;
      if (!n) { svg.appendChild(sv("circle", { class: "vuoto-luogo", cx: x(c.lon), cy: y(c.lat), r: 2 })); return; }
      var r = Math.min(15, 7 + n * 1.5);
      var cerchio = sv("circle", { class: "luogo", cx: x(c.lon), cy: y(c.lat), r: r });
      cerchio.addEventListener("click", function () { vaiAZona(c.nome); });
      svg.appendChild(cerchio);
      var num = sv("text", { class: "num", x: x(c.lon), y: y(c.lat) + 3 }); num.textContent = n; svg.appendChild(num);
      var nome = sv("text", { x: x(c.lon) + r + 3, y: y(c.lat) + 3 }); nome.textContent = c.nome.length <= 12 ? c.nome : c.nome.split(" ").slice(0, 2).join(" "); svg.appendChild(nome);
    });
    if (casa) {
      svg.appendChild(sv("circle", { class: "casa", cx: x(casa.lon), cy: y(casa.lat), r: 5 }));
    }
    v.appendChild(el("div", { class: "mappa" }, svg));
    v.appendChild(el("p", { class: "piccolo", text: "Cerchio ambra: " + DATI.casa + ". Gli anelli tratteggiati indicano all'incirca 45 e 90 minuti. Tocca un cerchio o una riga per vedere le offerte." }));
    var zone = Object.keys(conteggi).map(function (z) { return DATI.comuni.filter(function (c) { return c.nome === z; })[0]; })
      .filter(Boolean).sort(function (a, b) { return a.minuti - b.minuti; });
    v.appendChild(el("h2", { class: "sezione", text: "Zone con offerte attive" }));
    if (!zone.length) v.appendChild(el("p", { class: "vuoto", text: "Nessuna offerta con una zona riconosciuta." }));
    zone.forEach(function (c) {
      v.appendChild(el("button", { class: "zona-riga", onclick: function () { vaiAZona(c.nome); } },
        el("span", { text: c.nome + " (" + conteggi[c.nome] + ")" }), el("small", { text: c.minuti + " min · " + c.km + " km" })));
    });
  }
  function vaiAZona(z) { FILTRI = { testo: "", contratto: "", distanza: "", stato: "attive", fonte: "", zona: z }; cambiaVista("offerte"); }

  // ---------- scheda offerta ----------
  function dato(nome, valore) {
    return el("div", { class: "dato" }, el("span", { text: nome }), el("span", { class: valore ? "" : "nd", text: valore || "n.d." }));
  }
  function apriScheda(id) {
    var o = DATI.offerte.filter(function (z) { return z.id === id; })[0];
    var box = document.getElementById("scheda");
    box.textContent = "";
    var corpo = el("div");
    corpo.appendChild(el("button", { class: "chiudi", text: "‹ Indietro", onclick: chiudiScheda }));
    if (!o) {
      corpo.appendChild(el("p", { class: "vuoto", text: "Questa offerta non è più in elenco." }));
      box.appendChild(corpo); box.hidden = false; return;
    }
    var m = mio(o.id);
    corpo.appendChild(el("div", { class: "capo" },
      el("div", {}, el("h2", { text: o.datore || o.titolo }), o.datore ? el("p", { class: "ruolo", text: o.titolo }) : null),
      el("div", { class: classeVoto(o.punteggio), text: String(o.punteggio) })));
    if (o.scaduto) corpo.appendChild(el("p", { class: "avviso rosso", text: "Scadenza passata (" + giorno(o.scadenza) + ")." }));
    else if (giorniDa(o.scadenza) !== null && giorniDa(o.scadenza) <= 7) corpo.appendChild(el("p", { class: "avviso rosso", text: "Attenzione: " + quando(o) + "." }));
    if (o.sparito_dal) corpo.appendChild(el("p", { class: "avviso", text: "Dal " + giorno(o.sparito_dal) + " non compare più nell'elenco della fonte: potrebbe essere chiuso." }));
    if (o.cambi && o.cambi.length && eNuovo(o)) corpo.appendChild(el("p", { class: "avviso", text: "Aggiornato il " + giorno(o.data_novita) + ": " + o.cambi.join("; ") }));
    (o.avvisi || []).forEach(function (a) { corpo.appendChild(el("p", { class: "avviso", text: a })); });
    if (o.nota_manuale) corpo.appendChild(el("p", { class: "avviso", text: o.nota_manuale }));

    corpo.appendChild(el("a", { class: "apri", href: linkSicuro(o.url), target: "_blank", rel: "noopener noreferrer", text: "Apri l'annuncio originale" }));

    corpo.appendChild(el("div", { class: "blocco" },
      dato("Contratto", o.contratto), dato("Compenso", o.compenso), dato("Ore e turni", o.turni),
      dato("Zona", o.zona ? o.zona + " – circa " + o.minuti + " min, " + o.km + " km da " + DATI.casa : null),
      dato("Scadenza", o.scadenza ? giorno(o.scadenza) : null), dato("Pubblicato", o.pubblicato ? giorno(o.pubblicato) : null),
      dato("Fonte", o.fonte), dato("Visto dal", giorno(o.primo_visto) + (o.ultimo_visto ? " (ultimo controllo " + giorno(o.ultimo_visto).slice(0, 5) + ")" : ""))));

    corpo.appendChild(el("h2", { class: "sezione", text: "Perché " + o.punteggio + " punti su 100" }));
    var bl = el("div", { class: "blocco" });
    (o.dettaglio_punteggio || []).forEach(function (d) {
      var riga = el("div", { class: "barra" },
        el("div", { class: "sopra" }, el("span", { text: d.voce }), el("b", { text: d.max ? d.punti + " / " + d.max : String(d.punti) })));
      if (d.max) { var bin = el("div", { class: "binario" }), pieno = el("i"); pieno.style.width = Math.max(0, Math.round(d.punti / d.max * 100)) + "%"; bin.appendChild(pieno); riga.appendChild(bin); }
      riga.appendChild(el("small", { text: d.motivo }));
      bl.appendChild(riga);
    });
    corpo.appendChild(bl);

    corpo.appendChild(el("h2", { class: "sezione", text: "Il mio stato" }));
    var stati = el("div", { class: "stati" });
    Object.keys(ETICHETTE).forEach(function (s) {
      stati.appendChild(el("button", { class: m.stato === s ? "scelto" : "", text: ETICHETTE[s], "aria-pressed": String(m.stato === s), onclick: function () {
        MIEI[o.id] = MIEI[o.id] || {};
        MIEI[o.id].stato = MIEI[o.id].stato === s ? "" : s;
        salvaMiei(); apriScheda(o.id); disegna();
      } }));
    });
    corpo.appendChild(stati);
    var nota = el("textarea", { class: "nota", placeholder: "Nota personale (resta su questo telefono)", "aria-label": "Nota personale" });
    nota.value = m.nota || "";
    nota.addEventListener("input", function () { MIEI[o.id] = MIEI[o.id] || {}; MIEI[o.id].nota = nota.value; salvaMiei(); });
    corpo.appendChild(nota);

    if (o.estratto) {
      corpo.appendChild(el("h2", { class: "sezione", text: "Dall'annuncio" }));
      corpo.appendChild(el("div", { class: "blocco" }, el("p", { class: "estratto", text: o.estratto })));
    }
    corpo.appendChild(el("p", { class: "piccolo", text: "Dati estratti in automatico: possono contenere errori. Controlla sempre l'annuncio originale." }));
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

  // ---------- navigazione ----------
  function disegna() {
    var v = document.getElementById("vista");
    v.textContent = "";
    ({ offerte: vistaOfferte, scadenze: vistaScadenze, report: vistaReport, mappa: vistaMappa })[VISTA](v);
  }
  function cambiaVista(nome) {
    VISTA = nome;
    Array.prototype.forEach.call(document.querySelectorAll(".schede button"), function (b) {
      var att = b.getAttribute("data-vista") === nome;
      b.className = att ? "attiva" : ""; b.setAttribute("aria-current", att ? "page" : "false");
    });
    disegna(); window.scrollTo(0, 0);
  }
  Array.prototype.forEach.call(document.querySelectorAll(".schede button"), function (b) {
    b.addEventListener("click", function () { cambiaVista(b.getAttribute("data-vista")); });
  });

  // ---------- avvio ----------
  function mostraDati(d) {
    DATI = d;
    var s = document.getElementById("aggiornato");
    var vecchi = d.oggi && (Date.now() - Date.parse(d.oggi)) / 86400000 > 2.2;
    s.textContent = "Aggiornato il " + d.generato + (vecchi ? " · dati non recenti: controlla la connessione o riapri l'app" : "");
    s.className = "sotto" + (vecchi ? " vecchi" : "");
    disegna();
    var m = /^#o=([0-9a-f]+)$/.exec(location.hash);
    if (m) apriScheda(m[1]);
    else if (/^#(scadenze|report|mappa)$/.test(location.hash)) cambiaVista(location.hash.slice(1));
  }
  fetch("dati.json", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(mostraDati)
    .catch(function () {
      document.getElementById("aggiornato").textContent = "Dati non disponibili: apri l'app una volta con la connessione attiva.";
      disegna();
    });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () { navigator.serviceWorker.register("sw.js").catch(function () {}); });
  }
})();
