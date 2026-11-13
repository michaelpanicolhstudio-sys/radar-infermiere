"""Lettura della posta (solo lo stretto necessario).

1. Nella posta inviata cerca le email di primo contatto partite dall'app: hanno nell'oggetto un codice «Rif. R-…».
2. Nella posta in arrivo cerca SOLO le risposte degli indirizzi contattati (o con quel codice nell'oggetto).
3. Legge gli avvisi di lavoro che i portali (Indeed, LinkedIn…) mandano per email, se in config sono indicati.

Serve la stessa password per le app di Gmail già usata per inviare il report. La PEC è facoltativa
(segreti PEC_USER, PEC_PASSWORD, PEC_IMAP_HOST).
"""
from __future__ import annotations

import email
import imaplib
import os
import re
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime

from bs4 import BeautifulSoup

from . import estrai

RE_RIF = re.compile(r"R-([0-9a-f]{6,12})", re.I)
_MESI_IMAP = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_POSTA_COMUNE = ("gmail.com", "googlemail.com", "libero.it", "hotmail.", "outlook.", "yahoo.", "icloud.com", "live.",
                 "virgilio.it", "alice.it", "tiscali.it", "pec.it", "legalmail.it", "postecert.it", "arubapec.it")
RE_INCONTRO = re.compile(r"colloqui\w*|incontr\w+|appuntament\w*|vederci|conoscerci|conoscerla|venire\s+(?:a\s+trovarci|in\s+struttura)|"
                         r"gespr[äa]ch\w*|termin\b|vorstellung\w*|kennenlernen|treffen", re.I)
RE_ORA = re.compile(r"(?:ore|alle|um|h\.?)\s*(\d{1,2})(?:[:.,](\d{2}))?|\b(\d{1,2})[:.](\d{2})\s*(?:uhr)?", re.I)


def rif(id_annuncio: str) -> str:
    return "R-" + id_annuncio[:8]


def conti_di_posta() -> list[dict]:
    conti = []
    utente, chiave = os.environ.get("GMAIL_USER", "").strip(), os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if utente and chiave:
        conti.append({"nome": "gmail", "host": "imap.gmail.com", "utente": utente, "chiave": chiave})
    utente, chiave, host = (os.environ.get(k, "").strip() for k in ("PEC_USER", "PEC_PASSWORD", "PEC_IMAP_HOST"))
    if utente and chiave and host:
        conti.append({"nome": "pec", "host": host, "utente": utente, "chiave": chiave})
    return conti


def _data_imap(d: date) -> str:
    return f"{d.day:02d}-{_MESI_IMAP[d.month - 1]}-{d.year}"


def _intestazione(valore) -> str:
    try:
        return str(make_header(decode_header(valore or "")))
    except Exception:
        return str(valore or "")


def testo_messaggio(msg) -> tuple[str, str]:
    """(testo leggibile senza la parte citata, HTML se c'è)."""
    semplice, pagina = "", ""
    for parte in (msg.walk() if msg.is_multipart() else [msg]):
        if parte.get_content_maintype() != "text" or parte.get_filename():
            continue
        try:
            contenuto = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if parte.get_content_subtype() == "plain" and not semplice:
            semplice = contenuto
        elif parte.get_content_subtype() == "html" and not pagina:
            pagina = contenuto
    testo = semplice or BeautifulSoup(pagina, "html.parser").get_text("\n")
    return taglia_citazione(testo), pagina


def taglia_citazione(testo: str) -> str:
    """Tiene la risposta e toglie il messaggio originale citato sotto."""
    righe = []
    for riga in testo.replace("\r", "").split("\n"):
        pulita = riga.strip()
        if pulita.startswith(">") or re.match(r"^(?:Il\s.{4,90}ha scritto:|Am\s.{4,90}schrieb.*:|On\s.{4,90}wrote:|-{3,}\s*(?:Messaggio originale|Original)|Da:\s.+|Von:\s.+)", pulita, re.I):
            break
        righe.append(riga)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(righe)).strip()


