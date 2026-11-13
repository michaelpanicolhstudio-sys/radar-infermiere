"""Le uscite del Radar: email del mattino e web app."""
from __future__ import annotations

import html
import json
import os
import shutil
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from . import estrai, motore

RADICE = motore.RADICE
ROMA = ZoneInfo("Europe/Rome")
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre"]
ETICHETTE_CONTRATTO = {
    "P.IVA / libera professione": "Libera professione",
    "P.IVA o dipendente": "P.IVA possibile",
    "Collaborazione": "Collaborazione",
    "Concorso / graduatoria": "Concorso",
    "Dipendente a tempo determinato": "Tempo determinato",
    "Dipendente a tempo indeterminato": "Tempo indeterminato",
    "Dipendente": "Dipendente",
}


def _giorno(iso: str | None) -> str:
    if not iso:
        return "n.d."
    a, m, g = iso.split("-")
    return f"{g}/{m}/{a}"


def data_lunga(d: date) -> str:
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]}"


def _conta(n: int, uno: str, molti: str) -> str:
    return f"{n} {uno if n == 1 else molti}"


def _dettagli(r: dict) -> str:
    pezzi = [ETICHETTE_CONTRATTO.get(r.get("contratto"), "contratto n.d."),
             r.get("compenso") or "compenso n.d.",
             f"{r['zona']} ({r['minuti']} min)" if r.get("zona") else "zona n.d."]
    if r.get("scadenza"):
        pezzi.append(f"scade il {_giorno(r['scadenza'])[:5]}")
    return ", ".join(pezzi)


def _riga_testo(r: dict) -> str:
    capo = f"[{r['punteggio']}] {r.get('datore') or r['titolo']}"
    if r.get("datore") and r["titolo"] != r["datore"]:
        capo += f" – {r['titolo'][:90]}"
    return "\n   ".join([capo, _dettagli(r), r["url"]])


def _sicuro(url: str | None) -> str:
    return html.escape(url, quote=True) if url and url.startswith(("http://", "https://")) else "#"


def _riga_html(r: dict, url_app: str | None, extra: str = "") -> str:
    nome = html.escape(r.get("datore") or r["titolo"])
    ruolo = html.escape(r["titolo"][:120]) if r.get("datore") and r["titolo"] != r["datore"] else ""
    legame = _sicuro(f"{url_app.rstrip('/')}/#o={r['id']}") if url_app else _sicuro(r["url"])
    colore = "#2F47C2" if r.get("piva") else "#5B6873"
    return (
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='margin:0 0 14px'><tr>"
        f"<td width='46' valign='top' style=\"font:700 21px/1.1 'DIN Alternate','Helvetica Neue',Arial,sans-serif;color:{colore};padding-top:1px\">{r['punteggio']}</td>"
        "<td valign='top' style=\"font:15px/1.4 -apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#18222B\">"
        f"<a href='{legame}' style='color:#18222B;font-weight:600;text-decoration:none'>{nome}</a>"
        + (f"<br><span style='color:#3D4A55'>{ruolo}</span>" if ruolo else "")
        + f"<br><span style='font-size:13px;color:#5B6873'>{html.escape(_dettagli(r))}</span>"
        + (f"<br><span style='font-size:13px;color:#8A5300'>{html.escape(extra)}</span>" if extra else "")
        + f"<br><a href='{_sicuro(r['url'])}' style='font-size:13px;color:#2F47C2'>Annuncio originale</a>"
        "</td></tr></table>")


