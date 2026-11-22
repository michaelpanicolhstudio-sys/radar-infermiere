"""Invio delle lettere di primo contatto, poche al giorno, e resoconto delle risposte.

Regole:
- parte solo se in config.yaml c'è `invio.attivo: true` e solo nel giro pianificato del mattino;
- al massimo `invio.al_giorno` lettere per giro, con una pausa tra l'una e l'altra;
- mai due volte allo stesso indirizzo; chi ha già ricevuto una lettera (anche inviata a mano) è saltato;
- si usa l'email normale; la PEC solo se la struttura non ha altro (dalla Gmail può essere respinta).
"""
from __future__ import annotations

import hashlib
import os
import json
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
                   r"cerchiamo|ricerchiamo|(?<!candidati\s)disponibili\s+a|gerne|interesse\s+an|wir\s+suchen|bedarf\s+besteht|freuen\s+uns", re.I)
RE_LP = re.compile(r"libera\s+profession|libero\s+professionist|partita\s+iva|p\.\s?iva|freiberuf|mwst", re.I)
RE_DIP = re.compile(r"assunzion|tempo\s+(?:in)?determinato|dipendente|contratto\s+di\s+lavoro|anstellung|festanstellung|angestellt", re.I)


def coda(strutture: list[dict], memoria: dict, contatti: dict, cfg: dict, oggi: date) -> list[dict]:
    """Chi deve ancora ricevere la lettera, nell'ordine di invio: prima chi ha un annuncio in libera professione,
    poi le strutture dalla più vicina. Se in config c'è `invio.selezione`, solo quelle strutture e con la lettera breve."""
    selezione = [x.lower() for x in (cfg.get("invio") or {}).get("selezione") or []]
    conosciute = [x.lower() for x in (cfg.get("invio") or {}).get("gia_conosciute") or []]
    dedicate = (cfg.get("invio") or {}).get("dedicate") or {}
    voci = _coda(strutture, memoria, contatti, cfg, oggi)
    if not selezione:
        return voci
    scelte = []
    for v in voci:
        if any(x in v["nome"].lower() for x in selezione):
            rif = v["oggetto"].rsplit("Rif. ", 1)[-1].rstrip(")")
            dedicata = next((t for k, t in dedicate.items() if k.lower() in v["nome"].lower()), None)
            if dedicata:
                scelte.append({**v, **lettere.lettera_dedicata(dedicata, rif)})
                continue
            scrivi = lettere.lettera_conosciuta if any(x in v["nome"].lower() for x in conosciute) else lettere.lettera_breve
            scelte.append({**v, **scrivi({"nome": v["nome"], "minuti": v.get("minuti")}, rif)})
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


def rispondi(contatti: dict, rif: str, testo: str, oggi: date, cfg: dict, registra=print, allegato: str = "") -> bool:
    """Risponde una volta, su richiesta esplicita di Michael, all'ultima risposta ricevuta dal contatto con quel Rif.
    Stessa conversazione (Re: + In-Reply-To). Il testo arriva dall'avvio a mano del workflow, non sta nel repository."""
    utente = os.environ.get("GMAIL_USER", "").strip()
    chiave_gmail = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    chiave = next((k for k, v in contatti.items() if v.get("rif") == rif.strip()), None)
    if not (utente and chiave_gmail and chiave and testo.strip()):
        registra(f"⚠ Risposta non inviata: contatto {rif} non trovato o testo vuoto")
        return False
    voce = contatti[chiave]
    if not voce.get("risposte"):
        registra(f"⚠ Risposta non inviata: {rif} non ha ancora risposto")
        return False
    ultima = sorted(voce["risposte"], key=lambda r: r.get("data") or "")[-1]
    impronta = hashlib.sha256(estrai.chiave(testo).encode()).hexdigest()[:16]   # solo un'impronta: il testo non si salva
    if any(m.get("impronta") == impronta for m in voce.get("mie_risposte", [])):
        registra("⚠ Risposta già inviata: non la rimando")
        return False
    msg = EmailMessage()
    oggetto = ultima.get("oggetto") or ""
    msg["Subject"] = oggetto if oggetto.lower().startswith(("r:", "re:")) else "Re: " + oggetto
    msg["From"] = formataddr(((cfg.get("invio") or {}).get("mittente") or "Michael Panico", utente))
    msg["To"] = ultima["da"]
    msg["Message-ID"] = make_msgid(domain=utente.split("@")[-1])
    if ultima.get("mid"):
        msg["In-Reply-To"] = ultima["mid"]
        msg["References"] = ultima["mid"]
    msg.set_content(testo.strip())
    if allegato:
        # Solo file della cartella data/allegati (es. il CV), mai altro.
        percorso = (motore.RADICE / "data" / "allegati" / Path(allegato).name)
        if not percorso.is_file():
            registra(f"⚠ Risposta non inviata: allegato {Path(allegato).name} non trovato")
            return False
        tipo = "pdf" if percorso.suffix.lower() == ".pdf" else "octet-stream"
        msg.add_attachment(percorso.read_bytes(), maintype="application", subtype=tipo, filename=percorso.name)
    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=40)
        smtp.login(utente, chiave_gmail)
        smtp.send_message(msg)
        smtp.quit()
    except Exception as e:
        registra(f"⚠ Risposta non inviata ({type(e).__name__})")
        return False
    voce.setdefault("mie_risposte", []).append({"data": oggi.isoformat(), "a": ultima["da"], "impronta": impronta,
                                               **({"allegato": Path(allegato).name} if allegato else {})})
    registra(f"Risposta inviata a {ultima['da']}")
    return True


