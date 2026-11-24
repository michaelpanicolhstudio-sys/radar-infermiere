"""Prove offline: nessuna connessione, pagine finte.  Avvio:  python tests/prova.py"""
import sys
import tempfile
from datetime import date, datetime, timedelta
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
# 16/11: i 3 Google Alerts danno 0 voci da 26 giorni senza errori. Una pagina web ben formata
# (consenso, accesso) letta come «feed vuoto» non deve sembrare un feed senza novità.
verifica("feed: un feed vuoto è un feed", estrai.info_feed('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Google Alert - infermiere</title></feed>'),
         ("feed", "Google Alert - infermiere"))
verifica("feed: una pagina web non è un feed", estrai.info_feed("<html><head><title>Accedi</title></head><body></body></html>")[0], "html")

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

# suedtirolerjobs (Schloss Moos, giro del 16/11): l'annuncio è caricato in modo dinamico e nel testo restavano
# solo i «Ähnliche Jobs» di altri datori (Caritas Leifers, St. Josef Lana, Pegasus Bozen), finiti nell'estratto.
PAGINA_SJ = """<html><body><div class="content"><h1>Freiberufliche Tätigkeit in der Pflege</h1>
<p>Sozialgenossenschaft Zum Heiligen Vinzenz Wiesen, Pfitsch Vollzeit Teilzeit Freelancer Projektarbeit 18.10.2026
Sozialgenossenschaft Zum Heiligen Vinzenz Traustonstr. 190, 39049 Wiesen-Pfitsch Personalabteilung +39 0472 765179</p>
<p>Zum Arbeitgeber Profil</p><h2>Ähnliche Jobs</h2>
<p>Sozialbetreuer*in Vollzeit / Teilzeit Lana Pflegehelfer/in (Vollzeit) Leifers Caritas Krankenpfleger*in Lana ST. JOSEF
Freiberufler / Freelancer (m/w) Bozen, südtirolweit PEGASUS</p></div></body></html>"""
p_sj = estrai.leggi_pagina(PAGINA_SJ, "https://www.suedtirolerjobs.it/jobs/x,1", intera_se_vuota=True)
verifica("pagina: gli annunci simili di altri datori non entrano nel testo",
         ("Leifers" in p_sj["testo"], "PEGASUS" in p_sj["testo"], "Wiesen-Pfitsch" in p_sj["testo"]), (False, False, True))
verifica("pagina: un «annunci simili» in apertura non svuota il testo",
         "Krankenpfleger" in estrai.taglia_correlati("Annunci simili qui sotto. Cerchiamo Krankenpfleger in Lana. " * 3), True)

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
verifica("diagnostica: scarti con motivo e indirizzo", diag["fonti"]["Ente"]["scartati"], [["Cooperativa Sociale Stella Montis – ricerca di personale", "ruolo diverso (coordinamento, direzione o comando)", "https://ente.it/stella-montis/"]])
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

_fa = {"nome": "Google Alerts 9", "tipo": "rss", "url": "https://www.google.com/alerts/feeds/1/2", "affidabilita": "aggregatore", "solo_regione": True}
_es = motore.raccogli_fonte(_fa, ReteFinta({_fa["url"]: "<html><head><title>Prima di continuare</title></head><body></body></html>"}), CFG, COMUNI, OGGI, {}, {})
verifica("feed: una pagina web al posto del feed è un errore da segnalare", "pagina web" in (_es["errore"] or ""), True)

# Giro del 16/11: Google Alerts 4 ha portato due articoli di cronaca («infermiere aggredito al Santa Chiara»)
# finiti tra le «novità» dell'email come se fossero offerte di lavoro.
_n1 = motore._costruisci({"titolo": "Afferra per i polsi un infermiere , poi lo spintona: ancora violenza al pronto soccorso - TrentoToday",
                          "url": "https://www.trentotoday.it/cronaca/infermiere-aggredito-polsi-ospedale-santa-chiara-trento.html",
                          "sommario": "Afferra per i polsi un infermiere, poi lo spintona: ancora violenza al pronto soccorso a Trento"},
                         "Pochi giorni prima si era verificato un episodio simile all'ospedale Santa Chiara di Trento. Uil Fp: non è accettabile.",
                         None, _fa, CFG, COMUNI, OGGI, [])
_n2 = motore._costruisci({"titolo": "Trento , infermiere aggredito al Santa Chiara: la Uil chiede più sicurezza - L'Adige",
                          "url": "https://www.ladige.it/territori/trento/trento-infermiere-aggredito-al-santa-chiara-la-uil-chiede-piu-sicurezza-oe6h45bk"},
                         "La denuncia. Momenti di tensione sabato sera nel reparto di emergenza dell'ospedale di Trento.",
                         None, _fa, CFG, COMUNI, OGGI, [])
verifica("feed: un articolo di cronaca non è un'offerta", (_n1[0], _n1[1], _n2[0], _n2[1]),
         (None, "notizia, non un'offerta di lavoro", None, "notizia, non un'offerta di lavoro"))
_o1 = motore._costruisci({"titolo": "Infermieri RSA zona Rovereto", "url": "https://it.indeed.com/viewjob?jk=9",
                          "sommario": "ParaMedica cerca infermieri con partita IVA per RSA a Rovereto"},
                         "", None, _fa, CFG, COMUNI, OGGI, [])
_o2 = motore._costruisci({"titolo": "Trento, l'ospedale cerca infermieri: aperto il bando", "url": "https://www.ladige.it/territori/trento/bando-infermieri-1"},
                         "Il bando per infermieri a tempo determinato scade il 30 novembre 2026.", None, _fa, CFG, COMUNI, OGGI, [])
verifica("feed: offerte vere (anche su un giornale) restano", (_o1[0] is not None, _o2[0] is not None), (True, True))
# Giro del 18/11: un articolo di Nurse Times sulla sanità privata (sindacati, Parlamento) era una «novità» P.IVA.
_n3 = motore._costruisci({"titolo": "Sanità privata: 10 giorni per aprire il tavolo. E in Parlamento spunta il rinnovo automatico ...",
                          "url": "https://nursetimes.org/sanita-privata-10-giorni-per-aprire-il-tavolo-e-in-parlamento-spunta-il-rinnovo-automatico-degli-accreditamenti",
                          "sommario": "Fp Cgil, Cisl Fp e Uil Fp hanno diffidato Aiop: assunzioni e contratto degli infermieri delle RSA, anche in partita IVA"},
                         "Infermieri NT News Politica & Sindacato Sanità privata: 10 giorni per aprire il tavolo. Fp Cgil, Cisl Fp e Uil Fp hanno diffidato Aiop… 500 euro al mese, notti, Bolzano",
                         None, _fa, CFG, COMUNI, OGGI, [])
verifica("feed: notizia sindacale o politica non è un'offerta", (_n3[0], _n3[1]), (None, "notizia, non un'offerta di lavoro"))
verifica("feed: altre notizie Nurse Times del 18/11 (lettera al direttore, ricorso per mobbing)",
         (estrai.e_notizia("Il Contratto Aris Rsa è fermo al 2012, il diritto del lavoro no - Nurse Times",
                           "https://nursetimes.org/il-contratto-aris-rsa-e-fermo-al-2012-il-diritto-del-lavoro-no", ""),
          estrai.e_notizia("Bolzano , infermiere in prova licenziato per inedeguatezza: respinto il ricorso per mobbing",
                           "https://nursetimes.org/bolzano-infermiere-in-prova-licenziato", "assunto come infermiere"),
          estrai.e_notizia("Contratto RSA: cosa cambia", "https://nursetimes.org/x", "",
                           "Il Direttore Infermieri NT News Profilo professionale Egregio direttore, giorni fa…")),
         (True, True, True))
verifica("feed: titolo con offerta vince anche se il testo cita i sindacati",
         estrai.e_notizia("APSP di Mori cerca infermieri", "https://x.it/a", "Fp Cgil soddisfatta"), False)
_mem = {"n": {"id": "n", "titolo": "Trento , infermiere aggredito al Santa Chiara: la Uil chiede più sicurezza - L'Adige",
              "url": "https://www.ladige.it/territori/trento/x", "tipo_fonte": "rss", "fonte": "Google Alerts 4",
              "estratto": "", "ultimo_visto": "2026-11-12", "primo_visto": "2026-11-12", "scadenza": None}}
motore.aggiorna_memoria(_mem, [], set(), set(), set(), OGGI, CFG)
verifica("memoria: le notizie già salvate dai feed vengono tolte", "n" in _mem, False)

_f_sj = next(f for f in CFG["fonti"] if f["nome"].startswith("Schloss Moos – libera professione"))
_es_sj = motore.raccogli_fonte(_f_sj, ReteFinta({_f_sj["url"]: PAGINA_SJ}), CFG, COMUNI, OGGI, {}, {})
verifica("Schloss Moos: senza gli annunci simili resta un annuncio da infermiere a Vipiteno",
         [(a["titolo"], a["zona"], a["contratto"]) for a in _es_sj["annunci"]],
         [("Freiberufliche Tätigkeit in der Pflege (Krankenpfleger/in)", "Vipiteno", "P.IVA / libera professione")])

print("Memoria: datati, doppioni, dati a mano")
verifica("annuncio datato", (motore.e_datato({"pubblicato": "2026-03-05", "scadenza": None}, OGGI, CFG), motore.e_datato({"pubblicato": "2026-03-05", "scadenza": "2026-12-01"}, OGGI, CFG)), (True, False))
m2 = {"a": {"id": "a", "titolo": "Concorso per infermieri", "datore": "APSP Vannetti", "zona": "Rovereto", "scadenza": "2026-11-20", "contratto": "Concorso / graduatoria", "punteggio": 30, "primo_visto": "2026-11-12", "origine": "manuale"},
      "b": {"id": "b", "titolo": "APSP Vannetti Rovereto - Infermiere", "datore": None, "zona": "Rovereto", "scadenza": "2026-11-20", "contratto": "Concorso / graduatoria", "punteggio": 39, "primo_visto": "2026-11-13"},
      "c": {"id": "c", "titolo": "Incarichi libero-professionali", "datore": "APSP Vannetti", "zona": "Rovereto", "scadenza": "2026-11-20", "contratto": "P.IVA / libera professione", "punteggio": 60, "primo_visto": "2026-11-13"},
      "d": {"id": "d", "titolo": "Infermiere/a a tempo pieno o part time", "datore": None, "zona": "Caldaro", "scadenza": None, "contratto": None, "punteggio": 42, "primo_visto": "2026-11-13", "pubblicato": "2023-09-13"},
      "e": {"id": "e", "titolo": "Infermiere/a a tempo pieno o part time", "datore": None, "zona": "Caldaro", "scadenza": None, "contratto": None, "punteggio": 42, "primo_visto": "2026-11-13", "pubblicato": "2024-07-29"}}
motore.segna_doppioni(m2, OGGI)
verifica("doppioni: stesso bando su due siti e annuncio ripubblicato", [m2[k].get("doppione_di") for k in "abcde"], [None, "a", None, "e", None])

