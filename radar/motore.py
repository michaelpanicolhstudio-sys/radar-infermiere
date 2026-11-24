"""Il giro quotidiano: legge le fonti, estrae gli annunci, li confronta con la memoria."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import estrai, punteggio

RADICE = Path(__file__).resolve().parent.parent
FILE_ANNUNCI = RADICE / "data" / "annunci.json"
FILE_FONTI = RADICE / "data" / "fonti_stato.json"
FILE_DIAGNOSTICA = RADICE / "data" / "diagnostica.json"
CARTELLA_REPORT = RADICE / "data" / "report"

CAMPI_A_MANO = ("titolo", "datore", "contratto", "compenso", "euro_ora", "turni", "segnali_turni",
                "zona", "km", "minuti", "pubblicato")
CAMPI_CONFRONTO = ["titolo", "contratto", "compenso", "scadenza", "turni"]
NOMI_CAMPI = {"titolo": "titolo", "contratto": "contratto", "compenso": "compenso",
              "scadenza": "scadenza", "turni": "ore e turni"}
AVVISO_BANDO_COMUNE = "Stesso bando anche per: "
AVVISO_DAL_DOPPIONE = "Preso dallo stesso bando su "
AVVISO_DAL_DATORE = "Preso da un altro annuncio dello stesso datore su "
# Dati che, se mancano nell'annuncio mostrato, si prendono da un suo doppione dello stesso bando.
STRUTTURE_DAL_LAVORO = ("Stagionale o turistico", "Domiciliare")
CAMPI_DAL_DOPPIONE = {"compenso": "compenso", "euro_ora": None, "email": "email", "pec": "PEC"}
# Tra annunci diversi dello stesso datore si prendono solo i dati del datore, mai compenso o date.
CAMPI_DEL_DATORE = {"email": "email", "pec": "PEC", "struttura": None}
# Si aumenta quando cambiano le regole di pertinenza: le pagine già scartate vengono riaperte una volta.
VERSIONE_REGOLE = 11
VERSIONE_PDF = 5      # cambia quando migliorano le regole: i PDF già letti vengono riletti
# Siti-bacheca: i loro indirizzi email non sono il contatto della struttura che cerca personale.
DOMINI_BACHECA = {"opi.tn.it", "opibz.it", "upipa.tn.it", "suedtirolerjobs.it", "fnopi.it", "google.com"}


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
        fonti.append({"nome": f"Google Alerts {i}", "tipo": "rss", "url": url, "affidabilita": "aggregatore",
                      "solo_regione": True, "puo_essere_vuota": True})
    return fonti


# --------------------------------------------------------------------------
# Stato di un annuncio
# --------------------------------------------------------------------------

def e_dipendente(a: dict) -> bool:
    return (a.get("contratto") or "").startswith(("Dipendente", "Concorso"))


def e_piva(a: dict) -> bool:
    c = a.get("contratto") or ""
    return "P.IVA" in c or c == "Collaborazione"


def e_scaduto(a: dict, oggi: date) -> bool:
    return bool(a.get("scadenza")) and a["scadenza"] < oggi.isoformat()


def e_datato(a: dict, oggi: date, cfg: dict) -> bool:
    """Pubblicato da molto tempo e senza una scadenza ancora valida: probabilmente non è più aperto."""
    giorni = int(cfg.get("giorni_annuncio_datato", 120))
    if not a.get("pubblicato") or (a.get("scadenza") and a["scadenza"] >= oggi.isoformat()):
        return False
    return (oggi - date.fromisoformat(a["pubblicato"])).days > giorni


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


def aperto(a: dict, oggi: date, cfg: dict) -> bool:
    return visibile(a, cfg) and not e_scaduto(a, oggi) and not e_datato(a, oggi, cfg)


def _impronta(a: dict) -> str:
    return hashlib.sha1(json.dumps([a.get(c) for c in CAMPI_CONFRONTO],
                                   ensure_ascii=False).encode()).hexdigest()[:12]


# --------------------------------------------------------------------------
# Lettura di un annuncio
# --------------------------------------------------------------------------

def _leggi_pdf(link_pdf: list[dict], titolo: str, rete, cfg: dict, comuni: list[dict], oggi: date,
               vecchio: dict | None) -> tuple[dict | None, list[str]]:
    """Legge i PDF allegati (avviso, bando). Ritorna (dati ricavati, indirizzi letti)."""
    opzioni = cfg.get("pdf") or {}
    if not opzioni.get("leggi", True) or not link_pdf:
        return None, []
    indirizzi = [p["url"] for p in link_pdf[: int(opzioni.get("massimo_per_annuncio", 2))]]
    if (vecchio and vecchio.get("pdf_letti") == indirizzi and vecchio.get("da_pdf") is not None
            and vecchio["da_pdf"].get("v") == VERSIONE_PDF):
        return vecchio["da_pdf"], indirizzi  # già letti in un giro precedente: non si riscaricano
    testi, errori = [], 0
    for indirizzo in indirizzi:
        dati, errore = rete.get_pdf(indirizzo, float(opzioni.get("massimo_mb", 8)))
        if errore:
            errori += 1
            continue
        testi.append(estrai.testo_pdf(dati, int(opzioni.get("massimo_pagine", 12))))
    if errori == len(indirizzi):
        return None, []  # nessun PDF scaricato: si riprova al prossimo giro
    testo = " ".join(t for t in testi if t)
    if len(testo) < 100:
        return {"caratteri": len(testo), "v": VERSIONE_PDF}, indirizzi
    campi = estrai.estrai_campi(titolo, testo, comuni, oggi, cfg["parole"]["infermiere"])
    da_pdf = {k: campi[k] for k in ("compenso", "euro_ora", "scadenza", "scadenza_frase", "turni", "segnali_turni",
                                    "zona", "km", "minuti", "cita_tedesco", "estratto")}
    da_pdf["v"] = VERSIONE_PDF
    if da_pdf["compenso"] is None:
        da_pdf["indizi_compenso"] = estrai.indizi_compenso(testo)
    # Il tipo di rapporto si legge solo dall'intestazione: più avanti i bandi citano la
    # "libera professione" tra le incompatibilità, e sarebbe un falso segnale.
    da_pdf["contratto"] = estrai.estrai_contratto(testo[:1500])
    da_pdf["caratteri"] = len(testo)
    da_pdf["infermiere"] = estrai.contiene(testo, cfg["parole"]["infermiere"])
    da_pdf.update(estrai.trova_email(testo, DOMINI_BACHECA))
    return da_pdf, indirizzi


def _costruisci(cand: dict, testo: str, pubblicato, fonte: dict, cfg: dict, comuni: list[dict], oggi: date,
                avvisi: list[str], da_pdf: dict | None = None, pdf_letti: list[str] | None = None,
                controlla_ruolo: bool = True) -> tuple[dict | None, str | None]:
    """Ritorna (annuncio, None) oppure (None, motivo dello scarto)."""
    parole = cfg["parole"]
    titolo = cand["titolo"]
    corpo = testo or cand.get("sommario", "")
    tutto = f"{titolo} {cand.get('sommario', '')} {testo}"
    pdf_utile = bool(da_pdf) and da_pdf.get("caratteri", 0) >= 100

    if estrai.contiene(titolo, parole["escludi_titolo"]) and not estrai.contiene(titolo, parole["infermiere"]):
        return None, "ruolo diverso (dal titolo)"
    if fonte.get("tipo") == "rss" and estrai.e_notizia(titolo, cand.get("url", ""), cand.get("sommario", ""), testo):
        return None, "notizia, non un'offerta di lavoro"
    if controlla_ruolo and estrai.ruolo_diverso(titolo, corpo):
        return None, "ruolo diverso (coordinamento, direzione o comando)"
    ha_infermiere = estrai.contiene(tutto, parole["infermiere"]) or (pdf_utile and da_pdf.get("infermiere"))
    # Nelle bacheche dedicate agli infermieri (tutti_i_link) la parola può mancare: basta esserci.
    if not fonte.get("tutti_i_link") and not ha_infermiere:
        return None, "non riguarda infermieri"

    campi = estrai.estrai_campi(titolo, corpo, comuni, oggi, parole["infermiere"])
    contatti = estrai.trova_email(corpo, DOMINI_BACHECA)
    if pdf_utile:
        presi = []
        for campo in ("contratto", "scadenza", "turni"):
            if campi.get(campo) is None and da_pdf.get(campo) is not None:
                campi[campo] = da_pdf[campo]
                presi.append(NOMI_CAMPI[campo])
                if campo == "scadenza":
                    campi["scadenza_frase"] = da_pdf.get("scadenza_frase")
                if campo == "turni":
                    campi["segnali_turni"] = da_pdf.get("segnali_turni") or {}
        # Pagina e bando PDF con due scadenze diverse: vale la più lontana. Una proroga si scrive
        # sulla pagina (più tardi del PDF); negli avvisi aperti la pagina dà le date di valutazione
        # periodica («candidature che perverranno entro il 26 ottobre») e il PDF la chiusura vera.
        if campi.get("scadenza") and da_pdf.get("scadenza") and da_pdf["scadenza"] > campi["scadenza"]:
            vecchia = campi["scadenza"]
            campi["scadenza"], campi["scadenza_frase"] = da_pdf["scadenza"], da_pdf.get("scadenza_frase")
            avvisi.append(f"Scadenza dal bando PDF (la pagina indica anche il "
                          f"{date.fromisoformat(vecchia).strftime('%d/%m/%Y')}: apri l'annuncio)")
        if campi.get("euro_ora") is None and (da_pdf.get("euro_ora") is not None
                                              or (campi.get("compenso") is None and da_pdf.get("compenso"))):
            campi["compenso"], campi["euro_ora"] = da_pdf.get("compenso"), da_pdf.get("euro_ora")
            presi.append("compenso")
        if campi.get("zona") is None and da_pdf.get("zona"):
            campi.update(zona=da_pdf["zona"], km=da_pdf.get("km"), minuti=da_pdf.get("minuti"))
        campi["cita_tedesco"] = campi["cita_tedesco"] or bool(da_pdf.get("cita_tedesco"))
        if len(corpo) < 120 and da_pdf.get("estratto"):
            campi["estratto"] = da_pdf["estratto"]
        contatti = {"email": contatti["email"] or da_pdf.get("email"), "pec": contatti["pec"] or da_pdf.get("pec")}
        if presi:
            avvisi.append("Dal PDF allegato: " + ", ".join(presi))
    elif da_pdf is not None and pdf_letti:
        avvisi.append("PDF allegato non leggibile (forse è una scansione): apri l'annuncio")

    if not campi["zona"] and estrai.fuori_regione(titolo, parole.get("fuori_regione", [])):
        return None, "fuori regione"
    if fonte.get("solo_regione") and not campi["zona"] and not estrai.RE_REGIONE.search(tutto):
        return None, "fuori regione"

    # Una "scadenza" uguale al giorno di pubblicazione è quasi sempre la data del post letta per errore.
    if campi["scadenza"] and pubblicato and campi["scadenza"] == pubblicato.isoformat():
        campi["scadenza"] = campi["scadenza_frase"] = None
    if fonte.get("datore"):
        campi["datore"] = fonte["datore"]
    elif not campi["datore"]:
        campi["datore"] = estrai.datore_noto(f"{titolo} {corpo[:800]}")
    if not campi["zona"]:
        # Strutture conosciute che negli annunci non scrivono il comune.
        vicino = f"{titolo} {campi['datore'] or ''} {corpo[:600]}".lower()
        for parola, nome in (cfg.get("zone_strutture") or {}).items():
            c = next((c for c in comuni if c["nome"] == nome), None)
            if c and str(parola).lower() in vicino:
                campi.update(zona=c["nome"], km=c["km"], minuti=c["minuti"])
                break
    if cand.get("datore") and not fonte.get("datore"):
        campi["datore"] = cand["datore"]
        # Il nome della struttura nell'elenco (es. «Altenheim St. Pankraz») dice dove si lavora:
        # vale più dei comuni citati nel testo o nel bando (es. «Bozen» come provincia o sede dell'ufficio).
        dal_nome = estrai.trova_comune(cand["datore"], "", comuni)
        if dal_nome:
            campi.update(zona=dal_nome["nome"], km=dal_nome["km"], minuti=dal_nome["minuti"])
    if campi.get("datore"):
        # Il nome dice che posto è («Seniorenheim Algund», «… ÖBPB»): vale anche quando il testo cita
        # chi la gestisce (Schloss Moos «Sozialgenossenschaft», 17/11). Restano «stagionale» e
        # «domiciliare» del testo, che dicono com'è il lavoro, non chi è il datore.
        dal_nome = estrai.estrai_struttura(campi["datore"], "")
        if dal_nome and campi.get("struttura") not in STRUTTURE_DAL_LAVORO:
            campi["struttura"] = dal_nome
    if fonte.get("zona") and (not campi["zona"] or fonte.get("tipo") == "pagina"):
        c = next((c for c in comuni if c["nome"] == fonte["zona"]), None)
        if c:
            campi.update(zona=c["nome"], km=c["km"], minuti=c["minuti"])
    if campi["in_tedesco"]:
        avvisi.append("Annuncio in tedesco")
    elif campi["cita_tedesco"]:
        avvisi.append("Cita tedesco o bilinguismo")
    if not campi["zona"]:
        # «Provincia di Trento» da sola (avvisi dei portali, IQVIA 23/11): si dice la provincia, il comune resta n.d.
        prov = re.search(r"provincia\s+(?:autonoma\s+)?di\s+(trento|bolzano)|provinz\s+bozen", f"{titolo} {cand.get('sommario', '')}", re.I)
        if prov:
            avvisi.append(f"Zona: provincia di {(prov.group(1) or 'Bolzano').capitalize()}, comune non indicato")
        else:
            avvisi.append("Zona non riconosciuta")

    tipo = fonte.get("tipo", "elenco")
    a = {
        "id": cand.get("id") or estrai.id_annuncio(cand["url"]),
        "url": cand["url"],
        "titolo": titolo,
        "fonte": fonte["nome"],
        "tipo_fonte": tipo,
        "affidabilita": fonte.get("affidabilita", "aggregatore"),
        # La data di una pagina fissa "lavora con noi" non è la data dell'annuncio.
        "pubblicato": pubblicato.isoformat() if (pubblicato and tipo != "pagina") else None,
        "avvisi": avvisi,
        "letto_il": oggi.isoformat(),
        "regole": VERSIONE_REGOLE,
        "pdf_letti": pdf_letti or [],
        "da_pdf": da_pdf if pdf_letti else None,
        **campi,
        **contatti,
    }
    a["punteggio"], a["dettaglio_punteggio"] = punteggio.calcola(a, cfg)
    a["impronta"] = _impronta(a)
    return a, None


def _passeggero(errore: str) -> bool:
    """Errori che non dicono nulla sull'annuncio (rete lenta, server occupato), a differenza di un 404."""
    if errore.startswith(("tempo scaduto", "errore di rete")):
        return True
    m = re.match(r"risposta HTTP (\d+)", errore)
    return bool(m) and (m.group(1) == "429" or m.group(1).startswith("5"))


