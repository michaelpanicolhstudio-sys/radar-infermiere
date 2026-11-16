"""Invio delle lettere di primo contatto, poche al giorno, e resoconto delle risposte.

Regole:
- parte solo se in config.yaml c'è `invio.attivo: true` e solo nel giro pianificato del mattino;
- al massimo `invio.al_giorno` lettere per giro, con una pausa tra l'una e l'altra;
- mai due volte allo stesso indirizzo; chi ha già ricevuto una lettera (anche inviata a mano) è saltato;
- si usa l'email normale; la PEC solo se la struttura non ha altro (dalla Gmail può essere respinta).
"""
from __future__ import annotations

import os
import re
import smtplib
import time
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from . import conti, estrai, lettere, motore, posta

ESCLUDI_TIPI = re.compile(r"penitenziar", re.I)
RE_NO = re.compile(r"non\s+(?:abbiamo|cerchiamo|ricerchiamo|necessitiamo|è\s+previst|sono\s+previst|ci\s+avvaliamo|utilizziamo|collaboriamo)|"
                   r"al\s+momento\s+no|non\s+ci\s+sono\s+(?:posizioni|esigenze)|keinen\s+bedarf|derzeit\s+(?:nicht|kein)|"
                   r"leider\s+(?:nicht|kein)|nur\s+(?:angestellt|festangestellt)", re.I)
RE_SI = re.compile(r"siamo\s+interessat|interessat[oi]\s+a|volentieri|saremmo\s+lieti|ben\s+volentieri|abbiamo\s+bisogno|"
                   r"cerchiamo|ricerchiamo|disponibili\s+a|gerne|interesse\s+an|wir\s+suchen|bedarf\s+besteht|freuen\s+uns", re.I)
RE_LP = re.compile(r"libera\s+profession|libero\s+professionist|partita\s+iva|p\.\s?iva|freiberuf|mwst", re.I)
RE_DIP = re.compile(r"assunzion|tempo\s+(?:in)?determinato|dipendente|contratto\s+di\s+lavoro|anstellung|festanstellung|angestellt", re.I)


def coda(strutture: list[dict], memoria: dict, contatti: dict, cfg: dict, oggi: date) -> list[dict]:
    """Chi deve ancora ricevere la lettera, nell'ordine di invio: prima chi ha un annuncio in libera professione,
    poi le strutture dalla più vicina. Se in config c'è `invio.selezione`, solo quelle strutture e con la lettera breve."""
    selezione = [x.lower() for x in (cfg.get("invio") or {}).get("selezione") or []]
    voci = _coda(strutture, memoria, contatti, cfg, oggi)
    if not selezione:
        return voci
    scelte = []
    for v in voci:
        if any(x in v["nome"].lower() for x in selezione):
            scelte.append({**v, **lettere.lettera_breve({"nome": v["nome"], "minuti": v.get("minuti")},
                                                        v["oggetto"].rsplit("Rif. ", 1)[-1].rstrip(")"))})
    return scelte


def _coda(strutture: list[dict], memoria: dict, contatti: dict, cfg: dict, oggi: date) -> list[dict]:
    gia = {x.lower() for c in contatti.values() if c.get("inviata_il") for x in c.get("a", [])}
    voci, visti = [], set()
    modello = cfg.get("email_contatto") or {}
    for a in sorted(memoria.values(), key=lambda a: -a.get("punteggio", 0)):
        indirizzo = (a.get("email") or a.get("pec") or "").lower()
        if not indirizzo or not motore.e_piva(a) or not motore.aperto(a, oggi, cfg) or a.get("sparito_dal") or a.get("doppione_di"):
            continue
        if indirizzo in gia or indirizzo in visti or (contatti.get(a["id"]) or {}).get("inviata_il"):
            continue
        visti.add(indirizzo)
        voci.append({"chiave": a["id"], "nome": a.get("datore") or a["titolo"], "a": indirizzo, "via_pec": not a.get("email"),
                     "minuti": a.get("minuti"), "origine": "annuncio", **lettere.lettera_annuncio(a, modello, posta.rif(a["id"]))})
    for s in strutture:
        indirizzo = (s.get("email") or s.get("pec") or "").lower()
        if not indirizzo or ESCLUDI_TIPI.search(s.get("tipo") or "") or s.get("non_scrivere"):
            continue
        if indirizzo in gia or indirizzo in visti or (contatti.get(s["chiave"]) or {}).get("inviata_il"):
            continue
        visti.add(indirizzo)
        voci.append({"chiave": s["chiave"], "nome": s["nome"], "a": indirizzo, "via_pec": not s.get("email"),
                     "minuti": s.get("minuti"), "origine": "struttura", **lettere.lettera(s, s["rif"])})
    return voci