# Il PDF di un bando letto anche come annuncio a sé (ASUIT Cavalese) e un bando comune a più case (Eggental, VdS).
PDF_C = "https://www.asuit.tn.it/files/SC%2003%2026%20AVVISO%20APERTO%20INFERMIERE.pdf"
m3 = {"p": {"id": "p", "titolo": "Selezione pubblica Cavalese", "url": "https://www.asuit.tn.it/bandi-concorsi/selezione", "zona": "Cavalese", "scadenza": "2026-12-31", "pdf_letti": [PDF_C], "punteggio": 32, "primo_visto": "2026-11-13"},
      "f": {"id": "f", "titolo": "SC 03/26 AVVISO APERTO", "url": PDF_C, "zona": "Cavalese", "scadenza": None, "pdf_letti": [PDF_C], "punteggio": 32, "primo_visto": "2026-11-13"},
      "c": {"id": "c", "titolo": "Infermiere/a", "datore": "Claraheim", "zona": "Cornedo all'Isarco", "scadenza": "2026-11-30", "punteggio": 37, "primo_visto": "2026-11-13", "avvisi": [],
            "pdf_letti": ["https://www.vds-suedtirol.it/files/job-documents/20261104_kundmachung_berufskrankenpfleger_0.pdf"]},
      "l": {"id": "l", "titolo": "Infermiere/a", "datore": "Leoheim", "zona": "Nova Levante", "scadenza": "2026-11-30", "punteggio": 30, "primo_visto": "2026-11-13",
            "pdf_letti": ["https://www.vds-suedtirol.it/files/job-documents/20261104_kundmachung_berufskrankenpfleger_1.pdf"]},
      "s": {"id": "s", "titolo": "Infermiere/a", "datore": "Peter Paul Schrott", "zona": "Nova Ponente", "scadenza": "2026-11-30", "punteggio": 30, "primo_visto": "2026-11-13",
            "pdf_letti": ["https://www.vds-suedtirol.it/files/job-documents/20261104_kundmachung_berufskrankenpfleger.pdf"]},
      "x": {"id": "x", "titolo": "Infermiere/a", "datore": "Altra casa", "zona": "Lana", "scadenza": "2026-11-20", "punteggio": 30, "primo_visto": "2026-11-13",
            "pdf_letti": ["https://www.vds-suedtirol.it/files/job-documents/20261104_kundmachung_berufskrankenpfleger_2.pdf"]}}
motore.segna_doppioni(m3, OGGI)
verifica("doppioni: il PDF già allegato a una pagina non è un annuncio a parte", m3["f"].get("doppione_di"), "p")
verifica("doppioni: bando comune a più case con lo stesso PDF e la stessa scadenza", [m3[k].get("doppione_di") for k in "clsx"], [None, "c", "c", None])
motore.segna_doppioni(m3, OGGI)
verifica("doppioni: le altre case restano scritte (una volta sola)", m3["c"]["avvisi"], ["Stesso bando anche per: Leoheim (Nova Levante), Peter Paul Schrott (Nova Ponente)"])
m3["p"]["scadenza"] = "2026-10-22"
motore.segna_doppioni(m3, OGGI)
verifica("doppioni: una pagina scaduta non nasconde il PDF ancora aperto", m3["f"].get("doppione_di"), None)

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
verifica("al primo giro si fissano i campi scritti a mano", "turni" in dopo.get("campi_manuali", []) and "compenso" not in dopo["campi_manuali"], True)
# 20/11 sera: Vannetti P.IVA (a mano) teneva «turni da 12 h» letti in automatico da un PDF il giorno prima: salvati
# nell'annuncio, al giro dopo sembravano scritti a mano e nessuna lettura migliore li correggeva più.
manuale_b = {**manuale, "turni": "turni da 12 h, notti", "segnali_turni": {"dodici": True, "notti": True},
             "campi_manuali": ["titolo", "datore", "contratto", "zona", "km", "minuti", "pubblicato"]}
motore.scrivi_json(motore.FILE_ANNUNCI, {manuale_b["id"]: manuale_b})
r_b = motore.giro(cfg5, ReteFinta(pagine3), date(2026, 11, 14), registra=muto)
dopo_b = motore.leggi_json(motore.FILE_ANNUNCI, {})[manuale_b["id"]]
verifica("un dato letto in automatico su un annuncio a mano si aggiorna",
         (dopo_b["titolo"], dopo_b["turni"], dopo_b.get("segnali_turni")), ("Personale infermieristico (CCNL AIOP)", None, {}))
verifica("e non è un aggiornamento per Michael", [x["cambi"] for x in r_b["aggiornati"]], [["scadenza: n.d. → 2026-11-18"]])

print("Regole della seconda messa a punto")
verifica("compenso: tra medici e infermieri vale quello degli infermieri",
         estrai.estrai_compenso("ai medici un compenso orario lordo pari a € 80,00; agli infermieri un compenso orario lordo onnicomprensivo di Euro 40,00")[1], 40.0)
verifica("compenso: 'lordo omnicomprensivo orario'", estrai.estrai_compenso("compenso lordo omnicomprensivo orario di euro 40,00")[1], 40.0)
# ASUIT SLP 15/26 (18/11): «compenso orario lordo omnicomprensivo da corrispondere ai professionisti, è pari a € 85,00
# per i medici specialisti … e a € 40,00 per gli infermieri»: il compenso dell'infermiere non veniva letto.
verifica("compenso: seconda tariffa nella stessa frase (infermieri)",
         estrai.estrai_compenso("Il compenso orario lordo omnicomprensivo da corrispondere ai professionisti, è pari a € 85,00 "
                                "per i medici specialisti in ortopedia e traumatologia e a € 40,00 per gli infermieri.")[1], 40.0)
verifica("compenso: la sola tariffa dei medici non è dell'infermiere",
         estrai.estrai_compenso("Il compenso orario lordo omnicomprensivo da corrispondere ai professionisti, è pari a € 85,00 per i medici specialisti."),
         (None, None))
verifica("compenso: 'euro-pea' non è un indizio", estrai.indizi_compenso("cittadino di uno Stato membro dell'Unione euro- pea"), [])
verifica("compenso: indizi quando non si riconosce", len(estrai.indizi_compenso("Il budget complessivo è di € 12.000 annui.")), 1)
sc = estrai.estrai_scadenza_frase("Le domande dovranno pervenire entro e non oltre le ore 12.00 del giorno 06/11/2026. Proroga termini di scadenza: 27/11/2026 ore 12.00", OGGI)
verifica("scadenza con la frase da cui è presa", (str(sc[0]), "Proroga termini di scadenza: 27/11/2026" in sc[1]), ("2026-11-27", True))
verifica("scadenza: la data dell'aggiornamento nella frase dopo non è la scadenza (ASUIT Cavalese)",
         estrai.estrai_scadenza_frase("Saranno valutate le candidature pervenute entro il giorno 2 ottobre. AGGIORNAMENTO DI DATA 22/10/2026! Si comunica che", OGGI), (None, None))
verifica("scadenza: «20. November 2026» resta una data",
         str(estrai.estrai_scadenza("Bewerbungsfrist: 20. November 2026, 12 Uhr", OGGI)), "2026-11-20")
verifica("scadenza: «ore 12.00 del 27/11/2026. Le domande…» resta letta",
         str(estrai.estrai_scadenza("Scadenza: ore 12.00 del 27/11/2026. Le domande vanno inviate via PEC.", OGGI)), "2026-11-27")
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

# 16/11: ASUIT SLP 15/26 (Campiglio, scadenza 10/09) era nascosto dalla pagina OPI di gennaio sul bando invernale
# (senza scadenza): regola 4, «stesso datore e zona». Un bando con una sua scadenza è un bando a sé.
m6 = {"s": {"id": "s", "titolo": "Avviso SLP 15/26 pronto soccorso ortopedico", "datore": "ASUIT (Trentino)", "zona": "Madonna di Campiglio",
            "scadenza": "2026-09-10", "contratto": "P.IVA / libera professione", "punteggio": 55, "primo_visto": "2026-11-13"},
      "o": {"id": "o", "titolo": "Avviso potenziamento invernale", "datore": "ASUIT (Trentino)", "zona": "Madonna di Campiglio",
            "scadenza": None, "pubblicato": "2026-01-07", "contratto": "P.IVA / libera professione", "punteggio": 55, "primo_visto": "2026-11-13"},
      "v": {"id": "v", "titolo": "Ricerca infermieri liberi professionisti", "datore": "ASUIT (Trentino)", "zona": "Madonna di Campiglio",
            "scadenza": None, "pubblicato": "2025-01-10", "contratto": "P.IVA / libera professione", "punteggio": 55, "primo_visto": "2026-11-13"}}
motore.segna_doppioni(m6, OGGI)
verifica("doppioni: un bando con la sua scadenza non è nascosto da un annuncio senza data", m6["s"].get("doppione_di"), None)
verifica("doppioni: due annunci senza scadenza dello stesso datore restano uniti", m6["v"].get("doppione_di"), "o")

# 16/11: Heinrich von Rottenburg (Caldaro): una voce era doppione di un'altra che era a sua volta doppione.
m7 = {"a": {"id": "a", "titolo": "Infermiere/a a tempo pieno o part time", "datore": None, "zona": "Caldaro", "email": None, "scadenza": None,
            "pubblicato": "2023-09-13", "punteggio": 40, "primo_visto": "2026-11-13"},
      "b": {"id": "b", "titolo": "Infermiere/a a tempo pieno o part time", "datore": "Fondazione Heinrich von Rottenburg", "zona": "Caldaro", "email": None,
            "scadenza": None, "pubblicato": "2024-07-29", "punteggio": 40, "primo_visto": "2026-11-13"},
      "c": {"id": "c", "titolo": "Fondazione Heinrich von Rottenburg (APSP) ricerca", "datore": "Fondazione Heinrich von Rottenburg", "zona": "Caldaro", "email": None,
            "scadenza": None, "pubblicato": "2026-06-23", "punteggio": 40, "primo_visto": "2026-11-13"}}
m7["a"]["titolo"] = m7["b"]["titolo"]  # stesso titolo: regola 2 (a → b), poi regola 4 (b → c)
m7["a"]["datore"] = m7["b"]["datore"]
m7["c"]["titolo"] = "Ricerca personale infermieristico"
motore.segna_doppioni(m7, OGGI)
verifica("doppioni: niente catene, tutti puntano all'annuncio mostrato", [m7[k].get("doppione_di") for k in "abc"], ["c", "c", None])

print("Revisione del 14/11")
# 14/11: la pagina OPI di San Giuseppe (Primiero) non ha risposto (errore di rete) e la lettura buona del giorno prima è andata persa.
class ReteGuasta:
    richieste = 0
    def get(self, url, robots=True):
        return None, "errore di rete (ConnectionError)"
    def get_pdf(self, url, massimo_mb=8, robots=True):
        return None, "errore di rete (ConnectionError)"
letto_ieri = {"id": "x1", "url": "https://opi.tn.it/apsp-prova/", "titolo": "Infermiere – ricerca di personale", "datore": "APSP Prova",
              "contratto": "Concorso / graduatoria", "scadenza": "2026-12-04", "zona": "Lavis", "estratto": "…testo letto ieri…",
              "letto_il": "2026-11-13", "regole": motore.VERSIONE_REGOLE, "avvisi": [], "punteggio": 40}