def trova_incontro(testo: str, oggi: date) -> dict | None:
    """Se la risposta propone un incontro con una data, la restituisce (con l'ora, se c'è)."""
    for m in RE_INCONTRO.finditer(testo):
        finestra = testo[max(0, m.start() - 60): m.end() + 160]
        d = estrai.RE_DATA.search(finestra)
        if not d:
            continue
        giorno = estrai._data_da_match(d)
        if not giorno or not (0 <= (giorno - oggi).days <= 120):
            continue
        ora = None
        o = RE_ORA.search(finestra[d.end():]) or RE_ORA.search(finestra[:d.start()])
        if o:
            h, minuti = int(o.group(1) or o.group(3)), int(o.group(2) or o.group(4) or 0)
            if 6 <= h <= 21 and minuti < 60:
                ora = f"{h:02d}:{minuti:02d}"
        return {"data": giorno.isoformat(), "ora": ora, "frase": estrai.pulisci(finestra)[:200]}
    return None


def leggi_risposta(msg, oggi: date) -> dict:
    testo, _ = testo_messaggio(msg)
    try:
        quando = parsedate_to_datetime(msg.get("Date")).date().isoformat()
    except Exception:
        quando = oggi.isoformat()
    compenso, euro_ora = estrai.estrai_compenso(testo)
    turni, _ = estrai.estrai_turni(testo)
    return {"mid": (msg.get("Message-ID") or "").strip(), "data": quando,
            "da": (getaddresses([_intestazione(msg.get("From"))]) or [("", "")])[0][1].lower(),
            "oggetto": _intestazione(msg.get("Subject"))[:160], "testo": testo[:4000],
            "compenso": compenso, "euro_ora": euro_ora, "turni": turni, "incontro": trova_incontro(testo, oggi)}


def _cartella_inviati(M) -> str | None:
    esito, righe = M.list()
    for riga in righe or []:
        s = riga.decode("utf-8", errors="replace")
        if "\\Sent" in s:
            return s.rsplit(' "', 1)[-1].strip('"') if s.endswith('"') else s.rsplit(" ", 1)[-1]
    for nome in ("Sent", "INBOX.Sent", "Posta inviata", "INBOX.Posta inviata"):
        if M.select(f'"{nome}"', readonly=True)[0] == "OK":
            return nome
    return None


def _messaggi(M, criteri: list[str], massimo: int = 40):
    esito, dati = M.search(None, *criteri)
    if esito != "OK" or not dati or not dati[0]:
        return
    for numero in dati[0].split()[-massimo:]:
        esito, pezzi = M.fetch(numero, "(BODY.PEEK[])")
        if esito == "OK" and pezzi and isinstance(pezzi[0], tuple):
            yield email.message_from_bytes(pezzi[0][1])


def aggiorna_contatti(contatti: dict, chiavi: dict[str, str], oggi: date, registra=print) -> list[dict]:
    """Aggiorna contatti = {chiave: {inviata_il, a, via, risposte}}. chiavi: codice «R-…» -> chiave.
    Ritorna le risposte nuove di questo giro."""
    nuove = []
    dal = _data_imap(oggi - timedelta(days=90))
    for conto in conti_di_posta():
        try:
            M = imaplib.IMAP4_SSL(conto["host"], 993, timeout=40)
            M.login(conto["utente"], conto["chiave"])
        except Exception as e:
            registra(f"⚠ Posta {conto['nome']}: accesso non riuscito ({type(e).__name__}). "
                     "Per Gmail controlla che IMAP sia attivo nelle impostazioni.")
            continue
        try:
            inviati = _cartella_inviati(M)
            if inviati and M.select(f'"{inviati}"', readonly=True)[0] == "OK":
                for msg in _messaggi(M, ["SINCE", dal, "SUBJECT", '"Rif. R-"'], 200):
                    m = RE_RIF.search(_intestazione(msg.get("Subject")))
                    chiave = chiavi.get("R-" + m.group(1).lower()) if m else None
                    if not chiave:
                        continue
                    indirizzi = [x[1].lower() for x in getaddresses(msg.get_all("To", []) + msg.get_all("Cc", [])) if "@" in x[1]]
                    try:
                        quando = parsedate_to_datetime(msg.get("Date")).date().isoformat()
                    except Exception:
                        quando = oggi.isoformat()
                    voce = contatti.setdefault(chiave, {"risposte": []})
                    voce.setdefault("inviata_il", quando)
                    voce["via"] = conto["nome"]
                    voce["a"] = sorted(set(voce.get("a", [])) | set(indirizzi))
                    voce["rif"] = "R-" + m.group(1).lower()
            if M.select("INBOX", readonly=True)[0] != "OK":
                continue
            for chiave, voce in contatti.items():
                if not voce.get("inviata_il"):
                    continue
                dopo = _data_imap(date.fromisoformat(voce["inviata_il"]))
                ricerche = [["SINCE", dopo, "SUBJECT", f'"{voce["rif"]}"']] if voce.get("rif") else []
                for indirizzo in voce.get("a", []):
                    ricerche.append(["SINCE", dopo, "FROM", f'"{indirizzo}"'])
                    dominio = indirizzo.split("@")[-1]
                    if not any(x in dominio for x in _POSTA_COMUNE):
                        ricerche.append(["SINCE", dopo, "FROM", f'"@{dominio}"'])
                gia = {r.get("mid") for r in voce.get("risposte", [])}
                for criteri in ricerche:
                    for msg in _messaggi(M, criteri, 10):
                        risposta = leggi_risposta(msg, oggi)
                        if risposta["mid"] in gia or risposta["da"] == conto["utente"].lower():
                            continue
                        gia.add(risposta["mid"])
                        voce.setdefault("risposte", []).append(risposta)
                        nuove.append({"chiave": chiave, **risposta})
        except Exception as e:
            registra(f"⚠ Posta {conto['nome']}: lettura interrotta ({type(e).__name__}: {e})")
        finally:
            try:
                M.logout()
            except Exception:
                pass
    return nuove


