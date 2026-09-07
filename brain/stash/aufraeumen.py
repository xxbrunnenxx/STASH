"""Aus dem Gesprochenen wird Geschriebenes.

Man muss nicht druckreif sprechen. Abschweifen, neu ansetzen, Details
nachschieben — das fängt hier auf. Die rohe Fassung bleibt daneben stehen,
damit nichts wegfällt: Was hier fälschlich gestrichen wird, ist nicht verloren,
sondern eine Zeile weiter oben nachlesbar.
"""

from __future__ import annotations

import re

# Füllwörter, die am Satzanfang oder allein stehend nichts tragen. Bewusst kurz
# gehalten: „also" trägt mitten im Satz durchaus etwas, deshalb greift die Liste
# nur an Positionen, an denen sie es nachweislich nicht tut.
FUELLER = [
    "ähm", "ähem", "äh", "hm", "hmm", "öhm",
    "also", "warte", "warte mal", "ach ja", "ja also", "ne", "nech",
    "halt", "eigentlich", "irgendwie", "so", "und zwar", "sagen wir",
    "weißt du", "ich mein", "ich meine",
]

_FUELLER_RE = re.compile(
    r"(?:(?<=^)|(?<=[.!?]\s)|(?<=,\s))(?:" + "|".join(re.escape(f) for f in FUELLER) + r")\b[,\s]*",
    re.IGNORECASE,
)
_ALLEIN_RE = re.compile(
    r"[,;]\s*(?:" + "|".join(re.escape(f) for f in FUELLER) + r")\s*(?=[,;]|$)",
    re.IGNORECASE,
)
_WIEDERHOLUNG_RE = re.compile(r"\b(\w{3,})(\s*,?\s+\1\b)+", re.IGNORECASE)
_ABBRUCH_RE = re.compile(r"\b(\w+)-\s+\1", re.IGNORECASE)


def zaehle_fueller(text: str) -> int:
    return len(_FUELLER_RE.findall(text)) + len(_ALLEIN_RE.findall(text))


def bereinigen(roh: str) -> str:
    """Regelbasiert, ohne Modell. Läuft in Mikrosekunden und ist damit auch dann
    da, wenn nachts kein Sprachmodell antwortet."""
    t = " ".join(roh.split())

    t = _ALLEIN_RE.sub(",", t)
    t = _FUELLER_RE.sub("", t)
    # Doppelkommas zusammenziehen, bevor die Wiederholung gesucht wird —
    # sonst steht zwischen „dann" und „dann" ein „,," und trennt die beiden.
    t = re.sub(r",\s*,+", ",", t)
    t = _ABBRUCH_RE.sub(r"\1", t)          # „Über- Überdachung"
    t = _WIEDERHOLUNG_RE.sub(r"\1", t)     # „das das das"

    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"([,.;:!?])(?=\w)", r"\1 ", t)
    t = re.sub(r",\s*,+", ",", t)
    # Ein Komma, das nach dem Streichen vor einer Konjunktion hängen bleibt,
    # war nie eins — es gehörte zum gestrichenen Wort.
    t = re.sub(r"\b(und|oder|aber|denn)\s*,\s*", r"\1 ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*,\s*(?=[.!?])", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,;")

    # Satzanfänge groß, damit es sich wie geschrieben liest.
    stuecke = re.split(r"(?<=[.!?])\s+", t)
    stuecke = [s[:1].upper() + s[1:] if s else s for s in stuecke]
    t = " ".join(stuecke).strip()

    if t and t[-1] not in ".!?":
        t += "."
    return t


def erste_zeile(text: str) -> str:
    """Der Anriss, der in Eingang und Übersicht steht."""
    satz = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    return satz if len(satz) <= 120 else satz[:117].rstrip() + "…"