def componi_email(report: dict, url_app: str | None) -> tuple[str, str, str]:
    """Ritorna (oggetto, testo semplice, HTML)."""
    giorno = date.fromisoformat(report["data"])
    breve = _giorno(report["data"])[:5]
    nuovi, aggiornati = report["nuovi"], report["aggiornati"]
    nuovi_piva = [r for r in nuovi if r.get("piva")]
    altri_nuovi = [r for r in nuovi if not r.get("piva")]
    n, s, p = len(nuovi), len(report["scadenze7"]), len(report["problemi"])
    stato = f"{_conta(report['attivi'], 'offerta attiva', 'offerte attive')}, {report['fonti_lette']} fonti lette su {report['fonti_totali']}"

    if not (n or s or p or aggiornati):
        oggetto = f"Radar {breve}: niente di nuovo"
        riga = f"Niente di nuovo oggi. {stato[0].upper() + stato[1:]}."
        if url_app:
            riga += f" App: {url_app}"
        return oggetto, riga, f"<p style=\"font:15px/1.5 -apple-system,'Segoe UI',Arial,sans-serif;color:#18222B\">{html.escape(riga)}</p>"

    parti = []
    if n:
        parti.append(_conta(n, "novità", "novità") + (f" ({len(nuovi_piva)} in libera professione)" if nuovi_piva else ""))
    if aggiornati:
        parti.append(_conta(len(aggiornati), "annuncio aggiornato", "annunci aggiornati"))
    if s:
        parti.append(_conta(s, "scadenza vicina", "scadenze vicine"))
    if p and not parti:
        parti.append(_conta(p, "fonte da controllare", "fonti da controllare"))
    titolo = ", ".join(parti)
    oggetto = f"Radar {breve}: {titolo}"

    sezioni: list[tuple[str, list[dict], bool]] = []
    if nuovi_piva:
        sezioni.append(("Novità in libera professione", nuovi_piva[:10], False))
    if altri_nuovi:
        sezioni.append(("Altre novità", altri_nuovi[:10], False))
    if aggiornati:
        sezioni.append(("Annunci aggiornati", aggiornati[:10], True))
    if report["scadenze7"]:
        sezioni.append(("Scadenze entro 7 giorni", report["scadenze7"], False))
    if report["top5"]:
        sezioni.append(("Le 5 migliori per punteggio", report["top5"], False))

    testo = [titolo[0].upper() + titolo[1:] + ".", stato[0].upper() + stato[1:] + "."]
    if url_app:
        testo.append(f"Apri l'app: {url_app}")
    stile_base = "font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#18222B"
    corpo = [
        f"<p style='margin:0;font-size:13px;color:#5B6873'>Radar infermiere, {html.escape(data_lunga(giorno))}</p>",
        f"<h1 style=\"margin:4px 0 6px;font:700 24px/1.2 'DIN Alternate','Helvetica Neue',Arial,sans-serif;color:#18222B\">{html.escape(titolo[0].upper() + titolo[1:])}</h1>",
        f"<p style='margin:0 0 16px;font-size:14px;color:#5B6873'>{html.escape(stato[0].upper() + stato[1:])}.</p>",
    ]
    if url_app:
        corpo.append(f"<p style='margin:0 0 22px'><a href='{_sicuro(url_app)}' style='display:inline-block;background:#2F47C2;"
                     "color:#ffffff;font-weight:600;font-size:15px;text-decoration:none;padding:11px 20px;border-radius:10px'>Apri l'app</a></p>")
    for nome, righe, con_cambi in sezioni:
        testo += ["", nome.upper()]
        corpo.append(f"<h2 style='margin:22px 0 12px;padding-top:14px;border-top:1px solid #DCE2E7;font-size:16px;font-weight:700'>{html.escape(nome)}</h2>")
        for r in righe:
            extra = ("Cambiato: " + "; ".join(r.get("cambi") or [])) if con_cambi and r.get("cambi") else ""
            testo.append("- " + _riga_testo(r) + (f"\n   {extra}" if extra else ""))
            corpo.append(_riga_html(r, url_app, extra))
    if report["problemi"]:
        testo += ["", "FONTI DA CONTROLLARE"] + [f"- {x}" for x in report["problemi"]]
        corpo.append("<h2 style='margin:22px 0 10px;padding-top:14px;border-top:1px solid #DCE2E7;font-size:16px;font-weight:700'>Fonti da controllare</h2>")
        corpo += [f"<p style='margin:0 0 8px;font-size:13px;color:#8A5300'>{html.escape(x)}</p>" for x in report["problemi"]]
    nota = "I dati sono estratti in automatico: apri sempre l'annuncio prima di muoverti."
    testo += ["", nota]
    corpo.append(f"<p style='margin:22px 0 0;font-size:12px;color:#7A8791'>{nota}</p>")
    pagina = f"<div style=\"max-width:560px;margin:0 auto;padding:8px 4px;{stile_base}\">" + "".join(corpo) + "</div>"
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
# Calendario (.ics) per le scadenze
# --------------------------------------------------------------------------

