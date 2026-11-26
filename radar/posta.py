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
from urllib.parse import parse_qsl, urlencode, urlparse

from bs4 import BeautifulSoup

from . import estrai

DIAGNOSTICA_AVVISI: dict[str, dict] = {}   # per la messa a punto: email lette, link scartati, esempi
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
    righe = testo.replace("\r", "").split("\n")
    tenute = []
    for i, riga in enumerate(righe):
        pulita = riga.strip()
        # L'intestazione può andare a capo: «Il giorno … Michael Panico <» / «indirizzo> ha scritto:» (Città Azzurra, 23/11).
        con_dopo = f"{pulita} {righe[i + 1].strip()}" if i + 1 < len(righe) else pulita
        if (pulita.startswith(">")
                or re.match(r"^(?:Il\s.{4,90}ha scritto:|Am\s.{4,90}schrieb.*:|On\s.{4,90}wrote:|-{3,}\s*(?:Messaggio originale|Original)|"
                            r"(?:Da|Von|From):\s.+|Da\s+\"[^\"]+\")", pulita, re.I)
                or re.match(r"^(?:Il|Am|On)\s.{4,160}(?:ha scritto|schrieb|wrote)\s*:", con_dopo, re.I)
                # La lettera di Michael incollata sotto senza intestazione (Casa Laner, 23/11).
                or re.match(r"^(?:mi chiamo|mein name ist)\s+michael\s+panico", pulita, re.I)):
            break
        tenute.append(riga)
    # Il saluto iniziale della lettera citata e la riga «______» di Outlook prima dell'intestazione.
    while tenute and (not tenute[-1].strip() or re.fullmatch(r"\s*(?:_{5,}|-{5,}|Buongiorno,?|Sehr geehrte.*|Gentil\w*\s.*,)\s*", tenute[-1], re.I)):
        if tenute[-1].strip() and len(tenute) == 1:
            break
        tenute.pop()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(tenute)).strip()


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


def _cartella_speciale(M, segno: str) -> str | None:
    """Nome della cartella con un attributo speciale IMAP (\\Sent, \\All…), qualunque sia la lingua di Gmail."""
    esito, righe = M.list()
    for riga in righe or []:
        s = riga.decode("utf-8", errors="replace")
        if segno in s:
            return s.rsplit(' "', 1)[-1].strip('"') if s.endswith('"') else s.rsplit(" ", 1)[-1]
    return None


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
            # Si cerca in «Tutti i messaggi» (Gmail): una risposta archiviata, finita in una scheda o con un'etichetta
            # non sta più in Posta in arrivo. Se la cartella non c'è si usa la Posta in arrivo.
            tutti = _cartella_speciale(M, "\\All")
            if not (tutti and M.select(f'"{tutti}"', readonly=True)[0] == "OK") and M.select("INBOX", readonly=True)[0] != "OK":
                continue
            for chiave, voce in contatti.items():
                if not voce.get("inviata_il"):
                    continue
                dopo = _data_imap(date.fromisoformat(voce["inviata_il"]))
                # Codice nell'oggetto o nel testo citato: così si trova anche chi risponde da un altro indirizzo.
                ricerche = [["SINCE", dopo, "SUBJECT", f'"{voce["rif"]}"'], ["SINCE", dopo, "TEXT", f'"{voce["rif"]}"']] if voce.get("rif") else []
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


PAROLE_PORTALI = ["nurse", "krankenschwester", "pflegerin", "pfleger/in", "pflegefachfrau", "pflegefachmann", "oss/infermier"]
_RE_RUMORE_LINK = re.compile(r"annulla|unsubscribe|abmelden|impostazioni|settings|privacy|condizioni|termini|"
                             r"vedi tutti|see all|alle anzeigen|scarica l'app|download|aiuto|help|accedi|log ?in", re.I)


# Conferme di candidatura (Indeed «Candidatura inviata», link apply.indeed.com/indeedapply, 26/11): non sono annunci.
_RE_CONFERMA = re.compile(r"candidatura\s+(?:inviata|completata|ricevuta)|application\s+submitted|bewerbung\s+(?:gesendet|eingegangen)", re.I)
_RE_URL_CONFERMA = re.compile(r"/indeedapply/|confirmemail", re.I)


