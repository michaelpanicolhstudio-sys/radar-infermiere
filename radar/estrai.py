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
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse, unquote

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
# 20/11: «…DET_304_26_dd_15_10_Allegato_signed.pdf» (Vannetti P.IVA) è l'avviso: l'allegato di una determinazione.
_RE_PDF_UTILE = re.compile(r"avviso|bando|selezion|incaric|ricerca|concorso|prorog|ausschreibung|stellen|annuncio|"
                           r"(?:^|[^a-z])det(?:ermina\w*)?[_\s.-]*(?:n[_.]?\s*)?\d+.*allegat", re.I)
_RE_ETICHETTA_VUOTA = re.compile(r"^(?:scarica(?:\s+il)?(?:\s+pdf)?|download|apri|visualizza|pdf|clicca\s+qui|leggi|allegato|file)?\W*$", re.I)
_RE_CONTORNO = re.compile(r"sidebar|^widget|footer|cookie|breadcrumb|navbar|^menu|-menu$|related|correlat", re.I)
_ATTRIBUTI_LINK = ("href", "src", "data", "data-src", "data-pdf", "data-pdf-url", "data-file", "data-url")

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


def _url_pdf(url: str) -> str | None:
    """L'indirizzo del PDF, se il link porta a un PDF (anche dentro un visualizzatore o un plugin di download)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return None
    percorso = p.path.lower()
    if percorso.endswith(".pdf") or "/content/download/" in percorso:
        return url
    parametri = parse_qs(p.query)
    for nome in ("file", "url", "src", "pdf"):
        for valore in parametri.get(nome, []):
            if ".pdf" in valore.lower():
                return urljoin(url, valore)
    if "wpdmdl" in parametri or "download_id" in parametri:
        return url
    return None


# 20/11: OPI Trento, Vannetti: la pagina mostra tre riquadri «scarica il pdf» (avviso, proroga), ma il
# Radar non trovava nessun PDF: l'indirizzo non sta in href/src (visualizzatori e pulsanti dei plugin lo
# tengono in attributi insoliti o negli script). Ultima risorsa: gli indirizzi .pdf scritti nel codice.
_RE_PDF_NEL_CODICE = re.compile(
    r"(?:https?:(?:\\?/){2}[^\s\"'<>()]+?|(?:\\?/)wp-content(?:\\?/)uploads(?:\\?/)[^\s\"'<>()]+?)\.pdf\b", re.I)


def _pdf_nel_codice(html: str, base: str, massimo: int = 3, scartati: bool = False) -> list[dict]:
    """PDF citati nel codice della pagina, tenuti solo se dal nome sembrano un avviso o un bando.
    Con scartati=True ritorna invece quelli lasciati fuori per il nome (per la diagnostica)."""
    visti: dict[str, dict] = {}
    for m in _RE_PDF_NEL_CODICE.finditer(html or ""):
        url = urljoin(base, m.group(0).replace("\\/", "/"))
        nome = unquote(urlparse(url).path.rsplit("/", 1)[-1])
        buono = not _RE_PDF_INUTILE.search(nome) and bool(_RE_PDF_UTILE.search(nome))
        if buono == scartati:
            continue
        visti.setdefault(normalizza_url(url), {"url": url, "testo": nome[:120], "peso": 0})
    return list(visti.values())[: (8 if scartati else massimo)]


def pdf_scartati_nel_codice(html: str, base: str) -> list[str]:
    """Messa a punto: indirizzi di PDF presenti nel codice ma non presi perché il nome non dice «avviso/bando»."""
    return [x["url"][:200] for x in _pdf_nel_codice(html, base, scartati=True)]


def _etichetta(tag) -> str:
    """Testo del link; se è solo «scarica» o «download», il titolo del blocco che lo contiene."""
    testo = pulisci(tag.get_text(" ") or "")
    if tag.name != "a":
        return pulisci(tag.get("title") or "")  # visualizzatori incorporati: conta il nome del file
    genitore = tag
    for _ in range(3):
        if not _RE_ETICHETTA_VUOTA.match(testo):
            break
        genitore = genitore.parent
        if genitore is None or genitore.name in ("body", "html", "main", "article"):
            break
        intorno = pulisci(genitore.get_text(" ") or "")
        if len(intorno) <= 160:
            testo = re.sub(r"\b(?:scarica(?:\s+il)?(?:\s+pdf)?|download)\b", " ", intorno, flags=re.I).strip()
    return pulisci(testo)


def _nel_contorno(tag) -> bool:
    for su in tag.parents:
        if su.name in ("nav", "header", "footer", "aside"):
            return True
        if su.get("data-elementor-type") in ("header", "footer"):
            return True
        for nome in list(su.get("class") or []) + [su.get("id") or ""]:
            # Elementor chiama "widget" ogni blocco del contenuto: quei nomi non contano.
            if nome and not nome.lower().startswith("elementor") and _RE_CONTORNO.search(nome):
                return True
    return False


def _link_pdf(nodo, base: str, solo_sicuri: bool = False) -> list[dict]:
    """PDF allegati all'annuncio, con prima quelli che sembrano l'avviso o il bando.
    Con solo_sicuri si cerca in tutta la pagina e si tengono solo quelli che dal nome sembrano un avviso."""
    visti: dict[str, dict] = {}
    for tag in nodo.find_all(True):
        for attributo in _ATTRIBUTI_LINK:
            valore = tag.get(attributo)
            if not isinstance(valore, str) or not valore.strip():
                continue
            url = _url_pdf(urljoin(base, valore.strip()))
            if not url:
                continue
            testo = _etichetta(tag)
            nome = testo + " " + unquote(urlparse(url).path.rsplit("/", 1)[-1])
            if _RE_PDF_INUTILE.search(nome):
                continue
            utile = bool(_RE_PDF_UTILE.search(nome))
            if solo_sicuri and (not utile or _nel_contorno(tag)):
                continue
            visti.setdefault(normalizza_url(url), {"url": url, "testo": testo[:120], "peso": 0 if utile else 1})
    return sorted(visti.values(), key=lambda x: x["peso"])


_RE_SOCIAL = re.compile(r"facebook|twitter|(?:^|\.)x\.com$|linkedin|whatsapp|instagram|youtube|telegram|t\.me$|pinterest|google|wordpress\.org", re.I)


def allegati_dubbi(html: str, base: str, massimo: int = 8) -> list[list[str]]:
    """Messa a punto: link che parlano di PDF o download ma che non sono stati riconosciuti."""
    soup = BeautifulSoup(html, "html.parser")
    trovati, visti = [], set()
    casa = urlparse(base).netloc.lower().removeprefix("www.")
    # 19/11: per OPI Trento comparivano solo le icone del sito (<link rel="icon"> nell'intestazione):
    # quelle non sono allegati. Contano anche i link del testo verso un altro sito o che parlano
    # di avviso/bando/albo (Vannetti: «l'avviso è… in calce alla pagina», ma nessun PDF trovato).
    for tag in soup.find_all(True):
        if tag.name in ("link", "meta", "script", "style") or _nel_contorno(tag):
            continue
        for attributo in _ATTRIBUTI_LINK:
            valore = tag.get(attributo)
            if not isinstance(valore, str) or not valore.strip() or valore.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            testo = pulisci(tag.get_text(" ") or "")[:60]
            indirizzo = urljoin(base, valore)
            host = urlparse(indirizzo).netloc.lower().removeprefix("www.")
            altro_sito = (tag.name == "a" and bool(casa) and host not in ("", casa)
                          and not _RE_SOCIAL.search(host))
            if (re.search(r"pdf|download|scarica|allegat|wp-content/uploads|avvis|bando|albo|document", valore + " " + testo, re.I)
                    or altro_sito) and valore not in visti:
                visti.add(valore)
                trovati.append([tag.name, testo, indirizzo[:200]])
    # 20/11: i pulsanti «scarica il pdf» senza indirizzo leggibile: si scrive com'è fatto il tag
    # (nome e attributi), così si capisce dove il sito tiene l'indirizzo del PDF.
    for tag in soup.find_all(True):
        if len(trovati) >= massimo or tag.name in ("script", "style", "html", "body") or _nel_contorno(tag):
            continue
        proprio = pulisci(" ".join(t for t in tag.find_all(string=True, recursive=False)))
        if not re.fullmatch(r"(?:scarica(?:\s+il)?\s+pdf|download(?:\s+pdf)?|scarica)\W*", proprio, re.I):
            continue
        # Anche i due contenitori sopra: spesso l'indirizzo sta nel riquadro, non nella scritta.
        pezzi = []
        for el in [tag] + [g for g in list(tag.parents)[:2] if g.name not in ("body", "html", "[document]")]:
            att = "; ".join(f"{k}={' '.join(v) if isinstance(v, list) else v}" for k, v in el.attrs.items())
            pezzi.append(f"{el.name}[{att}]" if el is not tag else att)
        attributi = " ↑ ".join(x for x in pezzi if x)
        if any(x[1] == proprio and x[2] == attributi[:200] for x in trovati):
            continue
        trovati.append([tag.name, proprio[:60], attributi[:200] or "(nessun attributo)"])
    return trovati[:massimo]


def trova_email(testo: str, escludi_domini: set[str] | None = None) -> dict:
    """Indirizzi della struttura citati nell'annuncio. Gli indirizzi privati (gmail, libero…) si scartano."""
    escludi = {d.lower() for d in (escludi_domini or set())}
    posta, pec = None, None
    trovati = [m.group(0).strip(".").lower() for m in _RE_EMAIL.finditer(testo or "")]
    for indirizzo in trovati:
        dominio = indirizzo.split("@", 1)[1]
        # Indirizzo spezzato a capo nel PDF («…@postacert.i» + «nps.gov.it», INPS 22/11): un dominio che finisce
        # con una sola lettera, o che è l'inizio di un altro indirizzo trovato, è un pezzo, non un indirizzo.
        if len(dominio.rsplit(".", 1)[-1]) < 2 or any(t != indirizzo and t.startswith(indirizzo) for t in trovati):
            continue
        if _POSTA_PRIVATA.search(indirizzo) or any(dominio == d or dominio.endswith("." + d) for d in escludi):
            continue
        if re.search(r"pec|legalmail|postacert|cert\.", dominio):
            pec = pec or indirizzo
        else:
            posta = posta or indirizzo
    return {"email": posta, "pec": pec}


