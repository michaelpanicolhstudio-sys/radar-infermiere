"""Elenco delle strutture che possono cercare infermieri, anche senza un annuncio aperto.

Tre fonti, in quest'ordine di precedenza:
1. data/strutture.csv — l'elenco scritto a mano (cliniche, cooperative, agenzie, correzioni): vince sempre.
2. Indice della Pubblica Amministrazione (IPA, open data ufficiale): tutte le APSP del Trentino e tutti gli
   enti pubblici per anziani dell'Alto Adige, con la PEC e il sito che gli enti stessi dichiarano.
3. Il sito della struttura: se manca l'email, si cerca nella home e nella pagina «contatti»
   (solo indirizzi dello stesso dominio del sito).

Il risultato automatico si salva in data/strutture_auto.json e si aggiorna una volta a settimana.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from . import estrai

ISTAT_COMUNI = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"
IPA_API = "https://indicepa.gov.it/ipa-dati/api/3/action/package_show?id=enti"
RE_PER_ANZIANI = re.compile(
    r"servizi\s+alla\s+persona|\bA\.?\s?P\.?\s?S\.?\s?P\b|pflege-?\s+und\s+betreuungsdienst|\b[ÖO]\.?\s?B\.?\s?P\.?\s?B\b|"
    r"seniorenwohnheim|altenheim|altersheim|pflegeheim|casa\s+di\s+riposo|residenza\s+per\s+anziani|seniorenheim", re.I)
PROVINCE_ISTAT = ("021", "022")   # 021 Bolzano, 022 Trento
GIORNI_AGGIORNAMENTO = 7


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _colonna(intestazioni: list[str], *pezzi: str) -> str | None:
    for h in intestazioni:
        n = _norm(h)
        if all(p in n for p in pezzi):
            return h
    return None


def _url_csv_ipa(rete) -> tuple[str | None, str | None]:
    testo, errore = rete.get(IPA_API)
    if errore:
        return None, f"IPA non raggiungibile ({errore})"
    try:
        risorse = json.loads(testo)["result"]["resources"]
    except Exception:
        return None, "IPA: risposta non riconosciuta"
    def tipo(r):
        return f"{r.get('format') or ''} {r.get('mimetype') or ''} {r.get('url') or ''}".lower()
    buone = [r for r in risorse if r.get("url") and re.search(r"csv|tsv|txt|text/plain|dump", tipo(r))]
    buone.sort(key=lambda r: (0 if "csv" in tipo(r) else 1))
    if buone:
        return buone[0]["url"], None
    elenco = "; ".join(f"{r.get('name')} [{r.get('format')}] {str(r.get('url'))[:90]}" for r in risorse[:8])
    return None, f"IPA: nessun file CSV nel dataset (risorse: {elenco})"


def leggi_istat(testo: str) -> dict[str, str]:
    """Codice ISTAT del comune (6 cifre) -> nome italiano, solo per le province di Trento e Bolzano."""
    lettore = csv.DictReader(io.StringIO(testo.lstrip("\ufeff")), delimiter=";")
    h = lettore.fieldnames or []
    c_cod = _colonna(h, "codicecomune", "alfanumerico") or _colonna(h, "codicecomune")
    c_nome = _colonna(h, "denominazione", "italiano") or _colonna(h, "denominazione")
    nomi = {}
    for r in lettore:
        codice = (r.get(c_cod) or "").strip().zfill(6)
        if codice.startswith(PROVINCE_ISTAT):
            nomi[codice] = (r.get(c_nome) or "").split("/")[0].strip()
    return nomi


def _comune_noto(nome: str | None, comuni: list[dict]) -> str | None:
    if not nome:
        return None
    for c in comuni:
        if any(n.lower() == nome.lower() for n in c["nomi"]):
            return c["nome"]
    return nome


def leggi_ipa(testo: str, comuni: list[dict], codici: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    """Dal CSV dell'IPA tiene solo gli enti per anziani delle province di Trento e Bolzano."""
    separatore = ";" if testo[:2000].count(";") > testo[:2000].count(",") else ","
    if testo[:3000].count("\t") > 5:
        separatore = "\t"
    lettore = csv.DictReader(io.StringIO(testo.lstrip("﻿")), delimiter=separatore)
    h = lettore.fieldnames or []
    c_nome = _colonna(h, "denominazione") or _colonna(h, "descrizione")
    c_istat = _colonna(h, "comune", "istat") or _colonna(h, "istat")
    c_prov = _colonna(h, "provincia")
    c_comune = next((x for x in h if _norm(x) in ("comune", "nomecomune", "denominazionecomune")), None)
    c_sito = _colonna(h, "sito")
    c_indirizzo = _colonna(h, "indirizzo")
    mail = [(x, _colonna(h, "tipo", "mail" + x[-1])) for x in h if re.fullmatch(r"mail\d", _norm(x))]
    info = {"colonne": h[:40], "righe": 0}
    trovate = []
    for r in lettore:
        info["righe"] += 1
        nome = (r.get(c_nome) or "").strip() if c_nome else ""
        if not nome or not RE_PER_ANZIANI.search(nome):
            continue
        istat = (r.get(c_istat) or "").strip() if c_istat else ""
        provincia = (r.get(c_prov) or "").strip().upper() if c_prov else ""
        if not (istat.zfill(6).startswith(PROVINCE_ISTAT) or provincia in ("TN", "BZ", "TRENTO", "BOLZANO")):
            continue
        email = pec = None
        for colonna, tipo in mail:
            indirizzo = (r.get(colonna) or "").strip().lower()
            if "@" not in indirizzo:
                continue
            if "pec" in (r.get(tipo) or "").lower() or re.search(r"pec|legalmail|postacert|cert\.", indirizzo.split("@")[1]):
                pec = pec or indirizzo
            else:
                email = email or indirizzo
        sito = (r.get(c_sito) or "").strip() if c_sito else ""
        if sito and not sito.startswith("http"):
            sito = "https://" + sito
        luogo = " ".join(x for x in [(r.get(c_comune) or "") if c_comune else "", (r.get(c_indirizzo) or "") if c_indirizzo else "", nome] if x)
        dal_codice = _comune_noto((codici or {}).get(istat.zfill(6)), comuni) if istat else None
        c = estrai.trova_comune(nome, luogo, comuni)
        comune = dal_codice or (c["nome"] if c else None) or (((r.get(c_comune) or "").title() or None) if c_comune else None)
        trovate.append({"nome": _bel_nome(nome), "tipo": "RSA pubblica", "comune": comune,
                        "email": email, "pec": pec, "sito": sito or None, "fonte": "IPA"})
    return trovate, info


