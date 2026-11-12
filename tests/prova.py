"""Prove offline: nessuna connessione, pagine finte.  Avvio:  python tests/prova.py"""
import sys, tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yaml
from radar import estrai, motore, punteggio, uscite

OGGI = date(2026, 11, 12)
RADICE = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((RADICE / "config.yaml").read_text(encoding="utf-8"))
COMUNI = estrai.carica_comuni(RADICE / "data" / "comuni.csv")
errori = []

def verifica(nome, ottenuto, atteso):
    ok = ottenuto == atteso
    print(("  ok  " if ok else "  NO  ") + nome + ("" if ok else f"\n        ottenuto: {ottenuto!r}\n        atteso:   {atteso!r}"))
    if not ok:
        errori.append(nome)

print("Estrazione dei campi")
t = ("L'APSP indice un avviso pubblico di selezione per il conferimento di incarichi libero-professionali "
     "di infermiere. Scadenza originaria 06/11/2026, PROROGATA al 27 novembre 2026 ore 12:00. "
     "Compenso orario lordo omnicomprensivo di € 40,00. Turni anche notturni e festivi.")
c = estrai.estrai_campi("A.P.S.P. C. Vannetti – Rovereto – Selezione per liberi professionisti", t, COMUNI, OGGI, CFG["parole"]["infermiere"])
verifica("contratto P.IVA", c["contratto"], "P.IVA / libera professione")
verifica("scadenza prorogata", c["scadenza"], "2026-11-27")
verifica("compenso orario", (c["compenso"], c["euro_ora"]), ("40 €/h", 40.0))
verifica("zona dal titolo", (c["zona"], c["minuti"]), ("Rovereto", 40))
verifica("datore dal titolo", c["datore"], "A.P.S.P. C. Vannetti")
verifica("turni", c["turni"], "notti, weekend/festivi")

c = estrai.estrai_campi("Freiberufliche Tätigkeit in der Pflege",
    "Wir suchen Krankenpfleger für Nachtdienste und Wochenenden in Wiesen. Zweisprachigkeit erwünscht. 35 Euro pro Stunde.",
    COMUNI, OGGI, CFG["parole"]["infermiere"])
verifica("tedesco: contratto", c["contratto"], "P.IVA / libera professione")
verifica("tedesco: zona con alias", c["zona"], "Vipiteno")
verifica("tedesco: compenso", c["euro_ora"], 35.0)
verifica("tedesco: bilinguismo citato", c["cita_tedesco"], True)

c = estrai.estrai_campi("Concorso pubblico per infermieri", "Bando di concorso per 10 posti a tempo indeterminato. Domande entro il 13/11/2026. Stipendio 1.900 € netti al mese.", COMUNI, OGGI, CFG["parole"]["infermiere"])
verifica("concorso", c["contratto"], "Concorso / graduatoria")
verifica("scadenza 'entro il'", c["scadenza"], "2026-11-13")
verifica("compenso mensile senza €/h", (c["compenso"], c["euro_ora"]), ("1.900 € netti al mese", None))
verifica("zona non trovata resta vuota", c["zona"], None)

c = estrai.estrai_campi("Cercasi infermiere", "Cerchiamo un infermiere.", COMUNI, OGGI, CFG["parole"]["infermiere"])
verifica("niente inventato", (c["contratto"], c["compenso"], c["scadenza"], c["turni"], c["zona"]), (None,) * 5)
verifica("'ora' non è un compenso", estrai.estrai_compenso("Per ora servono 2 infermieri, 36 ore a settimana")[1], None)
verifica("nome ambiguo ignorato", estrai.trova_comune("Infermiere", "Selezione chiusa. Chiusa la graduatoria.", COMUNI), None)

print("Punteggio")
a = {"contratto": "P.IVA / libera professione", "euro_ora": 40.0, "minuti": 15, "segnali_turni": {"dodici": True, "notti": True, "weekend": True}, "affidabilita": "ufficiale"}
verifica("massimo = 100", punteggio.calcola(a, CFG)[0], 100)
a = {"contratto": "Dipendente a tempo determinato", "euro_ora": None, "minuti": 120, "segnali_turni": {}, "affidabilita": "aggregatore"}
verifica("dipendente lontano = basso", punteggio.calcola(a, CFG)[0], 5 + 5 + 0 + 5 + 3)

