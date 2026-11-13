"""Accesso alla rete, in modo educato: robots.txt, pause, user-agent dichiarato, niente login."""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

_ERRORI_PASSEGGERI = (502, 503, 504, 520, 522, 524)


class Rete:
    def __init__(self, cfg: dict):
        self.ua = cfg.get("user_agent", "RadarInfermierePIVA/2.0")
        self.pausa = float(cfg.get("pausa_secondi", 3))
        self.timeout = float(cfg.get("timeout_secondi", 25))
        self.sessione = requests.Session()
        self.sessione.headers.update({
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5",
            "Accept-Language": "it-IT,it;q=0.9,de;q=0.7",
        })
        self.richieste = 0
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
                self.richieste += 1
                r = self.sessione.get(chiave + "/robots.txt", timeout=self.timeout)
                if r.status_code == 200 and "<html" not in r.text[:300].lower():
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

    def _richiedi(self, url: str, robots: bool, a_pezzi: bool = False):
        """Ritorna (risposta, errore). Riprova una volta se l'errore sembra passeggero."""
        if robots and not self.permesso(url):
            return None, "bloccata da robots.txt (il sito non vuole essere letto da programmi)"
        errore = None
        for tentativo in (1, 2):
            try:
                self._aspetta(urlparse(url).netloc)
                self.richieste += 1
                r = self.sessione.get(url, timeout=self.timeout, stream=a_pezzi)
            except requests.Timeout:
                errore = "tempo scaduto"
            except requests.RequestException as e:
                errore = f"errore di rete ({type(e).__name__})"
            else:
                if r.status_code == 200:
                    return r, None
                errore = f"risposta HTTP {r.status_code}"
                if r.status_code not in _ERRORI_PASSEGGERI:
                    r.close()
                    return None, errore
                r.close()
            if tentativo == 1:
                time.sleep(max(4.0, self.pausa))
        return None, errore

    def get(self, url: str, robots: bool = True) -> tuple[str | None, str | None]:
        """Ritorna (testo, errore). Uno dei due è sempre None."""
        r, errore = self._richiedi(url, robots)
        if errore:
            return None, errore
        tipo = r.headers.get("Content-Type", "").lower()
        if "pdf" in tipo:
            return None, "è un PDF"
        if r.encoding is None or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "utf-8"
        return r.text, None

    def get_pdf(self, url: str, massimo_mb: float = 8, robots: bool = True) -> tuple[bytes | None, str | None]:
        """Scarica un PDF (con un limite di dimensione). Ritorna (dati, errore)."""
        r, errore = self._richiedi(url, robots, a_pezzi=True)
        if errore:
            return None, errore
        try:
            tipo = r.headers.get("Content-Type", "").lower()
            if "pdf" not in tipo and "octet-stream" not in tipo:
                return None, "non è un PDF"
            limite = int(massimo_mb * 1024 * 1024)
            if int(r.headers.get("Content-Length") or 0) > limite:
                return None, "PDF troppo grande"
            pezzi, totale = [], 0
            for pezzo in r.iter_content(65536):
                totale += len(pezzo)
                if totale > limite:
                    return None, "PDF troppo grande"
                pezzi.append(pezzo)
            dati = b"".join(pezzi)
            if not dati.startswith(b"%PDF"):
                return None, "non è un PDF"
            return dati, None
        except requests.RequestException as e:
            return None, f"errore di rete ({type(e).__name__})"
        finally:
            r.close()