def _dettaglio(cand: dict, fonte: dict, rete, cfg: dict, comuni: list[dict], oggi: date,
               vecchio: dict | None, nota: dict | None = None) -> tuple[dict | None, str | None]:
    avvisi: list[str] = []
    testo, pubblicato, link_pdf = "", cand.get("pubblicato"), []
    if cand.get("pdf"):
        link_pdf = [{"url": cand["url"], "testo": cand["titolo"]}]
    else:
        html, errore = rete.get(cand["url"])
        if errore == "è un PDF":
            link_pdf = [{"url": cand["url"], "testo": cand["titolo"]}]
        elif errore and vecchio and vecchio.get("estratto") and _passeggero(errore):
            # Il sito oggi non risponde: resta la lettura buona dell'ultima volta (si riprova domani).
            return {**vecchio, "_riusato": True}, None
        elif errore:
            avvisi.append(f"Pagina non letta: {errore}")
        else:
            pagina = estrai.leggi_pagina(html, cand["url"])
            testo = pagina["testo"]
            pubblicato = pubblicato or pagina["pubblicato"]
            link_pdf = pagina["pdf"]
            if nota is not None and len(link_pdf) < 2 and len(nota.setdefault("pdf_scartati", [])) < 6:
                # 20/11: Vannetti P.IVA, trovata solo la proroga: quali altri PDF ha la pagina?
                altri = estrai.pdf_scartati_nel_codice(html, cand["url"])
                if altri:
                    nota["pdf_scartati"].append({"url": cand["url"], "presi": [p["url"] for p in link_pdf], "lasciati": altri})
            if nota is not None and not link_pdf and len(nota.setdefault("senza_pdf", [])) < 6:
                dubbi = estrai.allegati_dubbi(html, cand["url"])
                if dubbi:
                    nota["senza_pdf"].append({"url": cand["url"], "link": dubbi})
            if fonte.get("link_e_datore"):
                # Nell'elenco il link porta il nome della struttura: il titolo vero è nella pagina.
                vero = pagina["titolo"] if estrai.contiene(pagina["titolo"], cfg["parole"]["infermiere"]) \
                    else estrai.titolo_leggibile(estrai.titolo_da_indirizzo(cand["url"]))
                cand = {**cand, "datore": cand["titolo"], "titolo": vero or cand["titolo"]}
            elif len(cand["titolo"]) < 15 and pagina["titolo"]:
                cand = {**cand, "titolo": pagina["titolo"]}
            if len(testo) < 200 and not link_pdf:
                avvisi.append("Testo molto breve: l'annuncio potrebbe essere un'immagine. Apri il link")
    da_pdf, pdf_letti = _leggi_pdf(link_pdf, cand["titolo"], rete, cfg, comuni, oggi, vecchio)
    return _costruisci(cand, testo, pubblicato, fonte, cfg, comuni, oggi, avvisi, da_pdf, pdf_letti)


