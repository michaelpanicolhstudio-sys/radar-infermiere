"""Prove offline: nessuna connessione, pagine finte.  Avvio:  python tests/prova.py"""
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yaml

from radar import estrai, motore, punteggio, uscite

OGGI = date(2026, 11, 12)
RADICE = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((RADICE / "config.yaml").read_text(encoding="utf-8"))
COMUNI = estrai.carica_comuni(RADICE / "data" / "comuni.csv")
INF = CFG["parole"]["infermiere"]
errori = []


def verifica(nome, ottenuto, atteso):
    ok = ottenuto == atteso
    print(("  ok  " if ok else "  NO  ") + nome + ("" if ok else f"\n        ottenuto: {ottenuto!r}\n        atteso:   {atteso!r}"))
    if not ok:
        errori.append(nome)


def campi(titolo, testo):
    return estrai.estrai_campi(titolo, testo, COMUNI, OGGI, INF)


# ------------------------------------------------------------------ estrazione
print("Estrazione dei campi")
c = campi("A.P.S.P. C. Vannetti – Rovereto – Selezione per liberi professionisti",
          "L'APSP indice un avviso pubblico di selezione per il conferimento di incarichi libero-professionali "
          "di infermiere. Scadenza originaria 06/11/2026, PROROGATA al 27 novembre 2026 ore 12:00. "
          "Compenso orario lordo omnicomprensivo di € 40,00. Turni anche notturni e festivi.")
verifica("contratto P.IVA", c["contratto"], "P.IVA / libera professione")
verifica("scadenza prorogata", c["scadenza"], "2026-11-27")
verifica("compenso orario", (c["compenso"], c["euro_ora"]), ("40 €/h", 40.0))
verifica("zona dal titolo", (c["zona"], c["minuti"]), ("Rovereto", 40))
verifica("datore dal titolo", c["datore"], "A.P.S.P. C. Vannetti")
verifica("turni", c["turni"], "notti, weekend/festivi")
verifica("tipo di struttura", c["struttura"], "RSA o casa di riposo")

c = campi("Freiberufliche Tätigkeit in der Pflege",
          "Wir suchen Krankenpfleger für Nachtdienste und Wochenenden in Sterzing und Wiesen. Die Arbeit ist "
          "abwechslungsreich und wir bieten ein gutes Team mit flexiblen Zeiten. Zweisprachigkeit erwünscht. 35 Euro pro Stunde.")
verifica("tedesco: contratto", c["contratto"], "P.IVA / libera professione")
verifica("tedesco: zona con nome tedesco", c["zona"], "Vipiteno")
verifica("tedesco: compenso", c["euro_ora"], 35.0)
verifica("tedesco: bilinguismo citato e lingua riconosciuta", (c["cita_tedesco"], c["in_tedesco"]), (True, True))

c = campi("Concorso pubblico per infermieri", "Bando di concorso per 10 posti a tempo indeterminato. Domande entro il 13/11/2026. Stipendio 1.900 € netti al mese.")
verifica("concorso", c["contratto"], "Concorso / graduatoria")
verifica("scadenza 'entro il'", c["scadenza"], "2026-11-13")
verifica("compenso mensile senza €/h", (c["compenso"], c["euro_ora"]), ("1.900 € netti al mese", None))
verifica("zona non trovata resta vuota", c["zona"], None)

c = campi("Cercasi infermiere", "Cerchiamo un infermiere.")
verifica("niente inventato", (c["contratto"], c["compenso"], c["scadenza"], c["turni"], c["zona"]), (None,) * 5)
verifica("'ora' non è un compenso", estrai.estrai_compenso("Per ora servono 2 infermieri, 36 ore a settimana")[1], None)
verifica("compenso: 'pari a € 40,00' dopo 'compenso orario'", estrai.estrai_compenso("compenso orario lordo omnicomprensivo pari a € 40,00 per l'attività")[1], 40.0)
verifica("compenso: tariffa oraria in lettere", estrai.estrai_compenso("tariffa oraria di Euro 30,00 (trenta/00)")[1], 30.0)
verifica("compenso: a turno resta testo", estrai.estrai_compenso("€ 180,00 lordi a turno notturno"), ("€ 180,00 lordi a turno", None))
verifica("scadenza: ora prima della data", str(estrai.estrai_scadenza("Le domande devono pervenire entro le ore 12.00 del 27/11/2026.", OGGI)), "2026-11-27")

