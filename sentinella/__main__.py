"""Giro della Sentinella: python -m sentinella [--prova]

Variabili d'ambiente (GitHub Secrets): SENTINELLA_USER, SENTINELLA_APP_PASSWORD.
--prova: legge e stampa cosa avrebbe segnalato, senza mandare email e senza salvare.
"""
from __future__ import annotations

import argparse
import email
import hashlib
import html
import imaplib
import json
import os
import smtplib
import sys
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from . import regole

ROMA = ZoneInfo("Europe/Rome")
RADICE = Path(__file__).resolve().parent.parent
FILE_STATO = RADICE / "data" / "sentinella_stato.json"
GIORNI_INDIETRO = 3


def _intestazione(valore) -> str:
    try:
        return str(make_header(decode_header(valore or "")))
    except Exception:
        return str(valore or "")


def _testo(msg) -> str:
    parti = []
    for parte in msg.walk() if msg.is_multipart() else [msg]:
        tipo = parte.get_content_type()
        if tipo not in ("text/plain", "text/html") or parte.get_filename():
            continue
        try:
            corpo = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        if tipo == "text/html":
            import re
            corpo = re.sub(r"(?is)<(script|style).*?</\1>", " ", corpo)
            corpo = html.unescape(re.sub(r"<[^>]+>", " ", corpo))
        parti.append(corpo)
        if tipo == "text/plain":
            break
    return " ".join(" ".join(parti).split())


def _impronta(mid: str) -> str:
    return hashlib.sha256(mid.encode()).hexdigest()[:20]


def leggi_stato() -> dict:
    try:
        return json.loads(FILE_STATO.read_text())
    except Exception:
        return {"visti": [], "ultimo_giro": None}


def scrivi_stato(stato: dict) -> None:
    stato["visti"] = stato["visti"][-3000:]
    FILE_STATO.write_text(json.dumps(stato, ensure_ascii=False, indent=1) + "\n")


def leggi_posta(utente: str, chiave: str, oggi: date, visti: set[str]) -> list[dict]:
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
    M.login(utente, chiave)
    trovati = []
    try:
        M.select("INBOX", readonly=True)
        dal = (oggi - timedelta(days=GIORNI_INDIETRO)).strftime("%d-%b-%Y")
        _, dati = M.search(None, "SINCE", dal)
        numeri = (dati[0] or b"").split()[-400:]
        for n in numeri:
            _, d = M.fetch(n, "(BODY.PEEK[])")
            if not d or not isinstance(d[0], tuple):
                continue
            msg = email.message_from_bytes(d[0][1])
            mid = (msg.get("Message-ID") or "").strip()
            if not mid or _impronta(mid) in visti:
                continue
            mittente = _intestazione(msg.get("From"))
            if parseaddr(mittente)[1].lower() == utente.lower():
                continue  # i nostri stessi avvisi
            oggetto = _intestazione(msg.get("Subject"))
            testo = _testo(msg)
            newsletter = bool(msg.get("List-Unsubscribe"))
            cat = regole.categoria(mittente, oggetto, testo, newsletter)
            voce = {"mid": mid, "categoria": cat}
            if cat:
                tutto = oggetto + " " + testo
                date_ = regole.date_trovate(tutto, oggi)
                voce.update({"da": parseaddr(mittente)[0] or parseaddr(mittente)[1], "oggetto": oggetto,
                             "date": date_, "importo": regole.importo(tutto),
                             "giorni": regole.urgenza(date_, oggi)})
            trovati.append(voce)
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return trovati


def ics(voci: list[dict]) -> bytes:
    righe = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Sentinella//IT", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    adesso = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for v in voci:
        for d, etichetta in v.get("date") or []:
            titolo = f"{etichetta}: {v['oggetto']}"[:120].replace(",", "\\,").replace(";", "\\;")
            uid = hashlib.sha1((v["mid"] + d.isoformat()).encode()).hexdigest() + "@sentinella"
            righe += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{adesso}",
                      f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
                      f"SUMMARY:{titolo}", f"DESCRIPTION:Da {v['da']}".replace(",", "\\,"),
                      "BEGIN:VALARM", "TRIGGER:-PT15H", "ACTION:DISPLAY", "DESCRIPTION:Promemoria", "END:VALARM",
                      "END:VEVENT"]
    righe.append("END:VCALENDAR")
    return ("\r\n".join(righe) + "\r\n").encode()