print("Feed e link")
feed = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title type="html">&lt;b&gt;Infermiere&lt;/b&gt; partita IVA Trento</title>
<link href="https://www.google.com/url?rct=j&amp;sa=t&amp;url=https://esempio.it/annuncio-1&amp;ct=ga"/>
<published>2026-11-11T08:00:00Z</published><content type="html">Cercasi infermiere a Trento con P.IVA</content></entry></feed>"""
v = estrai.leggi_feed(feed)
verifica("feed Google Alerts", (v[0]["url"], v[0]["titolo"], str(v[0]["pubblicato"])), ("https://esempio.it/annuncio-1", "Infermiere partita IVA Trento", "2026-11-11"))

ELENCO = """<html><body><nav><a href="/chi-siamo/">Chi siamo e contatti dell'ente</a></nav><main>
<a href="/apsp-vannetti-lp/">A.P.S.P. C. Vannetti – Rovereto – Selezione per liberi professionisti</a>
<a href="/casa-cura-eremo/">Casa di cura Eremo – Arco – ricerca personale</a>
<a href="/bando.pdf">Bando di concorso per infermieri in formato PDF</a>
<a href="/privacy/">Informativa sulla privacy del sito</a></main></body></html>"""
l = estrai.link_da_elenco(ELENCO, "https://ente.it/annunci/", CFG["parole"]["link"], tutti=True)
verifica("link dell'elenco (menu e privacy esclusi)", [x["url"] for x in l], ["https://ente.it/apsp-vannetti-lp/", "https://ente.it/casa-cura-eremo/", "https://ente.it/bando.pdf"])

print("Giro completo su due giorni (rete finta)")
class ReteFinta:
    def __init__(self, pagine): self.pagine = pagine
    def get(self, url, robots=True):
        return (self.pagine[url], None) if url in self.pagine else (None, "risposta HTTP 404")

def art(t, corpo): return f"<html><head><title>x</title></head><body><article><h1>{t}</h1><p>{corpo}</p></article><footer>Ordine di Trento</footer></body></html>"
RIEMP = " Requisiti: laurea in infermieristica e iscrizione all'albo. " * 4
pagine = {
    "https://ente.it/annunci/": ELENCO,
    "https://ente.it/apsp-vannetti-lp/": art("A.P.S.P. C. Vannetti – Rovereto – Selezione per liberi professionisti", "Incarichi libero-professionali di infermiere. Scadenza 06/11/2026 prorogata al 20/11/2026." + RIEMP),
    "https://ente.it/casa-cura-eremo/": art("Casa di cura Eremo – Arco", "Cerchiamo personale infermieristico a tempo indeterminato, CCNL AIOP." + RIEMP),
    "https://clinica.it/lavora/": art("Lavora con noi", "Infermiere/a per assunzione o libera professione, turni da 12 ore." + RIEMP),
    "https://feed.it/a": feed,
}
cfg = dict(CFG)
cfg["fonti"] = [
    {"nome": "Ente", "tipo": "elenco", "url": "https://ente.it/annunci/", "affidabilita": "ufficiale", "tutti_i_link": True},
    {"nome": "Clinica", "tipo": "pagina", "url": "https://clinica.it/lavora/", "affidabilita": "struttura", "datore": "Clinica X", "zona": "Merano"},
    {"nome": "Rotta", "tipo": "pagina", "url": "https://rotta.it/", "affidabilita": "struttura"},
]
cfg["feed_google_alerts"] = ["https://feed.it/a"]
tmp = Path(tempfile.mkdtemp())
motore.FILE_ANNUNCI, motore.FILE_FONTI, motore.CARTELLA_REPORT = tmp / "annunci.json", tmp / "fonti.json", tmp / "report"
muto = lambda *_: None
r1 = motore.giro(cfg, ReteFinta(pagine), OGGI, registra=muto)
verifica("giorno 1: annunci nuovi", len(r1["nuovi"]), 5)
verifica("giorno 1: primo in classifica", r1["top5"][0]["datore"], "A.P.S.P. C. Vannetti")
verifica("giorno 1: fonte rotta segnalata", r1["problemi"], ["Rotta: risposta HTTP 404"])
verifica("giorno 1: scadenza entro 7 giorni", [x["scadenza"] for x in r1["scadenze7"]], [])
mem = motore.leggi_json(motore.FILE_ANNUNCI, {})
pdf = next(a for a in mem.values() if a["url"].endswith(".pdf"))
verifica("PDF: dati n.d. e avviso", (pdf["contratto"] is not None, pdf["avvisi"][0][:15]), (True, "Annuncio in PDF"))

pagine2 = dict(pagine)
pagine2["https://ente.it/apsp-vannetti-lp/"] = pagine["https://ente.it/apsp-vannetti-lp/"].replace("20/11/2026", "18/11/2026")
pagine2["https://ente.it/annunci/"] = "<html><body><main><p>Sito in manutenzione</p></main></body></html>"
r2 = motore.giro(cfg, ReteFinta(pagine2), date(2026, 11, 13), registra=muto)
verifica("giorno 2: niente di nuovo", len(r2["nuovi"]), 0)
verifica("giorno 2: struttura cambiata segnalata", "cambiato struttura" in r2["problemi"][0], True)
pagine2["https://ente.it/annunci/"] = ELENCO
r3 = motore.giro(cfg, ReteFinta(pagine2), date(2026, 11, 14), registra=muto)
verifica("giorno 3: annuncio aggiornato", [x["cambi"] for x in r3["aggiornati"]], [["scadenza: 2026-11-20 → 2026-11-18"]])
verifica("giorno 3: scadenza vicina", [x["scadenza"] for x in r3["scadenze7"]], ["2026-11-18"])

ogg, testo, pag = uscite.componi_email(r3, "https://app.esempio")
verifica("oggetto email", ogg, "Radar infermiere 14/11: 1 scadenza vicina, 1 aggiornata")
r4 = motore.giro(cfg, ReteFinta({k: v for k, v in pagine2.items() if k != "x"}), date(2026, 11, 15), registra=muto)
cfg4 = dict(cfg); cfg4["fonti"] = cfg["fonti"][:2]
r5 = motore.giro(cfg4, ReteFinta(pagine2), date(2026, 11, 19), registra=muto)
ogg, testo, _ = uscite.componi_email(r5, None)
verifica("niente di nuovo = una riga", (ogg, "\n" in testo), ("Radar infermiere 19/11: niente di nuovo", False))
dest = uscite.costruisci_sito(cfg, date(2026, 11, 14), tmp / "dist")
verifica("web app costruita", (dest / "dati.json").exists() and (dest / "index.html").exists(), True)

print("\nEmail di esempio (giorno 3):\n" + testo if False else "")
print("\n" + ("TUTTO OK" if not errori else f"{len(errori)} PROVE FALLITE: {errori}"))
sys.exit(1 if errori else 0)
