"""Radar Infermiere P.IVA – avvio:  python -m radar

Opzioni utili:
  --pianificato   esegue solo se a Roma sono passate le 7 e il giro del mattino non è ancora stato fatto
  --senza-email   non invia l'email (stampa il report)
  --solo-sito     ricostruisce solo la web app dai dati già salvati
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import yaml

from . import motore, uscite
from .rete import Rete

# Data dell'ultimo giro del mattino (quello pianificato). I giri avviati a mano non contano:
# così una prova fatta di notte non fa saltare l'email delle 7.
FILE_ULTIMO = motore.RADICE / "data" / "ultimo_giro.txt"


def _segnala_a_github(eseguito: bool) -> None:
    uscita = os.environ.get("GITHUB_OUTPUT")
    if uscita:
        with open(uscita, "a", encoding="utf-8") as f:
            f.write(f"eseguito={'true' if eseguito else 'false'}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Radar Infermiere P.IVA")
    ap.add_argument("--pianificato", action="store_true")
    ap.add_argument("--senza-email", action="store_true")
    ap.add_argument("--solo-sito", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((motore.RADICE / "config.yaml").read_text(encoding="utf-8"))
    adesso = datetime.now(uscite.ROMA)
    oggi = adesso.date()

    if args.solo_sito:
        print("Web app ricostruita in:", uscite.costruisci_sito(cfg, oggi))
        _segnala_a_github(True)
        return 0

    if args.pianificato:
        gia_fatto = FILE_ULTIMO.exists() and FILE_ULTIMO.read_text().strip() == oggi.isoformat()
        if adesso.hour < 7 or gia_fatto:
            print(f"Salto: a Roma sono le {adesso:%H:%M}" + (" e il giro del mattino è già stato fatto." if gia_fatto else "."))
            _segnala_a_github(False)
            return 0

    print(f"Radar Infermiere P.IVA – giro del {oggi:%d/%m/%Y}")
    report = motore.giro(cfg, Rete(cfg["rete"]), oggi)
    if args.pianificato:
        FILE_ULTIMO.write_text(oggi.isoformat() + "\n")
    uscite.costruisci_sito(cfg, oggi)

    url_app = os.environ.get("APP_URL", "").strip() or (cfg.get("app_url") or "").strip() or None
    oggetto, testo, pagina = uscite.componi_email(report, url_app)
    print("\n" + "=" * 60 + f"\n{oggetto}\n" + "=" * 60 + f"\n{testo}\n")
    if not args.senza_email:
        try:
            uscite.invia_email(oggetto, testo, pagina)
        except Exception as e:  # l'email non deve far fallire il giro: i dati sono già salvati
            print(f"⚠ Email non inviata: {type(e).__name__}: {e}", file=sys.stderr)
    _segnala_a_github(True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
