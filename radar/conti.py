"""I conti della libera professione: quanto resta in tasca e quanti turni servono per l'obiettivo.

È una stima, non una consulenza: regime forfettario (coefficiente 78%), contributo ENPAPI sul reddito,
imposta sostitutiva sul reddito al netto dei contributi. Il 4% integrativo ENPAPI lo paga il cliente in fattura.
Tutti i numeri si cambiano in config.yaml, alla voce "conti".
"""
from __future__ import annotations

import math
from pathlib import Path

BASE = {
    "obiettivo_netto_mese": 3000,   # quello che deve restare, dopo tutto
    "fondo_pensione_mese": 500,     # 6.000 € l'anno
    "spese_fisse_mese": 250,        # assicurazione, OPI, commercialista, formazione, maternità ENPAPI
    "costo_km": 0.25,
    "coefficiente": 0.78,
    "enpapi": 0.16,
    "imposta": 0.05,                # 5% nei primi 5 anni, poi 15%
    "ore_turno": 8,
    "turni_mese": 16,
    "tariffa_predefinita": 35,
    "limite_forfettario": 85000,
}


def parametri(cfg: dict) -> dict:
    p = dict(BASE)
    p.update({k: v for k, v in (cfg.get("conti") or {}).items() if k in BASE and v is not None})
    return p


def quota_netta(p: dict) -> float:
    """Quanto resta di ogni euro fatturato dopo ENPAPI e imposta."""
    contributi = p["coefficiente"] * p["enpapi"]
    imposta = (p["coefficiente"] - contributi) * p["imposta"]
    return 1 - contributi - imposta


def netto_mese(fatturato: float, p: dict, viaggio: float = 0.0) -> float:
    return fatturato * quota_netta(p) - viaggio - p["spese_fisse_mese"] - p["fondo_pensione_mese"]


def conto_offerta(a: dict, p: dict) -> dict:
    """Numeri di un'offerta: netto all'ora, anche contando il viaggio, e turni per arrivare all'obiettivo."""
    tariffa = a.get("euro_ora")
    stimata = tariffa is None
    tariffa = float(tariffa or p["tariffa_predefinita"])
    ore = 12 if (a.get("segnali_turni") or {}).get("dodici") else p["ore_turno"]
    km, minuti = float(a.get("km") or 0), float(a.get("minuti") or 0)
    viaggio_turno = 2 * km * p["costo_km"]
    netto_turno = tariffa * ore * quota_netta(p) - viaggio_turno
    serve = p["obiettivo_netto_mese"] + p["fondo_pensione_mese"] + p["spese_fisse_mese"]
    turni = math.ceil(serve / netto_turno) if netto_turno > 0 else None
    return {
        "tariffa": tariffa, "tariffa_stimata": stimata, "ore_turno": ore,
        "netto_turno": round(netto_turno, 2),
        "netto_ora": round(netto_turno / ore, 2),
        "netto_ora_porta_a_porta": round(netto_turno / (ore + 2 * minuti / 60), 2),
        "turni_per_obiettivo": turni,
        "fatturato_annuo": round(tariffa * ore * (turni or 0) * 12),
    }