cand_g = {"url": "https://opi.tn.it/apsp-prova/", "titolo": "Infermiere – ricerca di personale"}
fonte_g = {"nome": "OPI", "tipo": "elenco", "affidabilita": "ordine"}
a_g, _ = motore._dettaglio(cand_g, fonte_g, ReteGuasta(), CFG, COMUNI, OGGI, letto_ieri)
verifica("rete guasta: resta la lettura del giorno prima", (a_g.get("_riusato"), a_g["estratto"], a_g["contratto"]), (True, "…testo letto ieri…", "Concorso / graduatoria"))
class Rete404(ReteGuasta):
    def get(self, url, robots=True):
        return None, "risposta HTTP 404"
a_g404, _ = motore._dettaglio(cand_g, fonte_g, Rete404(), CFG, COMUNI, OGGI, letto_ieri)
verifica("pagina tolta (404): non si finge di averla letta", (a_g404 or {}).get("_riusato"), None)

# 14/11: San Giuseppe (OPI, scritto a mano, senza compenso) nascondeva lo stesso bando UPIPA con compenso ed email.
m4 = {"o": {"id": "o", "titolo": "Infermiere – ricerca di personale", "datore": "APSP San Giuseppe", "zona": "Primiero San Martino di Castrozza",
            "scadenza": "2026-12-04", "contratto": "Concorso / graduatoria", "compenso": None, "email": None, "origine": "manuale",
            "punteggio": 25, "primo_visto": "2026-11-12", "avvisi": []},
      "u": {"id": "u", "titolo": "APSP di Primiero - Infermiere", "datore": "APSP di Primiero", "zona": "Primiero San Martino di Castrozza",
            "scadenza": "2026-12-04", "contratto": "Concorso / graduatoria", "compenso": "stipendio base 23.001,72 € l'anno, più indennità",
            "email": "segreteria@apsp-primiero.net", "punteggio": 27, "primo_visto": "2026-11-13", "fonte": "UPIPA"}}
motore.segna_doppioni(m4, OGGI)
verifica("doppioni: il dato mancante si prende dallo stesso bando", (m4["u"].get("doppione_di"), m4["o"]["compenso"], m4["o"]["email"]),
         ("o", "stipendio base 23.001,72 € l'anno, più indennità", "segreteria@apsp-primiero.net"))
verifica("doppioni: l'avviso dice da dove viene il dato", any("UPIPA" in x for x in m4["o"]["avvisi"]), True)
motore.segna_doppioni(m4, OGGI)
verifica("doppioni: l'avviso non si ripete a ogni giro", sum("UPIPA" in x for x in m4["o"]["avvisi"]), 1)

# 14/11: Melittaklinik e Brixsana apparivano come «Lavora con noi» e «Auch im Job: in besten Händen».
titoli_fissi = {f["nome"]: f.get("titolo") for f in CFG["fonti"] if f["nome"].startswith(("Melittaklinik", "Brixsana"))}
verifica("pagine fisse: titolo chiaro in config", sorted(n for n, t in titoli_fissi.items() if t and "nfermier" in t), sorted(titoli_fissi))

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
# 17/11: Algund «Seniorenheim», St. Pankraz «Altenheim» e Vinzenzhaus restavano senza tipo di struttura:
# il testo tedesco non lo diceva, il nome del datore sì.
verifica("struttura: dal nome del datore quando il testo non la dice", a_vds["struttura"], "RSA o casa di riposo")
verifica("struttura: Seniorenheim e ÖBPB sono case di riposo",
         [estrai.estrai_struttura(x, "") for x in ("Seniorenheim Algund Mathias Ladurner", "Stiftung Hans Messerschmied Ö.B.P.B", "Bürgerheim Brixen")],
         ["RSA o casa di riposo"] * 3)
# 17/11: «18, 20 und 22 Wochenstunden» diventava «22 h/settimana», come se il posto fosse solo da 22 ore.
verifica("ore: più scelte di ore settimanali restano tutte", estrai.estrai_turni("Teilzeit mit 18, 20 und 22 Wochenstunden")[0],
         "18, 20 o 22 h/settimana, part-time")
verifica("ore: una sola cifra resta com'è", estrai.estrai_turni("Vollzeit 38 Stunden pro Woche")[0], "38 h/settimana, tempo pieno")
# 19/11: Altershilfe Tschögglberg «Bereitschaft zur Arbeit im 3 Schicht System» restava «n.d.»: tre turni vuol dire anche notti.
verifica("turni: sistema a 3 turni (tedesco)", estrai.estrai_turni("Ihr Profil: Bereitschaft zur Arbeit im 3 Schicht System")[0], "3 turni (anche notti)")
verifica("turni: tre turni (italiano) segnala le notti", estrai.estrai_turni("disponibilità a lavorare su tre turni")[1].get("notti"), True)
verifica("turni: «3 Schichten» con le notti già scritte non si ripete",
         estrai.estrai_turni("Dreischichtbetrieb inklusive Nachtdienst")[0], "notti, 3 turni")
verifica("turni: 3 posti non sono 3 turni", estrai.estrai_turni("3 posti per infermieri, turni da concordare")[0], None)
# 20/11 sera: avviso Vannetti P.IVA, presenza «possibilmente non superiore a 10 ore» e 12 ore solo «in relazione
# al periodo emergenziale»: risultava «turni da 12 h» e prendeva tutti i punti dei turni.
_t12 = estrai.estrai_turni("La presenza giornaliera sarà possibilmente non superiore a 10 ore; in relazione al periodo "
                           "emergenziale potranno essere richiesti turni fino a 12 ore. Compenso per ore ordinarie, festive e notturne.")
verifica("turni: 12 ore solo per emergenza non sono turni da 12 h", (_t12[0], _t12[1].get("dodici")),
         ("notti, weekend/festivi", None))
verifica("turni: la frase scartata resta per la diagnostica", "emergenziale" in _t12[1].get("dodici_escluso", ""), True)
verifica("turni: «non oltre 12 ore» è un limite", estrai.estrai_turni("orario non oltre 12 ore consecutive")[0], None)
verifica("turni: turni da 12 ore veri restano", estrai.estrai_turni("Turni da 12 ore, notti e festivi")[1].get("dodici"), True)
verifica("turni: dopo un'eccezione conta un 12 ore vero", estrai.estrai_turni(
    "In via eccezionale 12 ore. Di norma turni di 12 ore diurni")[0], "turni da 12 h")
verifica("VdS: titolo leggibile dall'indirizzo (ore)",
         estrai.titolo_leggibile("Krankenpflegerinnen 7ter fe mit 18 20 und 22 wochenstunden"), "Infermiere/a – part-time (18, 20 o 22 ore/settimana)")
verifica("VdS: titolo leggibile dall'indirizzo (graduatoria con altri profili)",
         estrai.titolo_leggibile("Kundmachung befristete rangordnung sozialbetreuer pflegehelfer krankenpfleger"),
         "Infermiere/a – graduatoria, a tempo determinato (con altri profili)")
verifica("VdS: titolo senza dettagli", estrai.titolo_leggibile("Berufskrankenpflegerin berufsbild nr 64 der viiter funktionsebeneinfermierea"), "Infermiere/a")
verifica("VdS: altri ruoli restano come sono", estrai.titolo_leggibile("Befristete anstellung als sozialbetreuerin"), "Befristete anstellung als sozialbetreuerin")
# 13/11: cambiate le regole, 8 annunci risultavano «aggiornati» solo per il titolo riscritto dal Radar.
vecchio = {"id": "v1", "titolo": "Altenheim X", "regole": motore.VERSIONE_REGOLE - 1, "impronta": "a", "scadenza": "2026-11-20",
           "novita": "nuovo", "data_novita": "2026-11-12", "primo_visto": "2026-11-12", "punteggio": 30}
nuovo = dict(vecchio, titolo="Infermiere/a", regole=motore.VERSIONE_REGOLE, impronta="b")
esito_m = motore.aggiorna_memoria({"v1": dict(vecchio)}, [dict(nuovo)], set(), set(), set(), OGGI, CFG)
verifica("regole cambiate: il titolo riscritto non è una novità", len(esito_m["aggiornati"]), 0)
esito_m = motore.aggiorna_memoria({"v1": dict(vecchio)}, [dict(nuovo, scadenza="2026-11-30")], set(), set(), set(), OGGI, CFG)
verifica("regole cambiate: una proroga resta una novità", [x["cambi"] for x in esito_m["aggiornati"]], [["scadenza: 2026-11-20 → 2026-11-30"]])
# 19/11: Vinzenzhaus «tempo pieno, part-time» → «part-time» alle 14:24 e di nuovo «tempo pieno, part-time» alle 14:34
# (pagina che cambia da sola): risultava «aggiornato» oggi anche se era tornato tutto com'era.
_vz = {"id": "vz", "titolo": "Posizioni aperte", "regole": motore.VERSIONE_REGOLE, "turni": "tempo pieno, part-time",
       "novita": "aggiornato", "data_novita": "2026-11-10", "cambi": ["titolo: Jobs → Posizioni aperte"], "primo_visto": "2026-11-10"}
_vz["impronta"] = motore._impronta(_vz)
_mem_vz = {"vz": dict(_vz)}
_giro1 = dict(_vz, turni="part-time"); _giro1["impronta"] = motore._impronta(_giro1)
motore.aggiorna_memoria(_mem_vz, [dict(_giro1)], set(), set(), set(), OGGI, CFG)
verifica("va e torna: il primo cambio è un aggiornamento", _mem_vz["vz"]["cambi"], ["ore e turni: tempo pieno, part-time → part-time"])
esito_vz = motore.aggiorna_memoria(_mem_vz, [dict(_vz)], set(), set(), set(), OGGI, CFG)
verifica("va e torna: il ritorno com'era prima non è una novità",
         (len(esito_vz["aggiornati"]), _mem_vz["vz"]["novita"], _mem_vz["vz"]["data_novita"], _mem_vz["vz"]["cambi"]),
         (0, "aggiornato", "2026-11-10", ["titolo: Jobs → Posizioni aperte"]))
_giro3 = dict(_vz, turni="part-time"); _giro3["impronta"] = motore._impronta(_giro3)
_mem_vz2 = {"vz": dict(_vz, cambi=["ore e turni: part-time → tempo pieno, part-time"], data_novita="2026-11-01")}
verifica("va e torna: dopo più giorni un ritorno è un cambio vero",
         len(motore.aggiorna_memoria(_mem_vz2, [dict(_giro3)], set(), set(), set(), OGGI, CFG)["aggiornati"]), 1)

# 14/11: ASUIT SC 04/26–13/26 ha due sessioni (15/11 e 11/12): dopo la prima risultava scaduto.
man = {"id": "m1", "titolo": "Selezioni ASUIT", "origine": "manuale", "scadenza": "2026-11-15", "scadenze": ["2026-11-15", "2026-12-11"],
       "primo_visto": "2026-11-12", "ultimo_visto": "2026-11-12", "punteggio": 45, "cambi": []}
esito_m = motore.aggiorna_memoria({"m1": dict(man)}, [], set(), set(), set(), date(2026, 11, 15), CFG)
verifica("più sessioni: il giorno della prima resta la prima", esito_m["aggiornati"], [])
mem_s = {"m1": dict(man)}
esito_m = motore.aggiorna_memoria(mem_s, [], set(), set(), set(), date(2026, 11, 16), CFG)
verifica("più sessioni: passata la prima, vale la seconda (ed è un aggiornamento)",
         (mem_s["m1"]["scadenza"], [x["cambi"] for x in esito_m["aggiornati"]]),
         ("2026-12-11", [["scadenza: 2026-11-15 → 2026-12-11 (sessione successiva)"]]))
