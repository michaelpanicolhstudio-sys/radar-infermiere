"""Il giro quotidiano: legge le fonti, estrae gli annunci, li confronta con la memoria."""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

from . import estrai, punteggio

RADICE = Path(__file__).resolve().parent.parent
FILE_ANNUNCI = RADICE / "data" / "annunci.json"
FILE_FONTI = RADICE / "data" / "fonti_stato.json"
CARTELLA_REPORT = RADICE / "data" / "report"

CAMPI_CONFRONTO = ["titolo", "contratto", "compenso", "scadenza", "turni"]
NOMI_CAMPI = {"titolo": "titolo", "contratto": "contratto", "compenso": "compenso",
              "scadenza": "scadenza", "turni": "ore e turni"}


# --------------------------------------------------------------------------
# File
# --------------------------------------------------------------------------

def leggi_json(percorso: Path, predefinito):
    if percorso.exists():
        return json.loads(percorso.read_text(encoding="utf-8"))
    return predefinito


def scrivi_json(percorso: Path, dati) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")


def tutte_le_fonti(cfg: dict) -> list[dict]:
    fonti = [f for f in cfg.get("fonti", []) if f.get("attiva", True) and f.get("url")]
    for i, url in enumerate(cfg.get("feed_google_alerts") or [], start=1):
        fonti.append({"nome": f"Google Alerts {i}", "tipo": "rss", "url": url,
                      "affidabilita": "aggregatore", "solo_regione": True})
    return fonti


# --------------------------------------------------------------------------
# Raccolta
# --------------------------------------------------------------------------

def _impronta(a: dict) -> str:
    return hashlib.sha1(json.dumps([a.get(c) for c in CAMPI_CONFRONTO],
                                   ensure_ascii=False).encode()).hexdigest()[:12]


def _costruisci(cand: dict, testo: str, pubblicato, fonte: dict, cfg: dict,
                comuni: list[dict], oggi: date, avvisi: list[str]) -> dict | None:
    parole = cfg["parole"]
    titolo = cand["titolo"]
    tutto = f"{titolo} {cand.get('sommario', '')} {testo}"
    # Pertinenza: deve parlare di infermieri. Nelle bacheche dedicate (tutti_i_link) basta esserci.
    if not fonte.get("tutti_i_link") and not estrai.contiene(tutto, parole["infermiere"]):
        return None
    if estrai.contiene(titolo, parole["escludi_titolo"]) and not estrai.contiene(titolo, parole["infermiere"]):
        return None
    campi = estrai.estrai_campi(titolo, testo or cand.get("sommario", ""), comuni, oggi,
                                parole["infermiere"])
    if fonte.get("solo_regione") and not campi["zona"] and not estrai.RE_REGIONE.search(tutto):
        return None  # avviso di ricerca fuori dal Trentino-Alto Adige
    if fonte.get("datore"):
        campi["datore"] = fonte["datore"]
    if fonte.get("zona") and not campi["zona"]:
        c = next((c for c in comuni if c["nome"] == fonte["zona"]), None)
        if c:
            campi.update(zona=c["nome"], km=c["km"], minuti=c["minuti"])
    if campi["cita_tedesco"]:
        avvisi.append("Cita tedesco o bilinguismo")
    if not campi["zona"]:
        avvisi.append("Zona non riconosciuta")
    a = {
        "id": estrai.id_annuncio(cand["url"]),
        "url": cand["url"],
        "titolo": titolo,
        "fonte": fonte["nome"],
        "affidabilita": fonte.get("affidabilita", "aggregatore"),
        "pubblicato": pubblicato.isoformat() if pubblicato else None,
        "avvisi": avvisi,
        **campi,
    }
    a["punteggio"], a["dettaglio_punteggio"] = punteggio.calcola(a, cfg)
    a["impronta"] = _impronta(a)
    return a


def _dettaglio(cand: dict, fonte: dict, rete, cfg, comuni, oggi) -> dict | None:
    avvisi: list[str] = []
    testo, pubblicato = "", cand.get("pubblicato")
    if cand.get("pdf"):
        avvisi.append("Annuncio in PDF: dati non letti, apri il link")
    else:
        html, errore = rete.get(cand["url"])
        if errore:
            avvisi.append(f"Pagina non letta: {errore}")
        else:
            pagina = estrai.leggi_pagina(html)
            testo = pagina["testo"]
            pubblicato = pubblicato or pagina["pubblicato"]
            if len(cand["titolo"]) < 15 and pagina["titolo"]:
                cand = {**cand, "titolo": pagina["titolo"]}
            if len(testo) < 200:
                avvisi.append("Pagina quasi vuota (forse caricata in modo dinamico)")
    return _costruisci(cand, testo, pubblicato, fonte, cfg, comuni, oggi, avvisi)


