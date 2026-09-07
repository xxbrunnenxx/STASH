"""Schlagwörter aus dem bereinigten Text.

Regelbasiert, ohne Modell — im Deutschen tragen die großgeschriebenen Wörter
den Inhalt, und das reicht für die Einsortierung. Die Wörter sind gleichzeitig
die Begründung, die später in der Listenansicht steht: Wer sehen will, warum
eine Notiz irgendwo gelandet ist, liest sie dort nach.
"""

from __future__ import annotations

import re
from collections import Counter

STOPP = {
    "aber", "alle", "allem", "allen", "aller", "alles", "als", "also", "andere",
    "auch", "auf", "aus", "bei", "beim", "bin", "bis", "bist", "dann", "das",
    "dass", "dem", "den", "der", "des", "die", "dies", "diese", "diesem",
    "diesen", "dieser", "dieses", "doch", "dort", "durch", "ein", "eine",
    "einem", "einen", "einer", "eines", "etwas", "für", "gegen", "gewesen",
    "hab", "habe", "haben", "hat", "hatte", "hatten", "heute", "hier", "ich",
    "ihr", "ihre", "immer", "ist", "kann", "kein", "keine", "machen", "mal",
    "man", "mehr", "mein", "meine", "mit", "muss", "nach", "nicht", "noch",
    "nur", "oder", "ohne", "schon", "sehr", "sein", "seine", "sich", "sie",
    "sind", "über", "und", "vom", "von", "vor", "war", "waren", "was", "weil",
    "wenn", "werden", "wie", "wieder", "wir", "wird", "wo", "würde", "zum",
    "zur", "zwei", "grad", "ding", "sachen", "stück", "uhr",
}

# Wortformen, die zwar großgeschrieben, aber inhaltlich leer sind.
LEER = {"Also", "Aber", "Und", "Der", "Die", "Das", "Ich", "Es", "Ein", "Eine",
        "Wenn", "Dann", "Mir", "Man", "So", "Da", "Wegen", "Für", "Mit", "Am",
        "Im", "Heut", "Heute", "Morgen", "Gestern", "Nachmittags", "Abends"}

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9\-]{2,}")


def schlagworte(text: str, hoechstens: int = 3) -> list[str]:
    woerter = _WORT.findall(text)

    # Großgeschriebenes zuerst — im Deutschen sind das die Substantive, und
    # Substantive sind das, worüber gesprochen wird.
    inhalt = [w for w in woerter if w[0].isupper() and w not in LEER]
    if not inhalt:
        inhalt = [w for w in woerter if w.lower() not in STOPP]

    zaehler = Counter()
    for w in inhalt:
        k = w.lower().strip("-")
        if k in STOPP or len(k) < 3:
            continue
        # Häufigkeit zählt, aber die erste Nennung wiegt schwerer: Worüber
        # jemand anfängt zu reden, ist meistens das Thema.
        zaehler[k] += 1
    if not zaehler:
        return []

    erste = {}
    for i, w in enumerate(inhalt):
        erste.setdefault(w.lower().strip("-"), i)

    sortiert = sorted(zaehler.items(), key=lambda kv: (-kv[1], erste.get(kv[0], 999)))
    return [k for k, _ in sortiert[:hoechstens]]