mem_s = {"m1": dict(man)}
motore.aggiorna_memoria(mem_s, [], set(), set(), set(), date(2026, 12, 15), CFG)
verifica("più sessioni: passate tutte, resta l'ultima (poi si toglie)", mem_s.get("m1", {}).get("scadenza"), "2026-12-11")

# 14/11: datore vuoto per Eurac («@Istituto per la Medicina…») e Annenberg («RESIDENZA PER ANZIANI…»).
verifica("datore: istituto nel titolo", estrai.estrai_datore("Study nurse @Bolzano @Istituto per la Medicina di Emergenza in Montagna – EURAC RESEARCH"),
         "Istituto per la Medicina di Emergenza in Montagna")
verifica("datore: residenza per anziani in maiuscolo", estrai.estrai_datore("Fondo Ospedale della S.S. Trinità RESIDENZA PER ANZIANI ANNENBERG LACES – Formazione di una graduatoria"),
         "Residenza per anziani Annenberg Laces")
verifica("datore: «residenza a Trento» resta una frase", estrai.estrai_datore("Infermiere in residenza a Trento"), None)

# 15/11: ASUIT SLP 15/26 risultava scaduto il 13/08 (data della delibera sotto «Date e scadenze»); il PDF diceva 10/09.
_ASUIT = "Tipo Argomenti Date e scadenze Cos'è In esecuzione della deliberazione del Direttore Generale n. 634 di data 13 agosto 2026 è indetto avviso"
verifica("scadenza: la data della delibera non è la scadenza", estrai.estrai_scadenza_frase(_ASUIT, OGGI), (None, None))
verifica("scadenza: dopo la delibera, la scadenza vera si trova",
         estrai.estrai_scadenza(_ASUIT + ". La domanda scade il giorno 10 settembre 2026 ad ore 23.59.", OGGI), date(2026, 9, 10))
verifica("scadenza: «entro il 20/11/2026» resta", estrai.estrai_scadenza("Domande entro il 20/11/2026 ore 12.", OGGI), date(2026, 11, 20))

# 15/11: ASUIT Cavalese (avviso aperto) risultava scaduto il 26/10 (valutazione periodica sulla pagina), il PDF chiude il 31/12.
_fonte_asuit = {"nome": "ASUIT", "tipo": "elenco", "affidabilita": "ufficiale", "datore": "ASUIT (Trentino)"}
_pdf_cav = {"caratteri": 9000, "scadenza": "2026-12-31", "scadenza_frase": "entro le ore 23.59 del giorno 31 dicembre 2026",
            "infermiere": True, "contratto": None, "compenso": None, "euro_ora": None, "turni": None, "zona": "Cavalese"}
_cav, _ = motore._costruisci({"titolo": "Selezione pubblica per infermieri – Cavalese", "url": "https://www.asuit.tn.it/bandi-concorsi/cav"},
                             "Avviso aperto per infermieri a Cavalese. Saranno valutate le candidature che perverranno entro il giorno lunedì 26 ottobre 2026. L'Azienda" + RIEMP,
                             None, _fonte_asuit, CFG, COMUNI, OGGI, [], da_pdf=_pdf_cav, pdf_letti=["https://www.asuit.tn.it/x.pdf"])
verifica("scadenza: pagina 26/10 e PDF 31/12 → vale il PDF, con avviso",
         (_cav["scadenza"], any(x.startswith("Scadenza dal bando PDF") for x in _cav["avvisi"])), ("2026-12-31", True))
_pro, _ = motore._costruisci({"titolo": "Incarichi libero-professionali infermieri", "url": "https://ente.it/lp"},
                             "Avviso per infermieri. Proroga termini di scadenza: 27/11/2026 ore 12.00." + RIEMP,
                             None, _fonte_asuit, CFG, COMUNI, OGGI, [], da_pdf=dict(_pdf_cav, scadenza="2026-11-13"), pdf_letti=["https://ente.it/x.pdf"])
verifica("scadenza: la proroga sulla pagina vince sul PDF", _pro["scadenza"], "2026-11-27")

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
mem["a5"] = {"id": "a5", "titolo": "Assunzione", "email": "k@clinica.it", "punteggio": 90, "contratto": "Dipendente a tempo indeterminato"}
mem["a6"] = {"id": "a6", "titolo": "Senza contratto", "email": "j@coop.it", "punteggio": 80, "contratto": None}
scelte = uscite.scegli_da_contattare(mem, {"a4": {"inviata_il": "2026-11-10", "a": ["z@rsa.it"]}}, cfg, OGGI)
verifica("contatti: mai due volte, solo libera professione, un solo messaggio per indirizzo", [a["id"] for a in scelte], ["a1"])
# Giro del 15/11: «Da contattare oggi» proponeva l'APSP Vannetti, che Michael ha escluso (invio.escludi: risponde lui all'avviso via PEC).
mem_v = {"v1": {"id": "v1", "titolo": "Incarichi libero-professionali", "datore": "APSP «Clementino Vannetti»", "pec": "apspvannetti@pec.it",
                "punteggio": 62, "contratto": "P.IVA / libera professione"},
         "v2": {"id": "v2", "titolo": "Freiberufliche Tätigkeit", "datore": "Schloss Moos", "email": "info@moos.it",
                "punteggio": 55, "contratto": "P.IVA / libera professione"}}
verifica("contatti: le strutture escluse in config non si propongono",
         [a["id"] for a in uscite.scegli_da_contattare(mem_v, {}, dict(cfg, invio={"escludi": ["Vannetti"]}), OGGI)], ["v2"])

print("Strutture dall'Indice della PA")
from radar import strutture as st
codici = st.leggi_istat("Codice Comune formato alfanumerico;Denominazione in italiano\n022117;Mezzolombardo\n021037;Lana\n")
ipa = ("Codice_IPA;Denominazione_ente;Codice_comune_ISTAT;Mail1;Tipo_Mail1;Mail2;Tipo_Mail2;Sito_istituzionale\n"
       "a;AZIENDA PUBBLICA DI SERVIZI ALLA PERSONA SAN GIOVANNI;022117;protocollo@pec.sangiovanni.tn.it;Pec;info@sangiovanni.tn.it;Altro;www.rsa-sangiovanni.it\n"
       "b;Seniorenwohnheim Lorenzerhof ÖBPB;21037;lorenzerhof@pec.it;Pec;;;\n"
       "c;Comune di Lavis;022102;comune@pec.it;Pec;;;\n"
       "d;APSP Casa di riposo di Brescia;017029;x@pec.it;Pec;;;\n")
trovate = st.leggi_ipa(ipa, COMUNI, codici)[0]
verifica("IPA: solo enti per anziani di Trento e Bolzano, con comune, PEC ed email",
         [(x["nome"], x["comune"], x["pec"], x["email"]) for x in trovate],
         [("APSP San Giovanni", "Mezzolombardo", "protocollo@pec.sangiovanni.tn.it", "info@sangiovanni.tn.it"),
          ("Seniorenwohnheim Lorenzerhof ÖBPB", "Lana", "lorenzerhof@pec.it", None)])
verifica("email dal sito: solo indirizzi dello stesso dominio", (st._stesso_dominio("info@rsa-sangiovanni.it", "https://www.rsa-sangiovanni.it"), st._stesso_dominio("mario@gmail.com", "https://www.rsa-sangiovanni.it")), (True, False))
verifica("strutture: la stessa PEC è la stessa struttura", bool(st.chiavi({"nome": "APSP San Giovanni", "pec": "protocollo@pec.sangiovanni.tn.it"}) & st.chiavi(trovate[0])), True)

print("Lettere e resoconto")
from radar import lettere, invio
it = lettere.lettera({"nome": "APSP Cristani - de Luca", "tipo": "RSA", "minuti": 6, "provincia": "TN"}, "R-1")
de = lettere.lettera({"nome": "Fondazione Lorenzerhof APSP", "tipo": "RSA pubblica", "minuti": 35, "provincia": "BZ"}, "R-2")
verifica("lettera: italiano per il Trentino, con distanza e codice", ("6 minuti" in it["testo"], "Rif. R-1" in it["oggetto"], "Sehr geehrte" in it["testo"]), (True, True, False))
breve = lettere.lettera_breve({"nome": "APSP Prova", "minuti": 15}, "R-5")
verifica("lettera breve: distanza, riservatezza, niente «sto valutando»", ("15 minuti" in breve["testo"], "riservata" in breve["testo"], "valutando" in breve["testo"], "Rif. R-5" in breve["oggetto"]), (True, True, False, True))
verifica("lettera: tedesco e italiano per l'Alto Adige", ("Sehr geehrte" in de["testo"], "Versione italiana" in de["testo"]), (True, True))
str_prova = [{"chiave": "s:1", "nome": "RSA Uno", "email": "a@rsa.it", "pec": None, "tipo": "RSA", "minuti": 5, "rif": "R-1", "provincia": "TN"},
             {"chiave": "s:2", "nome": "RSA Due", "email": "a@rsa.it", "pec": None, "tipo": "RSA", "minuti": 9, "rif": "R-2", "provincia": "TN"},
             {"chiave": "s:3", "nome": "Carcere", "email": None, "pec": "x@pec.it", "tipo": "Sanità penitenziaria", "minuti": 20, "rif": "R-3"},
             {"chiave": "s:4", "nome": "RSA Quattro", "email": "q@rsa.it", "pec": None, "tipo": "RSA", "minuti": 30, "rif": "R-4", "provincia": "TN"}]
verifica("coda: un indirizzo una volta, niente carcere, niente già scritti",
         [v["nome"] for v in invio.coda(str_prova, {}, {"s:4": {"inviata_il": "2026-11-10", "a": ["q@rsa.it"]}}, {**cfg, "invio": {}}, OGGI)], ["RSA Uno"])
verifica("coda con selezione: solo le strutture scelte, con la lettera breve",
         [(v["nome"], "riservata" in v["testo"]) for v in invio.coda(str_prova, {}, {}, {**cfg, "invio": {"selezione": ["Quattro"]}}, OGGI)], [("RSA Quattro", True)])
verifica("resoconto: interessati con compenso e da quando",
         {k: invio.leggi_esito("Siamo interessati, compenso orario di 38 euro, da gennaio 2027.")[k] for k in ("esito", "euro_ora", "da_quando")},
         {"esito": "sì", "euro_ora": 38.0, "da_quando": "da gennaio 2027"})
