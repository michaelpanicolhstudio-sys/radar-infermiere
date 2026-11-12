"""Estrazione dei dati dagli annunci: funzioni pure, senza rete.

Regola d'oro: se un dato non si trova, resta None e viene mostrato come "n.d.".
Niente viene inventato.
"""
from __future__ import annotations

import csv
import hashlib
import html as html_mod
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Utilità
# --------------------------------------------------------------------------

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    "januar": 1, "jänner": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}
_RE_DATA_NUM = r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4}|\d{2})(?!\d)"
_RE_DATA_MESE = r"(\d{1,2})\.?\s*°?\s+(" + "|".join(MESI) + r")\s+(\d{4})"
RE_DATA = re.compile(_RE_DATA_NUM + "|" + _RE_DATA_MESE, re.I)


def pulisci(testo: str) -> str:
    return re.sub(r"\s+", " ", html_mod.unescape(testo or "")).strip()


def senza_tag(testo: str) -> str:
    return pulisci(re.sub(r"<[^>]+>", " ", testo or ""))


def normalizza_url(url: str) -> str:
    """Toglie ancora, parametri di tracciamento e barra finale: serve per riconoscere i doppioni."""
    p = urlparse(url.strip())
    query = "&".join(
        q for q in p.query.split("&")
        if q and not re.match(r"(utm_|fbclid|gclid|mc_)", q, re.I)
    )
    percorso = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), percorso, "", query, ""))


def id_annuncio(url: str) -> str:
    return hashlib.sha1(normalizza_url(url).encode()).hexdigest()[:12]


def _data_da_match(m: re.Match) -> date | None:
    try:
        if m.group(1):
            g, me, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if a < 100:
                a += 2000
        else:
            g, me, a = int(m.group(4)), MESI[m.group(5).lower()], int(m.group(6))
        return date(a, me, g)
    except (ValueError, KeyError):
        return None


def trova_date(testo: str) -> list[date]:
    return [d for d in (_data_da_match(m) for m in RE_DATA.finditer(testo)) if d]


def contiene(testo: str, parole: list[str]) -> bool:
    t = testo.lower()
    return any(p.lower() in t for p in parole)


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

_RE_URL_DA_SALTARE = re.compile(
    r"(privacy|cookie|login|wp-content|wp-json|/tag/|/category/|/author/|/feed|"
    r"facebook\.|twitter\.|linkedin\.|instagram\.|whatsapp|youtube\.|"
    r"\.(jpg|jpeg|png|gif|svg|zip|docx?|xlsx?)(\?|$))", re.I)


def _nodo_principale(soup: BeautifulSoup, per_elenco: bool):
    if not per_elenco:
        articoli = soup.find_all("article")
        if len(articoli) == 1:
            return articoli[0]
    nodo = soup.find("main") or soup.find(id=re.compile(r"^(content|main|primary)", re.I))
    return nodo or soup.body or soup