def _url_pulito(url: str) -> str:
    """Toglie i parametri di tracciamento più comuni, tenendo quelli che identificano l'annuncio (jk, id…)."""
    p = urlparse(url)
    tieni = [(k, v) for k, v in parse_qsl(p.query) if not re.match(r"utm_|trk|refId|trackingId|from|tk$|alid|ref$", k, re.I)]
    return p._replace(query=urlencode(tieni), fragment="").geturl()


_RE_PRESSO = re.compile(r"^(.{8,140}?)\s+(?:presso|bei|at)\s+(.{2,80})$", re.I)


def _datore_da_oggetto(oggetto: str, titolo: str, sommario: str) -> str | None:
    """Indeed manda un'email per annuncio con oggetto «<titolo> presso <datore>» (21/11: Coop SOS).
    Vale solo se il titolo è proprio quello del link e il datore compare nel riassunto subito dopo il titolo."""
    m = _RE_PRESSO.match(estrai.pulisci(oggetto or ""))
    if not m or estrai.chiave(m.group(1)) != estrai.chiave(titolo):
        return None
    datore = m.group(2).strip(" !-–")
    if not re.search(r"\b[A-Za-z]\.(?:[A-Za-z]\.?)+$", datore):
        datore = datore.rstrip(" .")  # il punto finale di una sigla resta («S.R.L.», 24/11)
    resto = sommario[len(titolo):] if sommario.lower().startswith(titolo.lower()) else ""
    if not datore or not resto.strip().lower().startswith(datore.lower()):
        return None
    return estrai.nome_leggibile(datore)  # «CITTA' AZZURRA SOC. COOP.» → «Città Azzurra Soc. Coop.» (22/11)


def annunci_da_avviso(pagina: str, parole: list[str], note: dict | None = None, oggetto: str = "") -> list[dict]:
    """Dall'email di un portale (Indeed, LinkedIn…) prende i link agli annunci per infermieri,
    con il blocco di testo intorno (struttura, luogo, compenso) da cui il Radar estrae i dati."""
    soup = BeautifulSoup(pagina, "html.parser")
    parole = list(parole) + PAROLE_PORTALI
    trovati, visti = [], set()
    for a in soup.find_all("a", href=True):
        titolo = estrai.pulisci(a.get_text(" "))
        if not a["href"].startswith("http") or not (8 <= len(titolo) <= 140) or _RE_RUMORE_LINK.search(titolo):
            continue
        if not estrai.contiene(titolo, parole):
            if note is not None and len(note.setdefault("altri_link", [])) < 12:
                note["altri_link"].append(titolo[:80])
            continue
        blocco = a
        for _ in range(5):
            su = blocco.parent
            if su is None or len(estrai.pulisci(su.get_text(" "))) > 450:
                break
            # il blocco di un annuncio non deve inglobare gli altri annunci dell'email
            altri = [x for x in su.find_all("a", href=True) if x is not a and estrai.contiene(estrai.pulisci(x.get_text(" ")), parole)]
            if altri:
                break
            blocco = su
        intorno = estrai.pulisci(blocco.get_text(" "))
        if _RE_URL_CONFERMA.search(a["href"]) or _RE_CONFERMA.search(intorno[:200]):
            if note is not None:
                note.setdefault("conferme", []).append(titolo[:80])
            continue
        chiave = estrai.chiave(intorno[:160])
        if chiave in visti:
            continue
        visti.add(chiave)
        titolo = estrai.titolo_leggibile_maiuscolo(titolo)
        if titolo[:1].islower():
            titolo = titolo[:1].upper() + titolo[1:]  # «infermiere/a» del link → «Infermiere/a» (22/11)
        voce = {"titolo": titolo, "url": _url_pulito(a["href"]), "sommario": intorno[:450]}
        datore = _datore_da_oggetto(oggetto, titolo, intorno)
        if datore:
            voce["datore"] = datore
        trovati.append(voce)
    return trovati


RE_URL = re.compile(r"https?://[^\s<>\"')\]]+")
_RE_URL_INUTILE = re.compile(r"apple\.com|icloud\.com|google\.com/maps|mailto:|\.(?:png|jpe?g|gif)(?:\?|$)", re.I)