verifica("resoconto: risposta negativa in tedesco", invio.leggi_esito("Leider haben wir derzeit keinen Bedarf.")["esito"], "no")
# Risposte vere del 17-19/11 (frasi accorciate), con l'esito deciso da Michael in data/esiti.json.
_risposte_vere = [
    ("In questo momento non abbiamo bisogno, in ogni caso sarebbero assai gradite una sua offerta per l'anno 2027 e curriculum vitae", "più avanti"),
    ("Al momento non abbiamo necessità ma può comunque inviarci il curriculum.", "più avanti"),
    ("Attualmente non abbiamo la necessità di infermieri liberi professionisti. Le chiedo comunque di mandarci curriculum per possibili future esigenze", "più avanti"),
    ("La nostra struttura collabora con infermieri in libera professione. Per il momento siamo al completo, però se ci gira il suo curriculum lo consideriamo.", "più avanti"),
    ("Buongiorno, chiediamo gentilmente l'invio di un cv.", "più avanti"),
    ("A fine di trasmettere la sua candidatura agli uffici competenti, Le chiediamo gentilmente di trasmetterci il Suo curriculum vitae.", "più avanti"),
    ("La invito a trasmettere il suo cv aggiornato. Sarà contattato compatibilmente con le esigenze di servizio, ma prioritariamente l'accesso è tramite procedure concorsuali. Si valuta libera professione su eventuali esigenze indifferibili e qualora non vi siano candidati disponibili all'assunzione.", "più avanti"),
    ("Confermo che la nostra struttura collabora con Infermieri in libera professione, Le chiedo cortesemente di inviarci il curriculum vitae aggiornato.", "sì"),
    ("Collaboriamo anche con infermieri libero professionisti e pertanto può inviare il curriculum nel caso ci fossero esigenze.", "sì"),
    ("Buon giorno, si collaboriamo con infermieri in libera professione, può inviarmi un curriculum?", "sì"),
    ("Stiamo ancora cercando infermieri in libera professione. Se mi lascia il suo numero ci sentiamo domani.", "sì"),
    ("Se interessato ad un colloquio le chiedo di rispondere a questa mail.", "sì"),
    ("Buongiorno possiamo vederci già oggi pomeriggio alle 14.30. Avrei una certa urgenza", "sì"),
    ("Siamo sempre in difficoltà a reperire infermieri, quindi la Sua candidatura non è certamente fuori luogo. Al momento dovremmo essere a posto.", "sì"),
    ("Al momento il servizio infermieristico è coperto da personale dipendente. Avremo piacere di ricontattarla in caso di future opportunità.", "no"),
    ("La nostra è una struttura residenziale per minori e non sanitaria.", "no"),
    ("La ringrazio per l'interessamento, ma al momento non vi è necessità di attivare collaborazioni in libera professione.", "no"),
    ("Le chiediamo la cortesia di compilare l'apposito modulo di domanda di assunzione/collaborazione, che le alleghiamo.", "da fare"),
]
verifica("resoconto: esito delle risposte vere come deciso da Michael",
         [(t[:40], invio.leggi_esito(t)["esito"]) for t, _ in _risposte_vere], [(t[:40], e) for t, e in _risposte_vere])

avviso_html = ("<table><tr><td><a href='https://it.indeed.com/rc/clk?jk=abc&utm_source=x&from=mail'>Infermiere/a libero professionista</a>"
               "<div>Cooperativa Sociale Esempio</div><div>Trento, Trentino-Alto Adige</div><div>35 € all'ora</div></td></tr>"
               "<tr><td><a href='https://www.linkedin.com/jobs/view/123?trk=eml'>Registered Nurse – Seniorenwohnheim</a><div>Meran</div></td></tr>"
               "<tr><td><a href='https://it.indeed.com/x'>Cuoco di cucina</a></td></tr><tr><td><a href='https://it.indeed.com/u'>Annulla l'iscrizione</a></td></tr></table>")
nota_avv = {}
presi = posta.annunci_da_avviso(avviso_html, ["infermier", "krankenpfleg"], nota_avv)
verifica("avvisi dei portali: annunci per infermieri (anche «Nurse»), link puliti, il resto annotato",
         ([x["titolo"] for x in presi], presi[0]["url"], "35 €" in presi[0]["sommario"], nota_avv["altri_link"]),
         (["Infermiere/a libero professionista", "Registered Nurse – Seniorenwohnheim"], "https://it.indeed.com/rc/clk?jk=abc", True, ["Cuoco di cucina"]))

from email.message import EmailMessage as _Em
# 17/11: un'email di Indeed letta con 0 annunci e solo «Cerca lavoro, Supporto…»: senza l'oggetto non si capisce
# se era un avviso con annunci non riconosciuti o la sola conferma dell'iscrizione.
_av = _Em(); _av["Subject"] = "=?utf-8?q?Il_tuo_avviso_=C3=A8_attivo?="
verifica("avvisi dei portali: l'oggetto dell'email resta nella diagnostica", posta.oggetto_avviso(_av), "Il tuo avviso è attivo")
_m = _Em(); _m["Subject"] = "Infermiere libero professionista - Clinica Esempio"; _m["Date"] = "Mon, 16 Nov 2026 17:20:00 +0100"
_m.set_content("Guarda questo annuncio:\nInfermiere/a turni notturni, Clinica Esempio, Trento, 38 €/h\nhttps://it.indeed.com/viewjob?jk=123&from=share\n\nInviato da iPhone")
seg = posta.annunci_segnalati(_m)
verifica("segnalati: link, titolo dalla riga sopra, riassunto con il compenso",
         [(x["url"], x["titolo"], "38 €/h" in x["sommario"]) for x in seg],
         [("https://it.indeed.com/viewjob?jk=123", "Infermiere/a turni notturni, Clinica Esempio, Trento, 38 €/h", True)])

print("Web app e calendario")
dest = uscite.costruisci_sito(cfg, date(2026, 11, 14), tmp2 / "dist")
dati = __import__("json").loads((dest / "dati.json").read_text(encoding="utf-8"))
verifica("web app costruita", ((dest / "index.html").exists(), dati["oggi_lungo"], len(dati["offerte"]) >= 4), (True, "sabato 14 novembre", True))
ics = sorted((dest / "ics").glob("*.ics"))
verifica("calendario: un file per ogni scadenza futura", (len(ics) >= 2, "BEGIN:VEVENT" in ics[0].read_text(encoding="utf-8"), "DTSTART;VALUE=DATE:2026" in ics[0].read_text(encoding="utf-8")), (True, True, True))
riga_lunga = uscite._ics_piega("SUMMARY:" + "à" * 100)
verifica("calendario: righe piegate a 75 byte", max(len(x.encode("utf-8")) for x in riga_lunga.split("\r\n")) <= 75, True)

print("Radar dell'app (etichette)")
import shutil, subprocess, json as _json
if shutil.which("node"):
    _js = (RADICE / "webapp" / "app.js").read_text(encoding="utf-8")
    _pezzo = _js[_js.index("// <radar-etichette>"):_js.index("// </radar-etichette>")]
    # Bolzano (35 min) con il nome a sinistra finirebbe sopra la tacca «20′» dell'anello (giro del 15/11).
    _prova_js = _pezzo + """
var C = 180, R = 146; function raggio(m) { return R * Math.sqrt(Math.min(m, 90) / 90); }
var ost = [20, 45, 90].map(function (m) { var y = C - raggio(m) - 4; return { x1: C + 4, x2: C + 4 + String(m).length * 5.9 + 10, y1: y - 10, y2: y + 3 }; });
var punti = [{ nome: "Bolzano", c: { minuti: 35 }, x: 228.6, y: 103.0, raggio: 12.4 },
             { nome: "Cornedo all'Isarco", c: { minuti: 42 }, x: 240.6, y: 100.8, raggio: 9.2 },
             { nome: "Merano", c: { minuti: 55 }, x: 191.5, y: 66.4, raggio: 9.2 }];
etichetteRadar(punti, ost, 360);
var b = punti[0], e = b.etichetta, w = b.testo.length * 5.9 + 4;
var x1 = e ? (e.ancora === "start" ? e.x : e.ancora === "end" ? e.x - w : e.x - w / 2) : 0;
var sopra = e ? ost.some(function (t) { return t.x1 < x1 + w && t.x2 > x1 && t.y1 < e.y + 3 && t.y2 > e.y - 10; }) : false;
console.log(JSON.stringify({ sopra: sopra, nomi: ["Primiero San Martino di Castrozza", "Madonna di Campiglio", "Cornedo all'Isarco", "San Candido", "Pieve di Bono"].map(nomeCorto) }));
"""
    _ris = _json.loads(subprocess.run(["node", "-e", _prova_js], capture_output=True, text=True, check=True).stdout)
    verifica("radar: il nome di Bolzano non copre la tacca dei 20 minuti", _ris["sopra"], False)
    verifica("radar: nomi brevi senza «San» lasciato a metà", _ris["nomi"],
             ["Primiero", "Campiglio", "Cornedo", "San Candido", "Pieve di Bono"])
else:
    print("  --  node non c'è: prove del radar saltate")

print("\nRevisione del 17/11 (sera)")
# 17/11: Schloss Moos («Seniorenwohnheim») risultava «Disabilità o sociale»: il testo nomina la
# Sozialgenossenschaft che gestisce la casa, ma il posto di lavoro è una casa di riposo.
fonte_moos = {"nome": "Moos", "tipo": "pagina", "affidabilita": "struttura", "datore": "Seniorenwohnheim Schloss Moos", "zona": "Vipiteno"}
a_moos, _ = motore._costruisci({"url": "https://jobs.it/moos", "titolo": "Freiberufliche Tätigkeit in der Pflege (Krankenpfleger/in)"},
                               "Sozialgenossenschaft Vinzenz sucht Krankenpfleger/in freiberuflich, auch Nachtdienste." + RIEMP,
                               None, fonte_moos, CFG, COMUNI, OGGI, [])
verifica("struttura: il nome «Seniorenwohnheim» vale più della cooperativa citata nel testo", a_moos["struttura"], "RSA o casa di riposo")
fonte_camp = {"nome": "ASUIT", "tipo": "pagina", "affidabilita": "ente", "datore": "ASUIT (Trentino)", "zona": "Madonna di Campiglio"}
a_camp, _ = motore._costruisci({"url": "https://asuit.it/slp", "titolo": "Incarichi libero-professionali infermieri – stagione invernale"},
                               "Incarichi stagionali per il soccorso traumatologico di Campiglio." + RIEMP,
                               None, fonte_camp, CFG, COMUNI, OGGI, [])
verifica("struttura: «stagionale» detto dal testo resta (dice com'è il lavoro)", a_camp["struttura"], "Stagionale o turistico")
# 17/11: gli annunci scritti a mano (graduatoria ASDAA/SABES, selezioni ASUIT, KOS «centro di riabilitazione»)
# non vengono riletti e restavano senza tipo: sparivano dai filtri dell'app.
mem_t = {"m": {"id": "m", "titolo": "Graduatoria permanente infermieri", "datore": "ASDAA / SABES", "origine": "manuale",
               "struttura": None, "scadenza": "2027-01-31", "primo_visto": "2026-11-12", "ultimo_visto": "2026-11-12", "punteggio": 37, "cambi": []},
         "k": {"id": "k", "titolo": "Infermiere/a", "datore": "Paziente privato", "origine": "manuale",
               "struttura": None, "scadenza": None, "primo_visto": "2026-11-12", "ultimo_visto": "2026-11-12", "punteggio": 37, "cambi": []}}
esito_t = motore.aggiorna_memoria(mem_t, [], set(), set(), set(), OGGI, CFG)
verifica("struttura: anche agli annunci a mano la dice il nome del datore", (mem_t["m"]["struttura"], mem_t["k"]["struttura"]),
         ("Ospedale o azienda sanitaria", None))