def _bel_nome(nome: str) -> str:
    if nome.isupper():
        nome = nome.title()
    nome = re.sub(r"Azienda Pubblica (?:Di|di) Servizi (?:Alla|alla) Persona", "APSP", nome, flags=re.I)
    return re.sub(r"\s+", " ", nome).strip(" -")[:90]


def _stesso_dominio(email: str, sito: str) -> bool:
    d_mail = email.split("@")[-1].lower()
    d_sito = urlparse(sito).netloc.lower().removeprefix("www.")
    radice = ".".join(d_sito.split(".")[-2:])
    return bool(radice) and (d_mail == d_sito or d_mail.endswith("." + radice) or d_mail == radice)


def email_dal_sito(rete, sito: str) -> tuple[str | None, str | None]:
    """Email della struttura scritta sul suo sito (home o pagina contatti). Solo indirizzi del suo dominio."""
    html, errore = rete.get(sito)
    if errore:
        return None, errore
    pagine = [html]
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        if a["href"].lower().startswith("mailto:"):
            pagine.append(a["href"][7:].split("?")[0])
    contatti = next((a["href"] for a in soup.find_all("a", href=True)
                     if re.search(r"contatt|kontakt|dove-siamo|impressum", (a["href"] + " " + a.get_text(" ")).lower())), None)
    if contatti:
        url = urljoin(sito, contatti)
        if urlparse(url).netloc == urlparse(sito).netloc:
            altra, _ = rete.get(url)
            if altra:
                pagine.append(altra)
                for a in BeautifulSoup(altra, "html.parser").find_all("a", href=True):
                    if a["href"].lower().startswith("mailto:"):
                        pagine.append(a["href"][7:].split("?")[0])
    testo = " ".join(BeautifulSoup(p, "html.parser").get_text(" ") if "<" in p else p for p in pagine)
    for m in estrai._RE_EMAIL.finditer(testo):
        indirizzo = m.group(0).strip(".").lower()
        if _stesso_dominio(indirizzo, sito) and not re.search(r"pec|legalmail|postacert", indirizzo.split("@")[1]) \
                and not re.search(r"privacy|dpo|rpd|webmaster|noreply|no-reply", indirizzo):
            return indirizzo, None
    return None, "nessuna email del sito trovata"