# --------------------------------------------------------------------------
# Resoconto delle risposte
# --------------------------------------------------------------------------

# Lettura dell'esito, tarata sulle risposte vere del 17-19/11 classificate da Michael (data/esiti.json).
RE_DA_FARE = re.compile(r"compilare\s+(?:l['’]\s*)?(?:apposit[oa]\s+)?(?:modulo|scheda|domanda)|modulo\s+(?:di\s+domanda\s+)?da\s+compilare|"
                        r"formular\s+aus(?:zu)?f[üu]ll", re.I)
RE_SI_FORTE = re.compile(r"colloqui|vederci|incontrarci|stiamo\s+(?:ancora\s+)?cercando|ancora\s+cercando|"
                         r"difficolt[àa]\s+a\s+(?:reperire|trovare)|vorstellungsgespr[äa]ch|kennenlern", re.I)
RE_NO_ORA = re.compile(r"non\s+(?:abbiamo|vi\s+è|c['’]\s*è|ci\s+sono|si\s+ravvisa)\s+(?:al\s+momento\s+)?(?:la\s+|alcun[ao]?\s+)?(?:necessit|bisogno|esigenz)|"
                       r"al\s+completo|copert[oi]\s+da\s+personale|non\s+(?:è|e)\s+(?:una\s+struttura\s+)?sanitaria|non\s+sanitari[ao]", re.I)
RE_NO_DEFINITIVO = re.compile(r"non\s+sanitari[ao]|non\s+(?:è|e)\s+(?:una\s+struttura\s+)?sanitaria|non\s+collaboriamo|"
                              r"non\s+(?:ci\s+avvaliamo|utilizziamo)\s+(?:di\s+)?(?:liberi|libero|infermieri)", re.I)
RE_CV = re.compile(r"curricul|\bcv\b|lebenslauf", re.I)
RE_COLLABORA_LP = re.compile(r"(?<!non\s)collabor\w*\s+(?:anche\s+|già\s+)?con\s+(?:gli\s+|degli\s+|dei\s+)?(?:infermier\w*|liberi\s+professionist)", re.I)


def _esito(testo: str, euro_ora) -> str:
    """sì / più avanti / no / da fare / da leggere, come li sceglierebbe Michael leggendo la risposta."""
    if RE_DA_FARE.search(testo):
        return "da fare"
    if RE_NO_DEFINITIVO.search(testo):
        return "no"
    if RE_SI_FORTE.search(testo) or euro_ora:
        return "sì"
    no_ora = RE_NO_ORA.search(testo) or RE_NO.search(testo)
    if no_ora:
        # «Ora no, ma mandi il CV / un'offerta»: resta una porta aperta.
        return "più avanti" if RE_CV.search(testo) or re.search(r"offerta\s+per", testo, re.I) else "no"
    if RE_COLLABORA_LP.search(testo) or RE_SI.search(testo):
        return "sì"
    if RE_CV.search(testo):
        return "più avanti"
    return "da leggere"


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
    esito = _esito(testo, euro_ora)
    rapporto = "libera professione" if RE_LP.search(testo) else ("dipendente" if RE_DIP.search(testo) else None)
    m = re.search(r"(?:da\s+subito|subito|immediatamente|ab\s+sofort|da(?:l)?\s+(?:\d{1,2}\s+)?(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
                  r"agosto|settembre|ottobre|novembre|dicembre)(?:\s+\d{4})?)", testo, re.I)
    return {"esito": esito, "rapporto": rapporto, "compenso": compenso, "euro_ora": euro_ora, "turni": turni,
            "da_quando": m.group(0) if m else None}


def esiti_manuali(percorso: Path | None = None) -> dict:
    """Esiti e prossimi passi scritti a mano in data/esiti.json (chiave della struttura → esito, prossimo, aggiornato)."""
    percorso = percorso or motore.RADICE / "data" / "esiti.json"
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in dati.items() if not k.startswith("_") and isinstance(v, dict)}