verifica("struttura completata: non è un aggiornamento", esito_t["aggiornati"], [])
# 19/11: OPI Trento, Vannetti «l'avviso è… in calce alla pagina»: la diagnostica dei PDF mancanti
# mostrava solo le icone del sito (<link rel="icon">), quindi non diceva dove sta l'avviso.
_html_d = ("<html><head><link rel='icon' href='https://opi.tn.it/wp-content/uploads/2019/05/favicon.jpg'></head><body>"
           "<article><p>L'avviso è pubblicato sul sito e in calce alla pagina.</p>"
           "<a href='https://www.apspvannetti.it/Albo-pretorio/Avvisi/Incarichi-infermieri'>Incarichi infermieri</a>"
           "<a href='https://www.facebook.com/sharer.php?u=x'>Condividi</a><a href='/chi-siamo/'>Chi siamo</a></article></body></html>")
verifica("PDF mancanti: niente icone, sì al link dell'avviso su un altro sito",
         [x[2] for x in estrai.allegati_dubbi(_html_d, "https://opi.tn.it/a-p-s-p-c-vannetti-2-copy/")],
         ["https://www.apspvannetti.it/Albo-pretorio/Avvisi/Incarichi-infermieri"])
# 20/11: OPI Trento, Vannetti P.IVA: tre riquadri «scarica il pdf» (avviso e proroga) ma nessun PDF trovato:
# l'indirizzo sta in un attributo insolito o nello script del visualizzatore, non in href/src.
_html_v = ("<html><head><link rel='icon' href='https://opi.tn.it/x.ico'></head><body><article><h1>Vannetti – liberi professionisti</h1>"
           "<p>L'avviso è pubblicato in calce alla pagina.</p>"
           "<div class='pdf-box' data-source='https://opi.tn.it/wp-content/uploads/2026/10/Avviso-incarichi-LP-infermieri.pdf'>"
           "<span class='btn'>scarica il pdf</span></div>"
           "<script>var v={\"file\":\"https:\\/\\/opi.tn.it\\/wp-content\\/uploads\\/2026\\/11\\/PROROGA-termini.pdf\"};</script>"
           "<div data-x='/wp-content/uploads/2026/10/informativa-privacy.pdf'></div></article></body></html>")
verifica("PDF nel codice: avviso in un attributo insolito e proroga nello script, niente informativa",
         [x["url"] for x in estrai.leggi_pagina(_html_v, "https://opi.tn.it/a-p-s-p-c-vannetti-2-copy/")["pdf"]],
         ["https://opi.tn.it/wp-content/uploads/2026/10/Avviso-incarichi-LP-infermieri.pdf",
          "https://opi.tn.it/wp-content/uploads/2026/11/PROROGA-termini.pdf"])
verifica("PDF nel codice: la diagnostica elenca quelli lasciati fuori per il nome",
         estrai.pdf_scartati_nel_codice(_html_v, "https://opi.tn.it/v/"), ["https://opi.tn.it/wp-content/uploads/2026/10/informativa-privacy.pdf"])
_html_v2 = ("<div data-a='https://opi.tn.it/wp-content/uploads/2025/10/STAMPED20261016131231-DET_304_26_dd_15_10_Allegato_signed.pdf'></div>"
            "<div data-a='https://opi.tn.it/wp-content/uploads/2025/10/DET_294_26_dd__09_10_Allegato_domanda.pdf'></div>"
            "<div data-a='https://opi.tn.it/wp-content/uploads/2025/10/Determinato_allegato.pdf'></div>")
verifica("PDF nel codice: l'allegato di una determinazione è l'avviso (la domanda no)",
         [x["url"].rsplit("/", 1)[-1] for x in estrai.leggi_pagina(_html_v2, "https://opi.tn.it/v/")["pdf"]],
         ["STAMPED20261016131231-DET_304_26_dd_15_10_Allegato_signed.pdf"])
verifica("PDF nel codice: link normali hanno la precedenza",
         [x["url"] for x in estrai.leggi_pagina("<article><a href='/a/bando.pdf'>Bando</a><script>'https://x.it/avviso2.pdf'</script></article>",
                                                "https://opi.tn.it/p/")["pdf"]], ["https://opi.tn.it/a/bando.pdf"])
_html_b = ("<html><body><article><p>Avviso in calce.</p><div class='wpfd-file' data-id='77'><span>scarica il pdf</span></div>"
           "<button onclick='apri(77)'>Download</button></article></body></html>")
verifica("PDF mancanti: i pulsanti «scarica il pdf» senza indirizzo sono descritti",
         [x[:2] for x in estrai.allegati_dubbi(_html_b, "https://opi.tn.it/v/")], [["span", "scarica il pdf"], ["button", "Download"]])
verifica("PDF mancanti: si vedono gli attributi del pulsante",
         [x[2] for x in estrai.allegati_dubbi(_html_b, "https://opi.tn.it/v/")],
         ["div[class=wpfd-file; data-id=77] ↑ article[]", "onclick=apri(77) ↑ article[]"])
# 19/11: sei offerte in P.IVA scritte a mano (Italiassistenza ×2, Cerba, ParaMedica, IQVIA, Privatassistenza)
# erano senza tipo: il nome non lo dice, ma lo dicono il titolo («assistenza domiciliare», «RSA»)
# o l'elenco Strutture di Michael («Italiassistenza – Assistenza domiciliare»). Sparivano dal filtro «Domiciliare».
_el = [("italiassistenza", "Assistenza domiciliare"), ("cerba healthcare", "Prelievi e ambulatori"), ("paramedica", "Agenzia per RSA")]
_ss = lambda t, d: motore.struttura_senza_lettura({"titolo": t, "datore": d}, _el)
verifica("struttura a mano: dall'elenco Strutture (nome con spa)", _ss("Infermiere/a con partita IVA a Trento", "Italiassistenza spa"), "Domiciliare")
verifica("struttura a mano: dall'elenco Strutture (nome tra parentesi)", _ss("Infermiere P.IVA (TN)", "CHC Italy (Cerba HealthCare)"), "Clinica o ambulatorio")
verifica("struttura a mano: dal titolo (domiciliare)", _ss("Infermiere per attività domiciliari", "IQVIA Solutions Italy"), "Domiciliare")
verifica("struttura a mano: dal titolo (RSA)", _ss("Infermieri RSA zona Rovereto", "Ditta X"), "RSA o casa di riposo")
verifica("struttura a mano: nome simile ma diverso non conta", _ss("Infermiere/a", "Italia Servizi"), None)
verifica("struttura a mano: il nome del datore vince sull'elenco", _ss("Infermiere/a", "APSP Italiassistenza"), "RSA o casa di riposo")
verifica("elenco Strutture vero: Italiassistenza è domiciliare",
         dict(motore.tipi_dall_elenco(motore.RADICE / "data" / "strutture.csv")).get("italiassistenza"), "Assistenza domiciliare")
# 17/11: Fondazione Pitsch, due annunci diversi (graduatoria 2025 e ricerca di personale): quello mostrato
# non aveva né email né tipo di struttura, che il doppione nascosto aveva (personal@pitsch.it).
m8 = {"g": {"id": "g", "titolo": "Fondazione Pitsch cerca infermieri/e", "datore": "Fondazione Pitsch", "zona": "Merano", "email": None,
            "struttura": None, "compenso": None, "scadenza": None, "pubblicato": "2025-08-01", "punteggio": 30, "primo_visto": "2026-11-13",
            "fonte": "OPI Bolzano", "avvisi": []},
      "p": {"id": "p", "titolo": "Fondazione Pitsch cerca personale", "datore": "Fondazione Pitsch", "zona": "Merano", "email": "personal@pitsch.it",
            "struttura": "RSA o casa di riposo", "compenso": "30 €/h", "scadenza": None, "pubblicato": "2025-06-01", "punteggio": 30,
            "primo_visto": "2026-11-13", "fonte": "OPI Bolzano", "avvisi": []}}
motore.segna_doppioni(m8, OGGI)
verifica("stesso datore: email e struttura passano all'annuncio mostrato, il compenso no",
         (m8["p"].get("doppione_di"), m8["g"]["email"], m8["g"]["struttura"], m8["g"]["compenso"]),
         ("g", "personal@pitsch.it", "RSA o casa di riposo", None))
verifica("stesso datore: l'avviso dice da dove viene l'email", any(x.startswith(motore.AVVISO_DAL_DATORE) for x in m8["g"]["avvisi"])
         if hasattr(motore, "AVVISO_DAL_DATORE") else False, True)
motore.segna_doppioni(m8, OGGI)
verifica("stesso datore: l'avviso non si ripete a ogni giro", sum("stesso datore" in x for x in m8["g"]["avvisi"]), 1)

print("Revisione del 18/11 sera")
# 18/11: ASUIT ha scartato «AVVISO DI SELEZIONE PUBBLICA … INCARICHI LIBERO PROFESSIONA…» come «non riguarda infermieri»,
# ma lo scarto teneva solo 90 lettere e nessun indirizzo, e nei giri dopo non compariva più in diagnostica:
# impossibile capire se era un avviso per medici o un errore del Radar.
_tit_lp = ("AVVISO DI SELEZIONE PUBBLICA SELEZIONE PER IL CONFERIMENTO DI INCARICHI LIBERO PROFESSIONALI "
           "A MEDICI SPECIALISTI IN ANESTESIA PER LE ESIGENZE DELL'OSPEDALE DI CLES")
_el_lp = f'<html><body><ul><li><a href="https://asl.it/bandi/lp-medici">{_tit_lp}</a></li></ul></body></html>'
_f_lp = {"nome": "ASL", "tipo": "elenco", "url": "https://asl.it/bandi", "affidabilita": "ufficiale",
         "parole_link": ["libero profession", "infermier"]}
_rete_lp = ReteFinta({"https://asl.it/bandi": _el_lp,
                      "https://asl.it/bandi/lp-medici": art(_tit_lp, "Incarichi a medici anestesisti. " + "Requisiti: specializzazione. " * 20)})
_st_lp, _di_lp = {}, {}
motore.raccogli_fonte(_f_lp, _rete_lp, CFG, COMUNI, OGGI, {}, _st_lp, _di_lp)
_sc_lp = next(iter(_st_lp.get("scarti", {}).values()), {})
verifica("scarto: si ricorda l'indirizzo", _sc_lp.get("u"), "https://asl.it/bandi/lp-medici")
verifica("scarto: si ricorda il titolo intero", "MEDICI" in (_sc_lp.get("tl") or ""), True)
_di_lp2 = {}
motore.raccogli_fonte(_f_lp, _rete_lp, CFG, COMUNI, OGGI, {}, _st_lp, _di_lp2)
verifica("scarto ricordato: resta visibile in diagnostica con indirizzo",
         [(x[1], x[2]) for x in _di_lp2["ASL"].get("gia_scartati", [])], [(_sc_lp.get("m"), "https://asl.it/bandi/lp-medici")])

