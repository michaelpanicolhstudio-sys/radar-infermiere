"""Lettere di primo contatto, adattate alla struttura (tipo, lingua, distanza).

Sono richieste di informazioni, non candidature: si chiede se la struttura lavora con infermieri in libera
professione e a quali condizioni (compenso, turni e orari, periodo, referente). Le strutture dell'Alto Adige
ricevono il testo in tedesco con la versione italiana sotto.
"""
from __future__ import annotations

FIRMA_IT = "Cordiali saluti\nMichael Panico\nInfermiere"
FIRMA_DE = "Mit freundlichen Grüßen\nMichael Panico\nKrankenpfleger"

DOMANDE_IT = ("- il compenso orario (o per turno) previsto;\n"
              "- i turni e gli orari da coprire (mattina, pomeriggio, notte, fine settimana) e l'impegno minimo richiesto;\n"
              "- da quando ci sarebbe bisogno e per quanto tempo;\n"
              "- la persona di riferimento, per un eventuale breve colloquio.")
DOMANDE_DE = ("- den vorgesehenen Stundensatz (oder die Vergütung pro Dienst);\n"
              "- die zu besetzenden Dienste und Zeiten (Früh-, Spät-, Nachtdienst, Wochenende) und den Mindesteinsatz;\n"
              "- ab wann und für welchen Zeitraum Bedarf besteht;\n"
              "- eine Ansprechperson für ein kurzes Gespräch.")


def _vicino_it(s: dict) -> str:
    minuti = s.get("minuti")
    if minuti == 0:
        return "e abito qui a Mezzolombardo"
    if minuti is not None and minuti <= 45:
        return f"e abito a Mezzolombardo, a circa {minuti} minuti da voi"
    return "e abito a Mezzolombardo"


def _apertura_it(s: dict) -> str:
    nome, tipo = s["nome"], (s.get("tipo") or "").lower()
    if "agenzia" in tipo:
        return (f"vi scrivo per sapere se {nome} propone incarichi per infermieri in libera professione (con partita IVA) "
                "presso strutture o a domicilio in Trentino-Alto Adige, oppure solo lavoro in somministrazione.")
    if "domicil" in tipo:
        return (f"vi scrivo per sapere se {nome} collabora con infermieri libero professionisti per l'assistenza "
                "a domicilio o in struttura, in particolare tra Rotaliana, Trento e Bolzano.")
    if "soccorso" in tipo or "eventi" in tipo:
        return (f"vi scrivo per sapere se {nome} si avvale di infermieri libero professionisti per l'assistenza sanitaria "
                "a eventi e manifestazioni o per altri servizi.")
    if "casa di cura" in tipo or "clinica" in tipo or "dialisi" in tipo:
        return (f"vi scrivo per sapere se {nome} si avvale, o pensa di avvalersi, di infermieri libero professionisti "
                "nei reparti o negli ambulatori, anche per coperture di turni o sostituzioni.")
    if "prelievi" in tipo or "ambulator" in tipo:
        return (f"vi scrivo per sapere se {nome} collabora con infermieri libero professionisti, per esempio per "
                "prelievi o attività ambulatoriali, anche a ore.")
    return (f"vi scrivo per sapere se {nome} si avvale, o pensa di avvalersi, di infermieri libero professionisti "
            "per coprire turni, sostituzioni o periodi di maggiore bisogno.")


def lettera(s: dict, rif: str) -> dict:
    """Oggetto e testo per la struttura s (servono: nome, tipo, minuti, provincia)."""
    nome = s["nome"]
    italiano = (
        "Buongiorno,\n\n"
        f"mi chiamo Michael Panico, sono infermiere iscritto all'OPI {_vicino_it(s)}. "
        "Sto valutando di lavorare in libera professione, con partita IVA, nelle strutture del Trentino-Alto Adige e "
        + _apertura_it(s) + "\n\n"
        "Se è così, vi sarei grato se poteste indicarmi:\n" + DOMANDE_IT + "\n\n"
        "Resto a disposizione per qualsiasi chiarimento.\n\n" + FIRMA_IT)
    if s.get("provincia") == "BZ":
        tedesco = (
            "Sehr geehrte Damen und Herren,\n\n"
            "mein Name ist Michael Panico, ich bin eingetragener Krankenpfleger und wohne in Mezzolombardo. "
            "Ich überlege, als freiberuflicher Krankenpfleger (mit MwSt.-Nummer) in Südtirol zu arbeiten, und möchte fragen, "
            f"ob {nome} freiberufliche Pflegefachkräfte einsetzt oder einsetzen möchte, zum Beispiel für Dienste, Vertretungen "
            "oder Zeiten mit erhöhtem Bedarf.\n\n"
            "Falls ja, wäre ich Ihnen für folgende Informationen dankbar:\n" + DOMANDE_DE + "\n\n"
            "Ich spreche Italienisch und lerne Deutsch: Sie können mir gerne auch auf Italienisch antworten.\n\n" + FIRMA_DE)
        return {"oggetto": f"Freiberuflicher Krankenpfleger / Infermiere libero professionista – Anfrage (Rif. {rif})",
                "testo": tedesco + "\n\n— Versione italiana —\n\n" + italiano}
    return {"oggetto": f"Infermiere libero professionista – richiesta di informazioni (Rif. {rif})", "testo": italiano}


def lettera_annuncio(a: dict, modello: dict, rif: str) -> dict:
    """Per chi ha pubblicato un annuncio: il modello di config.yaml (email_contatto)."""
    valori = {"titolo": a.get("titolo") or "", "datore": a.get("datore") or "", "fonte": a.get("fonte") or "", "rif": rif}
    return {"oggetto": (modello.get("oggetto") or "Richiesta di informazioni – {titolo} (Rif. {rif})").format(**valori),
            "testo": (modello.get("testo") or "").format(**valori)}
