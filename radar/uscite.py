"""Le uscite del Radar: email del mattino e web app."""
from __future__ import annotations

import html
import json
import os
import shutil
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from . import estrai, motore

RADICE = motore.RADICE
ROMA = ZoneInfo("Europe/Rome")


def _giorno(iso: str | None) -> str:
    if not iso:
        return "n.d."
    a, m, g = iso.split("-")
    return f"{g}/{m}/{a}"


def _riga_testo(r: dict) -> str:
    pezzi = [f"[{r['punteggio']}] {r.get('datore') or r['titolo']}"]
    if r.get("datore") and r["titolo"] != r["datore"]:
        pezzi.append(r["titolo"][:90])
    dettagli = [r.get("contratto") or "contratto n.d.", r.get("compenso") or "compenso n.d.",
                (f"{r['zona']} ({r['minuti']} min)" if r.get("zona") else "zona n.d.")]
    if r.get("scadenza"):
        dettagli.append(f"scade il {_giorno(r['scadenza'])}")
    return "\n   ".join([" – ".join(pezzi), " · ".join(dettagli), r["url"]])


def componi_email(report: dict, url_app: str | None) -> tuple[str, str, str]:
    """Ritorna (oggetto, testo semplice, HTML)."""
    giorno = _giorno(report["data"])[:5]
    n, s, p = len(report["nuovi"]), len(report["scadenze7"]), len(report["problemi"])
    niente = not (n or s or p or report["aggiornati"])

    if niente:
        oggetto = f"Radar infermiere {giorno}: niente di nuovo"
        riga = f"Niente di nuovo oggi. {report['attivi']} offerte attive."
        if url_app:
            riga += f" App: {url_app}"
        return oggetto, riga, f"<p>{html.escape(riga)}</p>"

    parti = []
    if n:
        parti.append(f"{n} nuov{'a' if n == 1 else 'e'}")
    if s:
        parti.append(f"{s} scadenz{'a' if s == 1 else 'e'} vicin{'a' if s == 1 else 'e'}")
    if report["aggiornati"]:
        parti.append(f"{len(report['aggiornati'])} aggiornat{'a' if len(report['aggiornati']) == 1 else 'e'}")
    if p and not parti:
        parti.append(f"{p} font{'e' if p == 1 else 'i'} con problemi")
    oggetto = f"Radar infermiere {giorno}: " + ", ".join(parti)

    sezioni: list[tuple[str, list[str]]] = []
    if report["nuovi"]:
        sezioni.append(("NOVITÀ RISPETTO A IERI", [_riga_testo(r) for r in report["nuovi"][:10]]))
    if report["aggiornati"]:
        righe = [_riga_testo(r) + "\n   Cambiato: " + "; ".join(r.get("cambi") or [])
                 for r in report["aggiornati"][:10]]
        sezioni.append(("ANNUNCI AGGIORNATI", righe))
    if report["scadenze7"]:
        sezioni.append(("SCADENZE ENTRO 7 GIORNI", [_riga_testo(r) for r in report["scadenze7"]]))
    if report["top5"]:
        sezioni.append(("LE 5 MIGLIORI PER PUNTEGGIO", [_riga_testo(r) for r in report["top5"]]))
    if report["problemi"]:
        sezioni.append(("FONTI NON LETTE O DA CONTROLLARE", report["problemi"]))

    testo = [f"{report['attivi']} offerte attive · {report['fonti_lette']} fonti lette su {report['fonti_totali']}"]
    if url_app:
        testo.append(f"Apri l'app: {url_app}")
    corpo_html = [f"<p style='color:#555'>{html.escape(testo[0])}</p>"]
    if url_app:
        corpo_html.append(f"<p><a href='{html.escape(url_app)}'>Apri l'app</a></p>")
    for titolo, righe in sezioni:
        testo += ["", titolo] + [f"- {r}" for r in righe]
        corpo_html.append(f"<h3 style='margin:18px 0 6px;font-size:15px'>{html.escape(titolo)}</h3>")
        for r in righe:
            blocco = html.escape(r).replace("\n   ", "<br>")
            corpo_html.append(f"<p style='margin:0 0 10px;font-size:14px;line-height:1.4'>{blocco}</p>")
    testo += ["", "I dati sono estratti in automatico: apri sempre l'annuncio prima di muoverti."]
    corpo_html.append("<p style='color:#777;font-size:12px'>I dati sono estratti in automatico: "
                      "apri sempre l'annuncio prima di muoverti.</p>")
    pagina = "<div style='font-family:-apple-system,Segoe UI,sans-serif;max-width:560px'>" + "".join(corpo_html) + "</div>"
    return oggetto, "\n".join(testo), pagina