print("\nSentinella (posta personale)")
from datetime import date as _d
from sentinella import regole as _sr
_oggi = _d(2026, 11, 17)
verifica("airbnb prenotazione", _sr.categoria("Airbnb <automated@airbnb.com>", "Prenotazione confermata - Luca arriva il 3 dic", ""), "airbnb")
verifica("booking cancellazione", _sr.categoria("Booking.com <noreply@booking.com>", "Cancellazione prenotazione 123", "", True), "booking")
verifica("bolletta dolomiti energia", _sr.categoria("Dolomiti Energia <info@dolomitienergia.it>", "La tua bolletta di novembre", "scadenza 05/12/2026 importo € 84,30", True), "energia")
verifica("pubblicita luce scartata", _sr.categoria("Enel <promo@enel.it>", "Offerta speciale: 20% di sconto", "", True), None)
verifica("newsletter qualsiasi scartata", _sr.categoria("Zalando <news@zalando.it>", "Novità della settimana", "", True), None)
verifica("appuntamento", _sr.categoria("Studio dentistico <x@y.it>", "Promemoria appuntamento", ""), "appuntamento")
verifica("scadenza bollo", _sr.categoria("ACI <a@aci.it>", "Bollo auto in scadenza", ""), "scadenza")
verifica("date con etichetta", _sr.date_trovate("Check-in 3 dicembre 2026, check-out 06/12/2026", _oggi), [(_d(2026,12,3), "Check-in"), (_d(2026,12,6), "Check-out")])
verifica("data passata ignorata", _sr.date_trovate("scadenza 01/10/2026", _oggi), [])
verifica("importo", _sr.importo("Totale da pagare € 84,30 entro"), "84,30 €")

# Esiti scritti a mano: vincono sulla lettura automatica finché la struttura non scrive di nuovo.
from radar import invio as _inv
_tm = Path(tempfile.mkdtemp()) / "esiti.json"
_tm.write_text('{"_nota": "x", "s:a": {"esito": "più avanti", "aggiornato": "2026-11-18", "prossimo": "CV inviato"}}', encoding="utf-8")
verifica("esiti a mano: letti e senza le note", _inv.esiti_manuali(_tm), {"s:a": {"esito": "più avanti", "aggiornato": "2026-11-18", "prossimo": "CV inviato"}})
_orig = _inv.esiti_manuali
_inv.esiti_manuali = lambda percorso=None: _orig(_tm)
_c = {"s:a": {"inviata_il": "2026-11-17", "risposte": [{"data": "2026-11-18", "testo": "Al momento non abbiamo bisogno"}], "mie_risposte": [{"data": "2026-11-18"}]}}
_r = _inv.resoconto([{"chiave": "s:a", "nome": "A", "comune": "Mori", "minuti": 45}], {}, _c, CFG)[0]
verifica("esiti a mano: esito, prossimo passo e mia risposta", (_r["esito"], _r["prossimo"], _r["mia_risposta_il"]), ("più avanti", "CV inviato", "2026-11-18"))
_c["s:a"]["risposte"].append({"data": "2026-11-20", "testo": "Siamo interessati"})
_r = _inv.resoconto([{"chiave": "s:a", "nome": "A", "comune": "Mori", "minuti": 45}], {}, _c, CFG)[0]
verifica("esiti a mano: nuova risposta dopo l'aggiornamento li sospende", (_r["esito"] != "più avanti", _r["prossimo"]), (True, None))
# 21/11: Casa Laner restava «Tocca a te: compila il modulo» (esito del 18/11) anche dopo che Michael aveva risposto il 21/11.
_tm.write_text('{"s:b": {"esito": "da fare", "aggiornato": "2026-11-18", "prossimo": "Compila il loro modulo."}}', encoding="utf-8")
_cb = {"s:b": {"inviata_il": "2026-11-17", "risposte": [{"data": "2026-11-18", "testo": "le chiediamo di compilare l'apposito modulo"}],
               "mie_risposte": [{"data": "2026-11-21"}]}}
_r = _inv.resoconto([{"chiave": "s:b", "nome": "B"}], {}, _cb, CFG)[0]
verifica("esiti: «da fare» già fatto quando Michael ha risposto dopo", (_r["esito"], _r["prossimo"]),
         ("hai risposto", "Hai risposto il 21/11: ora tocca a loro. Passo scritto il 18/11: Compila il loro modulo."))
_cb["s:b"]["mie_risposte"] = [{"data": "2026-11-18"}]
_r = _inv.resoconto([{"chiave": "s:b", "nome": "B"}], {}, _cb, CFG)[0]
verifica("esiti: risposta di Michael dello stesso giorno, il passo resta", (_r["esito"], _r["prossimo"]), ("da fare", "Compila il loro modulo."))
_tm.write_text('{}', encoding="utf-8")
_cb["s:b"]["mie_risposte"] = [{"data": "2026-11-19"}]
_r = _inv.resoconto([{"chiave": "s:b", "nome": "B"}], {}, _cb, CFG)[0]
verifica("esiti: «da fare» letto in automatico, Michael ha risposto dopo", (_r["esito"], _r["prossimo"]),
         ("hai risposto", "Hai risposto il 19/11: ora tocca a loro."))
# 24/11: Città Azzurra («può inviarci gentilmente un CV…?») era solo «Interessati», senza passo: la richiesta del CV
# non compariva tra le cose da fare. Griesfeld («Potrebbe inviarci il curriculum») era «Più avanti» anche dopo il CV di Michael.
_cc = {"s:c": {"inviata_il": "2026-11-22", "risposte": [{"data": "2026-11-23", "testo": "Gentile sig. Panico,\npuò inviarci gentilmente un CV per valutare un possibile colloquio\nconoscitivo?"}]}}
_r = _inv.resoconto([{"chiave": "s:c", "nome": "C"}], {}, _cc, CFG)[0]
verifica("esiti: CV chiesto e non ancora mandato è da fare", (_r["esito"], _r["prossimo"]),
         ("da fare", "Ti hanno chiesto il CV il 23/11: se non l'hai ancora mandato, rispondi alla loro email con il CV."))
_cc["s:c"]["mie_risposte"] = [{"data": "2026-11-23", "allegato": "CV_Michael.pdf"}]
_r = _inv.resoconto([{"chiave": "s:c", "nome": "C"}], {}, _cc, CFG)[0]
verifica("esiti: CV chiesto e mandato, tocca a loro", (_r["esito"], _r["prossimo"]),
         ("hai risposto", "Hai risposto il 23/11 con il CV: ora tocca a loro."))
_cc["s:c"]["risposte"] = [{"data": "2026-11-23", "testo": "Grazie per averci inviato il curriculum, la terremo presente."}]
_cc["s:c"].pop("mie_risposte")
verifica("esiti: CV già ricevuto non è una richiesta",
         _inv.resoconto([{"chiave": "s:c", "nome": "C"}], {}, _cc, CFG)[0]["esito"] != "da fare", True)
_tm.write_text('{"s:c": {"esito": "più avanti", "aggiornato": "2026-11-23", "prossimo": "CV inviato il 23/11."}}', encoding="utf-8")
_cc["s:c"]["risposte"] = [{"data": "2026-11-23", "testo": "Potrebbe inviarci il curriculum"}]
_r = _inv.resoconto([{"chiave": "s:c", "nome": "C"}], {}, _cc, CFG)[0]
verifica("esiti: con l'esito scritto a mano la richiesta del CV non cambia nulla", (_r["esito"], _r["prossimo"]), ("più avanti", "CV inviato il 23/11."))
verifica("richiesta del CV: frasi vere", [bool(_inv.RE_CHIEDE_CV.search(t)) for t in (
    "Potrebbe inviarci il curriculum", "chiediamo gentilmente l'invio di un cv.", "Le chiediamo gentilmente di trasmetterci il Suo curriculum vitae.",
    "se ci gira il suo curriculum lo consideriamo", "può inviarmi un curriculum?", "Abbiamo ricevuto il suo CV", "Grazie per averci inviato il CV")],
    [True, True, True, True, True, False, False])
_inv.esiti_manuali = _orig

# Allarmi: un bando ASUIT sui centri traumatologici fa scattare l'allarme una volta sola; altri siti no.
from radar import uscite as _usc
_cfg_al = {"allarmi": [{"nome": "Trauma", "siti": ["asuit.tn.it"], "parole": ["traumatolog", "campiglio"]}]}
_mem = {"a1": {"titolo": "Avviso incarichi libero professionali infermieri centri traumatologici", "url": "https://www.asuit.tn.it/bandi-concorsi/x"},
        "a2": {"titolo": "Infermiere centro traumatologico", "url": "https://www.indeed.it/x"},
        "a3": {"titolo": "Concorso infermieri", "url": "https://www.asuit.tn.it/bandi-concorsi/y"},
        "a4": {"titolo": "Centro traumatologico Campiglio", "url": "https://www.asuit.tn.it/z", "sparito_dal": "2026-01-01"}}
verifica("allarmi: solo il bando giusto dal sito giusto", [x["id"] for x in _usc.trova_allarmi(_mem, _cfg_al)], ["a1"])
verifica("allarmi: bando scaduto ignorato", _usc.trova_allarmi({"s": {"titolo": "centri traumatologici", "url": "https://www.asuit.tn.it/s", "scadenza": "2020-01-01"}}, _cfg_al), [])
verifica("allarmi: non si ripetono", _usc.trova_allarmi(_mem, _cfg_al, {"Trauma": ["a1"]}), [])
_o, _t, _p = _usc.componi_allarme(_usc.trova_allarmi(_mem, _cfg_al))
verifica("allarmi: oggetto riconoscibile", _o.startswith("⚠️ ALLARME Radar: Trauma"), True)

# 22/11 sera: l'avviso invernale di Campiglio/Sèn Jan l'anno scorso è uscito anche su OPI Trento (pagina del 07/01),
# ma l'allarme guardava solo asuit.tn.it. Aggiungendo OPI, la pagina vecchia di gennaio (senza scadenza, «datata»)
# non deve far scattare l'allarme, e un bando visto su due siti (doppione) deve dare un allarme solo.
_cfg_al2 = {"giorni_annuncio_datato": 120,
            "allarmi": [{"nome": "Trauma", "siti": ["asuit.tn.it", "opi.tn.it"], "parole": ["traumatolog", "campiglio"]}]}
_oggi_al = date.today()
_mem2 = {"vecchio": {"titolo": "Avviso incarichi libero professionali infermieri ambulatori traumatologici Campiglio",
                     "url": "https://opi.tn.it/avviso-x/", "pubblicato": (_oggi_al - timedelta(days=300)).isoformat()},
         "nuovo": {"titolo": "Avviso incarichi libero professionali infermieri ambulatori traumatologici Campiglio",
                   "url": "https://opi.tn.it/avviso-y/", "pubblicato": _oggi_al.isoformat()},
         "copia": {"titolo": "SLP 20/26 centri traumatologici", "url": "https://www.asuit.tn.it/bandi-concorsi/slp",
                   "doppione_di": "nuovo"}}
verifica("allarmi: pagina OPI nuova sì, vecchia «datata» no, doppione no",
         [x["id"] for x in _usc.trova_allarmi(_mem2, _cfg_al2)], ["nuovo"])
verifica("allarmi: bando già segnalato, la sua copia su un altro sito non ripete l'allarme",
         _usc.trova_allarmi({"copia": {**_mem2["copia"], "doppione_di": None},
                             "nuovo": {**_mem2["nuovo"], "doppione_di": "copia"}}, _cfg_al2, {"Trauma": ["nuovo"]}), [])

# 20/11: primo avviso vero di Indeed («Infermieri ParaMedica srl Asiago, Veneto»): la diagnostica diceva solo
# «candidati 1, accettati 0», senza dire che cosa era stato scartato e perché.
_tmp_av = Path(tempfile.mkdtemp())
motore.FILE_ANNUNCI, motore.FILE_FONTI, motore.CARTELLA_REPORT = _tmp_av / "a.json", _tmp_av / "f.json", _tmp_av / "r"
motore.FILE_DIAGNOSTICA = _tmp_av / "d.json"
_cfg_av = dict(cfg5)
_cfg_av["fonti"], _cfg_av["feed_google_alerts"], _cfg_av["esplora"] = [], [], []
_av = {"Indeed": [{"url": "https://it.indeed.com/viewjob?jk=1", "titolo": "Infermieri",
                   "sommario": "Infermieri ParaMedica srl Asiago, Veneto"},
                  {"url": "https://it.indeed.com/viewjob?jk=2", "titolo": "Infermiere/a con partita IVA",
                   "sommario": "Infermiere/a con partita IVA Italiassistenza Trento, Trentino-Alto Adige"}]}
