"""Estrazione dei dati dagli annunci: funzioni pure, senza rete.

Regola d'oro: se un dato non si trova, resta None e viene mostrato come "n.d.".
Niente viene inventato.
"""
from __future__ import annotations

import csv
import hashlib
import html as html_mod
import io
import re
import unicodedata
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
_RE_DATA_NUM = r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4}|\d{2})(?!\d)"
_RE_DATA_MESE = r"(?<!\d)(\d{1,2})\.?\s*°?\s+(" + "|".join(MESI) + r")\s+(\d{4})"
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


_PAROLE_VUOTE = {"apsp", "a", "p", "s", "rsa", "fondazione", "casa", "di", "riposo", "cura", "cooperativa",
                 "sociale", "societa", "onlus", "srl", "spa", "azienda", "pubblica", "servizi", "alla",
                 "persona", "il", "la", "le", "per", "e", "de", "del", "della", "dei", "the"}


def chiave(testo: str | None) -> str:
    """Forma ridotta di un nome o titolo, per riconoscere lo stesso annuncio scritto in due modi."""
    if not testo:
        return ""
    t = unicodedata.normalize("NFKD", testo.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = RE_DATA.sub(" ", t)
    parole = [p for p in re.split(r"[^a-z0-9]+", t) if p and p not in _PAROLE_VUOTE]
    return " ".join(parole)


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

_TAG_RUMORE = ["script", "style", "noscript", "nav", "form", "aside", "footer", "svg", "iframe", "button", "select"]
# Blocchi che non fanno parte dell'annuncio: condivisione social, annunci simili, briciole, autore e data.
_RE_CLASSE_RUMORE = re.compile(
    r"(?:^|[-_\s])(?:share|sharing|social|related|similar|sidebar|breadcrumbs?|comments?|cookie|newsletter|"
    r"pagination|pager|widget|meta|author|byline|tags?|toolbar|banner|popup|modal)(?:[-_\s]|$)", re.I)

_RE_PDF_INUTILE = re.compile(
    r"domanda|modulo|fac[\s_-]?simile|informativa|privacy|curriculum|autocertific|consenso|graduatoria|esito|"
    r"verbale|calendario|convocaz|diario|ammess|schema|carta[\s_-]dei[\s_-]servizi|organigramma|statuto|"
    r"regolamento|tariff|menu|bilancio", re.I)
_RE_PDF_UTILE = re.compile(r"avviso|bando|selezion|incaric|ricerca|concorso|ausschreibung|stellen|annuncio", re.I)

_POSTA_PRIVATA = re.compile(
    r"@(?:gmail|googlemail|libero|hotmail|yahoo|outlook|live|virgilio|alice|tiscali|icloud|me|tim|email|"
    r"fastwebnet|gmx|web|rolmail|msn|inwind|iol|aruba|protonmail|proton)\.", re.I)
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _nodo_principale(soup: BeautifulSoup, per_elenco: bool):
    if not per_elenco:
        articoli = soup.find_all("article")
        if len(articoli) == 1:
            return articoli[0]
    nodo = soup.find("main") or soup.find(id=re.compile(r"^(content|main|primary)", re.I))
    return nodo or soup.body or soup


def _ripulisci(nodo) -> None:
    """Toglie dal blocco menu, moduli, pulsanti di condivisione, 'annunci simili' e simili."""
    for tag in nodo.find_all(_TAG_RUMORE):
        tag.decompose()
    totale = len(nodo.get_text(" ", strip=True)) or 1

    def rumore(el) -> bool:
        attributi = " ".join(el.get("class") or []) + " " + (el.get("id") or "")
        return bool(attributi.strip()) and bool(_RE_CLASSE_RUMORE.search(attributi))

    for el in nodo.find_all(rumore):
        try:
            if getattr(el, "decomposed", False):
                continue
            # Un blocco che contiene metà del testo non è rumore: è il contenitore dell'annuncio.
            if len(el.get_text(" ", strip=True)) < 0.5 * totale:
                el.decompose()
        except Exception:  # elemento già rimosso insieme a un suo contenitore
            continue


def _link_pdf(nodo, base: str) -> list[dict]:
    """PDF allegati all'annuncio, con prima quelli che sembrano l'avviso o il bando."""
    visti: dict[str, dict] = {}
    for a in nodo.find_all("a", href=True):
        url = urljoin(base, a["href"].strip())
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            continue
        percorso = p.path.lower()
        if not (percorso.endswith(".pdf") or "/content/download/" in percorso):
            continue
        testo = pulisci(a.get_text(" ") or "")
        nome = testo + " " + percorso.rsplit("/", 1)[-1]
        if _RE_PDF_INUTILE.search(nome):
            continue
        visti.setdefault(normalizza_url(url), {"url": url, "testo": testo[:120],
                                               "peso": 0 if _RE_PDF_UTILE.search(nome) else 1})
    return sorted(visti.values(), key=lambda x: x["peso"])


def trova_email(testo: str, escludi_domini: set[str] | None = None) -> dict:
    """Indirizzi della struttura citati nell'annuncio. Gli indirizzi privati (gmail, libero…) si scartano."""
    escludi = {d.lower() for d in (escludi_domini or set())}
    posta, pec = None, None
    for m in _RE_EMAIL.finditer(testo or ""):
        indirizzo = m.group(0).strip(".").lower()
        dominio = indirizzo.split("@", 1)[1]
        if _POSTA_PRIVATA.search(indirizzo) or any(dominio == d or dominio.endswith("." + d) for d in escludi):
            continue
        if re.search(r"pec|legalmail|postacert|cert\.", dominio):
            pec = pec or indirizzo
        else:
            posta = posta or indirizzo
    return {"email": posta, "pec": pec}


def leggi_pagina(html: str, base: str = "", intera_se_vuota: bool = False) -> dict:
    """Titolo, testo principale, data di pubblicazione (se dichiarata) e PDF allegati di una pagina."""
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
            pubblicato = datetime.fromisoformat(grezzo.strip().replace("Z", "+00:00")).date()
        except ValueError:
            m = RE_DATA.search(grezzo)
            pubblicato = _data_da_match(m) if m else None

    nodo = _nodo_principale(soup, per_elenco=False)
    pdf = _link_pdf(nodo, base) if base else []
    _ripulisci(nodo)
    testo = pulisci(nodo.get_text(" "))
    if intera_se_vuota and len(testo) < 200 and soup.body is not None and nodo is not soup.body:
        # Pagine "lavora con noi" senza un blocco principale riconoscibile: si legge tutto il corpo.
        pdf = pdf or (_link_pdf(soup.body, base) if base else [])
        _ripulisci(soup.body)
        for tag in soup.body.find_all("header"):
            tag.decompose()
        testo = pulisci(soup.body.get_text(" "))
    return {"titolo": titolo[:200], "testo": testo, "pubblicato": pubblicato, "pdf": pdf}


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
        if re.match(r"(torna|indietro|zur[üu]ck|leggi tutto|continua|weiterlesen|scarica)\b", titolo, re.I):
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


_RE_LINK_INTERESSANTE = re.compile(
    r"concors|bandi|bando|avvis|lavor|selezion|personale|stellen|job|karriere|career|albo|incaric|"
    r"traspar|recruit|posizioni|candidat|mitarbeit|ausschreib|pflege|infermier", re.I)


def tutti_i_link(html: str, base: str, massimo: int = 70) -> list[list[str]]:
    """Per la diagnostica: i link di una pagina, prima quelli che parlano di lavoro e concorsi."""
    soup = BeautifulSoup(html, "html.parser")
    utili, altri, visti = [], [], set()
    for a in (soup.body or soup).find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(base, href)
        if url in visti or not url.startswith("http"):
            continue
        visti.add(url)
        testo = pulisci(a.get_text(" ") or a.get("title") or "")[:70]
        (utili if _RE_LINK_INTERESSANTE.search(testo + " " + url) else altri).append([testo, url])
    return (utili[:massimo] + altri[:max(0, min(20, massimo - len(utili)))])


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

def testo_pdf(dati: bytes, massimo_pagine: int = 12) -> str:
    """Testo di un PDF. Ritorna '' se la libreria manca, il file è rovinato o è una scansione."""
    try:
        import logging
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)
    except ImportError:
        return ""
    try:
        lettore = PdfReader(io.BytesIO(dati))
        pezzi = []
        for pagina in lettore.pages[:massimo_pagine]:
            pezzi.append(pagina.extract_text() or "")
        return pulisci(" ".join(pezzi))[:40000]
    except Exception:
        return ""


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
            url = _url_vero(link)
            voci.append({"url": url, "titolo": titolo[:200], "sommario": sommario[:600],
                         "pubblicato": quando, "pdf": urlparse(url).path.lower().endswith(".pdf")})
    return voci


