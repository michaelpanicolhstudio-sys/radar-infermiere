"""Radar Infermiere P.IVA – avvio:  python -m radar

Opzioni utili:
  --pianificato   esegue solo se a Roma sono passate le 7 e il giro del mattino non è ancora stato fatto
  --senza-email   non invia l'email (stampa il report)
  --solo-sito     ricostruisce solo la web app dai dati già salvati
  --solo-posta    controlla solo le risposte delle strutture (ogni 2 ore, 8-22); email solo se ce ne sono di nuove
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import yaml

from . import estrai, invio, motore, strutture, uscite
from .rete import Rete

# Data dell'ultimo giro del mattino (quello pianificato). I giri avviati a mano non contano:
# così una prova fatta di notte non fa saltare l'email delle 7.
FILE_ULTIMO = motore.RADICE / "data" / "ultimo_giro.txt"


def _segnala_a_github(eseguito: bool) -> None:
    uscita = os.environ.get("GITHUB_OUTPUT")
    if uscita:
        with open(uscita, "a", encoding="utf-8") as f:
            f.write(f"eseguito={'true' if eseguito else 'false'}\n")


def controlla_risposte(cfg: dict, oggi, adesso) -> int:
    """Controllo leggero: solo le risposte alle lettere. Non legge i siti, non tocca i report.
    Se non c'è niente di nuovo non salva e non pubblica nulla."""
    if not 8 <= adesso.hour <= 22:
        print(f"Salto: a Roma sono le {adesso:%H:%M}.")
        _segnala_a_github(False)
        return 0
    try:
        nuove, _ = uscite.aggiorna_posta(cfg, oggi)
    except Exception as e:
        print(f"⚠ Posta non letta: {type(e).__name__}: {e}", file=sys.stderr)
        _segnala_a_github(False)
        return 0
    if not nuove:
        print("Nessuna risposta nuova.")
        _segnala_a_github(False)
        return 0
    uscite.costruisci_sito(cfg, oggi)
    url_app = os.environ.get("APP_URL", "").strip() or (cfg.get("app_url") or "").strip() or ""
    oggetto = f"Radar {oggi:%d/%m}: " + (f"{len(nuove)} risposte nuove" if len(nuove) > 1 else f"ha risposto {nuove[0].get('nome') or nuove[0]['da']}")
    blocchi = []
    for r in nuove:
        pezzo = (r.get("testo") or "").strip()
        if len(pezzo) > 700:
            pezzo = pezzo[:700].rsplit(" ", 1)[0] + "…"
        blocchi.append(f"{r.get('nome') or r['da']} ({r['da']})\n{pezzo}")
    testo = "\n\n".join(blocchi) + ("\n\nTutte le risposte nell'app, in Altro > Contatti: " + url_app if url_app else "")
    import html as _html
    pagina = "<div style=\"font-family:sans-serif;font-size:15px;line-height:1.5\">" + "".join(
        f"<p><b>{_html.escape(b.split(chr(10), 1)[0])}</b><br>{_html.escape(b.split(chr(10), 1)[1] if chr(10) in b else '').replace(chr(10), '<br>')}</p>"
        for b in blocchi) + (f"<p><a href=\"{_html.escape(url_app)}\">Apri il Radar</a></p>" if url_app else "") + "</div>"
    print(oggetto + "\n" + testo)
    try:
        uscite.invia_email(oggetto, testo, pagina)
    except Exception as e:
        print(f"⚠ Email non inviata: {type(e).__name__}: {e}", file=sys.stderr)
    _segnala_a_github(True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Radar Infermiere P.IVA")
    ap.add_argument("--pianificato", action="store_true")
    ap.add_argument("--senza-email", action="store_true")
    ap.add_argument("--solo-sito", action="store_true")
    ap.add_argument("--solo-posta", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((motore.RADICE / "config.yaml").read_text(encoding="utf-8"))
    adesso = datetime.now(uscite.ROMA)
    oggi = adesso.date()

    if args.solo_sito:
        print("Web app ricostruita in:", uscite.costruisci_sito(cfg, oggi))
        _segnala_a_github(True)
        return 0

    if args.solo_posta:
        return controlla_risposte(cfg, oggi, adesso)

    if args.pianificato:
        gia_fatto = FILE_ULTIMO.exists() and FILE_ULTIMO.read_text().strip() == oggi.isoformat()
        if adesso.hour < 7 or gia_fatto:
            print(f"Salto: a Roma sono le {adesso:%H:%M}" + (" e il giro del mattino è già stato fatto." if gia_fatto else "."))
            _segnala_a_github(False)
            return 0

    print(f"Radar Infermiere P.IVA – giro del {oggi:%d/%m/%Y}")
    try:
        # Nei giri di prova (senza email) la posta non si legge: una risposta registrata lì non verrebbe mai segnalata.
        risposte_nuove, avvisi = ([], {}) if args.senza_email else uscite.aggiorna_posta(cfg, oggi)
    except Exception as e:  # la posta non deve far fallire il giro
        print(f"⚠ Posta non letta: {type(e).__name__}: {e}", file=sys.stderr)
        risposte_nuove, avvisi = [], {}
    report = motore.giro(cfg, Rete(cfg["rete"]), oggi, avvisi=avvisi)
    try:
        comuni = estrai.carica_comuni(motore.RADICE / "data" / "comuni.csv")
        cache = motore.leggi_json(uscite.FILE_STRUTTURE_AUTO, {})
        cache, note = strutture.aggiorna(Rete(cfg["rete"]), comuni, oggi, cache)
        motore.scrivi_json(uscite.FILE_STRUTTURE_AUTO, cache)
        diag = motore.leggi_json(motore.FILE_DIAGNOSTICA, {})
        diag["strutture"] = note
        motore.scrivi_json(motore.FILE_DIAGNOSTICA, diag)
    except Exception as e:  # l'elenco delle strutture non deve far fallire il giro
        print(f"⚠ Strutture non aggiornate: {type(e).__name__}: {e}", file=sys.stderr)
    if args.pianificato:
        FILE_ULTIMO.write_text(oggi.isoformat() + "\n")
    inviate = []
    if args.pianificato and not args.senza_email:
        # Lettere di primo contatto: solo nel giro del mattino e solo se attivate in config.yaml.
        try:
            comuni = estrai.carica_comuni(motore.RADICE / "data" / "comuni.csv")
            contatti = motore.leggi_json(uscite.FILE_CONTATTI, {})
            voci = invio.coda(uscite.leggi_strutture(comuni), motore.leggi_json(motore.FILE_ANNUNCI, {}), contatti, cfg, oggi)
            inviate = invio.invia(voci, contatti, cfg, oggi)
            motore.scrivi_json(uscite.FILE_CONTATTI, contatti)
        except Exception as e:
            print(f"⚠ Lettere non inviate: {type(e).__name__}: {e}", file=sys.stderr)
    # Invio una tantum («tastare il terreno»): una sola volta, nel giorno indicato in config.yaml (invio.una_tantum),
    # anche nei giri di prova. Le strutture con sola PEC si saltano: le invia Michael dalla sua casella PEC.
    una_tantum = str((cfg.get("invio") or {}).get("una_tantum") or "")
    segno = motore.RADICE / "data" / "invio_una_tantum.txt"
    if una_tantum == oggi.isoformat() and (not segno.exists() or segno.read_text().strip() != una_tantum):
        try:
            comuni = estrai.carica_comuni(motore.RADICE / "data" / "comuni.csv")
            contatti = motore.leggi_json(uscite.FILE_CONTATTI, {})
            voci = [v for v in invio.coda(uscite.leggi_strutture(comuni), motore.leggi_json(motore.FILE_ANNUNCI, {}), contatti, cfg, oggi)
                    if not v["via_pec"] and not any(x.lower() in v["nome"].lower() for x in (cfg.get("invio") or {}).get("escludi", []))]
            inviate += invio.invia(voci, contatti, cfg, oggi, forza=True, massimo=int((cfg.get("invio") or {}).get("una_tantum_massimo", 80)))
            motore.scrivi_json(uscite.FILE_CONTATTI, contatti)
            segno.write_text(una_tantum + "\n")
        except Exception as e:
            print(f"⚠ Lettere una tantum non inviate: {type(e).__name__}: {e}", file=sys.stderr)
    dest = uscite.costruisci_sito(cfg, oggi)
    memoria = motore.leggi_json(motore.FILE_ANNUNCI, {})
    contatti = motore.leggi_json(uscite.FILE_CONTATTI, {})
    report["risposte_nuove"] = risposte_nuove
    report["lettere_inviate"] = [v["nome"] for v in inviate]
    report["da_contattare"] = [{"id": a["id"], "titolo": a["titolo"], "datore": a.get("datore")}
                               for a in uscite.scegli_da_contattare(memoria, contatti, cfg, oggi)]
    allegati = []
    if risposte_nuove and (dest / "report" / "resoconto-contatti.xlsx").exists():
        allegati.append(dest / "report" / "resoconto-contatti.xlsx")
    for r in risposte_nuove:
        sid = r["chiave"].split(":")[-1]
        allegati += [f for f in (dest / "report" / f"{sid}.xlsx", dest / "ics" / f"incontro-{sid}.ics") if f.exists() and f not in allegati]

    url_app = os.environ.get("APP_URL", "").strip() or (cfg.get("app_url") or "").strip() or None
    oggetto, testo, pagina = uscite.componi_email(report, url_app)
    print("\n" + "=" * 60 + f"\n{oggetto}\n" + "=" * 60 + f"\n{testo}\n")
    if not args.senza_email:
        try:
            uscite.invia_email(oggetto, testo, pagina, allegati=allegati)
        except Exception as e:  # l'email non deve far fallire il giro: i dati sono già salvati
            print(f"⚠ Email non inviata: {type(e).__name__}: {e}", file=sys.stderr)
    _segnala_a_github(True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