def _riusabile(vecchio: dict, oggi: date, cfg: dict) -> bool:
    """Annunci datati o scaduti da tempo: non serve riaprirli ogni giorno."""
    letto = vecchio.get("letto_il")
    if vecchio.get("regole") != VERSIONE_REGOLE:
        return False  # le regole sono cambiate: si rilegge
    if not letto or (oggi - date.fromisoformat(letto)).days >= int(cfg.get("giorni_rilettura_datati", 30)):
        return False
    scaduto_da_tempo = e_scaduto(vecchio, oggi) and (oggi - date.fromisoformat(vecchio["scadenza"])).days > 14
    return e_datato(vecchio, oggi, cfg) or scaduto_da_tempo


def raccogli_fonte(fonte: dict, rete, cfg: dict, comuni: list[dict], oggi: date, memoria: dict,
                   stato: dict, diagnostica: dict | None = None) -> dict:
    """Ritorna {annunci, candidati, errore, scartati, riusati, letti}."""
    tipo = fonte.get("tipo", "elenco")
    massimo = int(cfg["rete"].get("max_annunci_per_fonte", 25))
    esito = {"annunci": [], "candidati": 0, "errore": None, "scartati": 0, "riusati": 0, "letti": 0}
    nota = {"pagine": [], "accettati": [], "scartati": []}
    if diagnostica is not None:
        diagnostica[fonte["nome"]] = nota

    if tipo == "pagina":
        html, errore = rete.get(fonte["url"])
        if errore:
            esito["errore"] = errore
            return esito
        pagina = estrai.leggi_pagina(html, fonte["url"], intera_se_vuota=True)
        esito["candidati"] = esito["letti"] = 1
        nota["pagine"].append({"url": fonte["url"], "caratteri": len(pagina["testo"])})
        if len(pagina["testo"]) < 200:
            esito["errore"] = "pagina quasi vuota: forse è cambiata o è caricata in modo dinamico"
            return esito
        cand = {"url": fonte["url"], "titolo": fonte.get("titolo") or pagina["titolo"] or fonte["nome"]}
        nota["pagine"][-1]["inizio"] = pagina["testo"][:400]
        nota["pagine"][-1]["pdf"] = [x["url"] for x in pagina["pdf"][:6]]
        a, motivo = _costruisci(cand, pagina["testo"], None, fonte, cfg, comuni, oggi, [], controlla_ruolo=False)
        if a:
            esito["annunci"].append(a)
            nota["accettati"].append(a["titolo"][:90])
        else:
            nota["scartati"].append([cand["titolo"][:90], motivo])
        return esito

    if tipo == "rss":
        xml, errore = rete.get(fonte["url"], robots=False)  # i feed sono fatti per essere letti da programmi
        if errore:
            esito["errore"] = errore
            return esito
        try:
            radice, titolo_feed = estrai.info_feed(xml)
            candidati = estrai.leggi_feed(xml)
        except ET.ParseError:
            esito["errore"] = "il feed non è leggibile (formato non valido): controlla il link"
            return esito
        if radice not in estrai.TAG_FEED:
            # Una pagina web (accesso, consenso) non è «un feed senza novità».
            esito["errore"] = f"il link non porta a un feed ma a una pagina web («{titolo_feed or radice}»): controlla il link"
            return esito
        nota["pagine"].append({"url": "feed", "candidati": len(candidati), "titolo_feed": titolo_feed,
                               "caratteri": len(xml or "")})
    else:  # elenco
        candidati, visti = [], set()
        parole_link = fonte.get("parole_link") or cfg["parole"]["link"]
        for i, url in enumerate([fonte["url"]] + list(fonte.get("altre_pagine") or [])):
            html, errore = rete.get(url)
            if errore:
                nota["pagine"].append({"url": url, "errore": errore})
                if i == 0:
                    esito["errore"] = errore
                    return esito
                continue
            trovati = estrai.link_da_elenco(html, url, parole_link, bool(fonte.get("tutti_i_link")))
            pagina_nota = {"url": url, "candidati": len(trovati)}
            if not trovati and i == 0:
                pagina_nota["link_in_pagina"] = estrai.tutti_i_link(html, url, 40)
            nota["pagine"].append(pagina_nota)
            for c in trovati:
                chiave = estrai.normalizza_url(c["url"])
                if chiave not in visti:
                    visti.add(chiave)
                    candidati.append(c)

    esito["candidati"] = len(candidati)
    scarti = stato.setdefault("scarti", {})
    giorni_scarti = int(cfg.get("giorni_memoria_scarti", 14))
    for cand in candidati[:massimo]:
        if not cand.get("titolo"):
            continue
        ident = estrai.id_annuncio(cand["url"])
        vecchio = memoria.get(ident)
        scarto = scarti.get(ident)
        if scarto and (oggi - date.fromisoformat(scarto["d"])).days < giorni_scarti and scarto.get("t") == cand["titolo"][:90] \
                and scarto.get("u"):  # gli scarti di prima del 18/11 senza indirizzo si riaprono una volta
            esito["scartati"] += 1  # già aperto e scartato di recente: non si riapre
            # ...ma resta visibile in diagnostica, con titolo intero e indirizzo, per un controllo a mano.
            nota.setdefault("gia_scartati", []).append(
                [cand["titolo"][:200], scarto.get("m"), cand["url"], scarto["d"]])
            continue
        if vecchio and _riusabile(vecchio, oggi, cfg):
            esito["annunci"].append({**vecchio, "_riusato": True})
            esito["riusati"] += 1
            continue
        a, motivo = _dettaglio(cand, fonte, rete, cfg, comuni, oggi, vecchio, nota)
        esito["letti"] += 1
        if a:
            esito["annunci"].append(a)
            scarti.pop(ident, None)
            nota["accettati"].append(a["titolo"][:90])
        else:
            scarti[ident] = {"d": oggi.isoformat(), "m": motivo, "t": cand["titolo"][:90], "u": cand["url"]}
            if len(cand["titolo"]) > 90:
                scarti[ident]["tl"] = cand["titolo"][:200]  # «t» resta a 90 lettere: serve al confronto
            esito["scartati"] += 1
            nota["scartati"].append([cand["titolo"][:200], motivo, cand["url"]])
    for ident, scarto in list(scarti.items()):
        if (oggi - date.fromisoformat(scarto["d"])).days > 45:
            del scarti[ident]
    return esito