def componi(voci: list[dict], oggi: date) -> tuple[str, str, str]:
    urgenti = [v for v in voci if v.get("giorni") is not None and v["giorni"] <= 7]
    oggetto = f"Posta importante: {len(voci)} " + ("cosa" if len(voci) == 1 else "cose")
    if urgenti:
        oggetto += f", {len(urgenti)} entro 7 giorni"
    blocchi_txt, blocchi_html = [], []
    for cat in ("scadenza", "energia", "appuntamento", "airbnb", "booking"):
        gruppo = sorted([v for v in voci if v["categoria"] == cat], key=lambda v: (v.get("giorni") is None, v.get("giorni") or 0))
        if not gruppo:
            continue
        blocchi_txt.append(regole.TITOLI[cat].upper())
        blocchi_html.append(f"<h3 style='margin:18px 0 6px;font-size:16px'>{regole.TITOLI[cat]}</h3>")
        for v in gruppo:
            dettagli = []
            for d, etichetta in v.get("date") or []:
                giorni = (d - oggi).days
                quando = "oggi" if giorni == 0 else "domani" if giorni == 1 else f"tra {giorni} giorni"
                dettagli.append(f"{etichetta} {d:%d/%m/%Y} ({quando})")
            if v.get("importo"):
                dettagli.append(f"Importo {v['importo']}")
            link = "https://mail.google.com/mail/u/0/#search/" + quote("rfc822msgid:" + v["mid"].strip("<>"))
            blocchi_txt.append(f"- {v['da']}: {v['oggetto']}" + (f"\n  {' · '.join(dettagli)}" if dettagli else "") + f"\n  {link}")
            urg = v.get("giorni") is not None and v["giorni"] <= 7
            blocchi_html.append(
                "<p style='margin:0 0 10px'>" + ("<b style='color:#b42318'>Entro 7 giorni</b><br>" if urg else "")
                + f"<b>{html.escape(v['da'])}</b>: {html.escape(v['oggetto'])}"
                + (f"<br><span style='color:#475467'>{html.escape(' · '.join(dettagli))}</span>" if dettagli else "")
                + f"<br><a href='{html.escape(link)}'>Apri in Gmail</a></p>")
    nota = "Le date trovate sono nel file allegato: aprilo per aggiungerle al calendario."
    testo = "\n".join(blocchi_txt) + "\n\n" + nota
    pagina = ("<div style='font-family:-apple-system,Segoe UI,sans-serif;font-size:15px;line-height:1.45;color:#101828'>"
              + "".join(blocchi_html) + f"<p style='color:#475467;font-size:13px'>{nota}</p></div>")
    return oggetto, testo, pagina


def invia(utente: str, chiave: str, oggetto: str, testo: str, pagina: str, allegato: bytes | None) -> None:
    msg = EmailMessage()
    msg["Subject"] = oggetto
    msg["From"] = formataddr(("Sentinella", utente))
    msg["To"] = utente
    msg["Message-ID"] = make_msgid(domain=utente.split("@")[-1])
    msg.set_content(testo)
    msg.add_alternative(pagina, subtype="html")
    if allegato:
        msg.add_attachment(allegato, maintype="text", subtype="calendar", filename="date-da-ricordare.ics")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=40) as s:
        s.login(utente, chiave)
        s.send_message(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prova", action="store_true")
    args = ap.parse_args()
    utente = os.environ.get("SENTINELLA_USER", "").strip()
    chiave = os.environ.get("SENTINELLA_APP_PASSWORD", "").replace(" ", "")
    if not (utente and chiave):
        print("Sentinella non configurata: mancano SENTINELLA_USER e SENTINELLA_APP_PASSWORD nei Secrets.")
        return 0
    oggi = datetime.now(ROMA).date()
    stato = leggi_stato()
    visti = set(stato["visti"])
    try:
        voci = leggi_posta(utente, chiave, oggi, visti)
    except Exception as e:
        print(f"⚠ Posta non letta: {type(e).__name__}")
        return 1
    importanti = [v for v in voci if v["categoria"]]
    print(f"Messaggi nuovi letti: {len(voci)}, importanti: {len(importanti)}")
    for v in importanti:
        print(f"  [{v['categoria']}] giorni={v.get('giorni')} date={[d.isoformat() for d, _ in v.get('date') or []]}")
    if args.prova:
        return 0
    if importanti:
        oggetto, testo, pagina = componi(importanti, oggi)
        con_date = [v for v in importanti if v.get("date")]
        invia(utente, chiave, oggetto, testo, pagina, ics(con_date) if con_date else None)
        print("Avviso inviato.")
    stato["visti"] += [_impronta(v["mid"]) for v in voci]
    stato["ultimo_giro"] = datetime.now(ROMA).isoformat(timespec="minutes")
    scrivi_stato(stato)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("eseguito=true\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