# Titoli dei riquadri con gli annunci di altri datori, in fondo alla pagina di un annuncio.
_RE_CORRELATI = re.compile(
    r"\b(?:ähnliche|weitere|passende)\s+(?:jobs|stellen(?:angebote)?|stellenanzeigen)\b|"
    r"\b(?:annunci|offerte|lavori)\s+simili\b|\baltri\s+annunci\b|\bpotrebbero\s+interessarti\b|"
    r"\bsimilar\s+jobs\b", re.I)


def taglia_correlati(testo: str) -> str:
    """Toglie dal testo la coda con gli annunci correlati (solo se prima c'è già un po' di testo)."""
    m = next((m for m in _RE_CORRELATI.finditer(testo) if m.start() >= 150), None)
    return testo[:m.start()].rstrip() if m else testo


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
    if base and not pdf and soup.body is not None and nodo is not soup.body:
        # Alcuni temi mettono gli allegati fuori dal testo dell'articolo.
        pdf = _link_pdf(soup.body, base, solo_sicuri=True)
    if base and not pdf:
        pdf = _pdf_nel_codice(html, base)
    _ripulisci(nodo)
    testo = pulisci(nodo.get_text(" "))
    if intera_se_vuota and len(testo) < 200 and soup.body is not None and nodo is not soup.body:
        # Pagine "lavora con noi" senza un blocco principale riconoscibile: si legge tutto il corpo.
        pdf = pdf or (_link_pdf(soup.body, base) if base else [])
        _ripulisci(soup.body)
        for tag in soup.body.find_all("header"):
            tag.decompose()
        testo = pulisci(soup.body.get_text(" "))
    testo = taglia_correlati(testo)
    return {"titolo": taglia_titolo(titolo), "testo": testo, "pubblicato": pubblicato, "pdf": pdf}


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
        visti[norm] = {"url": url, "titolo": taglia_titolo(titolo), "pdf": p.path.lower().endswith(".pdf")}
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