print("Falsi segnali da evitare")
verifica("la partita IVA dell'ente non è un contratto",
         estrai.estrai_contratto("Posto a tempo indeterminato. Fondazione X, via Mendola 21. Codice IPA: UFMPXZ Partita IVA 00123456789 – C.F. e P.IVA: 00123456789"),
         "Dipendente a tempo indeterminato")
verifica("'collaborazione' generica non è un contratto", estrai.estrai_contratto("Cerchiamo persone con spirito di collaborazione con l'équipe."), None)
verifica("contratto di collaborazione", estrai.estrai_contratto("È previsto un contratto di collaborazione."), "Collaborazione")
verifica("ruolo: coordinatore nel testo", estrai.ruolo_diverso("Cooperativa Stella Montis – ricerca di personale", "Cerchiamo un/una Coordinatore/Coordinatrice Infermieristico/a per la nostra RSA."), True)
verifica("ruolo: infermiere che lavora col coordinatore", estrai.ruolo_diverso("Cercasi infermiere", "L'infermiere lavora in collaborazione con il coordinatore infermieristico."), False)
verifica("ruolo: comando di dipendenti pubblici", estrai.ruolo_diverso("INPS – Ricerca infermiere/a", "La sede cerca un infermiere in forza presso la ASL (Dipendente Pubblico) in comando ai termini dell'art. 30."), True)
verifica("fuori regione", (estrai.fuori_regione("Infermiere a Caorle", CFG["parole"]["fuori_regione"]), estrai.fuori_regione("Infermiere a Cles", CFG["parole"]["fuori_regione"])), (True, False))

print("Comuni")
def zona(titolo, testo=""):
    c = estrai.trova_comune(titolo, testo, COMUNI)
    return c["nome"] if c else None
verifica("nome ambiguo ignorato", zona("Infermiere", "Selezione chiusa. Chiusa la graduatoria."), None)
verifica("'Fondo' non batte LACES", zona("Fondo Ospedale della S.S. Trinità RESIDENZA PER ANZIANI ANNENBERG LACES", "Fondo Ospedale, via Centrale 57, 39021 Laces. Fondo Ospedale."), "Laces")
verifica("nome ambiguo con provincia", zona("Casa di cura Eremo – Arco TN"), "Arco")
verifica("comune piccolo", zona("A.P.S.P. Padre Odone Nicolini – Pieve di Bono – Prezzo TN"), "Pieve di Bono-Prezzo")
verifica("comune dal testo", zona("APSP Suor Agnese – Concorso", "APSP “SUOR AGNESE” – Castello Tesino TN. Bando di concorso."), "Castello Tesino")

print("Punteggio")
a = {"contratto": "P.IVA / libera professione", "euro_ora": 40.0, "minuti": 15, "segnali_turni": {"dodici": True, "notti": True, "weekend": True}, "affidabilita": "ufficiale"}
verifica("massimo = 100", punteggio.calcola(a, CFG)[0], 100)
a = {"contratto": "Dipendente a tempo determinato", "euro_ora": None, "minuti": 120, "segnali_turni": {}, "affidabilita": "aggregatore"}
verifica("dipendente lontano = basso", punteggio.calcola(a, CFG)[0], 5 + 5 + 0 + 5 + 3)