def raccogli_fonte(fonte: dict, rete, cfg: dict, comuni: list[dict], oggi: date) -> dict:
    """Ritorna {annunci, candidati, errore}. 'candidati' = voci viste prima del filtro."""
    tipo = fonte.get("tipo", "elenco")
    massimo = int(cfg["rete"].get("max_annunci_per_fonte", 25))
    esito = {"annunci": [], "candidati": 0, "errore": None}

    if tipo == "pagina":
        html, errore = rete.get(fonte["url"])
        if errore:
            esito["errore"] = errore
            return esito
        pagina = estrai.leggi_pagina(html)
        esito["candidati"] = 1
        if len(pagina["testo"]) < 200:
            esito["errore"] = "pagina quasi vuota: forse è cambiata o è caricata in modo dinamico"
            return esito
        cand = {"url": fonte["url"], "titolo": pagina["titolo"] or fonte["nome"]}
        a = _costruisci(cand, pagina["testo"], pagina["pubblicato"], fonte, cfg, comuni, oggi, [])
        if a:
            esito["annunci"].append(a)
        return esito

    if tipo == "rss":
        xml, errore = rete.get(fonte["url"], robots=False)  # i feed sono fatti per essere letti da programmi
        if errore:
            esito["errore"] = errore
            return esito
        try:
            candidati = estrai.leggi_feed(xml)
        except ET.ParseError:
            esito["errore"] = "il feed non è leggibile (formato non valido): controlla il link"
            return esito
    else:  # elenco
        candidati, visti = [], set()
        for i, url in enumerate([fonte["url"]] + list(fonte.get("altre_pagine") or [])):
            html, errore = rete.get(url)
            if errore:
                if i == 0:
                    esito["errore"] = errore
                    return esito
                continue
            for c in estrai.link_da_elenco(html, url, cfg["parole"]["link"],
                                           bool(fonte.get("tutti_i_link"))):
                chiave = estrai.normalizza_url(c["url"])
                if chiave not in visti:
                    visti.add(chiave)
                    candidati.append(c)

    esito["candidati"] = len(candidati)
    for cand in candidati[:massimo]:
        if not cand.get("titolo"):
            continue
        a = _dettaglio(cand, fonte, rete, cfg, comuni, oggi)
        if a:
            esito["annunci"].append(a)
    return esito


# --------------------------------------------------------------------------
# Memoria e confronto con ieri
# --------------------------------------------------------------------------

def e_dipendente(a: dict) -> bool:
    return (a.get("contratto") or "").startswith(("Dipendente", "Concorso"))


def e_scaduto(a: dict, oggi: date) -> bool:
    return bool(a.get("scadenza")) and a["scadenza"] < oggi.isoformat()


def e_datato(a: dict, oggi: date, cfg: dict) -> bool:
    """Pubblicato da molto tempo e senza una scadenza ancora valida: probabilmente non è più aperto."""
    giorni = int(cfg.get("giorni_annuncio_datato", 120))
    if not a.get("pubblicato") or (a.get("scadenza") and a["scadenza"] >= oggi.isoformat()):
        return False
    return (oggi - date.fromisoformat(a["pubblicato"])).days > giorni


def segna_doppioni(memoria: dict, oggi: date) -> None:
    """Lo stesso bando visto su due siti (stessa zona, stessa scadenza, stesso tipo): ne resta uno."""
    gruppi: dict[tuple, list[dict]] = {}
    for a in memoria.values():
        a.pop("doppione_di", None)
        if a.get("scadenza") and a.get("zona") and not e_scaduto(a, oggi):
            famiglia = "piva" if "P.IVA" in (a.get("contratto") or "") else "altro"
            gruppi.setdefault((a["zona"], a["scadenza"], famiglia), []).append(a)
    for gruppo in gruppi.values():
        if len(gruppo) < 2:
            continue
        gruppo.sort(key=lambda a: (a.get("origine") != "manuale", -a["punteggio"], a["primo_visto"]))
        for altro in gruppo[1:]:
            altro["doppione_di"] = gruppo[0]["id"]