def invia_email(oggetto: str, testo: str, pagina: str, registra=print) -> bool:
    """Invia con Gmail. Servono i segreti GMAIL_USER e GMAIL_APP_PASSWORD (EMAIL_TO è facoltativo)."""
    utente = os.environ.get("GMAIL_USER", "").strip()
    chiave = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    destinatario = os.environ.get("EMAIL_TO", "").strip() or utente
    if not utente or not chiave:
        registra("Email non inviata: mancano i segreti GMAIL_USER e GMAIL_APP_PASSWORD.")
        return False
    msg = EmailMessage()
    msg["Subject"] = oggetto
    msg["From"] = f"Radar Infermiere <{utente}>"
    msg["To"] = destinatario
    msg.set_content(testo)
    msg.add_alternative(pagina, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(utente, chiave)
        smtp.send_message(msg)
    registra(f"Email inviata: {oggetto}")
    return True


# --------------------------------------------------------------------------
# Web app
# --------------------------------------------------------------------------

CAMPI_APP = ["id", "url", "titolo", "datore", "contratto", "compenso", "euro_ora", "turni", "zona", "km",
             "minuti", "scadenza", "pubblicato", "fonte", "affidabilita", "punteggio", "dettaglio_punteggio",
             "avvisi", "estratto", "primo_visto", "ultimo_visto", "novita", "data_novita", "cambi",
             "sparito_dal", "origine", "nota_manuale"]


def costruisci_sito(cfg: dict, oggi: date, destinazione: Path | None = None) -> Path:
    dest = destinazione or RADICE / "dist"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(RADICE / "webapp", dest)

    memoria = motore.leggi_json(motore.FILE_ANNUNCI, {})
    offerte = []
    for a in memoria.values():
        if not motore.visibile(a, cfg):
            continue
        o = {k: a.get(k) for k in CAMPI_APP}
        o["datato"] = motore.e_datato(a, oggi, cfg)
        o["scaduto"] = motore.e_scaduto(a, oggi) or o["datato"]
        o["dipendente"] = motore.e_dipendente(a)
        offerte.append(o)
    offerte.sort(key=lambda o: -o["punteggio"])

    report = []
    for f in sorted(motore.CARTELLA_REPORT.glob("*.json"), reverse=True)[:60]:
        report.append(json.loads(f.read_text(encoding="utf-8")))

    comuni = [{k: c[k] for k in ("nome", "km", "minuti", "lat", "lon")}
              for c in estrai.carica_comuni(RADICE / "data" / "comuni.csv")]
    adesso = datetime.now(ROMA)
    dati = {"generato": adesso.strftime("%d/%m/%Y %H:%M"), "oggi": oggi.isoformat(),
            "casa": cfg.get("profilo", {}).get("casa", "Mezzolombardo"),
            "offerte": offerte, "report": report, "comuni": comuni}
    (dest / "dati.json").write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")

    # Ogni pubblicazione ha una versione nuova: così il telefono scarica i file aggiornati.
    sw = dest / "sw.js"
    sw.write_text(sw.read_text(encoding="utf-8").replace("__VERSIONE__", adesso.strftime("%Y%m%d%H%M")),
                  encoding="utf-8")
    return dest
