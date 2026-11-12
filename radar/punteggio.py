"""Punteggio 0–100 di un'offerta. I pesi stanno in config.yaml."""
from __future__ import annotations


def _contratto(c: str | None) -> tuple[float, str]:
    if c == "P.IVA / libera professione":
        return 1.0, "libera professione / P.IVA"
    if c == "P.IVA o dipendente":
        return 0.8, "P.IVA possibile (anche assunzione)"
    if c == "Collaborazione":
        return 0.67, "collaborazione"
    if c is None:
        return 0.27, "contratto non indicato"
    return 0.17, "posto da dipendente"


def _compenso(euro_ora: float | None, testo: str | None) -> tuple[float, str]:
    if euro_ora is None:
        return 0.2, f"compenso orario non indicato{f' ({testo})' if testo else ''}"
    if euro_ora >= 40:
        return 1.0, f"{euro_ora:g} €/h: ottimo"
    if euro_ora >= 30:
        return 0.6, f"{euro_ora:g} €/h: nella media"
    if euro_ora >= 25:
        return 0.4, f"{euro_ora:g} €/h: basso"
    return 0.2, f"{euro_ora:g} €/h: molto basso"


def _distanza(minuti: int | None) -> tuple[float, str]:
    if minuti is None:
        return 0.25, "zona non riconosciuta"
    if minuti <= 20:
        return 1.0, f"circa {minuti} min d'auto"
    if minuti <= 45:
        return 0.6, f"circa {minuti} min d'auto"
    if minuti <= 90:
        return 0.25, f"circa {minuti} min d'auto"
    return 0.0, f"circa {minuti} min d'auto: lontano"


def _turni(segnali: dict, testo: str | None) -> tuple[float, str]:
    if not segnali:
        return 0.33, "ore e turni non indicati"
    f = 0.3
    f += 0.35 if segnali.get("dodici") else 0
    f += 0.30 if segnali.get("notti") else 0
    f += 0.20 if segnali.get("weekend") else 0
    f += 0.15 if (segnali.get("pieno") or segnali.get("ore_settimana", 0) >= 20) else 0
    return min(1.0, f), testo or ""


_FONTE = {"ufficiale": (1.0, "ente o albo ufficiale"),
          "struttura": (0.8, "sito della struttura"),
          "aggregatore": (0.3, "aggregatore o avviso di ricerca")}


def calcola(a: dict, cfg: dict) -> tuple[int, list[dict]]:
    pesi = cfg["pesi"]
    parti = [
        ("Contratto", pesi["contratto"], *_contratto(a.get("contratto"))),
        ("Compenso", pesi["compenso"], *_compenso(a.get("euro_ora"), a.get("compenso"))),
        ("Distanza", pesi["distanza"], *_distanza(a.get("minuti"))),
        ("Ore e turni", pesi["turni"], *_turni(a.get("segnali_turni") or {}, a.get("turni"))),
        ("Fonte", pesi["fonte"], *_FONTE.get(a.get("affidabilita"), _FONTE["aggregatore"])),
    ]
    dettaglio, totale = [], 0.0
    for voce, peso, frazione, motivo in parti:
        punti = round(peso * frazione)
        totale += punti
        dettaglio.append({"voce": voce, "punti": punti, "max": peso, "motivo": motivo})
    if a.get("cita_tedesco") and cfg.get("profilo", {}).get("tedesco") == "no":
        pen = int(cfg.get("penalita_bilinguismo", 0))
        if pen:
            totale -= pen
            dettaglio.append({"voce": "Tedesco", "punti": -pen, "max": 0,
                              "motivo": "l'annuncio cita tedesco o bilinguismo"})
    return max(0, min(100, round(totale))), dettaglio