# --------------------------------------------------------------------------
# Comuni e distanze
# --------------------------------------------------------------------------

# Nomi che sono anche parole comuni: valgono solo se ripetuti o seguiti dalla provincia, es. "Arco (TN)".
_NOMI_AMBIGUI = {"Chiusa", "Mori", "Nomi", "Lana", "Arco", "Badia", "Avio", "Fondo", "Comano", "Scena", "Postal",
                 "Renon", "Funes", "Riva", "Novella", "Tirolo", "Wiesen", "Brenner", "Varna", "La Villa"}
# Nomi troppo comuni: valgono solo con la provincia accanto.
_NOMI_STRETTI = {"Ala", "Ora", "Auer", "Ton", "Dro", "Prad"}
_PROVINCIA = r"\s*[\(\-–,]?\s*(?:TN|BZ|Tn|Bz|Trento\)|Bolzano\))(?![a-zà-ù])"


def carica_comuni(percorso: Path) -> list[dict]:
    comuni = []
    with open(percorso, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nomi = [r["nome"]] + [n for n in (r.get("altri_nomi") or "").split("|") if n]
            comuni.append({"nome": r["nome"], "km": int(r["km"]), "minuti": int(r["minuti"]),
                           "lat": float(r["lat"]), "lon": float(r["lon"]), "nomi": nomi})
    return comuni


def _occorrenze(nome: str, testo: str) -> list[int]:
    """Posizioni in cui compare il nome (anche tutto maiuscolo), come parola intera."""
    varianti = {nome, nome.upper()}
    schema = r"(?<![\wà-ùÀ-Ù])(?:" + "|".join(re.escape(v) for v in varianti) + r")(?![\wà-ùÀ-Ù])"
    return [m.start() for m in re.finditer(schema, testo)]


def _con_provincia(nome: str, testo: str) -> bool:
    varianti = {nome, nome.upper()}
    schema = r"(?<![\wà-ùÀ-Ù])(?:" + "|".join(re.escape(v) for v in varianti) + r")" + _PROVINCIA
    return bool(re.search(schema, testo))


def trova_comune(titolo: str, testo: str, comuni: list[dict]) -> dict | None:
    """Comune dell'annuncio: prima quello nel titolo, poi il più citato nel testo."""
    tutto = f"{titolo} {testo}"
    # 1) Nel titolo: vince il primo nome sicuro; i nomi ambigui valgono solo con conferme.
    migliore, posizione = None, None
    for c in comuni:
        for nome in c["nomi"]:
            dove = _occorrenze(nome, titolo)
            if not dove:
                continue
            if nome in _NOMI_STRETTI and not _con_provincia(nome, titolo):
                continue
            if nome in _NOMI_AMBIGUI and not (_con_provincia(nome, tutto) or len(_occorrenze(nome, tutto)) >= 3):
                continue
            rango = (1 if nome in _NOMI_AMBIGUI else 0, dove[0])
            if posizione is None or rango < posizione:
                migliore, posizione = c, rango
    if migliore:
        return migliore
    # 2) Nel testo: il comune citato più volte.
    voti_migliori = 0
    for c in comuni:
        voti = 0
        for nome in c["nomi"]:
            if nome in _NOMI_STRETTI:
                voti += 2 if _con_provincia(nome, testo) else 0
                continue
            k = len(_occorrenze(nome, testo))
            if nome in _NOMI_AMBIGUI and k < 2 and not _con_provincia(nome, testo):
                k = 0
            voti += k
        if voti > voti_migliori:
            migliore, voti_migliori = c, voti
    return migliore


RE_REGIONE = re.compile(r"trentino|alto adige|s[üu]dtirol|\(tn\)|\(bz\)|provincia di (trento|bolzano)", re.I)
_RE_PROVINCIA_ALTRA = re.compile(r"\((?:VE|VR|VI|BL|PD|TV|RO|BS|BG|SO|MI|MN|UD|PN|TS|GO|BO|MO|TO|RM|FI|NA)\)")


def fuori_regione(titolo: str, parole_fuori: list[str]) -> bool:
    """Il titolo indica chiaramente un posto fuori dal Trentino-Alto Adige."""
    return bool(_RE_PROVINCIA_ALTRA.search(titolo)) or any(
        re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", titolo, re.I) for p in parole_fuori)


# --------------------------------------------------------------------------
# Campi dell'annuncio
# --------------------------------------------------------------------------

# "P.IVA 01234567890" in fondo alla pagina è il numero dell'azienda, non il tipo di contratto: va tolto prima.
RE_NUMERO_IVA = re.compile(
    r"(?:partita\s*i\.?\s?v\.?\s?a\.?|p\.?\s?i\.?\s?v\.?\s?a\.?|part\.\s*iva|mwst\.?(?:\s*-?\s*nr\.?)?|steuernummer)"
    r"[^a-zA-Z\d]{0,6}(?:(?:e|ed)\s+)?(?:(?:c\.?\s?f\.?|cod(?:ice)?\.?\s+fisc\w*)[^a-zA-Z\d]{0,6})?"
    r"(?:n\.?|nr\.?)?\s*(?:IT)?\s*\d{8,11}", re.I)
RE_PIVA = re.compile(
    r"partita\s*iva|p\.\s?iva|\bp\.?iva\b|liber[oaie][\s-]*profession|incaric\w+\s+lp\b|"
    r"freiberuf|freelanc|honorarbasis|auf\s+honorar|lavoro\s+autonomo|werkvertrag", re.I)
RE_COLLAB = re.compile(
    r"contratt\w+\s+di\s+collaborazion|rapport\w+\s+di\s+collaborazion|"
    r"collaborazion\w+\s+(?:coordinat|occasional|autonom|professional|estern|libero)|collaborazione\s*/\s*p\.?\s?iva|"
    r"co\.?\s?co\.?\s?co\b|prestazion\w+\s+occasional|collaborator\w+\s+estern|freie\s+mitarbeit", re.I)
RE_DIP_TI = re.compile(r"tempo\s+indeterminato|\bunbefristet", re.I)
RE_DIP_TD = re.compile(r"tempo\s+determinato|(?<!un)befristet", re.I)
RE_CONCORSO = re.compile(r"concorso|graduatori|wettbewerb|rangordnung", re.I)
RE_DIP = re.compile(r"assunzion|contratto\s+(?:di\s+lavoro\s+)?(?:subordinato|dipendente)|ccnl|festanstellung|anstellung", re.I)

# Ruoli diversi dall'infermiere di reparto (coordinamento, direzione, posti riservati a dipendenti pubblici).
_RUOLI = (r"coordinat(?:ore|rice|ori)\w*(?:\s*/\s*\w+)?\s+(?:infermieristic|dei\s+servizi|sanitari|di\s+(?:nucleo|struttura|reparto))"
          r"|responsabile\s+(?:di\s+piano|di\s+nucleo|di\s+struttura|tecnico|infermieristic|assistenzial|sanitari|dei\s+servizi)"
          r"|direttor[ei]\s+(?:sanitari|general|di\s+struttura)|dirigente\s+(?:medic|infermieristic|delle\s+profession|sanitari)"
          r"|pflegedienstleit|wohnbereichsleit|stationsleit|bereichsleit|heimleit|pflegedirektor")
RE_RUOLO_TITOLO = re.compile(_RUOLI + r"|\bin\s+comando\b", re.I)
RE_RUOLO_TESTO = re.compile(
    r"(?:cerc\w+|ricerc\w+|selezion\w+|assum\w+|post[oi]\s+di|incarico\s+di|figura\s+di|profilo\s+di|suchen)[^.]{0,80}?(?:" + _RUOLI + r")"
    , re.I)
# Posti riservati a chi è già dipendente pubblico (comando, mobilità).
RE_SOLO_PUBBLICI = re.compile(r"\(dipendente\s+pubblico\)|in\s+comando\s+ai\s+(?:sensi|termini)|\bmobilità\s+(?:volontaria|esterna|tra\s+enti)", re.I)

_NUM = r"(\d{1,3}(?:[.,]\d{1,2})?)"
_EURO = r"(?:€|euro|eur)"
_AGG = r"(?:(?:lord\w+|nett\w+|omnicomprensiv\w+)\s*)*"
_UNITA = r"(?:/|all['’]\s*|l['’]\s*|a\s+|per\s+(?:ogni\s+|ciascuna\s+)?|pro\s+)?\s*(?:h\b|ora\b|orari\w*|stunde)"
RE_EURO_ORA = [
    re.compile(_NUM + r"\s*" + _EURO + r"\s*" + _AGG + _UNITA, re.I),
    re.compile(_EURO + r"\s*" + _NUM + r"\s*(?:\([^)]{0,40}\)\s*)?" + _AGG + _UNITA, re.I),
    re.compile(r"(?:compenso|tariffa|corrispettivo|importo|retribuzione)\s+(?:lord\w+\s+)?orari\w+\D{0,60}?"
               r"(?:" + _EURO + r"\s*" + _NUM + r"|" + _NUM + r"\s*" + _EURO + r")", re.I),
    re.compile(r"stunden(?:lohn|satz|honorar)\D{0,30}?(?:" + _EURO + r"\s*" + _NUM + r"|" + _NUM + r"\s*" + _EURO + r")", re.I),
]
_IMPORTO = r"(?:" + _EURO + r"\s*\d[\d.]*(?:,\d{1,2})?|\d[\d.]*(?:,\d{1,2})?\s*" + _EURO + r")"
RE_EURO_TURNO = re.compile(_IMPORTO + r"\s*" + _AGG + r"(?:a|per|al|pro)\s+(?:turno|notte|accesso|prestazione|giornata|schicht|nacht)", re.I)
RE_EURO_MESE = re.compile(
    _IMPORTO + r"\s*" + _AGG + r"(?:al\s+mese|mensil\w*|/\s*mese|monatlich|l['’]anno|annu\w+|/\s*anno|all['’]anno)", re.I)

RE_SCADENZA_FORTE = re.compile(
    r"scadenz\w*|scade\b|termine\s+(?:di\s+)?(?:presentazione|ultimo|perentorio)|pervenire\s+entro|"
    r"entro\s+(?:e\s+non\s+oltre\s+)?(?:le\s+ore\s+[\d.:,]+\s+)?(?:del(?:\s+giorno)?|il(?:\s+giorno)?)\s|"
    r"entro\s+e\s+non\s+oltre|prorog\w*|bewerbungsfrist|einreichfrist|bis\s+(?:zum|spätestens)", re.I)
RE_SCADENZA_DEBOLE = re.compile(r"entro\b|termine\b|frist\w*", re.I)

RE_LINGUA = re.compile(
    r"bilingu|zweisprach|patentino|attestato\s+di\s+(?:bilinguismo|conoscenza)|deutschkenntnis|"
    r"lingua\s+tedesca|tedesco|gruppo\s+linguistico|sprachgruppe", re.I)

_STRUTTURE = [
    ("Stagionale o turistico", re.compile(r"stagional|soggiorn\w+[\s-]+vacanz|\bhotel\b|soccorso\s+traumatolog|saison", re.I)),
    ("Domiciliare", re.compile(r"domicil|hauspflege|hauskrankenpflege", re.I)),
    ("RSA o casa di riposo", re.compile(r"\brsa\b|a\.?\s?p\.?\s?s\.?\s?p\b|casa\s+di\s+riposo|residenza\s+(?:per\s+)?anzian|seniorenwohnheim|altersheim|pflegeheim", re.I)),
    ("Clinica o ambulatorio", re.compile(r"casa\s+di\s+cura|clinic|klinik|riabilitaz|poliambulator|ambulator|emodialisi|centro\s+medico", re.I)),
    ("Ospedale o azienda sanitaria", re.compile(r"ospedal|azienda\s+(?:provinciale|sanitaria)|asuit|\bapss\b|sabes|krankenhaus|sanit[äa]tsbetrieb", re.I)),
    ("Disabilità o sociale", re.compile(r"disabilit|cooperativa\s+social|sozialgenossenschaft|centro\s+diurno|comunità\s+comprensoriale", re.I)),
]
_RE_TEDESCO = re.compile(r"\b(?:und|der|die|das|für|wir|suchen|mit|bei|sind|ihre|eine[nr]?|oder|als)\b", re.I)
_RE_ITALIANO = re.compile(r"\b(?:di|per|con|che|della|il|la|siamo|ricerca|presso|sono|una|gli|nel)\b", re.I)


def _numero(s: str) -> float:
    s = s.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def estrai_contratto(testo: str) -> str | None:
    testo = RE_NUMERO_IVA.sub(" ", testo)
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
        for m in rx.finditer(testo):
            grezzo = next((g for g in m.groups() if g), None)
            if not grezzo:
                continue
            try:
                valore = _numero(grezzo)
            except ValueError:
                continue
            if 8 <= valore <= 150:
                return f"{valore:g} €/h".replace(".", ","), valore
    for rx in (RE_EURO_TURNO, RE_EURO_MESE):
        m = rx.search(testo)
        if m:
            return pulisci(m.group(0))[:60], None
    return None, None


def estrai_scadenza(testo: str, oggi: date) -> date | None:
    def candidati(rx: re.Pattern) -> list[date]:
        trovati = []
        for m in rx.finditer(testo):
            finestra = testo[m.end(): m.end() + 110]
            for d in RE_DATA.finditer(finestra):
                giorno = _data_da_match(d)
                if giorno and abs((giorno - oggi).days) < 730:
                    trovati.append(giorno)
                    break
        return trovati

    date_trovate = candidati(RE_SCADENZA_FORTE) or candidati(RE_SCADENZA_DEBOLE)
    if not date_trovate:
        return None
    if re.search(r"prorog|verl[äa]nger", testo, re.I):
        return max(date_trovate)
    return date_trovate[0]


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


def estrai_struttura(titolo: str, testo: str) -> str | None:
    for campione in (titolo, testo[:700]):
        for etichetta, rx in _STRUTTURE:
            if rx.search(campione):
                return etichetta
    return None


def lingua_tedesca(testo: str) -> bool:
    campione = testo[:900]
    de, it = len(_RE_TEDESCO.findall(campione)), len(_RE_ITALIANO.findall(campione))
    return de >= 6 and de > it


def ruolo_diverso(titolo: str, testo: str) -> bool:
    """L'annuncio cerca un coordinatore, un dirigente o un dipendente pubblico in comando."""
    if RE_RUOLO_TITOLO.search(titolo) or RE_SOLO_PUBBLICI.search(titolo + " " + testo[:800]):
        return True
    titolo_da_infermiere = bool(re.search(r"infermier[ei]\b|krankenpfleger", titolo, re.I))
    return not titolo_da_infermiere and bool(RE_RUOLO_TESTO.search(testo[:600]))


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
        "in_tedesco": lingua_tedesca(testo),
        "struttura": estrai_struttura(titolo, testo),
        "estratto": frammento(testo, parole_infermiere) if testo else "",
    }
