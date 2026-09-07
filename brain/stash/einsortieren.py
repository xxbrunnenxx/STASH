"""Wohin die Notiz gehört. Ohne Rückfrage.

„In welche Liste gehört das?" ist genau die Frage, an der eine Notiz liegen
bleibt. Sie wird nicht gestellt. Stattdessen entscheidet eine billige Regel
sofort, und der Nachtlauf räumt hinterher auf.

Die Regel: Anteil der Schlagwörter, die ein Trigger-Wort einer Liste treffen.
Über der Schwelle wandert die Notiz dorthin, darunter entsteht eine neue Liste.
Das fragmentiert lange Projekte — genau deshalb gibt es den Nachtlauf.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

FESTE_LISTEN = {
    "einkauf":  ["einkaufen", "besorgen", "holen", "mitbringen", "kaufen"],
    "tagebuch": ["heute war", "feierabend", "rückblick"],
    "ideen":    ["idee", "einfall", "vielleicht könnte man"],
    "termine":  ["termin", "kommt", "uhr"],
}

# Erzählform in der Vergangenheit, kein Auftrag, kein Termin → Tagebuch.
_TAGEBUCH_MARKER = re.compile(
    r"\b(feierabend|rückblick|heute war|war ich|hab ich|habe ich|hatte ich|"
    r"war der tag|den ganzen tag|vormittags|nachmittags|abends noch)\b",
    re.IGNORECASE,
)
_AUFTRAG = re.compile(r"\b(muss|müssen|soll|bestellen|besorgen|erfragen|prüfen|"
                      r"nachmessen|anrufen|nachschauen|kaufen)\b", re.IGNORECASE)
_UHRZEIT = re.compile(r"\b(\d{1,2}[:.]\d{2}|halb \w+|viertel \w+|\d{1,2} uhr)\b",
                      re.IGNORECASE)
_WOCHENTAG = re.compile(r"\b(montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)\b",
                        re.IGNORECASE)


@dataclass
class Liste:
    art: str = "gewachsen"            # fest · gewachsen · verblasst
    anzahl: int = 0
    seit: str = ""
    trigger: list[str] = field(default_factory=list)
    zuletzt: str = ""

    def as_dict(self) -> dict:
        return {"art": self.art, "anzahl": self.anzahl, "seit": self.seit,
                "trigger": self.trigger, "zuletzt": self.zuletzt}

    @staticmethod
    def from_dict(d: dict) -> "Liste":
        return Liste(d.get("art", "gewachsen"), int(d.get("anzahl", 0)),
                     d.get("seit", ""), list(d.get("trigger", [])),
                     d.get("zuletzt", ""))


@dataclass
class Zuordnung:
    ziel: str
    art: str                  # liste · tagebuch · neu
    score: float
    grund: str
    bestes_ziel: str = ""


def frische_listen() -> dict[str, Liste]:
    heute = date.today().strftime("%d.%m.")
    return {name: Liste("fest", 0, heute, list(trig))
            for name, trig in FESTE_LISTEN.items()}


def treffer(schlagworte: list[str], trigger: list[str]) -> float:
    """Anteil der Schlagwörter, die ein Trigger-Wort treffen.

    Bei drei Schlagwörtern gibt es nur 0 · 0,33 · 0,67 · 1,00 — dazwischen
    ändert die Schwelle nichts. Das ist keine Ungenauigkeit, sondern der Grund,
    warum an der Schwelle zu drehen so wenig bringt.
    """
    if not schlagworte:
        return 0.0
    menge = {t.lower() for t in trigger}
    getroffen = sum(
        1 for s in schlagworte
        if s.lower() in menge or any(t in s.lower() or s.lower() in t for t in menge)
    )
    return getroffen / len(schlagworte)


def einsortieren(text: str, schlagworte: list[str], listen: dict[str, Liste],
                 schwelle: float = 0.62) -> Zuordnung:
    # Tagebuch vor allem anderen: Wer erzählt, was war, will keine Liste.
    if _TAGEBUCH_MARKER.search(text) and not _AUFTRAG.search(text) and not _UHRZEIT.search(text):
        return Zuordnung("tagebuch", "tagebuch", 0.88,
                         "Erzählform in der Vergangenheit, kein Auftrag, kein Termin")

    if _UHRZEIT.search(text) and _WOCHENTAG.search(text):
        return Zuordnung("termine", "liste", 0.96,
                         "Wochentag und Uhrzeit erkannt")

    # Feste Listen zuerst, und für sie genügt ein wörtlicher Treffer. Sie sind
    # die vier, die nie verschwinden — wenn „einkaufen" fällt, darf daneben
    # keine zweite Einkaufsliste entstehen, nur weil die anderen zwei
    # Schlagwörter den Anteil unter die Schwelle drücken.
    klein = {s.lower() for s in schlagworte}
    for name, liste in listen.items():
        if liste.art != "fest":
            continue
        if klein & {t.lower() for t in liste.trigger} or name in klein:
            return Zuordnung(name, "liste", max(treffer(schlagworte, liste.trigger), 0.62),
                             "Trigger-Wort der festen Liste trifft")

    bestes, bester_wert = "", 0.0
    for name, liste in listen.items():
        w = treffer(schlagworte, liste.trigger + [name])
        if w > bester_wert:
            bester_wert, bestes = w, name

    if bester_wert >= schwelle:
        art = listen[bestes].art
        return Zuordnung(bestes, "liste", bester_wert,
                         f"Trigger-Wort trifft · {'feste' if art == 'fest' else 'gewachsene'} Liste")

    # Kein Treffer: Die neue Liste heißt nach dem erstgenannten Schlagwort,
    # nicht nach dem alphabetisch ersten. Worüber jemand anfängt zu reden, ist
    # das Thema — „#überdachung" statt „#meter". Der Name bleibt trotzdem eine
    # Verlegenheit; der Nachtlauf benennt um, wenn er den Zusammenhang sieht.
    name = schlagworte[0] if schlagworte else "unsortiert"
    return Zuordnung(name, "neu", bester_wert,
                     f"kein Treffer über Schwelle {schwelle:.2f}"
                     + (f" · bestes Ziel #{bestes} mit {bester_wert:.2f}" if bestes else ""),
                     bestes_ziel=bestes)


def aufgaben(text: str) -> list[str]:
    """Was aus der Notiz eine Erledigung ist. Absichtlich zurückhaltend: Eine
    erfundene Aufgabe kostet mehr Vertrauen, als eine übersehene kostet."""
    gefunden = []
    for satz in re.split(r"(?<=[.!?;])\s+", text):
        if not _AUFTRAG.search(satz):
            continue
        s = satz.strip(" .;")
        s = re.sub(r"^(und|aber|dann|also)\s+", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^(ich\s+)?(muss|müsste|sollte|soll)\s+(ich\s+)?", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(nochmal|unbedingt|noch)\b", "", s, flags=re.IGNORECASE)
        s = " ".join(s.split())
        if 4 <= len(s) <= 90:
            gefunden.append(s[:1].upper() + s[1:])
    return gefunden[:3]


def uebernehmen(zu: Zuordnung, schlagworte: list[str], listen: dict[str, Liste]) -> None:
    """Die Zuordnung in den Listenbestand einbuchen."""
    heute = date.today().strftime("%d.%m.")
    if zu.ziel not in listen:
        listen[zu.ziel] = Liste("gewachsen", 0, heute, list(schlagworte))
    liste = listen[zu.ziel]
    liste.anzahl += 1
    liste.zuletzt = date.today().isoformat()
    # Eine getroffene Liste lernt die Wörter dazu, mit denen sie getroffen
    # wurde. Sonst bliebe jede Liste bei dem Vokabular ihres ersten Tages.
    for s in schlagworte:
        if s not in liste.trigger:
            liste.trigger.append(s)
