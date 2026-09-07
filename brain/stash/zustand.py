"""Was das Gerät gerade zeigt.

Der Zustand liegt hier, nicht auf dem ESP32. Der Drehknopf schickt nur
„zurueck / oeffnen / weiter"; was daraus wird, entscheidet diese Datei. Das
Gerät bleibt damit ein Blatt Papier mit einem Knopf.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

ANSICHTEN = ["heute", "eingang", "listen", "detail", "notiz",
             "tagebuch", "kalender", "warteschlange"]


@dataclass
class Notiz:
    nr: int
    wann: datetime
    dauer_s: float
    roh: str
    rein: str
    schlagworte: list[str]
    ziel: str
    art: str
    score: float
    grund: str
    aufgaben: list[str] = field(default_factory=list)
    vertrauen: float = 0.0
    audio_bis: str = ""


@dataclass
class Zustand:
    ansicht: str = "heute"
    zurueck: str = "heute"
    detail_liste: str = ""
    notiz_nr: int | None = None
    roh_zeigen: bool = False

    akku: int = 100
    wlan: bool = True
    wartend: int = 0

    notizen: list[Notiz] = field(default_factory=list)
    tagebuch: list[tuple[str, str]] = field(default_factory=list)
    termine: dict[int, list[tuple[str, str]]] = field(default_factory=dict)
    erinnerungen: list[tuple[str, bool]] = field(default_factory=list)
    morgenseite: str = ""
    geklaert: list[tuple[str, str]] = field(default_factory=list)
    # Ruhe: das Gerät wird gerade nicht bedient und zeigt die Sperrseite.
    ruhe: bool = False

    def blaettern(self, richtung: int) -> None:
        # In der Tiefe (Notiz, Listen-Detail) blättert der Knopf nicht weiter,
        # sondern führt zurück — sonst landet man aus Versehen woanders und
        # muss den Weg noch einmal suchen.
        if self.ansicht in ("notiz", "detail"):
            self.ansicht = self.zurueck
            return
        i = ANSICHTEN.index(self.ansicht) if self.ansicht in ANSICHTEN else 0
        sichtbar = [a for a in ANSICHTEN if a not in ("notiz", "detail")]
        j = sichtbar.index(ANSICHTEN[i]) if ANSICHTEN[i] in sichtbar else 0
        self.ansicht = sichtbar[(j + richtung) % len(sichtbar)]

    def oeffnen(self, listen: dict) -> None:
        if self.ansicht in ("notiz", "detail"):
            self.ansicht = self.zurueck
            return
        if self.ansicht in ("heute", "eingang") and self.notizen:
            self.zurueck = self.ansicht
            self.notiz_nr = self.notizen[-1].nr
            self.roh_zeigen = False
            self.ansicht = "notiz"
            return
        if self.ansicht == "listen":
            gewachsen = [n for n, l in sorted(listen.items(), key=lambda kv: -kv[1].anzahl)
                         if l.art == "gewachsen"]
            if gewachsen:
                self.zurueck = "listen"
                self.detail_liste = gewachsen[0]
                self.ansicht = "detail"

    @property
    def mittentext(self) -> str:
        if self.ansicht in ("notiz", "detail"):
            return "schließen"
        if self.ansicht in ("heute", "eingang") and self.notizen:
            return "Notiz öffnen"
        if self.ansicht == "listen":
            return "Liste öffnen"
        return "—"
