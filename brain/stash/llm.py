"""Das Sprachmodell für den Nachtlauf.

Tagsüber wird keines gebraucht: Da entscheidet die billige Regel, und zwar
sofort, weil eine Rückmeldung nach zwei Sekunden etwas anderes ist als eine
nach zwanzig. Nachts ist Zeit — und nachts liegt zum ersten Mal alles
nebeneinander, was tagsüber einzeln vorbeikam.

STASH bringt kein Modell mit. Es spricht mit dem, das auf dem Pi läuft, über
die OpenAI-Schnittstelle — llama.cpp, Ollama und vLLM sprechen sie alle.
Antwortet keines, läuft der Nachtlauf trotzdem: Er legt dann Listen zusammen
und verdichtet nicht. Das ist die Hälfte des Nutzens, aber es fällt nichts aus.
"""

from __future__ import annotations

import logging

import httpx

from .einstellungen import Einstellungen

log = logging.getLogger("stash.llm")


class Modell:
    def __init__(self, e: Einstellungen):
        self.endpunkt = e.llm_endpunkt.rstrip("/")
        self.modell = e.llm_modell
        self.zeitlimit = e.llm_zeitlimit_s

    def erreichbar(self) -> bool:
        try:
            r = httpx.get(f"{self.endpunkt}/models", timeout=5)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def frage(self, auftrag: str, text: str, hoechstens: int = 700) -> str | None:
        """Eine Runde. Gibt None zurück, wenn nichts antwortet — Aufrufer prüfen
        das und machen ohne weiter, statt eine Ausnahme durchzureichen."""
        try:
            r = httpx.post(
                f"{self.endpunkt}/chat/completions",
                json={
                    "model": self.modell,
                    "messages": [
                        {"role": "system", "content": auftrag},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.2,     # Es soll zusammenfassen, nicht dichten.
                    "max_tokens": hoechstens,
                },
                timeout=self.zeitlimit,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as f:
            log.warning("kein LLM erreichbar (%s) — es wird nur zusammengelegt", f)
            return None


VERDICHTEN = (
    "Du fasst Sprachnotizen eines Tages zu einem Absatz zusammen, auf Deutsch.\n"
    "Regeln:\n"
    "- Nur wiedergeben, was dasteht. Nichts ergänzen, nichts ausschmücken.\n"
    "- Sachlich und beiläufig, wie eine Notiz an sich selbst.\n"
    "- Entscheidungen als Feststellung, Ungeklärtes getrennt darunter mit „Offen:\".\n"
    "- Keine Bewertung, keine Ermunterung, keine Frage an den Leser.\n"
    "- Höchstens fünf Sätze."
)

NAMEN = (
    "Du bekommst Stichwortlisten. Gib für jede in einer Zeile einen kurzen\n"
    "Themennamen aus, kleingeschrieben, ein Wort, ohne Raute, auf Deutsch.\n"
    "Antworte nur mit den Namen, einer je Zeile, in derselben Reihenfolge."
)

GEKLAERT = (
    "Du bekommst offene Fragen von gestern und Notizen von heute.\n"
    "Gib nur die Fragen aus, die heute beantwortet wurden, je Zeile im Format\n"
    "Frage | Antwort. Antwortet nichts darauf, lass die Zeile weg. Nichts erfinden."
)