# --------------------------------------------------------------------------
# Memoria e confronto con ieri
# --------------------------------------------------------------------------

GIORNI_VA_E_TORNA = 2  # un dato che torna com'era entro questi giorni era un'oscillazione della pagina


def _inverso(cambio: str) -> str:
    nome, _, resto = cambio.partition(": ")
    prima, _, dopo = resto.partition(" → ")
    return f"{nome}: {dopo} → {prima}"


def _torna_come_prima(cambi: list[str], vecchio: dict, oggi: date) -> bool:
    """Vero se i cambi di oggi annullano esattamente l'ultimo aggiornamento, arrivato da poco."""
    if not vecchio.get("prima_del_cambio") or vecchio.get("novita") != "aggiornato":
        return False
    try:
        giorni = (oggi - date.fromisoformat(vecchio.get("data_novita") or "")).days
    except ValueError:
        return False
    return 0 <= giorni <= GIORNI_VA_E_TORNA and sorted(cambi) == sorted(_inverso(c) for c in vecchio.get("cambi") or [])


def aggiorna_memoria(memoria: dict, trovati: list[dict], fonti_lette: set[str], fonti_attive: set[str],
                     scartati: set[str], oggi: date, cfg: dict) -> dict:
    """Unisce gli annunci di oggi alla memoria. Ritorna {nuovi, aggiornati}."""
    oggi_s = oggi.isoformat()
    nuovi, aggiornati = [], []
    visti_oggi = set()
    for a in memoria.values():
        togli_dal_doppione(a)  # i dati presi da un doppione non sono del sito: non contano nei confronti
    for a in trovati:
        visti_oggi.add(a["id"])
        vecchio = memoria.get(a["id"])
        if a.pop("_riusato", False) and vecchio is not None:
            vecchio["ultimo_visto"] = oggi_s  # ancora in elenco, non riletto
            continue
        if vecchio is None:
            a.update(primo_visto=oggi_s, ultimo_visto=oggi_s, novita="nuovo", data_novita=oggi_s, cambi=[])
            memoria[a["id"]] = a
            nuovi.append(a)
            continue
        cambi = []
        # Se sono cambiate le regole di lettura, le differenze vengono dal Radar, non dall'annuncio:
        # non sono novità per Michael. Fa eccezione la scadenza (una proroga non va persa).
        regole_cambiate = vecchio.get("regole") != a.get("regole")
        if vecchio.get("impronta") != a["impronta"]:
            for campo in CAMPI_CONFRONTO:
                if regole_cambiate and campo != "scadenza":
                    continue
                if vecchio.get(campo) != a.get(campo):
                    cambi.append(f"{NOMI_CAMPI[campo]}: {vecchio.get(campo) or 'n.d.'} → {a.get(campo) or 'n.d.'}")
        a["primo_visto"] = vecchio.get("primo_visto", oggi_s)
        a["ultimo_visto"] = oggi_s
        # Annunci letti a mano: i dati controllati da una persona vincono su quelli automatici.
        # Fa eccezione la scadenza, che può essere prorogata.
        if vecchio.get("origine") == "manuale":
            # Vincono solo i campi scritti davvero a mano (`campi_manuali`, fissati al primo giro):
            # un dato letto in automatico e salvato non deve diventare «a mano» e restare fermo
            # (Vannetti: turni da 12 h presi da una lettura vecchia del PDF, mai più corretti).
            manuali = vecchio.get("campi_manuali")
            if manuali is None:
                manuali = [c for c in CAMPI_A_MANO if vecchio.get(c) not in (None, "", {})]
            for campo in manuali:
                if vecchio.get(campo) not in (None, "", {}):
                    a[campo] = vecchio[campo]
            a["campi_manuali"] = manuali
            if a.get("scadenza") is None:
                a["scadenza"] = vecchio.get("scadenza")
            a["origine"] = "manuale"
            a["nota_manuale"] = vecchio.get("nota_manuale")
            if vecchio.get("scadenze"):
                a["scadenze"] = vecchio["scadenze"]
            a["impronta"] = _impronta(a)
            cambi = ([f"scadenza: {vecchio.get('scadenza') or 'n.d.'} → {a['scadenza']}"]
                     if a.get("scadenza") != vecchio.get("scadenza") else [])
        prima = vecchio.get("prima_del_cambio")
        if cambi and _torna_come_prima(cambi, vecchio, oggi):
            # La pagina è tornata com'era (Vinzenzhaus 19/11, «part-time» per 10 minuti): niente novità,
            # si rimette lo stato di prima del cambio annullato.
            a.update(novita=prima.get("novita"), data_novita=prima.get("data_novita"), cambi=prima.get("cambi") or [])
            a.pop("prima_del_cambio", None)
        elif cambi:
            a.update(novita="aggiornato", data_novita=oggi_s, cambi=cambi,
                     prima_del_cambio={"novita": vecchio.get("novita"), "data_novita": vecchio.get("data_novita"),
                                       "cambi": vecchio.get("cambi", [])})
            aggiornati.append(a)
        else:
            a.update(novita=vecchio.get("novita"), data_novita=vecchio.get("data_novita"),
                     cambi=vecchio.get("cambi", []))
            if prima:
                a["prima_del_cambio"] = prima
        memoria[a["id"]] = a

    giorni = int(cfg.get("giorni_prima_di_togliere", 30))
    for ident, a in list(memoria.items()):
        cambio = passa_alla_prossima_scadenza(a, oggi)
        if cambio:
            a.update(novita="aggiornato", data_novita=oggi_s, cambi=[cambio])
            if a not in aggiornati:
                aggiornati.append(a)
        # Annunci a mano (non riletti): il tipo di struttura, se manca, lo dicono il nome del datore,
        # l'elenco Strutture di Michael o il titolo scritto a mano.
        if not a.get("struttura"):
            a["struttura"] = struttura_senza_lettura(a)
        # I pesi possono essere cambiati in config: il punteggio si ricalcola sempre.
        a["punteggio"], a["dettaglio_punteggio"] = punteggio.calcola(a, cfg)
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
        if ident in scartati:
            del memoria[ident]  # riletto e giudicato non pertinente
            continue
        if a.get("tipo_fonte") == "rss":
            if a.get("origine") != "manuale" and estrai.e_notizia(a.get("titolo") or "", a.get("url") or "", "", a.get("estratto") or ""):
                del memoria[ident]  # articolo di giornale entrato con regole vecchie (giro del 16/11)
                continue
            # Gli avvisi di ricerca scorrono via dal feed: non vuol dire che l'annuncio sia chiuso.
            if (oggi - date.fromisoformat(a.get("ultimo_visto", oggi_s))).days > giorni:
                del memoria[ident]
            continue
        if a.get("fonte") in fonti_attive and a.get("fonte") not in fonti_lette:
            continue  # la fonte oggi non rispondeva: non si può dire che l'annuncio sia sparito
        a.setdefault("sparito_dal", oggi_s)
        if (oggi - date.fromisoformat(a["sparito_dal"])).days > giorni:
            del memoria[ident]
    return {"nuovi": nuovi, "aggiornati": aggiornati}