def resoconto(strutture: list[dict], memoria: dict, contatti: dict, cfg: dict) -> list[dict]:
    nomi = {s["chiave"]: s for s in strutture}
    par = conti.parametri(cfg)
    manuali = esiti_manuali()
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
        mano = manuali.get(chiave) or {}
        if mano and ultima and ultima.get("data", "") > mano.get("aggiornato", ""):
            mano = {}  # la struttura ha scritto di nuovo: l'esito scritto a mano va riletto
        mie = c.get("mie_risposte") or []
        riga = {"chiave": chiave, "nome": s.get("nome") or a.get("datore") or a.get("titolo") or chiave,
                "comune": s.get("comune") or a.get("zona"), "minuti": s.get("minuti", a.get("minuti")), "km": s.get("km", a.get("km")),
                "inviata_il": c["inviata_il"], "risposta_il": ultima.get("data") if ultima else None,
                "esito": esito.get("esito") or "in attesa", "rapporto": esito.get("rapporto"),
                "compenso": esito.get("compenso"), "euro_ora": esito.get("euro_ora"), "turni": esito.get("turni"),
                "da_quando": esito.get("da_quando"), "incontro": incontro, "netto_ora": None, "turni_obiettivo": None,
                "mia_risposta_il": mie[-1].get("data") if mie else None, "prossimo": mano.get("prossimo")}
        if mano.get("esito"):
            riga["esito"] = mano["esito"]
        for campo in ("da_quando", "turni", "rapporto", "compenso", "euro_ora", "comune", "km", "minuti"):
            if mano.get(campo):
                riga[campo] = mano[campo]
        if isinstance(mano.get("incontro"), dict) and mano["incontro"].get("data"):
            riga["incontro"] = mano["incontro"]
        # 21/11 Casa Laner: «Tocca a te» restava anche dopo la risposta di Michael. Se lui ha scritto dopo
        # che il passo «da fare» è stato deciso (o dopo l'ultima risposta della struttura), ora tocca a loro.
        riferimento = mano.get("aggiornato") if mano else (ultima.get("data") if ultima else None)
        if riga["esito"] == "da fare" and riga["mia_risposta_il"] and riferimento and riga["mia_risposta_il"] > riferimento:
            gg = lambda iso: f"{iso[8:10]}/{iso[5:7]}"
            riga["esito"] = "hai risposto"
            riga["prossimo"] = f"Hai risposto il {gg(riga['mia_risposta_il'])}: ora tocca a loro." + (
                f" Passo scritto il {gg(riferimento)}: {riga['prossimo']}" if riga.get("prossimo") else "")
        if riga["euro_ora"]:
            calcolo = conti.conto_offerta({"euro_ora": riga["euro_ora"], "km": riga["km"] or 0, "minuti": riga["minuti"] or 0,
                                           **{k: mano[k] for k in ("ore_turno", "ore_pagate", "turni_max_mese") if mano.get(k)}}, par)
            riga["netto_ora"], riga["turni_obiettivo"] = calcolo["netto_ora_porta_a_porta"], calcolo["turni_per_obiettivo"]
            riga["ore_turno"], riga["ore_pagate"] = calcolo["ore_turno"], calcolo["ore_pagate"]
            riga["turni_max_mese"], riga["basta_da_sola"] = calcolo["turni_max_mese"], calcolo["basta_da_sola"]
        righe.append(riga)
    ordine = {"da fare": 0, "sì": 1, "hai risposto": 1.5, "da leggere": 2, "più avanti": 3, "in attesa": 4, "no": 5}
    return sorted(righe, key=lambda r: (ordine.get(r["esito"], 9), -(r["euro_ora"] or 0), r["minuti"] if r["minuti"] is not None else 999))


def scrivi_resoconto_excel(righe: list[dict], percorso: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Resoconto contatti"
    intestazione = ["Struttura", "Comune", "Minuti", "Inviata il", "Risposta il", "Esito", "Prossimo passo", "Rapporto", "Compenso",
                    "€/h", "Netto €/h col viaggio", "Turni/mese per l'obiettivo", "Turni e orari", "Da quando", "Incontro"]
    ws.append(intestazione)
    for cella in ws[1]:
        cella.font = Font(bold=True)
    colori = {"sì": "E3F1E3", "no": "F6E1E1", "da leggere": "FFF4CC", "da fare": "FFE2C2", "hai risposto": "E3F1E3", "più avanti": "E6EEF7"}
    for r in righe:
        ws.append([r["nome"], r["comune"], r["minuti"], r["inviata_il"], r["risposta_il"], r["esito"], r.get("prossimo"), r["rapporto"],
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