def annunci_segnalati(msg) -> list[dict]:
    """Email mandata da Michael all'indirizzo «+radar»: ogni link è un annuncio da seguire.
    Titolo dalla riga del link o dall'oggetto; il testo dell'email fa da riassunto (struttura, luogo, compenso)."""
    testo, pagina = testo_messaggio(msg)
    oggetto = _intestazione(msg.get("Subject")).strip()
    if pagina and len(testo) < 30:
        testo = BeautifulSoup(pagina, "html.parser").get_text("\n")
    righe = [r.strip() for r in testo.replace("\r", "").split("\n")]
    trovati, visti = [], set()
    for i, riga in enumerate(righe):
        for m in RE_URL.finditer(riga):
            url = m.group(0).rstrip(".,;")
            if _RE_URL_INUTILE.search(url) or url in visti:
                continue
            visti.add(url)
            prima = riga[: m.start()].strip(" :-–") or next((r for r in reversed(righe[max(0, i - 3):i]) if r and not RE_URL.search(r)), "")
            titolo = estrai.pulisci(prima) if 8 <= len(estrai.pulisci(prima)) <= 140 else ""
            titolo = titolo or re.sub(r"^(?:fwd?|i|r|re|wg)\s*:\s*", "", oggetto, flags=re.I) or "Annuncio segnalato"
            vicino = " ".join(r for r in righe[max(0, i - 4): i + 5] if r)
            trovati.append({"titolo": titolo[:140], "url": _url_pulito(url),
                            "sommario": estrai.pulisci(f"{oggetto} {vicino}")[:600]})
    return trovati


def oggetto_avviso(msg) -> str:
    """Oggetto leggibile di un'email di un portale, per la diagnostica (avviso con annunci o sola conferma?)."""
    return estrai.pulisci(_intestazione(msg.get("Subject")))[:100]


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
        # «Tutti i messaggi»: così gli avvisi si trovano anche se un filtro di Gmail li archivia o li etichetta.
        tutti = _cartella_speciale(M, "\\All")
        if not (tutti and M.select(f'"{tutti}"', readonly=True)[0] == "OK"):
            M.select("INBOX", readonly=True)
        dal = _data_imap(oggi - timedelta(days=int((cfg.get("posta") or {}).get("giorni_avvisi", 3))))
        for nome, mittente in mittenti.items():
            candidati, note = [], {"email": 0}
            for msg in _messaggi(M, ["SINCE", dal, "FROM", f'"{mittente}"'], 15):
                note["email"] += 1
                if len(note.setdefault("oggetti", [])) < 5:
                    note["oggetti"].append(oggetto_avviso(msg))
                _, pagina = testo_messaggio(msg)
                try:
                    quando = parsedate_to_datetime(msg.get("Date")).date()
                except Exception:
                    quando = oggi
                for c in annunci_da_avviso(pagina, cfg["parole"]["infermiere"], note, estrai.pulisci(_intestazione(msg.get("Subject")))):
                    candidati.append({**c, "pubblicato": quando, "id": estrai.id_annuncio("avviso:" + estrai.chiave(c["sommario"][:120]))})
            risultati[nome] = candidati
            DIAGNOSTICA_AVVISI[nome] = {**note, "annunci": len(candidati), "esempi": [c["sommario"][:200] for c in candidati[:3]]}
        # Annunci segnalati da Michael: email all'indirizzo «nome+radar@gmail.com» (arrivano nella stessa casella).
        locale, dominio = conto["utente"].split("@", 1)
        segnalati, gia = [], set()
        for msg in _messaggi(M, ["SINCE", _data_imap(oggi - timedelta(days=int((cfg.get("posta") or {}).get("giorni_segnalati", 30)))),
                                 "TO", f'"{locale}+radar@{dominio}"'], 60):
            mid = (msg.get("Message-ID") or "").strip()
            if mid in gia:
                continue
            gia.add(mid)
            try:
                quando = parsedate_to_datetime(msg.get("Date")).date()
            except Exception:
                quando = oggi
            for c in annunci_segnalati(msg):
                segnalati.append({**c, "pubblicato": quando, "id": estrai.id_annuncio("segnalato:" + c["url"])})
        if segnalati:
            risultati["Segnalati da Michael"] = segnalati
        DIAGNOSTICA_AVVISI["Segnalati da Michael"] = {"email": len(gia), "annunci": len(segnalati),
                                                       "esempi": [s_["titolo"] for s_ in segnalati[:5]]}
        M.logout()
    except Exception as e:
        registra(f"⚠ Avvisi dei portali: lettura non riuscita ({type(e).__name__})")
    return risultati