def _norm_nome(s: str, senza_parentesi: bool = True) -> str:
    s = (s or "").lower()
    if senza_parentesi:  # «Italiassistenza (sede di Bolzano)» nell'elenco; nel datore la parentesi è un nome
        s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b(?:s\.?p\.?a|s\.?r\.?l|srl|spa|onlus|soc\.?\s*coop)\b\.?", " ", s)
    return " ".join(re.findall(r"[0-9a-zà-ÿ]+", s))


_TIPI_ELENCO: list[tuple[str, str]] | None = None


def tipi_dall_elenco(percorso: Path | None = None) -> list[tuple[str, str]]:
    """(nome normalizzato, tipo) delle strutture scritte a mano in data/strutture.csv."""
    global _TIPI_ELENCO
    if percorso is None and _TIPI_ELENCO is not None:
        return _TIPI_ELENCO
    import csv
    righe = []
    try:
        with open(percorso or RADICE / "data" / "strutture.csv", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                nome, tipo = _norm_nome(r.get("nome") or ""), (r.get("tipo") or "").strip()
                if len(nome) >= 6 and tipo:
                    righe.append((nome, tipo))
    except OSError:
        pass
    if percorso is None:
        _TIPI_ELENCO = righe
    return righe


def struttura_senza_lettura(a: dict, elenco: list[tuple[str, str]] | None = None) -> str | None:
    """Tipo di struttura per un annuncio che non passa dalla lettura (scritto a mano, 19/11):
    il titolo se dice com'è il lavoro (domiciliare, stagionale), poi il nome del datore,
    poi il tipo che l'elenco Strutture dà a quel datore, infine il resto del titolo."""
    titolo, datore = a.get("titolo") or "", a.get("datore") or ""
    dal_titolo = estrai.estrai_struttura(titolo, "")
    if dal_titolo in STRUTTURE_DAL_LAVORO:
        return dal_titolo
    if datore:
        dal_nome = estrai.estrai_struttura(datore, "")
        if dal_nome:
            return dal_nome
        d = " " + _norm_nome(datore, senza_parentesi=False) + " "
        for nome, tipo in (tipi_dall_elenco() if elenco is None else elenco):
            if " " + nome + " " in d:
                dal_tipo = estrai.estrai_struttura(tipo, "")
                if dal_tipo:
                    return dal_tipo
    return dal_titolo


def passa_alla_prossima_scadenza(a: dict, oggi: date) -> str | None:
    """Annunci a mano con più sessioni («scadenze»: [...]): la scadenza è la prima non ancora passata.
    Ritorna la frase del cambio (per l'email) o None. Le date sono solo quelle scritte a mano."""
    date_s = sorted(d for d in (a.get("scadenze") or []) if d)
    if not date_s:
        return None
    prossima = next((d for d in date_s if date.fromisoformat(d) >= oggi), date_s[-1])
    if prossima == a.get("scadenza"):
        return None
    vecchia = a.get("scadenza")
    a["scadenza"] = prossima
    if vecchia and date.fromisoformat(vecchia) < date.fromisoformat(prossima):
        return f"scadenza: {vecchia} → {prossima} (sessione successiva)"
    return None


def togli_dal_doppione(a: dict) -> None:
    """Toglie i dati presi in prestito da un doppione (si ricalcolano a ogni giro)."""
    for campo in a.pop("dal_doppione", None) or []:
        a[campo] = None
    if a.get("avvisi"):
        a["avvisi"] = [x for x in a["avvisi"] if not x.startswith((AVVISO_BANDO_COMUNE, AVVISO_DAL_DOPPIONE, AVVISO_DAL_DATORE))]


def _completa(principale: dict, altri: list[dict], campi: dict = CAMPI_DAL_DOPPIONE,
              avviso: str = AVVISO_DAL_DOPPIONE) -> None:
    """Lo stesso bando visto su più siti: i dati che mancano a quello mostrato si prendono dagli altri."""
    for altro in altri:
        presi = [c for c in campi if not principale.get(c) and altro.get(c)]
        if not presi:
            continue
        for c in presi:
            principale[c] = altro[c]
        principale.setdefault("dal_doppione", []).extend(presi)
        nomi = [campi[c] for c in presi if campi[c]]
        if nomi:
            principale.setdefault("avvisi", []).append(f"{avviso}{altro.get('fonte') or 'n.d.'}: {', '.join(nomi)}")


def segna_doppioni(memoria: dict, oggi: date) -> list[dict]:
    """Lo stesso annuncio visto su due siti, o ripubblicato: ne resta uno (a mano, poi il più recente).
    Ritorna gli annunci completati con dati presi da un doppione (il punteggio va ricalcolato)."""
    for a in memoria.values():
        a.pop("doppione_di", None)
        togli_dal_doppione(a)

    def preferenza(a: dict):
        return (a.get("origine") != "manuale", -(date.fromisoformat(a["pubblicato"]).toordinal() if a.get("pubblicato") else 0),
                -a.get("punteggio", 0), a.get("primo_visto", ""))

    def risolvi(gruppi: dict, stesso_bando: bool = False) -> None:
        for gruppo in gruppi.values():
            if len(gruppo) > 1:
                gruppo.sort(key=preferenza)
                for altro in gruppo[1:]:
                    altro["doppione_di"] = gruppo[0]["id"]
                if stesso_bando:
                    _completa(gruppo[0], gruppo[1:])
                else:
                    # Annunci diversi dello stesso datore (Fondazione Pitsch, 17/11): l'email del datore
                    # e il tipo di struttura valgono per tutti; compenso e date no.
                    datore = estrai.chiave(gruppo[0].get("datore"))
                    simili = [x for x in gruppo[1:] if len(datore) >= 6 and estrai.chiave(x.get("datore")) == datore]
                    _completa(gruppo[0], simili, CAMPI_DEL_DATORE, AVVISO_DAL_DATORE)

    # 0) Il PDF di un bando letto anche come annuncio a sé: resta la pagina che lo allega.
    allegati = {}
    for a in memoria.values():
        for pdf in a.get("pdf_letti") or []:
            if pdf != a.get("url"):
                allegati.setdefault(estrai.normalizza_url(pdf), a)
    for a in memoria.values():
        pagina = allegati.get(estrai.normalizza_url(a.get("url") or ""))
        # Se la pagina risulta scaduta e il PDF no, la pagina è stata letta male: non si nasconde il PDF.
        if pagina is not None and pagina is not a and not (e_scaduto(pagina, oggi) and not e_scaduto(a, oggi)):
            a["doppione_di"] = pagina["id"]
    # 0 bis) Un bando comune a più strutture, pubblicato da ognuna con lo stesso PDF
    #    (sul sito diventa «bando.pdf», «bando_0.pdf», «bando_1.pdf») e la stessa scadenza.
    gruppi: dict[tuple, list[dict]] = {}
    for a in memoria.values():
        if a.get("doppione_di") or not a.get("scadenza") or not a.get("pdf_letti"):
            continue
        p = urlparse(a["pdf_letti"][0])
        nome = re.sub(r"_\d+$", "", unquote(p.path).rsplit("/", 1)[-1].lower().removesuffix(".pdf"))
        if len(nome) >= 12:
            gruppi.setdefault((p.netloc.lower(), nome, a["scadenza"], e_piva(a)), []).append(a)
    for gruppo in gruppi.values():
        if len(gruppo) > 1:
            gruppo.sort(key=preferenza)
            altri = [f"{x.get('datore') or 'n.d.'} ({x.get('zona') or 'n.d.'})" for x in gruppo[1:]]
            gruppo[0].setdefault("avvisi", []).append(AVVISO_BANDO_COMUNE + ", ".join(altri))
            for altro in gruppo[1:]:
                altro["doppione_di"] = gruppo[0]["id"]
            _completa(gruppo[0], gruppo[1:])
    # 1) Stesso bando: stessa zona, stessa scadenza, stesso tipo di rapporto.
    gruppi = {}
    for a in memoria.values():
        if a.get("doppione_di"):
            continue
        if a.get("scadenza") and a.get("zona") and not e_scaduto(a, oggi):
            gruppi.setdefault((a["zona"], a["scadenza"], e_piva(a)), []).append(a)
    risolvi(gruppi, stesso_bando=True)
    # 2) Stesso annuncio ripubblicato: stesso datore, stesso titolo, stessa zona.
    gruppi = {}
    for a in memoria.values():
        if a.get("doppione_di") or not a.get("zona"):
            continue
        datore, titolo = estrai.chiave(a.get("datore")), estrai.chiave(a.get("titolo"))
        if len(titolo) >= (8 if datore else 15):
            gruppi.setdefault((datore, titolo, a["zona"], e_piva(a)), []).append(a)
    risolvi(gruppi)
    # 3) Stessa struttura che ripubblica la ricerca: stesso indirizzo email, stessa zona, nessuna scadenza aperta.
    #    Resta l'annuncio a mano o il più recente.
    gruppi = {}
    for a in memoria.values():
        if a.get("doppione_di") or not a.get("zona") or not a.get("email"):
            continue
        if a.get("scadenza") and not e_scaduto(a, oggi):
            continue
        gruppi.setdefault((a["email"].lower(), a["zona"], e_piva(a)), []).append(a)
    risolvi(gruppi)
    # 4) Stesso datore nella stessa zona, stesso tipo di rapporto, nessuna scadenza aperta.
    gruppi = {}
    for a in memoria.values():
        datore = estrai.chiave(a.get("datore"))
        if a.get("doppione_di") or not a.get("zona") or len(datore) < 6:
            continue
        if a.get("scadenza") and not e_scaduto(a, oggi):
            continue
        # Un bando con una sua scadenza (anche passata) è un bando a sé: si unisce solo a chi ha la stessa data,
        # non a un annuncio generico senza data (ASUIT SLP 15/26 nascosto dalla pagina OPI di gennaio, 16/11).
        gruppi.setdefault((datore, a["zona"], e_piva(a), a.get("scadenza")), []).append(a)
    risolvi(gruppi)
    # Niente catene (a → b → c): ogni doppione punta all'annuncio che si vede.
    for a in memoria.values():
        visti, capo = {a.get("id")}, a.get("doppione_di")
        while capo in memoria and memoria[capo].get("doppione_di") and capo not in visti:
            visti.add(capo)
            capo = memoria[capo]["doppione_di"]
        if capo:
            a["doppione_di"] = capo
    return [a for a in memoria.values() if a.get("dal_doppione")]


def aggiorna_stato_fonti(stato: dict, fonte: dict, esito: dict, oggi: date) -> str | None:
    """Tiene la storia di ogni fonte e ritorna un eventuale problema da segnalare."""
    nome = fonte["nome"]
    stato.setdefault("massimo_candidati", 0)
    stato.update(ultimo_giro=oggi.isoformat(), letti=esito["letti"], riusati=esito["riusati"],
                 scartati=esito["scartati"], pertinenti=len(esito["annunci"]))
    if esito["errore"]:
        stato["ultimo_errore"] = esito["errore"]
        return f"{nome}: {esito['errore']}"
    stato.pop("ultimo_errore", None)
    stato["ultimi_candidati"] = esito["candidati"]
    if esito["candidati"] == 0:
        stato["giorni_a_zero"] = stato.get("giorni_a_zero", 0) + 1
        if fonte.get("puo_essere_vuota"):
            stato["ultimo_ok"] = oggi.isoformat()
            return None
        if stato.get("massimo_candidati", 0) > 0:
            return (f"{nome}: oggi nessun annuncio nell'elenco, mentre prima ce n'erano "
                    f"(ultima lettura buona: {stato.get('ultimo_ok')}). Il sito potrebbe aver cambiato struttura.")
        return f"{nome}: nessun link ad annunci trovato. Controlla l'indirizzo in config.yaml."
    stato["giorni_a_zero"] = 0
    stato["ultimo_ok"] = oggi.isoformat()
    stato["massimo_candidati"] = max(stato.get("massimo_candidati", 0), esito["candidati"])
    return None


# --------------------------------------------------------------------------
# Giro completo
# --------------------------------------------------------------------------

def provincia_senza_comune(a: dict) -> str | None:
    """«Trento»/«Bolzano» quando l'annuncio dice solo la provincia (avvisi dei portali): serve al riassunto
    dell'email e dell'app, che altrimenti direbbero «zona n.d.» (Cerba, 24/11). Mai un comune inventato."""
    if a.get("zona"):
        return None
    for avviso in a.get("avvisi") or []:
        m = re.match(r"Zona: provincia di (Trento|Bolzano), comune non indicato", avviso)
        if m:
            return m.group(1)
    return None


def _riga(a: dict) -> dict:
    riga = {k: a.get(k) for k in ("id", "titolo", "datore", "contratto", "compenso", "zona", "minuti",
                                  "scadenza", "punteggio", "url", "cambi")}
    riga["piva"] = e_piva(a)
    riga["provincia"] = provincia_senza_comune(a)
    return riga


def _esplora(cfg: dict, rete, registra) -> list[dict]:
    """Messa a punto: elenca i link di alcune pagine, per capire dove pubblicano concorsi e avvisi."""
    risultati = []
    for url in cfg.get("esplora") or []:
        registra(f"• esploro {url}")
        html, errore = rete.get(url)
        if errore:
            risultati.append({"url": url, "errore": errore})
            continue
        pagina = estrai.leggi_pagina(html, url, intera_se_vuota=True)
        risultati.append({"url": url, "titolo": pagina["titolo"], "caratteri": len(pagina["testo"]),
                          "inizio": pagina["testo"][:300], "link": estrai.tutti_i_link(html, url, 60)})
    return risultati


def giro(cfg: dict, rete, oggi: date, registra=print, diagnostica: bool = True,
         avvisi: dict[str, list[dict]] | None = None) -> dict:
    comuni = estrai.carica_comuni(RADICE / "data" / "comuni.csv")
    memoria = leggi_json(FILE_ANNUNCI, {})
    stato_fonti = leggi_json(FILE_FONTI, {})
    fonti = tutte_le_fonti(cfg)
    fonti_attive = {f["nome"] for f in fonti}
    diag = {"data": oggi.isoformat(), "fonti": {}, "esplora": []}

    trovati, problemi, fonti_lette, scartati = {}, [], set(), set()
    for fonte in fonti:
        registra(f"• {fonte['nome']}")
        stato = stato_fonti.setdefault(fonte["nome"], {})
        if stato.get("regole") != VERSIONE_REGOLE:
            stato["scarti"], stato["regole"] = {}, VERSIONE_REGOLE
        try:
            esito = raccogli_fonte(fonte, rete, cfg, comuni, oggi, memoria, stato, diag["fonti"])
        except Exception as e:  # una fonte rotta non deve fermare le altre
            esito = {"annunci": [], "candidati": 0, "scartati": 0, "riusati": 0, "letti": 0,
                     "errore": f"errore imprevisto ({type(e).__name__}: {e})"}
        scartati |= set(stato.get("scarti", {}))
        problema = aggiorna_stato_fonti(stato, fonte, esito, oggi)
        if problema:
            problemi.append(problema)
            registra(f"   ⚠ {problema}")
        if not esito["errore"] and (esito["candidati"] > 0 or fonte.get("puo_essere_vuota")):
            fonti_lette.add(fonte["nome"])  # un elenco vuoto imprevisto non prova che gli annunci siano spariti
        for a in esito["annunci"]:
            vecchio = trovati.get(a["id"])  # stesso annuncio da due fonti: vince la più affidabile
            if not vecchio or a.get("punteggio", 0) > vecchio.get("punteggio", 0):
                trovati[a["id"]] = a
        registra(f"   {esito['candidati']} voci: {len(esito['annunci'])} pertinenti "
                 f"({esito['letti']} lette, {esito['riusati']} già note, {esito['scartati']} scartate)")
    for nome in list(stato_fonti):
        if nome not in fonti_attive:
            del stato_fonti[nome]  # fonte tolta o spenta in config

    if diagnostica:
        diag["esplora"] = _esplora(cfg, rete, registra)

    # Avvisi di lavoro arrivati per email dai portali (Indeed, LinkedIn…): si usa solo ciò che dice l'email.
    for nome, candidati in (avvisi or {}).items():
        segnalati = nome == "Segnalati da Michael"
        fonte = ({"nome": "Segnalati da Michael", "tipo": "rss", "affidabilita": "struttura", "solo_regione": False} if segnalati else
                 {"nome": f"Avvisi email – {nome}", "tipo": "rss", "affidabilita": "aggregatore", "solo_regione": True})
        fonti_attive.add(fonte["nome"])
        fonti_lette.add(fonte["nome"])
        presi, scarti_email = 0, []
        for cand in candidati:
            a, motivo = _costruisci(cand, cand.get("sommario", ""), cand.get("pubblicato"), fonte, cfg, comuni, oggi,
                               ["Segnalato da te via email: apri il link per i dettagli"] if segnalati else
                               ["Dall'avviso email del portale: apri il link per i dettagli"],
                               controlla_ruolo=not segnalati)
            if a and a["id"] not in trovati:
                trovati[a["id"]] = a
                presi += 1
            elif not a:
                # 20/11: Indeed «Infermieri ParaMedica srl Asiago, Veneto» risultava solo «candidati 1, accettati 0»:
                # la diagnostica deve dire che cosa è stato scartato e perché.
                scarti_email.append([(cand.get("sommario") or cand.get("titolo") or "")[:120], motivo or "n.d.", cand.get("url", "")[:200]])
        registra(f"• {fonte['nome']}: {presi} annunci" + (f" ({len(scarti_email)} scartati)" if scarti_email else ""))
        if diagnostica:
            diag["fonti"][fonte["nome"]] = {"candidati": len(candidati), "accettati": presi, "scartati": scarti_email[:10]}

    novita = aggiorna_memoria(memoria, list(trovati.values()), fonti_lette, fonti_attive, scartati, oggi, cfg)
    for a in segna_doppioni(memoria, oggi):
        a["punteggio"], a["dettaglio_punteggio"] = punteggio.calcola(a, cfg)

    attivi = [a for a in memoria.values() if aperto(a, oggi, cfg) and not a.get("sparito_dal")]
    attivi.sort(key=lambda a: -a["punteggio"])
    tra7 = (oggi + timedelta(days=7)).isoformat()
    scadenze = sorted((a for a in attivi if a.get("scadenza") and a["scadenza"] <= tra7),
                      key=lambda a: a["scadenza"])
    nuovi = sorted((_riga(a) for a in novita["nuovi"] if aperto(a, oggi, cfg)), key=lambda r: -r["punteggio"])
    aggiornati = [_riga(a) for a in novita["aggiornati"] if aperto(a, oggi, cfg)]
    report = {
        "data": oggi.isoformat(),
        "attivi": len(attivi),
        "attivi_piva": sum(1 for a in attivi if e_piva(a)),
        "nuovi": nuovi,
        "aggiornati": aggiornati,
        "top5": [_riga(a) for a in attivi[:5]],
        "scadenze7": [_riga(a) for a in scadenze],
        "problemi": problemi,
        "fonti_lette": len(fonti_lette),
        "fonti_totali": len(fonti_attive),
        "giri": 1,
    }
    # Più giri nello stesso giorno: nell'archivio le novità si sommano, non si sovrascrivono.
    del_giorno = dict(report)
    precedente = leggi_json(CARTELLA_REPORT / f"{oggi.isoformat()}.json", None)
    if precedente and precedente.get("data") == oggi.isoformat():
        for voce in ("nuovi", "aggiornati"):
            presenti = {r["id"] for r in report[voce]}
            ancora = [r for r in precedente.get(voce, [])
                      if r["id"] not in presenti and r["id"] in memoria and aperto(memoria[r["id"]], oggi, cfg)
                      and memoria[r["id"]].get("data_novita") == oggi.isoformat()]  # un cambio annullato non resta
            del_giorno[voce] = report[voce] + ancora
        del_giorno["giri"] = int(precedente.get("giri", 1)) + 1

    scrivi_json(FILE_ANNUNCI, memoria)
    scrivi_json(FILE_FONTI, stato_fonti)
    scrivi_json(CARTELLA_REPORT / f"{oggi.isoformat()}.json", del_giorno)
    if diagnostica:
        diag["richieste"] = getattr(rete, "richieste", None)
        scrivi_json(FILE_DIAGNOSTICA, diag)
    return report