def visibile(a: dict, cfg: dict) -> bool:
    profilo = cfg.get("profilo", {})
    if a.get("doppione_di"):
        return False
    if not profilo.get("includi_dipendenti", True) and e_dipendente(a):
        return False
    limite = profilo.get("minuti_massimi")
    if limite and a.get("minuti") is not None and a["minuti"] > limite:
        return False
    return True


def aggiorna_memoria(memoria: dict, trovati: list[dict], fonti_lette: set[str],
                     oggi: date, cfg: dict) -> dict:
    """Unisce gli annunci di oggi alla memoria. Ritorna {nuovi, aggiornati}."""
    oggi_s = oggi.isoformat()
    nuovi, aggiornati = [], []
    visti_oggi = set()
    for a in trovati:
        visti_oggi.add(a["id"])
        vecchio = memoria.get(a["id"])
        if vecchio is None:
            a.update(primo_visto=oggi_s, ultimo_visto=oggi_s, novita="nuovo", data_novita=oggi_s, cambi=[])
            memoria[a["id"]] = a
            nuovi.append(a)
            continue
        cambi = []
        if vecchio.get("impronta") != a["impronta"]:
            for campo in CAMPI_CONFRONTO:
                if vecchio.get(campo) != a.get(campo):
                    cambi.append(f"{NOMI_CAMPI[campo]}: {vecchio.get(campo) or 'n.d.'} → {a.get(campo) or 'n.d.'}")
        a["primo_visto"] = vecchio.get("primo_visto", oggi_s)
        a["ultimo_visto"] = oggi_s
        # Annunci letti a mano: i dati controllati da una persona vincono su quelli automatici.
        # Fa eccezione la scadenza, che può essere prorogata.
        if vecchio.get("origine") == "manuale":
            for campo in ("titolo", "datore", "contratto", "compenso", "euro_ora", "turni", "segnali_turni",
                          "zona", "km", "minuti", "pubblicato"):
                if vecchio.get(campo) not in (None, "", {}):
                    a[campo] = vecchio[campo]
            if a.get("scadenza") is None:
                a["scadenza"] = vecchio.get("scadenza")
            a["origine"] = "manuale"
            a["nota_manuale"] = vecchio.get("nota_manuale")
            a["punteggio"], a["dettaglio_punteggio"] = punteggio.calcola(a, cfg)
            a["impronta"] = _impronta(a)
            cambi = ([f"scadenza: {vecchio.get('scadenza') or 'n.d.'} → {a['scadenza']}"]
                     if a.get("scadenza") != vecchio.get("scadenza") else [])
        if cambi:
            a.update(novita="aggiornato", data_novita=oggi_s, cambi=cambi)
            aggiornati.append(a)
        else:
            a.update(novita=vecchio.get("novita"), data_novita=vecchio.get("data_novita"),
                     cambi=vecchio.get("cambi", []))
        memoria[a["id"]] = a

    giorni = int(cfg.get("giorni_prima_di_togliere", 30))
    for ident, a in list(memoria.items()):
        if ident in visti_oggi:
            a.pop("sparito_dal", None)
            continue
        if a.get("origine") == "manuale":
            # Annunci inseriti a mano: restano finché non scadono (+7 giorni) o per 45 giorni.
            limite = (date.fromisoformat(a["scadenza"]) + timedelta(days=7)) if a.get("scadenza") \
                else date.fromisoformat(a["primo_visto"]) + timedelta(days=45)
            if oggi > limite:
                del memoria[ident]
            continue
        if a.get("fonte") not in fonti_lette:
            continue  # la fonte oggi non rispondeva: non si può dire che l'annuncio sia sparito
        a.setdefault("sparito_dal", oggi_s)
        if (oggi - date.fromisoformat(a["sparito_dal"])).days > giorni:
            del memoria[ident]
    return {"nuovi": nuovi, "aggiornati": aggiornati}