motore.giro(_cfg_av, ReteFinta({}), date(2026, 11, 20), registra=muto, avvisi=_av)
_d_av = motore.leggi_json(motore.FILE_DIAGNOSTICA, {})["fonti"]["Avvisi email – Indeed"]
verifica("avvisi email: la diagnostica dice cosa è stato scartato e perché",
         (_d_av["accettati"], [x[:2] for x in _d_av["scartati"]]),
         (1, [["Infermieri ParaMedica srl Asiago, Veneto", "fuori regione"]]))

# 21/11: Coop SOS (Indeed, Bolzano) era tra le novità senza datore: titolo «Infermiera / Infermiere Professionale»
# e basta, anche se l'oggetto dell'email diceva «… presso Coop SOS» e il riassunto «… Coop SOS Bolzano - Bozen».
_html_sos = ("<table><tr><td><a href='https://cts.indeed.com/v3/abc'>Infermiera / Infermiere Professionale</a>"
             "<div>Coop SOS</div><div>Bolzano - Bozen, Trentino-Alto Adige</div></td></tr></table>")
_sos = posta.annunci_da_avviso(_html_sos, ["infermier"], {}, "Infermiera / Infermiere Professionale presso Coop SOS")
verifica("avvisi dei portali: il datore dall'oggetto «… presso X» se il riassunto lo conferma",
         [x.get("datore") for x in _sos], ["Coop SOS"])
verifica("avvisi dei portali: oggetto di un altro annuncio, nessun datore",
         [x.get("datore") for x in posta.annunci_da_avviso(_html_sos, ["infermier"], {}, "Cuoco presso Hotel Alpi")], [None])
verifica("avvisi dei portali: datore che il riassunto non conferma, nessun datore",
         [x.get("datore") for x in posta.annunci_da_avviso(_html_sos, ["infermier"], {}, "Infermiera / Infermiere Professionale presso Clinica X")], [None])
_av2 = {"Indeed": [{**_sos[0], "id": "sos1"}]}
motore.giro(_cfg_av, ReteFinta({}), date(2026, 11, 21), registra=muto, avvisi=_av2)
_a_sos = motore.leggi_json(motore.FILE_ANNUNCI, {}).get("sos1") or {}
verifica("avvisi email: il datore dell'avviso arriva nell'annuncio", (_a_sos.get("datore"), _a_sos.get("zona")), ("Coop SOS", "Bolzano"))

# 22/11: l'unica novità del giorno (Indeed) aveva il datore tutto in maiuscolo, come lo scrive l'oggetto
# dell'email: «CITTA' AZZURRA SOC. COOP. BOLZANO». Sul telefono si legge male; «CITTA'» è «Città».
_html_ca = ("<table><tr><td><a href='https://cts.indeed.com/v3/xyz'>infermiere/a</a>"
            "<div>CITTA' AZZURRA SOC. COOP. BOLZANO</div><div>39100 Bolzano - Bozen</div></td></tr></table>")
verifica("avvisi dei portali: datore in maiuscolo riscritto leggibile",
         [x.get("datore") for x in posta.annunci_da_avviso(_html_ca, ["infermier"], {}, "infermiere/a presso CITTA' AZZURRA SOC. COOP. BOLZANO")],
         ["Città Azzurra Soc. Coop. Bolzano"])
# 22/11 sera: nell'app la novità si leggeva «infermiere/a», minuscolo come nel link di Indeed.
verifica("avvisi dei portali: il titolo comincia con la maiuscola",
         [x["titolo"] for x in posta.annunci_da_avviso(_html_ca, ["infermier"], {}, "")], ["Infermiere/a"])
# 24/11: unica novità del giorno «INFERMIERE M/F» di «Cerba Healthcare Corporate Servicelab S.R.L» (il punto finale della sigla tolto).
_html_cb = ("<table><tr><td><a href='https://cts.indeed.com/v3/abc'>INFERMIERE M/F</a>"
            "<div>CERBA HEALTHCARE CORPORATE SERVICELAB S.R.L.</div><div>Provincia di Trento, Trentino-Alto Adige</div></td></tr></table>")
_cb_av = posta.annunci_da_avviso(_html_cb, ["infermier"], {}, "INFERMIERE M/F presso CERBA HEALTHCARE CORPORATE SERVICELAB S.R.L.")
verifica("avvisi dei portali: titolo in maiuscolo leggibile, sigle intatte", [(x["titolo"], x.get("datore")) for x in _cb_av],
         [("Infermiere M/F", "Cerba Healthcare Corporate Servicelab S.R.L.")])
verifica("avvisi dei portali: titoli in maiuscolo di una parola o con (m/w/d)",
         [x["titolo"] for x in posta.annunci_da_avviso("<a href='https://it.indeed.com/x'>INFERMIERE</a><a href='https://it.indeed.com/y'>KRANKENPFLEGER (M/W/D)</a>",
                                                       ["infermier", "krankenpfleg"], {})], ["Infermiere", "Krankenpfleger (M/W/D)"])
verifica("nome leggibile: nomi già scritti bene restano uguali",
         [estrai.nome_leggibile(x) for x in ("Coop SOS", "ParaMedica srl", "INPS", None)], ["Coop SOS", "ParaMedica srl", "INPS", None])

# 22/11: INPS Bolzano aveva la PEC «direzione.provinciale.bolzano@postacert.i» (presa dal PDF, dove l'indirizzo
# va a capo); poco più avanti lo stesso PDF la scrive intera. Una PEC monca porterebbe una lettera nel vuoto.
verifica("email: indirizzo spezzato a capo, vale quello intero",
         estrai.trova_email("a mezzo PEC all'indirizzo direzione.provinciale.bolzano@postacert.i nps.gov.it. "
                            "Inviare a direzione.provinciale.bolzano@postacert.inps.gov.it entro il 26/12."),
         {"email": None, "pec": "direzione.provinciale.bolzano@postacert.inps.gov.it"})
verifica("email: indirizzo spezzato e mai scritto intero, meglio nessuno",
         estrai.trova_email("PEC: direzione.provinciale.bolzano@postacert.i nps.gov.it"), {"email": None, "pec": None})

# 23/11: nelle risposte vere resta il messaggio di Michael citato sotto, con intestazioni che la regola non
# riconosceva: «Il giorno … Michael Panico <» spezzata su due righe (Città Azzurra), «From:» di Outlook (Chiesa
# Serena), «Da "Michael Panico"» senza due punti (Borgo), la lettera incollata senza intestazione (Casa Laner).
verifica("posta: citazione con intestazione su due righe",
         posta.taglia_citazione("Può inviarci un CV?\n\nIl giorno dom 22 nov 2026 alle ore 15:51 Michael Panico <\ninfermiere@x.it> ha scritto:\n\nSono disponibile da subito."),
         "Può inviarci un CV?")
verifica("posta: citazione di Outlook «From:» e «Da \"…\"»",
         [posta.taglia_citazione(t) for t in ("Domani alle 10?\n________________________________\nFrom: Michael Panico <a@x.it>\nSent: …",
                                             "Saluti\n\nDa \"Michael Panico\" a@x.it\n\nA b@x.it\n\nSarei disponibile martedì")],
         ["Domani alle 10?", "Saluti"])
verifica("posta: la lettera di Michael incollata sotto senza intestazione",
         posta.taglia_citazione("Le chiediamo di compilare il modulo.\nCordiali saluti\nBuongiorno,\n\nmi chiamo Michael Panico e sono un infermiere iscritto all'OPI."),
         "Le chiediamo di compilare il modulo.\nCordiali saluti")
# 23/11: Città Azzurra chiedeva solo il CV, ma la lettura dava «libera professione» (dalla firma
# «C.F./P.Iva/St.Nr./MwSt – 01493930216») e «da subito» (dalla nota legale «cancellare il messaggio subito dopo»).
_citta_azzurra = ("Gentile sig. Panico,\npuò inviarci gentilmente un CV per valutare un possibile colloquio\nconoscitivo?\nCordiali saluti\n\n"
                  "Soc. Coop. Città Azzurra\n*C.F./P.Iva/St.Nr./MwSt – 01493930216 *\n\n"
                  "Questo documento è indirizzato esclusivamente al destinatario. Tutte le\ninformazioni sono soggette a\nriservatezza secondo i termini del D.Lgs. 196/2003. "
                  "Se avesse ricevuto per errore questo messaggio, La\npreghiamo di contattare il mittente e di\ncancellare il messaggio subito dopo.\n\n"
                  "Wer diese Mitteilung irrtuemlicherweise erhaelt ist\ngebeten uns umgehend zu informieren")
verifica("resoconto: firma e nota legale non dicono rapporto né data",
         {k: invio.leggi_esito(_citta_azzurra)[k] for k in ("esito", "rapporto", "da_quando")},
         {"esito": "sì", "rapporto": None, "da_quando": None})
verifica("resoconto: «da subito» detto davvero resta",
         invio.leggi_esito("Cerchiamo infermieri in libera professione da subito.\n\nLe informazioni contenute in questo messaggio sono riservate.")["da_quando"], "da subito")

# 23/11: l'avviso Indeed di IQVIA diceva solo «Provincia di Trento, Trentino-Alto Adige»: nell'app «Zona non
# riconosciuta», come se potesse essere fuori regione. Il comune resta n.d. (niente minuti inventati), ma si dice la provincia.
_iq = motore._costruisci({"titolo": "IQVIA Italia Infermiere per attività domiciliari", "url": "https://cts.indeed.com/v3/x",
                          "sommario": "IQVIA Italia Infermiere per attività domiciliari IQVIA Solutions Italy srl Provincia di Trento, Trentino-Alto Adige"},
                         "", None, _fa, CFG, COMUNI, OGGI, [])[0]
verifica("zona: solo la provincia, comune n.d.", (_iq["zona"], [x for x in _iq["avvisi"] if "ona" in x]),
         (None, ["Zona: provincia di Trento, comune non indicato"]))

# 24/11: per Cerba (Indeed, «Provincia di Trento») l'email diceva «zona n.d.» e l'app «zona n.d.», anche se
# l'avviso nella scheda diceva già la provincia: si perdeva l'informazione proprio nel riassunto che Michael legge.
_rg = motore._riga({**_iq, "punteggio": 26})
verifica("email: la provincia al posto di «zona n.d.»", uscite._dettagli(_rg),
         "contratto n.d., compenso n.d., provincia di Trento (comune n.d.)")
verifica("provincia: solo se manca il comune", (motore.provincia_senza_comune(_iq),
         motore.provincia_senza_comune({**_iq, "zona": "Trento"}), motore.provincia_senza_comune({"avvisi": []})), ("Trento", None, None))
print("\n" + ("TUTTO OK" if not errori else f"{len(errori)} PROVE FALLITE: {errori}"))
sys.exit(1 if errori else 0)
