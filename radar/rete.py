"""Accesso alla rete, in modo educato: robots.txt, pause, user-agent dichiarato, niente login."""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import requests


class Rete:
    def __init__(self, cfg: dict):
        self.ua = cfg.get("user_agent", "RadarInfermierePIVA/1.0")
        self.pausa = float(cfg.get("pausa_secondi", 3))
        self.timeout = float(cfg.get("timeout_secondi", 25))
        self.sessione = requests.Session()
        self.sessione.headers.update({
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5",
            "Accept-Language": "it-IT,it;q=0.9,de;q=0.7",
        })
        self._ultima: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _aspetta(self, host: str) -> None:
        trascorso = time.monotonic() - self._ultima.get(host, 0)
        if trascorso < self.pausa:
            time.sleep(self.pausa - trascorso)
        self._ultima[host] = time.monotonic()

    def _regole(self, url: str):
        p = urlparse(url)
        chiave = f"{p.scheme}://{p.netloc}"
        if chiave not in self._robots:
            regole = None
            try:
                self._aspetta(p.netloc)
                r = self.sessione.get(chiave + "/robots.txt", timeout=self.timeout)
                if r.status_code == 200:
                    regole = urllib.robotparser.RobotFileParser()
                    regole.parse(r.text.splitlines())
                elif r.status_code >= 500:
                    regole = urllib.robotparser.RobotFileParser()
                    regole.parse(["User-agent: *", "Disallow: /"])
            except requests.RequestException:
                regole = None  # robots.txt non raggiungibile: l'errore vero emergerà sulla pagina
            self._robots[chiave] = regole
        return self._robots[chiave]

    def permesso(self, url: str) -> bool:
        regole = self._regole(url)
        return True if regole is None else regole.can_fetch(self.ua, url)

    def get(self, url: str, robots: bool = True) -> tuple[str | None, str | None]:
        """Ritorna (testo, errore). Uno dei due è sempre None."""
        if robots and not self.permesso(url):
            return None, "bloccata da robots.txt (il sito non vuole essere letto da programmi)"
        try:
            self._aspetta(urlparse(url).netloc)
            r = self.sessione.get(url, timeout=self.timeout)
        except requests.Timeout:
            return None, "tempo scaduto"
        except requests.RequestException as e:
            return None, f"errore di rete ({type(e).__name__})"
        if r.status_code != 200:
            return None, f"risposta HTTP {r.status_code}"
        tipo = r.headers.get("Content-Type", "").lower()
        if "pdf" in tipo:
            return None, "è un PDF (non letto)"
        if r.encoding is None or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "utf-8"
        return r.text, None