def aggiorna_stato_fonti(stato: dict, nome: str, esito: dict, oggi: date) -> str | None:
    """Tiene la storia di ogni fonte e ritorna un eventuale problema da segnalare."""
    s = stato.setdefault(nome, {"massimo_candidati": 0, "ultimo_ok": None, "giorni_a_zero": 0})
    if esito["errore"]:
        s["ultimo_errore"] = esito["errore"]
        return f"{nome}: {esito['errore']}"
    s.pop("ultimo_errore", None)
    if esito["candidati"] == 0:
        s["giorni_a_zero"] = s.get("giorni_a_zero", 0) + 1
        if s.get("massimo_candidati", 0) > 0:
            return (f"{nome}: oggi nessun annuncio nell'elenco, mentre prima ce n'erano "
                    f"(ultima lettura buona: {s.get('ultimo_ok')}). Il sito potrebbe aver cambiato struttura.")
        return f"{nome}: nessun link ad annunci trovato. Controlla l'indirizzo in config.yaml."
    s["giorni_a_zero"] = 0
    s["ultimo_ok"] = oggi.isoformat()
    s["massimo_candidati"] = max(s.get("massimo_candidati", 0), esito["candidati"])
    s["ultimi_candidati"] = esito["candidati"]
    return None


# --------------------------------------------------------------------------
# Giro completo
# --------------------------------------------------------------------------

def _riga(a: dict) -> dict:
    return {k: a.get(k) for k in ("id", "titolo", "datore", "contratto", "compenso", "zona", "minuti",
                                  "scadenza", "punteggio", "url", "cambi")}


def giro(cfg: dict, rete, oggi: date, registra=print) -> dict:
    comuni = estrai.carica_comuni(RADICE / "data" / "comuni.csv")
    memoria = leggi_json(FILE_ANNUNCI, {})
    stato_fonti = leggi_json(FILE_FONTI, {})

    trovati, problemi, fonti_lette = {}, [], set()
    for fonte in tutte_le_fonti(cfg):
        registra(f"• {fonte['nome']}")
        try:
            esito = raccogli_fonte(fonte, rete, cfg, comuni, oggi)
        except Exception as e:  # una fonte rotta non deve fermare le altre
            esito = {"annunci": [], "candidati": 0, "errore": f"errore imprevisto ({type(e).__name__}: {e})"}
        problema = aggiorna_stato_fonti(stato_fonti, fonte["nome"], esito, oggi)
        if problema:
            problemi.append(problema)
            registra(f"   ⚠ {problema}")
        if not esito["errore"] and esito["candidati"] > 0:
            fonti_lette.add(fonte["nome"])  # un elenco vuoto non prova che gli annunci siano spariti
        for a in esito["annunci"]:
            # Stesso annuncio da due fonti: vince la più affidabile.
            vecchio = trovati.get(a["id"])
            if not vecchio or a["punteggio"] > vecchio["punteggio"]:
                trovati[a["id"]] = a
        registra(f"   {esito['candidati']} voci, {len(esito['annunci'])} annunci pertinenti")

    novita = aggiorna_memoria(memoria, list(trovati.values()), fonti_lette, oggi, cfg)
    segna_doppioni(memoria, oggi)

    def aperto(a: dict) -> bool:
        return visibile(a, cfg) and not e_scaduto(a, oggi) and not e_datato(a, oggi, cfg)

    attivi = [a for a in memoria.values() if aperto(a) and not a.get("sparito_dal")]
    attivi.sort(key=lambda a: -a["punteggio"])
    tra7 = (oggi + timedelta(days=7)).isoformat()
    scadenze = sorted((a for a in attivi if a.get("scadenza") and a["scadenza"] <= tra7),
                      key=lambda a: a["scadenza"])
    report = {
        "data": oggi.isoformat(),
        "attivi": len(attivi),
        "nuovi": [_riga(a) for a in novita["nuovi"] if aperto(a)],
        "aggiornati": [_riga(a) for a in novita["aggiornati"] if aperto(a)],
        "top5": [_riga(a) for a in attivi[:5]],
        "scadenze7": [_riga(a) for a in scadenze],
        "problemi": problemi,
        "fonti_lette": len(fonti_lette),
        "fonti_totali": len(tutte_le_fonti(cfg)),
    }
    report["nuovi"].sort(key=lambda r: -r["punteggio"])

    scrivi_json(FILE_ANNUNCI, memoria)
    scrivi_json(FILE_FONTI, stato_fonti)
    scrivi_json(CARTELLA_REPORT / f"{oggi.isoformat()}.json", report)
    return report