# ------------------------------------------------------------------ pagine, feed, PDF
print("Pagine, feed e PDF")
feed = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title type="html">&lt;b&gt;Infermiere&lt;/b&gt; partita IVA Trento</title>
<link href="https://www.google.com/url?rct=j&amp;sa=t&amp;url=https://esempio.it/annuncio-1&amp;ct=ga"/>
<published>2026-11-11T08:00:00Z</published><content type="html">Cercasi infermiere a Trento con P.IVA</content></entry></feed>"""
v = estrai.leggi_feed(feed)
verifica("feed Google Alerts", (v[0]["url"], v[0]["titolo"], str(v[0]["pubblicato"])), ("https://esempio.it/annuncio-1", "Infermiere partita IVA Trento", "2026-11-11"))

ELENCO = """<html><body><nav><a href="/chi-siamo/">Chi siamo e contatti dell'ente</a></nav><main>
<a href="/segreteria/">Torna alla pagina precedente Segreteria</a>
<a href="/apsp-vannetti-lp/">A.P.S.P. C. Vannetti – Rovereto – Selezione per liberi professionisti 16 ottobre 2026 – A.P.S.P. Clementino Vannetti</a>
<a href="/casa-cura-eremo/">Casa di cura Eremo – Arco TN – ricerca personale</a>
<a href="/stella-montis/">Cooperativa Sociale Stella Montis – ricerca di personale</a>
<a href="/bando.pdf">Bando di concorso per infermieri in formato PDF</a>
<a href="/privacy/">Informativa sulla privacy del sito</a></main></body></html>"""
l = estrai.link_da_elenco(ELENCO, "https://ente.it/segreteria/annunci-di-lavoro/", CFG["parole"]["link"], tutti=True)
verifica("link dell'elenco: niente menu, privacy e 'torna indietro'", [x["url"].rsplit("/", 2)[-2] if x["url"].endswith("/") else x["url"].rsplit("/", 1)[-1] for x in l],
         ["apsp-vannetti-lp", "casa-cura-eremo", "stella-montis", "bando.pdf"])
verifica("titolo senza data e riassunto", l[0]["titolo"], "A.P.S.P. C. Vannetti – Rovereto – Selezione per liberi professionisti")

PAGINA = """<html><head><meta property="article:published_time" content="2026-10-16T09:00:00+02:00"></head><body>
<header>Ordine delle professioni infermieristiche</header><article><h1>A.P.S.P. C. Vannetti</h1>
<div class="fusion-meta-info">admin 2026-10-16 | JOB</div>
<p>Avviso pubblico per incarichi di infermiere. L'avviso è in calce alla pagina. Scrivere a personale@apsp-prova.it oppure a mario.rossi@gmail.com.</p>
<a href="/files/Avviso_LP_infermieri.pdf">Avviso</a> <a href="/files/Domanda_ammissione.pdf">Domanda</a>
<div class="fusion-sharing-box">Share This Story, Choose Your Platform! Facebook X Reddit</div>
<div class="related-posts">Altri annunci: OSS a Trento</div></article><footer>Ordine di Trento, P.IVA 01234567890</footer></body></html>"""
p = estrai.leggi_pagina(PAGINA, "https://ente.it/apsp-vannetti-lp/")
verifica("pagina: senza condivisione, autore e annunci simili", ("Share" in p["testo"], "admin" in p["testo"], "OSS" in p["testo"], "incarichi di infermiere" in p["testo"]), (False, False, False, True))
verifica("pagina: PDF dell'avviso sì, modulo di domanda no", [x["url"] for x in p["pdf"]], ["https://ente.it/files/Avviso_LP_infermieri.pdf"])
verifica("pagina: data di pubblicazione", str(p["pubblicato"]), "2026-10-16")
verifica("email: solo quella della struttura", estrai.trova_email(p["testo"] + " info@opi.tn.it apsp@pec.it", motore.DOMINI_BACHECA), {"email": "personale@apsp-prova.it", "pec": "apsp@pec.it"})

PDF = (RADICE / "tests" / "avviso_prova.pdf").read_bytes()
testo_pdf = estrai.testo_pdf(PDF)
verifica("PDF: testo letto", ("INCARICHI LIBERO PROFESSIONALI" in testo_pdf, "40,00" in testo_pdf), (True, True))
verifica("PDF rovinato non blocca", estrai.testo_pdf(b"%PDF-1.4 rotto"), "")

verifica("datore: taglia 'cerca…'", estrai.estrai_datore("Fondazione Pitsch cerca infermieri/e"), "Fondazione Pitsch")
verifica("datore: titolo generico = nessuno", estrai.estrai_datore("Avviso – Collegio tecnico – Dirigenza"), None)

# ------------------------------------------------------------------ giro completo
print("Giro completo su più giorni (rete finta)")


class ReteFinta:
    def __init__(self, pagine):
        self.pagine, self.richieste, self.aperte = pagine, 0, []

    def get(self, url, robots=True):
        self.richieste += 1
        self.aperte.append(url)
        if url.endswith(".pdf"):
            return None, "è un PDF"
        return (self.pagine[url], None) if url in self.pagine else (None, "risposta HTTP 404")

    def get_pdf(self, url, massimo_mb=8, robots=True):
        self.richieste += 1
        self.aperte.append(url)
        return (self.pagine[url], None) if url in self.pagine else (None, "risposta HTTP 404")


def art(t, corpo, data="2026-10-16"):
    return (f'<html><head><title>x</title><meta property="article:published_time" content="{data}T09:00:00+02:00"></head>'
            f"<body><article><h1>{t}</h1><p>{corpo}</p></article><footer>Ordine di Trento – P.IVA 01234567890</footer></body></html>")


RIEMP = " Requisiti: laurea in infermieristica e iscrizione all'albo. " * 4
BASE = "https://ente.it/segreteria/annunci-di-lavoro/"
pagine = {
    BASE: ELENCO,
    "https://ente.it/apsp-vannetti-lp/": art("A.P.S.P. C. Vannetti", "Avviso pubblico di selezione per infermieri: i dettagli sono nell'avviso allegato. "
                                             '<a href="/files/Avviso_LP_infermieri.pdf">Avviso</a>' + RIEMP),
    "https://ente.it/files/Avviso_LP_infermieri.pdf": PDF,
    "https://ente.it/casa-cura-eremo/": art("Casa di cura Eremo – Arco", "Cerchiamo personale infermieristico a tempo indeterminato, CCNL AIOP. Arco (TN)." + RIEMP),
    "https://ente.it/stella-montis/": art("Stella Montis", "Cerchiamo un/una Coordinatore/Coordinatrice Infermieristico/a per la nostra struttura." + RIEMP),
    "https://ente.it/bando.pdf": PDF,
    "https://clinica.it/lavora/": art("Lavora con noi", "Infermiere/a per assunzione o libera professione, turni da 12 ore." + RIEMP, data="2019-07-17"),
    "https://feed.it/a": feed,
}
cfg = dict(CFG)
cfg["fonti"] = [
    {"nome": "Ente", "tipo": "elenco", "url": BASE, "affidabilita": "ufficiale", "tutti_i_link": True},
    {"nome": "Clinica", "tipo": "pagina", "url": "https://clinica.it/lavora/", "affidabilita": "struttura", "datore": "Clinica X", "zona": "Merano"},
    {"nome": "Rotta", "tipo": "pagina", "url": "https://rotta.it/", "affidabilita": "struttura"},
    {"nome": "Avvisi vuoti", "tipo": "elenco", "url": "https://vuota.it/avvisi/", "affidabilita": "ufficiale", "puo_essere_vuota": True},
]
pagine["https://vuota.it/avvisi/"] = "<html><body><main><p>Nessun avviso in pubblicazione</p></main></body></html>"
cfg["feed_google_alerts"] = ["https://feed.it/a"]
cfg["esplora"] = ["https://clinica.it/lavora/"]
tmp = Path(tempfile.mkdtemp())
motore.FILE_ANNUNCI, motore.FILE_FONTI, motore.CARTELLA_REPORT = tmp / "annunci.json", tmp / "fonti.json", tmp / "report"
motore.FILE_DIAGNOSTICA = tmp / "diagnostica.json"
muto = lambda *_: None

rete1 = ReteFinta(pagine)
r1 = motore.giro(cfg, rete1, OGGI, registra=muto)
mem = motore.leggi_json(motore.FILE_ANNUNCI, {})
per_url = {a["url"].rstrip("/").rsplit("/", 1)[-1]: a for a in mem.values()}
verifica("giorno 1: annunci nuovi (coordinatore scartato)", sorted(per_url), ["annuncio-1", "apsp-vannetti-lp", "bando.pdf", "casa-cura-eremo", "lavora"])
lp = per_url["apsp-vannetti-lp"]
verifica("dati presi dal PDF allegato", (lp["contratto"], lp["euro_ora"], lp["scadenza"], lp["email"]),
         ("P.IVA / libera professione", 40.0, "2026-11-27", "personale@apsp-prova.it"))
verifica("avviso sul PDF", lp["avvisi"][0][:16], "Dal PDF allegato")
verifica("link a un PDF letto direttamente", (per_url["bando.pdf"]["euro_ora"], per_url["bando.pdf"]["zona"]), (40.0, "Rovereto"))
verifica("pagina fissa: la data della pagina non conta", per_url["lavora"]["pubblicato"], None)
verifica("giorno 1: primo in classifica", r1["top5"][0]["datore"], "A.P.S.P. C. Vannetti")
verifica("giorno 1: solo la fonte rotta è segnalata (l'elenco vuoto previsto no)", r1["problemi"], ["Rotta: risposta HTTP 404"])
diag = motore.leggi_json(motore.FILE_DIAGNOSTICA, {})
verifica("diagnostica: scarti con motivo", diag["fonti"]["Ente"]["scartati"], [["Cooperativa Sociale Stella Montis – ricerca di personale", "ruolo diverso (coordinamento, direzione o comando)"]])
verifica("diagnostica: esplorazione", diag["esplora"][0]["url"], "https://clinica.it/lavora/")

# Giorno 2: elenco in manutenzione, niente deve sparire; il PDF non si riscarica; lo scarto non si riapre.
pagine2 = dict(pagine)
pagine2[BASE] = "<html><body><main><p>Sito in manutenzione</p></main></body></html>"
r2 = motore.giro(cfg, ReteFinta(pagine2), date(2026, 11, 13), registra=muto)
verifica("giorno 2: niente di nuovo", len(r2["nuovi"]), 0)
verifica("giorno 2: struttura cambiata segnalata", any("cambiato struttura" in x for x in r2["problemi"]), True)
verifica("giorno 2: nessun annuncio dato per sparito", [a.get("sparito_dal") for a in motore.leggi_json(motore.FILE_ANNUNCI, {}).values()], [None] * 5)

pagine3 = dict(pagine)
pagine3["https://ente.it/casa-cura-eremo/"] = pagine["https://ente.it/casa-cura-eremo/"].replace("Arco (TN).", "Arco (TN). Candidature entro il 18/11/2026.")
rete3 = ReteFinta(pagine3)
r3 = motore.giro(cfg, rete3, date(2026, 11, 14), registra=muto)
verifica("giorno 3: annuncio aggiornato", [x["cambi"] for x in r3["aggiornati"]], [["scadenza: n.d. → 2026-11-18"]])
verifica("giorno 3: scadenza vicina", [x["scadenza"] for x in r3["scadenze7"]], ["2026-11-18"])
verifica("giorno 3: PDF già letto non riscaricato, pagina scartata non riaperta",
         ("https://ente.it/files/Avviso_LP_infermieri.pdf" in rete3.aperte, "https://ente.it/stella-montis/" in rete3.aperte), (False, False))

ogg, testo, pag = uscite.componi_email(r3, "https://app.esempio")
verifica("oggetto email", ogg, "Radar 14/11: 1 annuncio aggiornato, 1 scadenza vicina")
verifica("email: link diretto all'app", "https://app.esempio/#o=" in pag, True)

# Stesso giorno, secondo giro: l'archivio somma le novità invece di sovrascriverle.
pagine3b = dict(pagine3)
pagine3b[BASE] = ELENCO.replace("</main>", '<a href="/nuovo-rsa/">RSA di Cles cerca infermieri liberi professionisti</a></main>')
pagine3b["https://ente.it/nuovo-rsa/"] = art("RSA di Cles", "Cerchiamo infermieri in libera professione per turni notturni a Cles (TN)." + RIEMP, data="2026-11-14")
r3b = motore.giro(cfg, ReteFinta(pagine3b), date(2026, 11, 14), registra=muto)
archivio = motore.leggi_json(motore.CARTELLA_REPORT / "2026-11-14.json", {})
verifica("secondo giro del giorno: novità del giro e archivio del giorno", (len(r3b["nuovi"]), len(archivio["aggiornati"]), archivio["giri"]), (1, 1, 2))

cfg5 = dict(cfg)
cfg5["fonti"] = [f for f in cfg["fonti"] if f["nome"] != "Rotta"]
r5 = motore.giro(cfg5, ReteFinta(pagine3b), date(2026, 11, 19), registra=muto)
ogg, testo, _ = uscite.componi_email(r5, None)
verifica("niente di nuovo = una riga", (ogg, "\n" in testo), ("Radar 19/11: niente di nuovo", False))

print("Memoria: datati, doppioni, dati a mano")
verifica("annuncio datato", (motore.e_datato({"pubblicato": "2026-03-05", "scadenza": None}, OGGI, CFG), motore.e_datato({"pubblicato": "2026-03-05", "scadenza": "2026-12-01"}, OGGI, CFG)), (True, False))
m2 = {"a": {"id": "a", "titolo": "Concorso per infermieri", "datore": "APSP Vannetti", "zona": "Rovereto", "scadenza": "2026-11-20", "contratto": "Concorso / graduatoria", "punteggio": 30, "primo_visto": "2026-11-12", "origine": "manuale"},
      "b": {"id": "b", "titolo": "APSP Vannetti Rovereto - Infermiere", "datore": None, "zona": "Rovereto", "scadenza": "2026-11-20", "contratto": "Concorso / graduatoria", "punteggio": 39, "primo_visto": "2026-11-13"},
      "c": {"id": "c", "titolo": "Incarichi libero-professionali", "datore": "APSP Vannetti", "zona": "Rovereto", "scadenza": "2026-11-20", "contratto": "P.IVA / libera professione", "punteggio": 60, "primo_visto": "2026-11-13"},
      "d": {"id": "d", "titolo": "Infermiere/a a tempo pieno o part time", "datore": None, "zona": "Caldaro", "scadenza": None, "contratto": None, "punteggio": 42, "primo_visto": "2026-11-13", "pubblicato": "2023-09-13"},
      "e": {"id": "e", "titolo": "Infermiere/a a tempo pieno o part time", "datore": None, "zona": "Caldaro", "scadenza": None, "contratto": None, "punteggio": 42, "primo_visto": "2026-11-13", "pubblicato": "2024-07-29"}}
motore.segna_doppioni(m2, OGGI)
verifica("doppioni: stesso bando su due siti e annuncio ripubblicato", [m2[k].get("doppione_di") for k in "abcde"], [None, "a", None, "e", None])

# Dati letti a mano: una lettura automatica peggiore non li sovrascrive, ma una proroga sì.
manuale = {"id": estrai.id_annuncio("https://ente.it/casa-cura-eremo/"), "url": "https://ente.it/casa-cura-eremo/", "titolo": "Personale infermieristico (CCNL AIOP)",
           "datore": "Casa di Cura Eremo", "contratto": "Dipendente a tempo indeterminato", "compenso": None, "euro_ora": None, "turni": "turni da 12 h",
           "segnali_turni": {"dodici": True}, "zona": "Arco", "km": 55, "minuti": 55, "scadenza": None, "pubblicato": "2026-10-19", "fonte": "Ente",
           "affidabilita": "ufficiale", "origine": "manuale", "nota_manuale": "Inserito a mano", "primo_visto": "2026-11-12", "ultimo_visto": "2026-11-12",
           "impronta": "x", "punteggio": 30, "avvisi": [], "cambi": []}
tmp2 = Path(tempfile.mkdtemp())
motore.FILE_ANNUNCI, motore.FILE_FONTI, motore.CARTELLA_REPORT, motore.FILE_DIAGNOSTICA = tmp2 / "a.json", tmp2 / "f.json", tmp2 / "report", tmp2 / "d.json"
motore.scrivi_json(motore.FILE_ANNUNCI, {manuale["id"]: manuale})
r = motore.giro(cfg5, ReteFinta(pagine3), date(2026, 11, 14), registra=muto)
dopo = motore.leggi_json(motore.FILE_ANNUNCI, {})[manuale["id"]]
verifica("dati a mano conservati, scadenza aggiornata", (dopo["titolo"], dopo["turni"], dopo["scadenza"], dopo["origine"]), ("Personale infermieristico (CCNL AIOP)", "turni da 12 h", "2026-11-18", "manuale"))
verifica("la proroga compare tra gli aggiornati", [x["cambi"] for x in r["aggiornati"]], [["scadenza: n.d. → 2026-11-18"]])

print("Regole della seconda messa a punto")
verifica("compenso: tra medici e infermieri vale quello degli infermieri",
         estrai.estrai_compenso("ai medici un compenso orario lordo pari a € 80,00; agli infermieri un compenso orario lordo onnicomprensivo di Euro 40,00")[1], 40.0)
verifica("compenso: 'lordo omnicomprensivo orario'", estrai.estrai_compenso("compenso lordo omnicomprensivo orario di euro 40,00")[1], 40.0)
verifica("compenso: 'euro-pea' non è un indizio", estrai.indizi_compenso("cittadino di uno Stato membro dell'Unione euro- pea"), [])
verifica("compenso: indizi quando non si riconosce", len(estrai.indizi_compenso("Il budget complessivo è di € 12.000 annui.")), 1)
sc = estrai.estrai_scadenza_frase("Le domande dovranno pervenire entro e non oltre le ore 12.00 del giorno 06/11/2026. Proroga termini di scadenza: 27/11/2026 ore 12.00", OGGI)
verifica("scadenza con la frase da cui è presa", (str(sc[0]), "Proroga termini di scadenza: 27/11/2026" in sc[1]), ("2026-11-27", True))
verifica("datore: minuscolo nel titolo", estrai.estrai_datore("La casa di riposo di Silandro cerca nuovi collaboratori/trici"), "Casa di riposo di Silandro")
verifica("datore: una frase non è un nome", estrai.estrai_datore("Cerchiamo infermiere per la nostra residenza a Trento"), None)
verifica("datore: dalle prime righe del testo", estrai.estrai_datore_da_testo("Infermiere/a a tempo pieno o part time Fondazione Casa di Riposo Heinrich von Rottenburg Kaltern – Caldaro Azienda pubblica di servizi alla persona Via Mendola 21"), "Fondazione Casa di Riposo Heinrich von Rottenburg Kaltern")
verifica("datore: vecchio nome dell'azienda sanitaria trentina", estrai.datore_noto("… potenziamento invernale – Azienda Provinciale per i Servizi Sanitari"), "ASUIT (Trentino)")
html_allegati = """<html><body><header><a href="/carta.pdf">Carta dei servizi</a></header>
<article><div class="entry-content"><p>L'APSP ricerca infermieri in libera professione. Domande entro il 27/11/2026.</p></div></article>
<div class="allegati"><div class="blocco"><h4>Avviso di pubblica selezione</h4><a href="/wp-content/uploads/2026/10/doc-123.pdf">scarica il pdf</a></div>
<div class="blocco"><h4>Modulo di domanda</h4><a href="/wp-content/uploads/2026/10/doc-124.pdf">download</a></div>
<iframe src="/visore/viewer.html?file=%2Fwp-content%2Fuploads%2F2026%2F10%2Fproroga-termini.pdf"></iframe></div>
<footer><a href="/privacy.pdf">Privacy</a></footer></body></html>"""
trovati_pdf = [x["url"] for x in estrai.leggi_pagina(html_allegati, "https://ente.it/avviso/")["pdf"]]
verifica("PDF fuori dal testo: presi avviso e proroga, non il modulo né il piè di pagina",
         trovati_pdf, ["https://ente.it/wp-content/uploads/2026/10/doc-123.pdf", "https://ente.it/wp-content/uploads/2026/10/proroga-termini.pdf"])
vecchi = {str(i): {"id": str(i), "titolo": t, "datore": None, "zona": "Caldaro", "email": "info@ah-kaltern.it", "contratto": None,
                   "scadenza": None, "pubblicato": pub, "punteggio": 40, "primo_visto": "2026-11-13"}
          for i, (t, pub) in enumerate([("Infermiere/a a tempo pieno o part time", "2023-09-13"), ("Fondazione Heinrich von Rottenburg Caldaro", "2025-06-25"),
                                        ("Ricerca personale infermieristico", "2026-06-23")])}
motore.segna_doppioni(vecchi, OGGI)
verifica("doppioni: stessa struttura (stessa email), resta il più recente", [a.get("doppione_di") for a in vecchi.values()], ["2", "2", None])

print("Bacheca delle case di riposo (VdS)")
# 13/11: «Altenheim St. Pankraz» finiva a Bolzano perché il testo nominava Bozen.
fonte_vds = {"nome": "VdS", "tipo": "elenco", "affidabilita": "struttura", "link_e_datore": True}
cand_vds = {"url": "https://vds.it/de/swh/507/job/krankenpflegerinnen-7ter-fe-mit-18-20-und-22-wochenstunden",
            "titolo": "Infermiere/a", "datore": "Altenheim St. Pankraz ÖBPB"}
a_vds, _ = motore._costruisci(cand_vds, "Wir suchen Krankenpfleger/innen. Bewerbungen an das Büro in Bozen, Bozen Zentrum." + RIEMP,
                              None, fonte_vds, CFG, COMUNI, OGGI, [])
verifica("VdS: la zona viene dal nome della casa di riposo", a_vds["zona"], "San Pancrazio")
cand_vds2 = dict(cand_vds, datore="Seniorenwohnheim \"Leoheim\"")
a_vds2, _ = motore._costruisci(cand_vds2, "Wir suchen Krankenpfleger/innen in Welschnofen." + RIEMP, None, fonte_vds, CFG, COMUNI, OGGI, [])
verifica("VdS: nome senza comune, resta la zona del testo", a_vds2["zona"], "Nova Levante")
verifica("VdS: titolo leggibile dall'indirizzo (ore)",
         estrai.titolo_leggibile("Krankenpflegerinnen 7ter fe mit 18 20 und 22 wochenstunden"), "Infermiere/a – part-time (18, 20 o 22 ore/settimana)")
verifica("VdS: titolo leggibile dall'indirizzo (graduatoria con altri profili)",
         estrai.titolo_leggibile("Kundmachung befristete rangordnung sozialbetreuer pflegehelfer krankenpfleger"),
         "Infermiere/a – graduatoria, a tempo determinato (con altri profili)")
verifica("VdS: titolo senza dettagli", estrai.titolo_leggibile("Berufskrankenpflegerin berufsbild nr 64 der viiter funktionsebeneinfermierea"), "Infermiere/a")
verifica("VdS: altri ruoli restano come sono", estrai.titolo_leggibile("Befristete anstellung als sozialbetreuerin"), "Befristete anstellung als sozialbetreuerin")

print("Conti, posta e contatti")
from radar import conti, posta
par = conti.parametri({})
verifica("conti: di ogni euro restano 84 centesimi", round(conti.quota_netta(par), 4), 0.8424)
co = conti.conto_offerta({"euro_ora": 35, "km": 40, "minuti": 40}, par)
verifica("conti: turni al mese per 3.000 netti a 35 €/h da Rovereto", (co["turni_per_obiettivo"], co["netto_ora"]), (18, 26.99))
foglio = conti.scrivi_excel({"datore": "APSP Prova", "titolo": "Infermiere", "euro_ora": 35, "km": 40, "minuti": 40}, par, Path(tempfile.mkdtemp()) / "p.xlsx", [])
verifica("conti: foglio Excel creato", foglio.exists() and foglio.stat().st_size > 4000, True)
verifica("posta: incontro con data e ora", posta.trova_incontro("Possiamo fissare un colloquio martedì 24/11/2026 alle ore 10.30 in struttura.", OGGI), {"data": "2026-11-24", "ora": "10:30", "frase": "Possiamo fissare un colloquio martedì 24/11/2026 alle ore 10.30 in struttura."})
verifica("posta: una data senza invito non è un incontro", posta.trova_incontro("Il bando scade il 24/11/2026.", OGGI), None)
verifica("posta: la parte citata si toglie", posta.taglia_citazione("Il compenso è 38 euro l'ora.\n\nIl giorno 13 nov 2026 Michael ha scritto:\n> ciao"), "Il compenso è 38 euro l'ora.")
verifica("posta: annunci dall'avviso di un portale", [x["titolo"] for x in posta.annunci_da_avviso('<a href="https://it.indeed.com/x">Infermiere libero professionista</a><a href="https://it.indeed.com/y">Cuoco</a>', ["infermier"])], ["Infermiere libero professionista"])
mem = {"a1": {"id": "a1", "titolo": "LP", "email": "x@rsa.it", "punteggio": 60, "contratto": "P.IVA / libera professione"},
       "a2": {"id": "a2", "titolo": "LP bis", "email": "x@rsa.it", "punteggio": 55, "contratto": "P.IVA / libera professione"},
       "a3": {"id": "a3", "titolo": "Concorso", "email": "y@ente.it", "punteggio": 70, "contratto": "Concorso / graduatoria"},
       "a4": {"id": "a4", "titolo": "Già scritto", "email": "z@rsa.it", "punteggio": 65, "contratto": "P.IVA o dipendente"}}
scelte = uscite.scegli_da_contattare(mem, {"a4": {"inviata_il": "2026-11-10", "a": ["z@rsa.it"]}}, cfg, OGGI)
verifica("contatti: mai due volte, niente concorsi, un solo messaggio per indirizzo", [a["id"] for a in scelte], ["a1"])

print("Web app e calendario")
dest = uscite.costruisci_sito(cfg, date(2026, 11, 14), tmp2 / "dist")
dati = __import__("json").loads((dest / "dati.json").read_text(encoding="utf-8"))
verifica("web app costruita", ((dest / "index.html").exists(), dati["oggi_lungo"], len(dati["offerte"]) >= 4), (True, "sabato 14 novembre", True))
ics = sorted((dest / "ics").glob("*.ics"))
verifica("calendario: un file per ogni scadenza futura", (len(ics) >= 2, "BEGIN:VEVENT" in ics[0].read_text(encoding="utf-8"), "DTSTART;VALUE=DATE:2026" in ics[0].read_text(encoding="utf-8")), (True, True, True))
riga_lunga = uscite._ics_piega("SUMMARY:" + "à" * 100)
verifica("calendario: righe piegate a 75 byte", max(len(x.encode("utf-8")) for x in riga_lunga.split("\r\n")) <= 75, True)

print("\n" + ("TUTTO OK" if not errori else f"{len(errori)} PROVE FALLITE: {errori}"))
sys.exit(1 if errori else 0)