TAG_FEED = ("rss", "feed", "rdf")


def info_feed(xml: str) -> tuple[str, str]:
    """Che cosa è arrivato: il tipo di radice («rss», «feed»… o «html» se è una pagina) e il suo titolo."""
    radice = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    titolo = ""
    for el in radice.iter():
        if _tag(el) == "title":
            titolo = senza_tag((el.text or "").strip())
            break
    return _tag(radice), titolo[:120]


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
            voci.append({"url": url, "titolo": taglia_titolo(titolo), "sommario": sommario[:600],
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
            comuni.append({"nome": r["nome"], "km": int(r["km"]), "minuti": int(r["minuti"]), "provincia": r.get("provincia") or None,
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


_CAPOLUOGHI = {"Bolzano", "Bozen", "Trento", "Trient"}
_RE_ENTE_PROVINCIALE = re.compile(r"(?:provinc\w*|provinz|tribunal\w*|\w*gericht|\btar|trga|regione|region|bollettino|"
                                  r"amtsblatt|agenzia|universit\w*|autonom\w*)\W+(?:\w+\W+){0,2}$", re.I)


def _citazioni(nome: str, testo: str) -> int:
    """Quante volte il testo nomina il comune come luogo (non come provincia, tribunale, ente…)."""
    dove = _occorrenze(nome, testo)
    if nome not in _CAPOLUOGHI:
        return len(dove)
    return sum(1 for p in dove if not _RE_ENTE_PROVINCIALE.search(testo[max(0, p - 45): p])
               and not re.match(r"\w+\s*[-–]\s*(?:S[üu]dtirol|Alto Adige)", testo[p: p + 40]))


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
            k = _citazioni(nome, testo)
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
_AGG = r"(?:(?:lord\w+|nett\w+|o[mn]nicomprensiv\w+|orari\w+)\s*)*"
_UNITA = r"(?:/|all['’]\s*|l['’]\s*|a\s+|per\s+(?:ogni\s+|ciascuna\s+)?|pro\s+)?\s*(?:h\b|ora\b|orari\w*|stunde)"
RE_EURO_ORA = [
    re.compile(_NUM + r"\s*" + _EURO + r"\s*" + _AGG + _UNITA, re.I),
    re.compile(_EURO + r"\s*" + _NUM + r"\s*(?:\([^)]{0,40}\)\s*)?" + _AGG + _UNITA, re.I),
    re.compile(r"(?:compenso|tariffa|corrispettivo|importo|retribuzione)\s+(?:\w+\s+){0,3}?orari\w+\D{0,90}?"
               r"(?:" + _EURO + r"\s*" + _NUM + r"|" + _NUM + r"\s*" + _EURO + r")", re.I),
    re.compile(r"stunden(?:lohn|satz|honorar)\D{0,30}?(?:" + _EURO + r"\s*" + _NUM + r"|" + _NUM + r"\s*" + _EURO + r")", re.I),
]
_IMPORTO = r"(?:" + _EURO + r"\s*\d[\d.]*(?:,\d{1,2})?|\d[\d.]*(?:,\d{1,2})?\s*" + _EURO + r")"
RE_EURO_TURNO = re.compile(_IMPORTO + r"\s*" + _AGG + r"(?:a|per|al|pro)\s+(?:turno|notte|accesso|prestazione|giornata|schicht|nacht)", re.I)
RE_EURO_MESE = re.compile(
    _IMPORTO + r"\s*" + _AGG + r"(?:al\s+mese|mensil\w*|/\s*mese|monatlich|l['’]anno|annu\w+|/\s*anno|all['’]anno)", re.I)

RE_STIPENDIO_ANNUO = re.compile(r"stipendio\s+(?:(?:tabellare|base|annuo|iniziale)\s+){1,3}(?:di\s+|pari\s+a\s+)?:?\s*"
                                + _EURO + r"\s*(\d{2,3}\.\d{3}(?:,\d{2})?)", re.I)

RE_SCADENZA_FORTE = re.compile(
    r"scadenz\w*|scade\b|termine\s+(?:di\s+)?(?:presentazione|ultimo|perentorio)|pervenire\s+entro|"
    r"entro\s+(?:e\s+non\s+oltre\s+)?(?:le\s+ore\s+[\d.:,]+\s+)?(?:del(?:\s+giorno)?|il(?:\s+giorno)?)\s|"
    r"entro\s+e\s+non\s+oltre|prorog\w*|bewerbungsfrist|einreichfrist|bis\s+(?:zum|spätestens)", re.I)
RE_SCADENZA_DEBOLE = re.compile(r"entro\b|termine\b|frist\w*", re.I)
_RE_DATA_ATTO = re.compile(
    r"(?:deliber\w*|determin\w*|decret\w*|provvediment\w*|beschlu\w*|dekret\w*)\s+"
    r"(?:\w+\s+){0,6}?(?:n\.?|nr\.?)\s*[\w/-]+\s*(?:di\s+data|in\s+data|del(?:l['’])?|dd\.?|vom)?\s*$", re.I)
_RE_FINE_FRASE = re.compile(r"(?<![\d\s])\s*[.!?]\s+(?=[A-ZÀ-ÖØ-Ý])")

RE_LINGUA = re.compile(
    r"bilingu|zweisprach|patentino|attestato\s+di\s+(?:bilinguismo|conoscenza)|deutschkenntnis|"
    r"lingua\s+tedesca|tedesco|gruppo\s+linguistico|sprachgruppe", re.I)

_STRUTTURE = [
    ("Stagionale o turistico", re.compile(r"stagional|soggiorn\w+[\s-]+vacanz|\bhotel\b|soccorso\s+traumatolog|saison", re.I)),
    ("Domiciliare", re.compile(r"domicil|hauspflege|hauskrankenpflege", re.I)),
    ("RSA o casa di riposo", re.compile(r"\brsa\b|a\.?\s?p\.?\s?s\.?\s?p\b|casa\s+di\s+riposo|residenza\s+(?:per\s+)?anzian|senioren(?:wohn)?heim|alte[nr]s?heim|pflegeheim|bürgerheim|"
                                         r"\bö\.?\s?b\.?\s?p\.?\s?b\b", re.I)),
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


_RE_ALTRO_IMPORTO = re.compile(r"(?:" + _EURO + r"\s*" + _NUM + r"|" + _NUM + r"\s*" + _EURO + r")(?![\d.])", re.I)
_RE_PER_MEDICI = re.compile(r"\s*(?:(?:lord|nett|orari|o[mn]nicomprensiv)\w*\s*)*(?:per\s+(?:i|ciascun)\s+|ai\s+)(?:medic|dirigent)", re.I)
_RE_INFERMIERE_VICINO = re.compile(r"infermier|krankenpfleg|pflegefach", re.I)


def estrai_compenso(testo: str) -> tuple[str | None, float | None]:
    """(testo da mostrare, euro all'ora se indicati).
    Se un avviso riporta più tariffe (es. medici e infermieri) vale quella più vicina alla parola «infermiere»."""
    trovati: list[tuple[int, float]] = []
    for rx in RE_EURO_ORA:
        for m in rx.finditer(testo):
            grezzo = next((g for g in m.groups() if g), None)
            if not grezzo:
                continue
            try:
                valore = _numero(grezzo)
            except ValueError:
                continue
            # «€ 85,00 per i medici specialisti»: la tariffa dei medici non è quella dell'infermiere.
            if 8 <= valore <= 150 and not _RE_PER_MEDICI.match(testo, m.end()):
                trovati.append((m.start(), valore))
            if rx is RE_EURO_ORA[2]:
                # «compenso orario … pari a € 85,00 per i medici … e a € 40,00 per gli infermieri» (ASUIT SLP 15/26):
                # gli importi che seguono nella stessa frase sono anch'essi orari.
                resto = testo[m.end(): m.end() + 300]
                fine = _RE_FINE_FRASE.search(resto)
                resto = resto[: fine.start()] if fine else resto
                for altro in _RE_ALTRO_IMPORTO.finditer(resto):
                    try:
                        v = _numero(next(g for g in altro.groups() if g))
                    except (ValueError, StopIteration):
                        continue
                    if 8 <= v <= 150 and not _RE_PER_MEDICI.match(resto, altro.end()):
                        trovati.append((m.end() + altro.start(), v))
    if trovati:
        trovati.sort()
        valore = trovati[0][1]
        if len({v for _, v in trovati}) > 1:
            citazioni = [m.start() for m in _RE_INFERMIERE_VICINO.finditer(testo)]
            if citazioni:
                valore = min(trovati, key=lambda t: min(abs(t[0] - c) for c in citazioni))[1]
        return f"{valore:g} €/h".replace(".", ","), valore
    for rx in (RE_EURO_TURNO, RE_EURO_MESE):
        m = rx.search(testo)
        if m:
            return pulisci(m.group(0))[:60], None
    m = RE_STIPENDIO_ANNUO.search(testo)
    if m:
        return f"stipendio base {m.group(1)} € l'anno, più indennità", None
    return None, None


def indizi_compenso(testo: str, massimo: int = 3) -> list[str]:
    """Messa a punto: le frasi dove si parla di soldi, quando il compenso non è stato riconosciuto."""
    frasi, ultimo = [], -200
    for m in re.finditer(r"€\s*\d|\beuro\s*\d|\d[\d.,]*\s*(?:€|euro\b)", testo, re.I):
        if m.start() - ultimo < 150:
            continue
        ultimo = m.start()
        frasi.append(pulisci(testo[max(0, m.start() - 80): m.end() + 60]))
        if len(frasi) >= massimo:
            break
    return frasi


def estrai_scadenza_frase(testo: str, oggi: date) -> tuple[date | None, str | None]:
    """La scadenza e la frase da cui è stata presa (così si può controllare a colpo d'occhio)."""
    def candidati(rx: re.Pattern) -> list[tuple[date, str]]:
        trovati = []
        for m in rx.finditer(testo):
            finestra = testo[m.end(): m.end() + 110]
            # La data deve stare nella stessa frase: «entro il 2 ottobre. AGGIORNAMENTO DEL 22/10/2026»
            # non è una scadenza al 22/10. Il punto dopo una cifra («20. November») non chiude la frase.
            fine = _RE_FINE_FRASE.search(finestra)
            if fine:
                finestra = finestra[: fine.start()]
            for d in RE_DATA.finditer(finestra):
                # «deliberazione n. 634 di data 13 agosto 2026» è la data di un atto, non una scadenza
                # (ASUIT: sotto il titolo «Date e scadenze» la prima data è quella della delibera).
                if _RE_DATA_ATTO.search(finestra[: d.start()]):
                    continue
                giorno = _data_da_match(d)
                if giorno and abs((giorno - oggi).days) < 730:
                    inizio = max(0, m.start() - 25)
                    if inizio:
                        inizio = testo.find(" ", inizio) + 1
                    frase = pulisci(testo[inizio: m.end() + d.end() + 12])
                    trovati.append((giorno, frase[:170]))
                    break
        return trovati

    trovate = candidati(RE_SCADENZA_FORTE) or candidati(RE_SCADENZA_DEBOLE)
    if not trovate:
        return None, None
    if re.search(r"prorog|verl[äa]nger", testo, re.I):
        return max(trovate, key=lambda t: t[0])
    return trovate[0]


def estrai_scadenza(testo: str, oggi: date) -> date | None:
    return estrai_scadenza_frase(testo, oggi)[0]


def estrai_turni(testo: str) -> tuple[str | None, dict]:
    etichette, segnali = [], {}
    # Più scelte («18, 20 und 22 Wochenstunden», «18, 24 o 30 ore settimanali»): si scrivono tutte.
    scelte = re.search(r"(?<![\d.,])((?:\d{1,2}\s*,\s*)+\d{1,2}|\d{1,2})\s+(?:und|e|o|oder|bzw\.?)\s+(\d{1,2})\s*"
                       r"(?:(?:h|ore|stunden)\s*(?:/|a|alla|pro|per)?\s*(?:settiman|woche)|wochenstunden)", testo, re.I)
    if scelte:
        numeri = [int(x) for x in re.findall(r"\d{1,2}", scelte.group(1))] + [int(scelte.group(2))]
        if all(4 <= n <= 48 for n in numeri) and len(set(numeri)) > 1:
            etichette.append(", ".join(map(str, numeri[:-1])) + f" o {numeri[-1]} h/settimana")
            segnali["ore_settimana"] = max(numeri)
    m = None if etichette else re.search(r"(?<![\d.,])(\d{1,2})(?:[.,]\d)?\s*(?:(?:h|ore|stunden)\s*(?:/|a|alla|pro|per)?\s*(?:settiman|woche)|wochenstunden)", testo, re.I)
    if m and 4 <= int(m.group(1)) <= 48:
        ore = int(m.group(1))
        etichette.append(f"{ore} h/settimana")
        segnali["ore_settimana"] = ore
    # Turni e ore al mese (risposte Benedetti e Vannetti, 25/11): «dai 7 ai 15 turni mensili per 8 h»,
    # «un massimo di 195 h al mese», «un minimo di 60/80 ore/mese», «120 Monatsstunden».
    tm = re.search(r"(?<![\d.,])(?:dai?\s+)?(\d{1,2})(?:\s*(?:-|–|a|ai|al|bis)\s*(\d{1,2}))?\s+(?:turni|dienste)\s+"
                   r"(?:mensili|al\s+mese|a\s+mese|/\s*mese|im\s+monat|pro\s+monat)(?:\s+(?:per|da|di|zu)\s+(\d{1,2})\s*(?:h\b|ore\b|stunden))?",
                   testo, re.I)
    if tm and 1 <= int(tm.group(1)) <= 31 and (not tm.group(2) or int(tm.group(1)) < int(tm.group(2)) <= 31):
        etichette.append((f"{tm.group(1)}–{tm.group(2)}" if tm.group(2) else tm.group(1)) + " turni/mese"
                         + (f" da {tm.group(3)} h" if tm.group(3) else ""))
    om = re.search(r"(?<![\d.,])(\d{2,3})(?:\s*(?:/|-|–)\s*(\d{2,3}))?\s*(?:(?:h|ore|stunden)\s*(?:/|al|a|per|pro|im)?\s*"
                   r"(?:mese\b|mensil|monat)|monatsstunden)", testo, re.I)
    if om and 10 <= int(om.group(1)) <= 250 and (not om.group(2) or int(om.group(1)) < int(om.group(2)) <= 250):
        prima = testo[max(0, om.start() - 30): om.start()]
        tipo = ("max " if re.search(r"(?:massimo|max\.?|fino\s+a|non\s+oltre|non\s+superiore\s+a|höchstens|bis\s+zu)\s*(?:di\s+)?$", prima, re.I)
                else "min. " if re.search(r"(?:minimo|almeno|min\.?|mindestens)\s*(?:di\s+)?$", prima, re.I) else "")
        etichette.append(tipo + (f"{om.group(1)}–{om.group(2)}" if om.group(2) else om.group(1)) + " h/mese")
        segnali["ore_mese"] = int(om.group(2) or om.group(1))
    # «12 ore» conta solo se descrive il turno: non quando è un limite («non oltre 12 ore»)
    # o un'eccezione («in relazione al periodo emergenziale… 12 ore»), come nell'avviso Vannetti.
    for m12 in re.finditer(r"\b12\s*(?:h\b|ore\b|stunden)", testo, re.I):
        inizio = max(testo.rfind(".", 0, m12.start()), testo.rfind(";", 0, m12.start())) + 1
        fine = [p for p in (testo.find(".", m12.end()), testo.find(";", m12.end())) if p >= 0]
        frase = testo[inizio: min(fine) if fine else len(testo)]
        prima = testo[max(inizio, m12.start() - 40): m12.start()]
        limite = re.search(r"(?:non\s+superiore\s+a(?:lle)?|non\s+oltre(?:\s+le)?|al\s+massimo|massimo\s+(?:di\s+)?|"
                           r"max\.?|höchstens|maximal)\s*$", prima, re.I)
        eccezione = re.search(r"emergenz|eccezional|straordinari|in\s+via\s+del\s+tutto|ausnahm|notfall", frase, re.I)
        if limite or eccezione:
            segnali.setdefault("dodici_escluso", pulisci(frase)[:160])
            continue
        etichette.append("turni da 12 h")
        segnali["dodici"] = True
        segnali.pop("dodici_escluso", None)
        break
    if re.search(r"\bnott[ei]\b|notturn|nachtdienst|nachtschicht|\bnächte", testo, re.I):
        etichette.append("notti")
        segnali["notti"] = True
    # «3 Schicht System», «Dreischichtbetrieb», «su tre turni»: mattina, pomeriggio e notte.
    if re.search(r"\b(?:3|drei)[\s-]*schicht|\bdreischicht|\b(?:su\s+)?(?:3|tre)\s+turni\b|\bturni\s+h\s?24\b", testo, re.I):
        if segnali.get("notti"):
            etichette.append("3 turni")
        else:
            etichette.append("3 turni (anche notti)")
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
            r"Seniorenwohnheim|Stiftung|Sozialgenossenschaft|Clinica|Poliambulatorio|Comunità|Hotel|Azienda|Istituto|INPS|INAIL)")
_RE_TAGLIO = re.compile(r"\s+(?:cerca|cercasi|ricerca|ricerchiamo|sucht|assume|seleziona|selezione|bando|concorso|avviso)\b.*$", re.I)


_ALIAS_DATORE = [
    (re.compile(r"azienda\s+provinciale\s+per\s+i\s+servizi\s+sanitari|\bAPSS\b|\bASUIT\b|"
                r"azienda\s+sanitaria\s+universitaria\s+integrata\s+del\s+trentino", re.I), "ASUIT (Trentino)"),
    (re.compile(r"azienda\s+sanitaria\s+dell['’]\s*alto\s+adige|s[üu]dtiroler\s+sanit[äa]tsbetrieb|\bSABES\b|\bASDAA\b", re.I),
     "ASDAA / SABES"),
]
_RE_ENTE_TESTO = (r"(?:A\.?\s?P\.?\s?S\.?\s?P\.?|RSA|Casa di (?:Cura|riposo)|(?:Società )?Cooperativa(?: Sociale)?|Fondazione|"
                  r"Seniorenwohnheim|Stiftung|Sozialgenossenschaft|Clinica|Altenheim|Altersheim|Pflegeheim|Wohn- und Pflegeheim)")
_RE_FINE_NOME = re.compile(r"\s+(?:via|viale|piazza|corso|tel|con sede|è|sono|ha|in|per|che|ist|sucht|cerca|ricerca|"
                           r"azienda pubblica|und|wir|unser\w*|la nostra|il nostro)\b.*$|\s*\d.*$|"
                           r"(?<!\bSt)(?<!\bS)(?<!\bDr)\.\s.*$", re.I)


def datore_noto(testo: str) -> str | None:
    for rx, nome in _ALIAS_DATORE:
        if rx.search(testo):
            return nome
    return None


def estrai_datore(titolo: str) -> str | None:
    """Nei titoli tipo 'APSP Vannetti – Rovereto – Selezione…' il datore è il primo pezzo.
    Se non si capisce con sicurezza, meglio None (nell'app compare il titolo)."""
    pezzi = [p.strip() for p in re.split(r"\s+[–—|-]\s+", titolo) if p.strip()]
    candidato = None
    if len(pezzi) >= 2 and re.match(_RE_ENTE, pezzi[0], re.I):
        candidato = pezzi[0]
    else:
        m = re.search("(" + _RE_ENTE + r"\s+[^,;:()–—|]{3,60})", titolo, re.I)
        candidato = m.group(1) if m else None
    if not candidato:
        return None
    candidato = pulisci(_RE_TAGLIO.sub("", candidato)).strip(" -–")
    if len(candidato) < 4 or candidato.lower() == titolo.lower().strip():
        return None
    if re.match(r"\S+\s+(?:a|ad|in|per|presso|con|e|che|da)\s", candidato, re.I) and \
            not re.match(r"(?:Istituto|Residenza)\s+per\s+(?:la|il|l['’]|gli|anziani)\b", candidato, re.I):
        return None  # "residenza a Trento": è una frase, non un nome ("Residenza per anziani X" invece sì)
    if not re.search(r"[a-zà-ü]", candidato) and len(candidato.split()) >= 3:
        candidato = _minuscole_nome(candidato)  # "RESIDENZA PER ANZIANI ANNENBERG" → "Residenza per anziani Annenberg"
    return (candidato[0].upper() + candidato[1:])[:80]


_PAROLE_PICCOLE = {"per", "di", "del", "della", "dei", "delle", "e", "la", "il", "lo", "gli", "in", "anziani", "da"}


_ACCENTI = {"A": "à", "E": "è", "I": "ì", "O": "ò", "U": "ù"}


def _minuscole_nome(nome: str) -> str:
    parole = []
    for p in nome.split():
        # «CITTA'» (maiuscolo senza accenti, scritto con l'apostrofo) → «Città» (22/11, Indeed)
        p = re.sub(r"([AEIOU])['’]$", lambda m: _ACCENTI[m.group(1)].upper(), p)
        if p.lower() in _PAROLE_PICCOLE:
            parole.append(p.lower())
        elif re.fullmatch(r"[A-ZÀ-Ü]{3,}\.", p):
            parole.append(p[0] + p[1:].lower())  # abbreviazioni: «SOC.» → «Soc.», «COOP.» → «Coop.»
        elif "." in p or p in ("RSA", "APSP", "ÖBPB") or re.fullmatch(r"\W*[A-Z](?:/[A-Z])+\W*", p):
            parole.append(p)  # sigle (S.S., A.P.S.P., RSA)
        else:
            parole.append(re.sub(r"^(\W*)(\w)", lambda m: m.group(1) + m.group(2).upper(), p.lower()))
    return " ".join(parole)


def nome_leggibile(nome: str | None) -> str | None:
    """Un nome di struttura tutto in maiuscolo («CITTA' AZZURRA SOC. COOP. BOLZANO») si riscrive
    in minuscolo leggibile, lasciando le sigle; gli altri nomi restano come sono."""
    if not nome or re.search(r"[a-zà-ü]", nome) or len(nome.split()) < 2:
        return nome
    return _minuscole_nome(nome)


_SIGLE_TITOLO = {"ASUIT", "APSS", "APSP", "ASDAA", "SABES", "RSA", "RSAO", "OSS", "OSA", "INPS", "OPI", "UPIPA", "ÖBPB",
                 "ENPAPI", "CCNL", "AIOP", "IVA", "TN", "BZ", "UO", "SC", "SLP", "SRL", "SPA", "ONLUS", "ASL", "ULSS", "PS"}


def _parola_titolo(p: str, prima: bool, seguente: str) -> str:
    nudo = re.sub(r"\W", "", p)
    if (nudo.upper() in _SIGLE_TITOLO or "." in p or re.search(r"\d", p) or re.fullmatch(r"\W*[A-Z](?:/[A-Z])+\W*", p)
            or (nudo.isalpha() and len(nudo) <= 3 and re.match(r"\d", seguente))):
        return p  # sigle e numeri: «SC 03/26», «M/F», «A.P.S.P.», «ASUIT»
    p = p.lower()
    return re.sub(r"^(\W*)(\w)", lambda m: m.group(1) + m.group(2).upper(), p) if prima else p


def taglia_titolo(titolo: str, massimo: int = 200) -> str:
    """Accorcia un titolo troppo lungo a fine parola, con «…» (ASUIT 24/11: «…DURANTE LA ST»)."""
    if len(titolo) <= massimo:
        return titolo
    corto = titolo[:massimo - 1]
    if " " in corto and not titolo[massimo - 1].isspace():
        corto = corto.rsplit(" ", 1)[0]
    return corto.rstrip(" ,;:–—-") + "…"


_RUOLO_MAIUSCOLO = re.compile(r"(?:INFERMIER|KRANKENPFLEG|PFLEGE|PERSONALE)[A-ZÀ-Ü/]*", re.I)


def _parola_maiuscola(p: str) -> bool:
    """Una parola scritta tutta in maiuscolo che non è una sigla («OPERA», non «ASUIT», «A.P.S.P.», «M/F», «03/26»)."""
    nudo = re.sub(r"\W", "", p)
    return (len(nudo) >= 2 and nudo.isalpha() and nudo.isupper() and "." not in p and "/" not in p
            and nudo.upper() not in _SIGLE_TITOLO)


def _maiuscole_nel_titolo(titolo: str) -> str:
    """In un titolo misto, i pezzi in maiuscolo (Sol spa, Indeed 25/11: «INFERMIERE - Trento e provincia»):
    se c'è la parola del ruolo sono una frase («INFERMIERE» → «Infermiere» a inizio frase, «infermiere» dentro);
    altrimenti due o più parole di fila sono un nome («OPERA ROMANI» → «Opera Romani»). Sigle e nomi singoli restano."""
    parole = titolo.split(" ")
    uscita, i = [], 0
    while i < len(parole):
        j = i
        while j < len(parole) and _parola_maiuscola(parole[j]):
            j += 1
        pezzo = parole[i:j]
        ruolo = any(_RUOLO_MAIUSCOLO.match(re.sub(r"^\W+", "", x)) for x in pezzo)
        if len(pezzo) >= 2 and not ruolo:
            uscita.append(_minuscole_nome(" ".join(pezzo)))
            i = j
            continue
        if ruolo:  # «CERCHIAMO INFERMIERE:I (m/f/d)» → «Cerchiamo infermiere:i (m/f/d)»: è una frase, non un nome
            frase = " ".join(pezzo).lower()
            if i == 0 or re.fullmatch(r"[-–—|:]+", parole[i - 1] or ""):
                frase = re.sub(r"^(\W*)(\w)", lambda m: m.group(1) + m.group(2).upper(), frase)
            uscita.append(frase)
            i = j
            continue
        uscita.append(parole[i])
        i += 1
    return " ".join(uscita)


def titolo_leggibile_maiuscolo(titolo: str, comuni: list[dict] | None = None) -> str:
    """Un titolo tutto in maiuscolo («INFERMIERE M/F», Indeed 24/11; avvisi ASUIT) si riscrive come frase:
    maiuscola all'inizio, sigle e numeri intatti, nomi dei comuni con la maiuscola (se passati)."""
    if titolo and re.search(r"[a-zà-ü]", titolo):
        return _maiuscole_nel_titolo(titolo)
    if not titolo or len(re.sub(r"\W", "", titolo)) <= 3:
        return titolo
    parole, uscita, inizio = titolo.split(), [], True
    for i, p in enumerate(parole):
        nuova = _parola_titolo(p, inizio, parole[i + 1] if i + 1 < len(parole) else "")
        inizio = inizio and nuova == p  # la maiuscola va alla prima parola che non è una sigla
        uscita.append(nuova)
    frase = " ".join(uscita)
    nomi = {n for c in comuni or [] for n in (c.get("nomi") or [c["nome"]])}
    nomi |= {unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode() for n in nomi}  # «Sèn Jan» scritto «SEN JAN»
    for nome in sorted(nomi, key=len, reverse=True):
        if len(nome) < 4:
            continue  # «Ala», «Dro»: parole troppo comuni per riconoscerle in un titolo
        schema = r"(?<![\wà-ü])" + re.escape(nome) + r"(?![\wà-ü])"
        frase = re.sub(schema, lambda m: " ".join(w if w.lower() in _PAROLE_PICCOLE else w[:1].upper() + w[1:]
                                                  for w in m.group(0).split(" ")), frase, flags=re.I)
    return frase


def estrai_datore_da_testo(testo: str) -> str | None:
    """Quando il titolo non nomina la struttura: la si cerca nelle prime righe dell'annuncio."""
    inizio = testo[:500]
    m = re.search("(" + _RE_ENTE_TESTO + r"\s+[^,;:()–—|\n]{3,70})", inizio)
    if not m:
        return None
    candidato = pulisci(_RE_FINE_NOME.sub("", _RE_TAGLIO.sub("", m.group(1)))).strip(" -–.")
    parole = candidato.split()
    if len(parole) < 2 or len(candidato) < 8:
        return None
    return " ".join(parole[:8])[:70]


def titolo_da_indirizzo(url: str) -> str:
    pezzo = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
    pezzo = re.sub(r"-\d+$", "", pezzo).replace("-", " ").replace("_", " ").strip()
    return (pezzo[:1].upper() + pezzo[1:])[:120]


_RE_ALTRI_PROFILI = re.compile(r"sozialbetreu|pflegehelf|heimgehilf|verwaltung|erzieh|\boss\b|\bosa\b|operator", re.I)


def titolo_leggibile(grezzo: str) -> str:
    """Titolo in italiano da un indirizzo in tedesco (es. «krankenpflegerinnen 7ter fe mit 18 20 und
    22 wochenstunden» → «Infermiere/a – part-time (18, 20 o 22 ore/settimana)»).
    Usa solo parole presenti nell'indirizzo; se non è un annuncio per infermieri lo lascia com'è."""
    t = grezzo.lower()
    if not re.search(r"krankenpfleg|pflegefach|infermier", t):
        return grezzo
    dettagli = []
    if re.search(r"rangordnung|graduatori", t):
        dettagli.append("graduatoria")
    if re.search(r"freiberuf|libera?\s+profession", t):
        dettagli.append("libera professione")
    if re.search(r"unbefrist|indeterminat", t):
        dettagli.append("a tempo indeterminato")
    elif re.search(r"befrist|provisorisch|determinat", t):
        dettagli.append("a tempo determinato")
    if re.search(r"vollzeit|tempo\s+pieno", t):
        dettagli.append("tempo pieno")
    ore = re.search(r"((?:\d{1,2}\s+)+)(?:und\s+(\d{1,2})\s+)?wochenstunden", t)
    if ore:
        numeri = ore.group(1).split() + ([ore.group(2)] if ore.group(2) else [])
        testo_ore = ", ".join(numeri[:-1]) + " o " + numeri[-1] if len(numeri) > 1 else numeri[0]
        dettagli.append(f"part-time ({testo_ore} ore/settimana)")
    elif re.search(r"teilzeit|part\s*time", t):
        dettagli.append("part-time")
    mesi = re.search(r"(\d{1,2})\s+monat", t)
    if mesi:
        dettagli.append(f"per {mesi.group(1)} mesi")
    titolo = "Infermiere/a" + (" – " + ", ".join(dettagli) if dettagli else "")
    if _RE_ALTRI_PROFILI.search(t):
        titolo += " (con altri profili)"
    return titolo


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


# Avvisi di ricerca (Google Alerts): accanto agli annunci arrivano articoli di giornale che parlano di
# infermieri (aggressioni, sindacati, carenza di personale). Sono notizie, non offerte.
_RE_SEZIONE_NOTIZIE = re.compile(r"/(cronaca|attualita|notizie|news|territori|politica|economia|salute|sanita)/", re.I)
_RE_TITOLO_NOTIZIA = re.compile(
    r"aggredit|aggression|violenz|spinton|picchiat|minacc|denunci|sindacat|\buil\b|\bcgil\b|\bcisl\b|nursind|"
    r"sciopero|protesta|incidente|\bmort[oaie]\b|arrestat|indagat|condannat|processo|tribunale|"
    r"carenza\s+di\s+(?:personale|infermieri)|mancano\s+(?:gli\s+)?infermieri|polemica|"
    r"licenziat|mobbing|ricors[oi]\b|sentenz|cassazione|\btar\b|giudice|diritto\s+del\s+lavoro", re.I)
# Segnali di un'offerta vera: se ci sono, l'articolo (o l'annuncio sul giornale) resta.
_RE_SEGNALE_OFFERTA = re.compile(
    r"\bcerc[ahoi]|\bricerc[ah]|selezion|avviso\s+pubblico|\bbando|concors|assum|assunzion|incaric|"
    r"offert[ae]\s+di\s+lavoro|posizion[ei]\s+apert|candidatur|candidars|libera\s+professione|partita\s+iva|"
    r"p\.\s?iva|collaborazion|lavora\s+con\s+noi|gesucht|wir\s+suchen|stellenangebot|graduatori", re.I)


# Notizie di politica sanitaria e sindacali (giro del 18/11, Nurse Times «Sanità privata: … tavolo … Parlamento»):
# il sommario dell'avviso può contenere parole da offerta («assunzioni», «contratto»), ma resta una notizia.
_RE_TITOLO_POLITICA = re.compile(
    r"parlament|\bgoverno\b|ministr[oaie]|manovra|emendament|legge\s+di\s+bilancio|\btavolo\b|accreditament|"
    r"diffid|vertenz|rinnovo\s+(?:del\s+)?contratt|interrogazion|mozion", re.I)
_RE_SINDACATI = re.compile(
    r"\b(?:fp\s+cgil|cisl\s+fp|uil\s+fp|nursind|nursing\s+up|fials)\b|politica\s*&\s*sindacat|"
    r"\bNT\s+News\b|egregio\s+direttore|lettera\s+al\s+direttore", re.I)


def e_notizia(titolo: str, url: str, sommario: str = "", testo: str = "") -> bool:
    """Articolo di giornale su infermieri, senza nulla che lo faccia somigliare a un'offerta."""
    if _RE_SEGNALE_OFFERTA.search(titolo):
        return False
    if _RE_TITOLO_POLITICA.search(titolo) or _RE_SINDACATI.search(f"{sommario} {(testo or '')[:400]}"):
        return True
    if _RE_SEGNALE_OFFERTA.search(sommario):
        return False
    return bool(_RE_TITOLO_NOTIZIA.search(titolo) or _RE_SEZIONE_NOTIZIE.search(url or ""))


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
    scadenza, frase_scadenza = estrai_scadenza_frase(tutto, oggi)
    return {
        "datore": estrai_datore(titolo) or estrai_datore_da_testo(testo),
        "contratto": estrai_contratto(tutto),
        "compenso": compenso,
        "euro_ora": euro_ora,
        "turni": turni,
        "segnali_turni": segnali,
        "zona": comune["nome"] if comune else None,
        "km": comune["km"] if comune else None,
        "minuti": comune["minuti"] if comune else None,
        "scadenza": scadenza.isoformat() if scadenza else None,
        "scadenza_frase": frase_scadenza,
        "cita_tedesco": bool(RE_LINGUA.search(tutto)),
        "in_tedesco": lingua_tedesca(testo),
        "struttura": estrai_struttura(titolo, testo),
        "estratto": frammento(testo, parole_infermiere) if testo else "",
    }