def leggi_pagina(html: str) -> dict:
    """Titolo, testo principale e data di pubblicazione (se dichiarata) di una pagina."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    og = soup.find("meta", attrs={"property": "og:title"})
    titolo = pulisci(h1.get_text(" ")) if h1 else ""
    if not titolo and og and og.get("content"):
        titolo = pulisci(og["content"])
    if not titolo and soup.title:
        titolo = pulisci(soup.title.get_text(" "))

    pubblicato = None
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    tempo = soup.find("time", attrs={"datetime": True})
    grezzo = (meta.get("content") if meta else None) or (tempo.get("datetime") if tempo else None)
    if grezzo:
        try:
            pubblicato = datetime.fromisoformat(grezzo.replace("Z", "+00:00")).date()
        except ValueError:
            pubblicato = None

    nodo = _nodo_principale(soup, per_elenco=False)
    for tag in nodo.find_all(["script", "style", "noscript", "nav", "form", "aside", "footer", "svg"]):
        tag.decompose()
    testo = pulisci(nodo.get_text(" "))
    if len(testo) < 200 and soup.body is not None and nodo is not soup.body:
        # Il blocco "principale" è quasi vuoto: meglio leggere tutta la pagina.
        for tag in soup.body.find_all(["script", "style", "noscript", "nav", "form", "footer", "svg"]):
            tag.decompose()
        testo = pulisci(soup.body.get_text(" "))
    return {"titolo": titolo[:200], "testo": testo, "pubblicato": pubblicato}


def link_da_elenco(html: str, base: str, parole: list[str], tutti: bool) -> list[dict]:
    """Link agli annunci in una pagina-elenco. Ritorna [{url, titolo, pdf}]."""
    soup = BeautifulSoup(html, "html.parser")
    nodo = _nodo_principale(soup, per_elenco=True)
    for tag in nodo.find_all(["nav", "footer", "form", "script", "style"]):
        tag.decompose()
    host_base = urlparse(base).netloc.lower().removeprefix("www.")
    visti: dict[str, dict] = {}
    base_norm = normalizza_url(base)
    for a in nodo.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(base, href)
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            continue
        if p.netloc.lower().removeprefix("www.") != host_base:
            continue
        if _RE_URL_DA_SALTARE.search(url):
            continue
        norm = normalizza_url(url)
        if norm == base_norm or norm in visti:
            continue
        if base_norm.startswith(norm.rstrip("/") + "/") or "/tags/" in p.path.lower():
            continue  # "torna indietro", pagine superiori, pagine di etichette
        titolo = pulisci(a.get_text(" ") or a.get("title") or "")
        if re.match(r"(torna|indietro|zur[üu]ck|leggi tutto|continua|weiterlesen)\b", titolo, re.I):
            continue
        # Alcune bacheche mettono nel link "Titolo  12 gennaio 2026 – riassunto": tiene solo il titolo.
        m_data = re.search(r"\s\d{1,2}\s+(?:" + "|".join(MESI) + r")\s+\d{4}", titolo, re.I)
        if m_data and m_data.start() >= 12:
            titolo = titolo[:m_data.start()].rstrip(" –—-|")
        if tutti:
            if len(titolo) < 15 or p.path.count("/") < 1 or p.path in ("", "/"):
                continue
        else:
            if len(titolo) < 6 or not contiene(titolo + " " + p.path.replace("-", " "), parole):
                continue
        visti[norm] = {"url": url, "titolo": titolo[:200], "pdf": p.path.lower().endswith(".pdf")}
    return list(visti.values())


# --------------------------------------------------------------------------
# Feed RSS / Atom (anche Google Alerts)
# --------------------------------------------------------------------------

def _tag(el) -> str:
    return el.tag.split("}")[-1].lower()


def _url_vero(link: str) -> str:
    """Google Alerts incarta il link in un reindirizzamento: qui lo scarta."""
    p = urlparse(link)
    if "google." in p.netloc and p.path == "/url":
        vero = parse_qs(p.query).get("url") or parse_qs(p.query).get("q")
        if vero:
            return vero[0]
    return link


def leggi_feed(xml: str) -> list[dict]:
    radice = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    voci = []
    for el in radice.iter():
        if _tag(el) not in ("item", "entry"):
            continue
        titolo = link = sommario = ""
        quando = None
        for figlio in el:
            nome = _tag(figlio)
            testo = (figlio.text or "").strip()
            if nome == "title":
                titolo = senza_tag(testo)
            elif nome == "link":
                link = link or figlio.get("href") or testo
            elif nome in ("description", "summary", "content"):
                sommario = sommario or senza_tag(testo)
            elif nome in ("pubdate", "published", "updated", "date") and not quando:
                try:
                    quando = parsedate_to_datetime(testo).date()
                except (TypeError, ValueError):
                    try:
                        quando = datetime.fromisoformat(testo.replace("Z", "+00:00")).date()
                    except ValueError:
                        quando = None
        if link:
            voci.append({"url": _url_vero(link), "titolo": titolo[:200],
                         "sommario": sommario[:600], "pubblicato": quando, "pdf": False})
    return voci


# --------------------------------------------------------------------------
# Comuni e distanze
# --------------------------------------------------------------------------

# Nomi che sono anche parole comuni: valgono solo nel titolo o se ripetuti.
_NOMI_AMBIGUI = {"Chiusa", "Mori", "Nomi", "Lana", "Arco", "Badia", "Avio", "Fondo", "Comano"}


def carica_comuni(percorso: Path) -> list[dict]:
    comuni = []
    with open(percorso, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nomi = [r["nome"]] + [n for n in (r.get("altri_nomi") or "").split("|") if n]
            comuni.append({"nome": r["nome"], "km": int(r["km"]), "minuti": int(r["minuti"]),
                           "lat": float(r["lat"]), "lon": float(r["lon"]), "nomi": nomi})
    return comuni


def _conta(nome: str, testo: str) -> int:
    return len(re.findall(r"(?<!\w)" + re.escape(nome) + r"(?!\w)", testo))


def trova_comune(titolo: str, testo: str, comuni: list[dict]) -> dict | None:
    """Comune citato nel titolo; altrimenti il più citato nel testo."""
    for c in comuni:
        if any(_conta(n, titolo) for n in c["nomi"]):
            return c
    migliore, voti = None, 0
    for c in comuni:
        n = 0
        for nome in c["nomi"]:
            k = _conta(nome, testo)
            if nome in _NOMI_AMBIGUI and k < 2:
                k = 0
            n += k
        if n > voti:
            migliore, voti = c, n
    return migliore


RE_REGIONE = re.compile(r"trentino|alto adige|s[üu]dtirol|\(tn\)|\(bz\)|provincia di (trento|bolzano)", re.I)


# --------------------------------------------------------------------------
# Campi dell'annuncio
# --------------------------------------------------------------------------

RE_PIVA = re.compile(
    r"partita\s*iva|p\.\s?iva|\bp\.?iva\b|liber[oaie][\s-]*profession|incaric\w+\s+lp\b|"
    r"freiberuf|freelanc|honorar|lavoro\s+autonomo|werkvertrag", re.I)
RE_COLLAB = re.compile(r"collaborazion|prestazion\w+\s+occasional|freie\s+mitarbeit", re.I)
RE_DIP_TI = re.compile(r"tempo\s+indeterminato|\bunbefristet", re.I)
RE_DIP_TD = re.compile(r"tempo\s+determinato|(?<!un)befristet", re.I)
RE_CONCORSO = re.compile(r"concorso|graduatori|wettbewerb|rangordnung", re.I)
RE_DIP = re.compile(r"assunzion|contratto\s+(?:di\s+lavoro\s+)?(?:subordinato|dipendente)|ccnl|festanstellung|anstellung", re.I)

_NUM = r"(\d{1,3}(?:[.,]\d{1,2})?)"
RE_EURO_ORA = [
    re.compile(_NUM + r"\s*(?:€|euro|eur)\s*(?:lord[io]\s*|nett[io]\s*)?(?:/|all['’]|l['’]|a\s+|per\s+|pro\s+)?\s*(?:h\b|ora\b|orari|stunde)", re.I),
    re.compile(r"(?:€|euro|eur)\s*" + _NUM + r"\s*(?:lord[io]\s*|nett[io]\s*)?(?:/|all['’]|l['’]|a\s+|per\s+|pro\s+)?\s*(?:h\b|ora\b|orari|stunde)", re.I),
    re.compile(r"(?:compenso|tariffa|corrispettivo)\s+orari[oa]\D{0,40}?" + _NUM + r"\s*(?:€|euro)", re.I),
    re.compile(r"(?:compenso|tariffa|corrispettivo)\s+orari[oa]\D{0,40}?(?:€|euro)\s*" + _NUM, re.I),
]
RE_EURO_MESE = re.compile(
    r"((?:€|euro)\s*\d[\d.]*(?:,\d{1,2})?|\d[\d.]*(?:,\d{1,2})?\s*(?:€|euro))\s*(?:nett[io]|lord[io])?\s*"
    r"(?:al\s+mese|mensil\w*|/\s*mese|monatlich|l['’]anno|annu\w+|/\s*anno)", re.I)

RE_SCADENZA = re.compile(
    r"scadenz\w*|scade\b|entro\b|termine\b|prorog\w*|bis\s+(?:zum|spätestens)|frist\w*|"
    r"bewerbungsschluss|einreichtermin", re.I)

RE_LINGUA = re.compile(
    r"bilingu|zweisprach|patentino|attestato\s+di\s+(?:bilinguismo|conoscenza)|deutschkenntnis|"
    r"lingua\s+tedesca|tedesco|gruppo\s+linguistico|sprachgruppe", re.I)


def _numero(s: str) -> float:
    s = s.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def estrai_contratto(testo: str) -> str | None:
    piva = bool(RE_PIVA.search(testo))
    dip = bool(RE_DIP_TI.search(testo) or RE_DIP_TD.search(testo) or RE_DIP.search(testo))
    if piva and dip:
        return "P.IVA o dipendente"
    if piva:
        return "P.IVA / libera professione"
    if RE_COLLAB.search(testo):
        return "Collaborazione"
    if RE_CONCORSO.search(testo):
        return "Concorso / graduatoria"
    if RE_DIP_TI.search(testo):
        return "Dipendente a tempo indeterminato"
    if RE_DIP_TD.search(testo):
        return "Dipendente a tempo determinato"
    if dip:
        return "Dipendente"
    return None


def estrai_compenso(testo: str) -> tuple[str | None, float | None]:
    """(testo da mostrare, euro all'ora se indicati)."""
    for rx in RE_EURO_ORA:
        m = rx.search(testo)
        if m:
            try:
                valore = _numero(m.group(1))
            except ValueError:
                continue
            if 8 <= valore <= 150:
                return f"{valore:g} €/h".replace(".", ","), valore
    m = RE_EURO_MESE.search(testo)
    if m:
        return pulisci(m.group(0))[:60], None
    return None, None


def estrai_scadenza(testo: str, oggi: date) -> date | None:
    candidati = []
    for m in RE_SCADENZA.finditer(testo):
        finestra = testo[m.end(): m.end() + 110]
        d = RE_DATA.search(finestra)
        if d:
            giorno = _data_da_match(d)
            if giorno and abs((giorno - oggi).days) < 730:
                candidati.append(giorno)
    if not candidati:
        return None
    if re.search(r"prorog|verl[äa]nger", testo, re.I):
        return max(candidati)
    return candidati[0]


def estrai_turni(testo: str) -> tuple[str | None, dict]:
    etichette, segnali = [], {}
    m = re.search(r"(\d{1,2})\s*(?:h|ore|stunden)\s*(?:/|a|alla|pro|per)?\s*(?:settiman|woche)", testo, re.I)
    if m and 4 <= int(m.group(1)) <= 48:
        ore = int(m.group(1))
        etichette.append(f"{ore} h/settimana")
        segnali["ore_settimana"] = ore
    if re.search(r"\b12\s*(?:h\b|ore\b|stunden)", testo, re.I):
        etichette.append("turni da 12 h")
        segnali["dodici"] = True
    if re.search(r"\bnott[ei]\b|notturn|nachtdienst|nachtschicht|\bnächte", testo, re.I):
        etichette.append("notti")
        segnali["notti"] = True
    if re.search(r"week\s?-?end|fine\s+settimana|festiv|wochenend", testo, re.I):
        etichette.append("weekend/festivi")
        segnali["weekend"] = True
    if re.search(r"tempo\s+pieno|full[\s-]?time|vollzeit", testo, re.I):
        etichette.append("tempo pieno")
        segnali["pieno"] = True
    if re.search(r"part[\s-]?time|tempo\s+parziale|teilzeit", testo, re.I):
        etichette.append("part-time")
        segnali["parziale"] = True
    if re.search(r"\balloggio|unterkunft", testo, re.I):
        etichette.append("alloggio")
    return (", ".join(etichette) or None), segnali


_RE_ENTE = (r"(?:A\.?\s?P\.?\s?S\.?\s?P\.?|RSA|Casa di (?:Cura|riposo)|(?:Società )?Cooperativa|Fondazione|Residenza|"
            r"Seniorenwohnheim|Stiftung|Sozialgenossenschaft|Clinica|Poliambulatorio|Comunità|Hotel|Azienda|INPS|INAIL)")
_RE_TAGLIO = re.compile(r"\s+(?:cerca|cercasi|ricerca|ricerchiamo|sucht|assume|seleziona|selezione|bando|concorso|avviso)\b.*$", re.I)


def estrai_datore(titolo: str) -> str | None:
    """Nei titoli tipo 'APSP Vannetti – Rovereto – Selezione…' il datore è il primo pezzo.
    Se non si capisce con sicurezza, meglio None (nell'app compare il titolo)."""
    pezzi = [p.strip() for p in re.split(r"\s+[–—|-]\s+", titolo) if p.strip()]
    candidato = None
    if len(pezzi) >= 2 and re.match(_RE_ENTE, pezzi[0], re.I):
        candidato = pezzi[0]
    else:
        m = re.search("(" + _RE_ENTE + r"\s+[^,;:()–—|]{3,60})", titolo)
        candidato = m.group(1) if m else None
    if not candidato:
        return None
    candidato = pulisci(_RE_TAGLIO.sub("", candidato)).strip(" -–")
    if len(candidato) < 4 or candidato.lower() == titolo.lower().strip():
        return None
    return candidato[:80]


def frammento(testo: str, parole: list[str], lunghezza: int = 220) -> str:
    """Breve estratto attorno alla prima parola chiave, per orientarsi nell'app."""
    basso = testo.lower()
    pos = min((basso.find(p) for p in parole if basso.find(p) >= 0), default=0)
    inizio = max(0, pos - 40)
    pezzo = testo[inizio: inizio + lunghezza].strip()
    return ("…" if inizio else "") + pezzo + ("…" if inizio + lunghezza < len(testo) else "")


def estrai_campi(titolo: str, testo: str, comuni: list[dict], oggi: date,
                 parole_infermiere: list[str]) -> dict:
    tutto = f"{titolo}. {testo}"
    compenso, euro_ora = estrai_compenso(tutto)
    turni, segnali = estrai_turni(tutto)
    comune = trova_comune(titolo, testo, comuni)
    scadenza = estrai_scadenza(tutto, oggi)
    return {
        "datore": estrai_datore(titolo),
        "contratto": estrai_contratto(tutto),
        "compenso": compenso,
        "euro_ora": euro_ora,
        "turni": turni,
        "segnali_turni": segnali,
        "zona": comune["nome"] if comune else None,
        "km": comune["km"] if comune else None,
        "minuti": comune["minuti"] if comune else None,
        "scadenza": scadenza.isoformat() if scadenza else None,
        "cita_tedesco": bool(RE_LINGUA.search(tutto)),
        "estratto": frammento(testo, parole_infermiere) if testo else "",
    }