def _ics_testo(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_piega(riga: str) -> str:
    """Le righe .ics non devono superare 75 byte: quelle lunghe si spezzano con uno spazio iniziale."""
    pezzi, corrente = [], ""
    for carattere in riga:
        if len((corrente + carattere).encode("utf-8")) > 73:
            pezzi.append(corrente)
            corrente = " " + carattere
        else:
            corrente += carattere
    pezzi.append(corrente)
    return "\r\n".join(pezzi)


def evento_ics(a: dict, adesso: datetime) -> str:
    giorno = date.fromisoformat(a["scadenza"])
    nome = a.get("datore") or a["titolo"]
    descrizione = "\n".join(x for x in [a["titolo"], a.get("contratto"), a["url"]] if x)
    righe = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Radar Infermiere//IT", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{a['id']}@radar-infermiere",
        f"DTSTAMP:{adesso.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}",
        f"DTSTART;VALUE=DATE:{giorno:%Y%m%d}",
        f"DTEND;VALUE=DATE:{giorno + timedelta(days=1):%Y%m%d}",
        f"SUMMARY:{_ics_testo('Scadenza: ' + nome)}",
        f"DESCRIPTION:{_ics_testo(descrizione)}",
        f"URL:{a['url']}",
        "BEGIN:VALARM", "TRIGGER:-P2D", "ACTION:DISPLAY", "DESCRIPTION:Scadenza tra 2 giorni", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(_ics_piega(r) for r in righe) + "\r\n"


# --------------------------------------------------------------------------
# Web app
# --------------------------------------------------------------------------

CAMPI_APP = ["id", "url", "titolo", "datore", "contratto", "compenso", "euro_ora", "turni", "zona", "km",
             "minuti", "scadenza", "pubblicato", "fonte", "affidabilita", "punteggio", "dettaglio_punteggio",
             "avvisi", "estratto", "primo_visto", "ultimo_visto", "novita", "data_novita", "cambi",
             "sparito_dal", "origine", "nota_manuale", "struttura", "email", "pec", "in_tedesco", "scadenza_frase", "pdf_letti"]


def costruisci_sito(cfg: dict, oggi: date, destinazione: Path | None = None) -> Path:
    dest = destinazione or RADICE / "dist"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(RADICE / "webapp", dest)
    adesso = datetime.now(ROMA)

    memoria = motore.leggi_json(motore.FILE_ANNUNCI, {})
    offerte = []
    (dest / "ics").mkdir(exist_ok=True)
    for a in memoria.values():
        if not motore.visibile(a, cfg):
            continue
        # Le scadenze passate da tempo non servono più: restano in memoria ma non nell'app.
        if a.get("scadenza") and (oggi - date.fromisoformat(a["scadenza"])).days > int(cfg.get("giorni_scaduti_visibili", 60)):
            continue
        o = {k: a.get(k) for k in CAMPI_APP}
        o["datato"] = motore.e_datato(a, oggi, cfg)
        o["scaduto"] = motore.e_scaduto(a, oggi) or o["datato"]
        o["dipendente"] = motore.e_dipendente(a)
        o["piva"] = motore.e_piva(a)
        o["etichetta"] = ETICHETTE_CONTRATTO.get(a.get("contratto"))
        o["calendario"] = bool(a.get("scadenza")) and not o["scaduto"]
        if o["calendario"]:
            (dest / "ics" / f"{a['id']}.ics").write_text(evento_ics(a, adesso), encoding="utf-8", newline="")
        offerte.append(o)
    offerte.sort(key=lambda o: -o["punteggio"])

    report = []
    for f in sorted(motore.CARTELLA_REPORT.glob("*.json"), reverse=True)[:60]:
        report.append(json.loads(f.read_text(encoding="utf-8")))

    comuni = [{k: c[k] for k in ("nome", "km", "minuti", "lat", "lon")}
              for c in estrai.carica_comuni(RADICE / "data" / "comuni.csv")]
    dati = {"generato": adesso.strftime("%d/%m/%Y %H:%M"), "ora": adesso.strftime("%H:%M"),
            "oggi": oggi.isoformat(), "oggi_lungo": data_lunga(oggi),
            "casa": cfg.get("profilo", {}).get("casa", "Mezzolombardo"),
            "email_contatto": cfg.get("email_contatto") or {},
            "offerte": offerte, "report": report, "comuni": comuni}
    (dest / "dati.json").write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")

    # Ogni pubblicazione ha una versione nuova: così il telefono scarica i file aggiornati.
    sw = dest / "sw.js"
    sw.write_text(sw.read_text(encoding="utf-8").replace("__VERSIONE__", adesso.strftime("%Y%m%d%H%M")),
                  encoding="utf-8")
    return dest