def data_prevista(posizione: int, oggi: date, al_giorno: int, attivo: bool) -> str | None:
    if not attivo or al_giorno <= 0:
        return None
    return (oggi + timedelta(days=1 + posizione // al_giorno)).isoformat()


def invia(voci: list[dict], contatti: dict, cfg: dict, oggi: date, registra=print,
          forza: bool = False, massimo: int | None = None) -> list[dict]:
    regole = cfg.get("invio") or {}
    utente = os.environ.get("GMAIL_USER", "").strip()
    chiave = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not ((regole.get("attivo") or forza) and utente and chiave):
        return []
    inviate = []
    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=40)
        smtp.login(utente, chiave)
    except Exception as e:
        registra(f"⚠ Lettere non inviate: accesso a Gmail non riuscito ({type(e).__name__})")
        return []
    try:
        for v in voci[: massimo if massimo is not None else int(regole.get("al_giorno", 12))]:
            msg = EmailMessage()
            msg["Subject"] = v["oggetto"]
            msg["From"] = formataddr((regole.get("mittente") or "Michael Panico", utente))
            msg["To"] = v["a"]
            msg["Message-ID"] = make_msgid(domain=utente.split("@")[-1])
            msg.set_content(v["testo"])
            try:
                smtp.send_message(msg)
            except Exception as e:
                registra(f"⚠ Lettera a {v['nome']} non inviata ({type(e).__name__})")
                continue
            contatti[v["chiave"]] = {**contatti.get(v["chiave"], {}), "inviata_il": oggi.isoformat(), "a": [v["a"]],
                                     "via": "gmail", "rif": v["oggetto"].rsplit("Rif. ", 1)[-1].rstrip(")"),
                                     "automatica": True, "risposte": (contatti.get(v["chiave"]) or {}).get("risposte", [])}
            inviate.append(v)
            time.sleep(float(regole.get("pausa_secondi", 20)))
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    registra(f"• Lettere di primo contatto inviate oggi: {len(inviate)}")
    return inviate


# --------------------------------------------------------------------------
# Resoconto delle risposte
# --------------------------------------------------------------------------

def leggi_esito(testo: str) -> dict:
    """Cosa dice una risposta: esito, tipo di rapporto, compenso, turni, quando."""
    compenso, euro_ora = estrai.estrai_compenso(testo)
    turni, _ = estrai.estrai_turni(testo)
    if not turni:
        parole = []
        for rx, nome in ((r"mattin|frühdienst|früh", "mattina"), (r"pomerigg|spätdienst|spät", "pomeriggio"), (r"nott|nachtdienst|nacht", "notte"),
                         (r"fine\s+settimana|weekend|wochenende|festiv", "fine settimana"), (r"\b12\s*ore|12-?stunden", "turni da 12 ore")):
            if re.search(rx, testo, re.I):
                parole.append(nome)
        ore = re.search(r"(\d{1,2})\s*(?:ore|stunden)\s*(?:settimanal|a\s+settimana|pro\s+woche|wöchentlich)", testo, re.I)
        if ore:
            parole.append(f"{ore.group(1)} ore a settimana")
        turni = ", ".join(parole) or None
    no, si = RE_NO.search(testo), RE_SI.search(testo)
    esito = "no" if no and not (si and si.start() > no.start() + 200) else ("sì" if si or euro_ora else "da leggere")
    rapporto = "libera professione" if RE_LP.search(testo) else ("dipendente" if RE_DIP.search(testo) else None)
    m = re.search(r"(?:da\s+subito|subito|immediatamente|ab\s+sofort|da(?:l)?\s+(?:\d{1,2}\s+)?(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
                  r"agosto|settembre|ottobre|novembre|dicembre)(?:\s+\d{4})?)", testo, re.I)
    return {"esito": esito, "rapporto": rapporto, "compenso": compenso, "euro_ora": euro_ora, "turni": turni,
            "da_quando": m.group(0) if m else None}


def resoconto(strutture: list[dict], memoria: dict, contatti: dict, cfg: dict) -> list[dict]:
    nomi = {s["chiave"]: s for s in strutture}
    par = conti.parametri(cfg)
    righe = []
    for chiave, c in contatti.items():
        if not c.get("inviata_il"):
            continue
        s = nomi.get(chiave) or {}
        a = memoria.get(chiave) or {}
        risposte = c.get("risposte") or []
        ultima = risposte[-1] if risposte else None
        esito = leggi_esito(" ".join(r.get("testo") or "" for r in risposte)) if risposte else {}
        incontro = next((r["incontro"] for r in reversed(risposte) if r.get("incontro")), None)
        riga = {"chiave": chiave, "nome": s.get("nome") or a.get("datore") or a.get("titolo") or chiave,
                "comune": s.get("comune") or a.get("zona"), "minuti": s.get("minuti", a.get("minuti")), "km": s.get("km", a.get("km")),
                "inviata_il": c["inviata_il"], "risposta_il": ultima.get("data") if ultima else None,
                "esito": esito.get("esito") or "in attesa", "rapporto": esito.get("rapporto"),
                "compenso": esito.get("compenso"), "euro_ora": esito.get("euro_ora"), "turni": esito.get("turni"),
                "da_quando": esito.get("da_quando"), "incontro": incontro, "netto_ora": None, "turni_obiettivo": None}
        if riga["euro_ora"]:
            calcolo = conti.conto_offerta({"euro_ora": riga["euro_ora"], "km": riga["km"] or 0, "minuti": riga["minuti"] or 0}, par)
            riga["netto_ora"], riga["turni_obiettivo"] = calcolo["netto_ora_porta_a_porta"], calcolo["turni_per_obiettivo"]
        righe.append(riga)
    ordine = {"sì": 0, "da leggere": 1, "in attesa": 2, "no": 3}
    return sorted(righe, key=lambda r: (ordine.get(r["esito"], 9), -(r["euro_ora"] or 0), r["minuti"] if r["minuti"] is not None else 999))


def scrivi_resoconto_excel(righe: list[dict], percorso: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Resoconto contatti"
    intestazione = ["Struttura", "Comune", "Minuti", "Inviata il", "Risposta il", "Esito", "Rapporto", "Compenso",
                    "€/h", "Netto €/h col viaggio", "Turni/mese per l'obiettivo", "Turni e orari", "Da quando", "Incontro"]
    ws.append(intestazione)
    for cella in ws[1]:
        cella.font = Font(bold=True)
    colori = {"sì": "E3F1E3", "no": "F6E1E1", "da leggere": "FFF4CC"}
    for r in righe:
        ws.append([r["nome"], r["comune"], r["minuti"], r["inviata_il"], r["risposta_il"], r["esito"], r["rapporto"],
                   r["compenso"], r["euro_ora"], r["netto_ora"], r["turni_obiettivo"], r["turni"], r["da_quando"],
                   (r["incontro"]["data"] + (" " + r["incontro"]["ora"] if r["incontro"].get("ora") else "")) if r["incontro"] else None])
        if r["esito"] in colori:
            for cella in ws[ws.max_row]:
                cella.fill = PatternFill("solid", fgColor=colori[r["esito"]])
    for colonna, larghezza in zip("ABCDEFGHIJKLMN", (42, 18, 8, 11, 11, 11, 18, 22, 7, 12, 12, 30, 14, 16)):
        ws.column_dimensions[colonna].width = larghezza
    ws.freeze_panes = "B2"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    wb.save(percorso)
    return percorso