def scrivi_excel(a: dict, p: dict, percorso: Path, risposte: list[dict] | None = None) -> Path:
    """Foglio costi-benefici di un'offerta, con le formule vive: cambi un numero e si ricalcola tutto."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    c = conto_offerta(a, p)
    wb = Workbook()
    ws = wb.active
    ws.title = "Costi e benefici"
    grassetto, grigio = Font(bold=True), Font(color="5B6873", italic=True)
    giallo = PatternFill("solid", fgColor="FFF4CC")
    ws["A1"], ws["A1"].font = (a.get("datore") or a.get("titolo") or "Offerta")[:90], Font(bold=True, size=14)
    ws["A2"], ws["A2"].font = (a.get("titolo") or "")[:120], grigio
    righe = [
        (4, "Dati (le caselle gialle si possono cambiare)", None, None),
        (5, "Compenso lordo all'ora (€)", c["tariffa"], "stimato: l'annuncio non lo dice" if c["tariffa_stimata"] else "dall'annuncio o dalla risposta"),
        (6, "Ore per turno", c["ore_turno"], None),
        (7, "Turni al mese", p["turni_mese"], None),
        (8, "Km di sola andata", a.get("km") or 0, a.get("zona") or "zona non indicata"),
        (9, "Minuti di sola andata", a.get("minuti") or 0, None),
        (10, "Costo dell'auto al km (€)", p["costo_km"], None),
        (11, "Coefficiente di redditività (forfettario)", p["coefficiente"], None),
        (12, "Contributo ENPAPI sul reddito", p["enpapi"], "il 4% integrativo lo paga il cliente"),
        (13, "Imposta sostitutiva", p["imposta"], "5% nei primi 5 anni, poi 15%"),
        (14, "Spese fisse al mese (€)", p["spese_fisse_mese"], "assicurazione, OPI, commercialista, formazione"),
        (15, "Fondo pensione al mese (€)", p["fondo_pensione_mese"], None),
        (16, "Obiettivo netto al mese (€)", p["obiettivo_netto_mese"], None),
        (18, "Risultato", None, None),
        (19, "Fatturato al mese", "=B5*B6*B7", None),
        (20, "Contributi ENPAPI", "=B19*B11*B12", None),
        (21, "Imposta sostitutiva", "=(B19*B11-B20)*B13", None),
        (22, "Costo dei viaggi", "=B7*2*B8*B10", None),
        (23, "Netto dopo tasse, contributi e viaggi", "=B19-B20-B21-B22", None),
        (24, "Netto dopo anche spese fisse e fondo pensione", "=B23-B14-B15", "è la cifra da confrontare con l'obiettivo"),
        (25, "Differenza rispetto all'obiettivo", "=B24-B16", "positivo: obiettivo raggiunto"),
        (26, "Netto per ora lavorata", "=IF(B6*B7>0,B23/(B6*B7),0)", None),
        (27, "Netto per ora contando il viaggio", "=IF(B7>0,B23/(B7*(B6+2*B9/60)),0)", "ore fuori casa, porta a porta"),
        (28, "Turni al mese per raggiungere l'obiettivo",
         "=IF(B5*B6*(1-B11*B12-(B11-B11*B12)*B13)-2*B8*B10>0,ROUNDUP((B16+B15+B14)/(B5*B6*(1-B11*B12-(B11-B11*B12)*B13)-2*B8*B10),0),\"n.d.\")", None),
        (29, "Fatturato in un anno", "=B19*12", None),
        (30, "Margine sotto il limite del forfettario", f"={p['limite_forfettario']}-B29", "se negativo si esce dal regime"),
    ]
    for riga, nome, valore, nota in righe:
        ws.cell(riga, 1, nome)
        if valore is None:
            ws.cell(riga, 1).font = grassetto
            continue
        cella = ws.cell(riga, 2, valore)
        if 5 <= riga <= 16:
            cella.fill = giallo
        cella.number_format = "0.00%" if riga in (11, 12, 13) else ("0" if riga in (6, 7, 8, 9, 28) else "#,##0.00")
        if nota:
            ws.cell(riga, 3, nota).font = grigio
    for riga in (24, 25, 28):
        ws.cell(riga, 1).font = ws.cell(riga, 2).font = grassetto
    ws["A32"], ws["A32"].font = "Stima, non consulenza fiscale: prima di decidere fai controllare i numeri al commercialista.", grigio
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width, ws.column_dimensions["C"].width = 46, 14, 48

    fogli = wb.create_sheet("Annuncio e risposte")
    fogli.column_dimensions["A"].width, fogli.column_dimensions["B"].width = 22, 110
    dati = [("Annuncio", a.get("url")), ("Contratto", a.get("contratto")), ("Compenso dichiarato", a.get("compenso")),
            ("Ore e turni", a.get("turni")), ("Scadenza", a.get("scadenza")), ("Contatti", a.get("email") or a.get("pec"))]
    for i, (nome, valore) in enumerate(dati, start=1):
        fogli.cell(i, 1, nome).font = grassetto
        fogli.cell(i, 2, valore or "n.d.")
    riga = len(dati) + 2
    for r in risposte or []:
        fogli.cell(riga, 1, f"Risposta del {r.get('data', '')}").font = grassetto
        fogli.cell(riga, 2, f"{r.get('da', '')} – {r.get('oggetto', '')}")
        cella = fogli.cell(riga + 1, 2, (r.get("testo") or "")[:3000])
        cella.alignment = Alignment(wrap_text=True, vertical="top")
        riga += 3
    percorso.parent.mkdir(parents=True, exist_ok=True)
    wb.save(percorso)
    return percorso