def annunci_da_avviso(pagina: str, parole: list[str]) -> list[dict]:
    """Dall'email di un portale (Indeed, LinkedIn…) prende i link agli annunci per infermieri."""
    soup = BeautifulSoup(pagina, "html.parser")
    trovati, visti = [], set()
    for a in soup.find_all("a", href=True):
        titolo = estrai.pulisci(a.get_text(" "))
        if not (8 <= len(titolo) <= 140) or not estrai.contiene(titolo, parole) or not a["href"].startswith("http"):
            continue
        blocco = a
        for _ in range(4):
            if blocco.parent is None or len(estrai.pulisci(blocco.parent.get_text(" "))) > 400:
                break
            blocco = blocco.parent
        intorno = estrai.pulisci(blocco.get_text(" "))
        chiave = estrai.chiave(intorno[:120])
        if chiave in visti:
            continue
        visti.add(chiave)
        trovati.append({"titolo": titolo, "url": a["href"], "sommario": intorno[:400]})
    return trovati


def avvisi_portali(cfg: dict, oggi: date, registra=print) -> dict[str, list[dict]]:
    """{nome del portale: [candidati]} dagli avvisi arrivati negli ultimi giorni."""
    mittenti = (cfg.get("posta") or {}).get("avvisi_da") or {}
    conto = next((c for c in conti_di_posta() if c["nome"] == "gmail"), None)
    if not mittenti or not conto:
        return {}
    risultati: dict[str, list[dict]] = {}
    try:
        M = imaplib.IMAP4_SSL(conto["host"], 993, timeout=40)
        M.login(conto["utente"], conto["chiave"])
        M.select("INBOX", readonly=True)
        dal = _data_imap(oggi - timedelta(days=int((cfg.get("posta") or {}).get("giorni_avvisi", 3))))
        for nome, mittente in mittenti.items():
            candidati = []
            for msg in _messaggi(M, ["SINCE", dal, "FROM", f'"{mittente}"'], 15):
                _, pagina = testo_messaggio(msg)
                try:
                    quando = parsedate_to_datetime(msg.get("Date")).date()
                except Exception:
                    quando = oggi
                for c in annunci_da_avviso(pagina, cfg["parole"]["infermiere"]):
                    candidati.append({**c, "pubblicato": quando, "id": estrai.id_annuncio("avviso:" + estrai.chiave(c["sommario"][:120]))})
            risultati[nome] = candidati
        M.logout()
    except Exception as e:
        registra(f"⚠ Avvisi dei portali: lettura non riuscita ({type(e).__name__})")
    return risultati