def chiavi(s: dict) -> set[str]:
    k = {"n:" + estrai.chiave(s.get("nome") or "")}
    for campo in ("email", "pec"):
        if s.get(campo):
            k.add("m:" + s[campo].lower())
    if s.get("sito"):
        k.add("d:" + urlparse(s["sito"]).netloc.lower().removeprefix("www."))
    return k


def aggiorna(rete, comuni: list[dict], oggi: date, cache: dict, registra=print, massimo_siti: int = 40) -> tuple[dict, dict]:
    """Aggiorna l'elenco automatico (una volta a settimana). Ritorna (cache nuova, note per la diagnostica)."""
    note: dict = {}
    ultimo = cache.get("aggiornato_il")
    if ultimo and (oggi - date.fromisoformat(ultimo)).days < GIORNI_AGGIORNAMENTO and not cache.get("da_completare"):
        return cache, {"saltato": f"aggiornato il {ultimo}"}
    strutture = {s["nome"]: s for s in cache.get("strutture", [])}
    if not ultimo or (oggi - date.fromisoformat(ultimo)).days >= GIORNI_AGGIORNAMENTO:
        url, errore = _url_csv_ipa(rete)
        if url:
            testo, errore = rete.get(url, robots=False)  # file di dati aperti scaricato una volta a settimana
        if errore:
            note["ipa_errore"] = errore
            registra(f"⚠ Strutture: {errore}")
        else:
            istat = {}
            elenco, errore_istat = rete.get(ISTAT_COMUNI, robots=False)
            if elenco:
                istat = leggi_istat(elenco)
            note["istat"] = errore_istat or f"{len(istat)} comuni"
            nuove, info = leggi_ipa(testo, comuni, istat)
            note["ipa"] = {**info, "trovate": len(nuove)}
            for s in nuove:
                vecchia = strutture.get(s["nome"], {})
                s["email"] = s["email"] or vecchia.get("email")  # tiene l'email trovata sul sito
                strutture[s["nome"]] = s
            registra(f"• Strutture dall'IPA: {len(nuove)} enti pubblici per anziani in Trentino-Alto Adige")
            if nuove:
                cache["aggiornato_il"] = oggi.isoformat()  # se fallisce, si riprova al giro dopo
    # Email dal sito, poche alla volta: il resto al giro successivo.
    da_cercare = [s for s in strutture.values() if s.get("sito") and not s.get("email") and not s.get("sito_controllato")]
    for s in da_cercare[:massimo_siti]:
        email, errore = email_dal_sito(rete, s["sito"])
        s["sito_controllato"] = oggi.isoformat()
        if email:
            s["email"] = email
    note["siti_controllati"] = min(len(da_cercare), massimo_siti)
    cache["da_completare"] = len(da_cercare) > massimo_siti
    cache["strutture"] = sorted(strutture.values(), key=lambda s: s["nome"])
    return cache, note
