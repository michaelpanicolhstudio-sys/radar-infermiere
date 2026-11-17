"""Regole della Sentinella: cosa è importante, di che tipo, e quali date e importi contiene.

Funzioni pure, senza rete: si provano in tests/prova.py.
"""
from __future__ import annotations

import re
from datetime import date

# Mittenti (pezzi del dominio o dell'indirizzo) per categoria.
MITTENTI = {
    "airbnb": ["airbnb."],
    "booking": ["booking.com"],
    "energia": ["enel", "eni.com", "plenitude", "edison", "a2a", "hera", "iren", "dolomitienergia",
                "dolomiti energia", "sorgenia", "acea", "illumia", "octopus", "engie", "eon-energia",
                "e.on", "servizioelettriconazionale", "servizio elettrico", "agsm", "estra", "iberdrola",
                "pulsee", "wekiwi", "nen.it", "alperia", "duferco", "enegan", "optima"],
}

# Parole nell'oggetto o nel testo, per categoria. Tutto in minuscolo.
PAROLE = {
    "airbnb": ["prenotazione confermata", "nuova prenotazione", "richiesta di prenotazione", "prenotazione cancellata",
               "cancellazione", "modifica della prenotazione", "reservation confirmed", "booking request",
               "cancelled", "canceled", "pagamento inviato", "payout", "recensione", "check-in"],
    "booking": ["nuova prenotazione", "cancellazione", "modifica", "new booking", "cancellation",
                "prenotazione confermata", "richiesta dell'ospite", "messaggio dall'ospite", "check-in", "fattura"],
    "energia": ["bolletta", "fattura", "scadenza", "variazione", "modifica unilaterale", "rinnovo", "nuove condizioni",
                "condizioni economiche", "addebito", "sollecito", "mora", "lettura contatore", "autolettura",
                "conguaglio", "contratto", "offerta in scadenza"],
    "appuntamento": ["appuntamento", "promemoria", "visita", "conferma prenotazione", "ti aspettiamo",
                     "il tuo appuntamento", "cup", "prenotazione confermata", "revisione", "tagliando"],
    "scadenza": ["in scadenza", "scadenza", "scade il", "scadrà", "rinnovo", "ultimo avviso", "sollecito", "mora",
                 "avviso di pagamento", "pagopa", "bollo auto", "rc auto", "polizza", "assicurazione",
                 "agenzia delle entrate", "f24", "tari", "imu", "multa", "verbale"],
}

TITOLI = {"airbnb": "Airbnb", "booking": "Booking", "energia": "Luce e gas",
          "appuntamento": "Appuntamenti", "scadenza": "Scadenze e pagamenti"}

# Parole che rendono «forte» un messaggio anche se è una newsletter.
FORTI = ["scadenza", "scade il", "appuntamento", "prenotazione", "cancellazione", "sollecito", "bolletta",
         "avviso di pagamento", "modifica unilaterale", "variazione", "rinnovo", "check-in", "reservation"]

# Pubblicità: si scartano se non c'è nulla di forte.
PUBBLICITA = ["offerta speciale", "sconto", "promo", "newsletter", "black friday", "saldi", "scopri",
              "ultimi giorni per", "risparmia", "regalo", "% di sconto", "codice sconto"]

MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
        "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
        "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8, "set": 9,
        "ott": 10, "nov": 11, "dic": 12}

# Parole che, vicino a una data, dicono che cosa è quella data.
INDIZI_DATA = [("check-in", "Check-in"), ("arrivo", "Arrivo ospiti"), ("check-out", "Check-out"),
               ("partenza", "Partenza ospiti"), ("scadenza", "Scadenza"), ("scade", "Scadenza"),
               ("entro il", "Scadenza"), ("entro", "Scadenza"), ("appuntamento", "Appuntamento"),
               ("visita", "Appuntamento"), ("il giorno", "Appuntamento"), ("dal", "Dal"), ("decorrenza", "Decorrenza")]


def _minuscolo(*parti: str) -> str:
    return " ".join(p or "" for p in parti).lower()


def categoria(mittente: str, oggetto: str, testo: str, newsletter: bool = False) -> str | None:
    """Restituisce la categoria del messaggio, o None se non è importante."""
    da = (mittente or "").lower()
    ogg = (oggetto or "").lower()
    tutto = _minuscolo(oggetto, testo[:4000] if testo else "")
    forte = any(p in tutto for p in FORTI)
    if any(p in ogg for p in PUBBLICITA) and not forte:
        return None
    for cat in ("airbnb", "booking", "energia"):
        if any(m in da for m in MITTENTI[cat]):
            if any(p in tutto for p in PAROLE[cat]):
                return cat
            return None if newsletter else (cat if cat != "energia" else None)
    if newsletter and not forte:
        return None
    if any(p in ogg for p in PAROLE["appuntamento"]):
        return "appuntamento"
    if any(p in ogg for p in PAROLE["scadenza"]):
        return "scadenza"
    if any(p in tutto for p in ["bolletta", "fornitura di energia", "fornitura gas", "pod ", "pdr "]):
        return "energia"
    return None


_RE_NUM = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\b")
_RE_TESTO = re.compile(r"\b(\d{1,2})\s+(" + "|".join(sorted(MESI, key=len, reverse=True)) + r")\.?\s+(\d{4})\b", re.I)
_RE_EURO = re.compile(r"(?:€\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)|(\d{1,3}(?:\.\d{3})*(?:,\d{2})|\d+,\d{2})\s?(?:€|euro|eur)\b)", re.I)


def _data(g: int, m: int, a: int) -> date | None:
    if a < 100:
        a += 2000
    try:
        return date(a, m, g)
    except ValueError:
        return None


def date_trovate(testo: str, oggi: date) -> list[tuple[date, str]]:
    """Date future (fino a 400 giorni) con un'etichetta presa dalle parole vicine. Senza doppioni."""
    t = (testo or "")
    trovate: list[tuple[int, date]] = []
    for m in _RE_NUM.finditer(t):
        d = _data(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            trovate.append((m.start(), d))
    for m in _RE_TESTO.finditer(t):
        d = _data(int(m.group(1)), MESI[m.group(2).lower()], int(m.group(3)))
        if d:
            trovate.append((m.start(), d))
    risultato: list[tuple[date, str]] = []
    viste = set()
    for pos, d in sorted(trovate):
        if not (oggi <= d and (d - oggi).days <= 400) or d in viste:
            continue
        prima = t[max(0, pos - 60):pos].lower()
        etichetta, vicino = "Data", -1
        for parola, nome in INDIZI_DATA:
            i = prima.rfind(parola)
            if i > vicino:  # vince la parola più vicina alla data
                etichetta, vicino = nome, i
        viste.add(d)
        risultato.append((d, etichetta))
    return risultato[:4]


def importo(testo: str) -> str | None:
    m = _RE_EURO.search(testo or "")
    if not m:
        return None
    return (m.group(1) or m.group(2)) + " €"


def urgenza(date_: list[tuple[date, str]], oggi: date) -> int | None:
    """Giorni alla prima data utile, oppure None."""
    giorni = [(d - oggi).days for d, _ in date_]
    return min(giorni) if giorni else None
