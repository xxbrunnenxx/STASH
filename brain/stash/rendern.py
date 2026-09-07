"""Das Panelbild. 480 × 800, ein Bit.

Alle Schriftarbeit passiert hier und nicht auf dem Gerät. Der Grund ist nicht
Bequemlichkeit: Umbruch, Verdichtung und die Frage, was auf die Seite passt,
gehören dorthin, wo der ganze Bestand liegt.

Das Panel kann kein Grau. Was grau wirken soll, ist ein Punktraster — sonst
wäre es ein Grau, das das Gerät nicht darstellen kann, und aus dem Raster würde
beim Anzeigen eine Fläche.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("stash.render")

BREITE, HOEHE = 480, 800
RAND = 18
KOPF_H, FUSS_H = 30, 34
WEISS, SCHWARZ = 1, 0

WOCHENTAG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
KURZ = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONAT = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
         "August", "September", "Oktober", "November", "Dezember"]

# Literata liest sich auf E-Ink deutlich besser als eine Grotesk — sie wurde
# für E-Reader gemacht. Fehlt sie, nimmt DejaVu ihren Platz ein und es sieht
# nur schlechter aus, statt abzubrechen.
_KANDIDATEN = {
    "serif": ["Literata-Regular.ttf", "Literata[opsz,wght].ttf",
              "DejaVuSerif.ttf", "FreeSerif.ttf"],
    "serif_fett": ["Literata-SemiBold.ttf", "DejaVuSerif-Bold.ttf", "FreeSerifBold.ttf"],
    "sans": ["IBMPlexSans-Regular.ttf", "DejaVuSans.ttf", "FreeSans.ttf"],
    "sans_fett": ["IBMPlexSans-SemiBold.ttf", "DejaVuSans-Bold.ttf", "FreeSansBold.ttf"],
    "mono": ["IBMPlexMono-Regular.ttf", "DejaVuSansMono.ttf", "FreeMono.ttf"],
}
_SUCHPFADE = [Path.home() / ".local/share/fonts", Path("/usr/share/fonts")]
_gemeldet = False


def _schrift(art: str, groesse: int) -> ImageFont.FreeTypeFont:
    global _gemeldet
    for name in _KANDIDATEN[art]:
        for wurzel in _SUCHPFADE:
            if not wurzel.exists():
                continue
            for treffer in wurzel.rglob(name):
                return ImageFont.truetype(str(treffer), groesse)
    if not _gemeldet:
        log.warning("Keine der gesuchten Schriften gefunden — Notschrift wird benutzt. "
                    "Literata und IBM Plex nach ~/.local/share/fonts legen.")
        _gemeldet = True
    return ImageFont.load_default(groesse)


class Blatt:
    """Eine Seite. Zeichnet von oben nach unten und merkt sich, wie weit sie ist."""

    def __init__(self):
        self.bild = Image.new("1", (BREITE, HOEHE), WEISS)
        self.d = ImageDraw.Draw(self.bild)
        self.y = KOPF_H + 15
        self.f = {
            "d1": _schrift("serif_fett", 31), "d2": _schrift("serif_fett", 20),
            "p": _schrift("serif", 15), "p_klein": _schrift("serif", 13),
            "u": _schrift("sans", 14), "u_fett": _schrift("sans_fett", 14),
            "m": _schrift("sans", 11), "mo": _schrift("mono", 11),
            "kursiv": _schrift("serif", 12),
        }

    # ── Grundformen ──────────────────────────────────────────────────────────

    def regel(self, stark: bool = False, eng: bool = False) -> None:
        self.y += 4 if eng else 7
        self.d.rectangle([RAND, self.y, BREITE - RAND, self.y + (1 if stark else 0)], fill=SCHWARZ)
        self.y += (2 if stark else 1) + (4 if eng else 7)

    def raster(self, x0: int, y0: int, x1: int, y1: int, anteil: int = 12) -> None:
        """Punktraster statt Fläche — das Einzige, was auf dem Panel wie Grau wirkt.

        Ein echtes Punktraster, kein Schrägstrich-Muster: Der Abstand ist in
        beiden Richtungen gleich, sonst entstehen Linien, die das Auge als
        Struktur liest statt als Ton.
        """
        n = {50: 2, 25: 2, 12: 4, 6: 8}.get(anteil, 4)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if anteil == 50:
                    treffer = (x + y) % 2 == 0
                else:
                    treffer = x % n == 0 and y % n == 0
                if treffer:
                    self.d.point((x, y), fill=SCHWARZ)

    def verblassen(self, y0: int, y1: int) -> None:
        """Gezeichnetes ausdünnen, statt es blasser zu setzen.

        Grau gibt es nicht. Eine verblasste Liste wird deshalb durch ein
        Löschraster geschickt: Sie ist noch da und noch lesbar, tritt aber
        sichtbar zurück — Eingeschlafenes soll gehen können, ohne dass man es
        wegwerfen muss.
        """
        for y in range(max(0, y0), min(HOEHE, y1)):
            for x in range(0, BREITE, 2):
                self.d.point((x + (y % 2), y), fill=WEISS)

    def band(self, text: str) -> None:
        h, links, rechts = 19, RAND - 8, BREITE - RAND + 8
        self.d.line([links, self.y, rechts, self.y], fill=SCHWARZ)
        self.d.line([links, self.y + h, rechts, self.y + h], fill=SCHWARZ)
        self.raster(links, self.y + 1, rechts, self.y + h, anteil=12)
        # Das Raster unter der Beschriftung wieder wegnehmen: gerastertes
        # Papier hinter kleiner Schrift macht sie auf E-Ink unleserlich.
        breite = self._breite(text, "kursiv")
        self.d.rectangle([RAND - 3, self.y + 2, RAND + breite + 3, self.y + h - 2], fill=WEISS)
        self.d.text((RAND, self.y + 3), text, font=self.f["kursiv"], fill=SCHWARZ)
        self.y += h + 7

    def _breite(self, text: str, art: str) -> int:
        return int(self.d.textlength(text, font=self.f[art]))

    def text(self, s: str, art: str = "p", x: int | None = None,
             dy: int = 0, rechts: bool = False) -> None:
        x = RAND if x is None else x
        if rechts:
            x = BREITE - RAND - self._breite(s, art)
        self.d.text((x, self.y + dy), s, font=self.f[art], fill=SCHWARZ)

    def absatz(self, s: str, art: str = "p", zeilenhoehe: int | None = None,
               breite: int | None = None, einzug: int = 0) -> None:
        """Umbruch von Hand, weil PIL keinen kennt."""
        maxb = (breite or (BREITE - 2 * RAND)) - einzug
        hoehe = zeilenhoehe or {"p": 22, "p_klein": 18, "u": 19, "m": 15}.get(art, 20)
        zeile = ""
        for wort in s.split():
            probe = f"{zeile} {wort}".strip()
            if self._breite(probe, art) <= maxb:
                zeile = probe
                continue
            self.text(zeile, art, x=RAND + einzug)
            self.y += hoehe
            zeile = wort
        if zeile:
            self.text(zeile, art, x=RAND + einzug)
            self.y += hoehe

    def kaestchen(self, x: int, y: int, gefuellt: bool = False) -> None:
        self.d.rectangle([x, y, x + 11, y + 11], outline=SCHWARZ)
        if gefuellt:
            self.d.line([x + 2, y + 6, x + 5, y + 9], fill=SCHWARZ, width=2)
            self.d.line([x + 5, y + 9, x + 9, y + 2], fill=SCHWARZ, width=2)

    def eintrag(self, links: str, rechts_text: str = "", art: str = "u",
                kasten: bool = False, hoehe: int = 21) -> None:
        x = RAND
        if kasten:
            self.kaestchen(RAND, self.y + 2)
            x = RAND + 18
        if rechts_text:
            self.text(rechts_text, "mo", rechts=True, dy=2)
        maxb = BREITE - RAND - x - (self._breite(rechts_text, "mo") + 10 if rechts_text else 0)
        s = links
        while self._breite(s, art) > maxb and len(s) > 4:
            s = s[:-2]
        if s != links:
            s = s.rstrip() + "…"
        self.text(s, art, x=x)
        self.y += hoehe

    def zweispaltig(self, links: tuple[str, list], rechts: tuple[str, list],
                    hoehe: int = 19, teiler: float = 0.58) -> None:
        """Zwei Spalten nebeneinander.

        Auf 480 Pixel Breite ist eine einspaltige Aufgabenliste Verschwendung:
        Die Zeilen sind kurz, rechts bleibt Papier leer. Ruhend, wo die Seite
        stundenlang steht und nicht bedient wird, zählt jede genutzte Zeile.
        """
        x_l, x_r = RAND, RAND + int((BREITE - 2 * RAND) * teiler)
        y0 = self.y
        self.d.text((x_l, y0), links[0], font=self.f["kursiv"], fill=SCHWARZ)
        self.d.text((x_r, y0), rechts[0], font=self.f["kursiv"], fill=SCHWARZ)
        y0 += 17

        maxb_l = x_r - x_l - 26
        for i, t in enumerate(links[1]):
            self.kaestchen(x_l, y0 + i * hoehe + 2)
            s = t
            while self._breite(s, "u") > maxb_l and len(s) > 4:
                s = s[:-2]
            self.d.text((x_l + 18, y0 + i * hoehe), s + ("…" if s != t else ""),
                        font=self.f["u"], fill=SCHWARZ)

        maxb_r = BREITE - RAND - x_r
        for i, (marke, t) in enumerate(rechts[1]):
            self.d.text((x_r, y0 + i * hoehe + 1), marke, font=self.f["mo"], fill=SCHWARZ)
            s, versatz = t, self._breite(marke, "mo") + 6
            while self._breite(s, "u") > maxb_r - versatz and len(s) > 4:
                s = s[:-2]
            self.d.text((x_r + versatz, y0 + i * hoehe), s + ("…" if s != t else ""),
                        font=self.f["u"], fill=SCHWARZ)

        self.y = y0 + max(len(links[1]), len(rechts[1])) * hoehe + 2

    def invers(self, text: str, hoehe: int = 24) -> None:
        self.d.rectangle([RAND - 8, self.y, BREITE - RAND + 8, self.y + hoehe], fill=SCHWARZ)
        self.d.text((RAND, self.y + 4), text, font=self.f["u_fett"], fill=WEISS)
        self.y += hoehe + 4

    # ── Leisten ──────────────────────────────────────────────────────────────

    def kopfleiste(self, akku: int, wlan: bool, wartend: int, uhr: str,
                   stempel: bool = False) -> None:
        """Die dünne Leiste oben.

        `stempel` macht aus der Uhrzeit eine Altersangabe: Auf einem Bild, das
        stundenlang steht, ist „von wann ist das hier" die nützlichste
        Information — aber an der Stelle, an der sonst eine Uhr sitzt, liest man
        erst einmal eine Uhr. Das Wort davor räumt die Zweideutigkeit weg.
        """
        self.d.line([0, KOPF_H, BREITE, KOPF_H], fill=SCHWARZ)
        self.d.text((14, 8), "S T A S H", font=self.f["m"], fill=SCHWARZ)

        zeit = f"Stand {uhr}" if stempel else uhr
        x = BREITE - 14
        x -= self._breite(zeit, "mo")
        self.d.text((x, 8), zeit, font=self.f["mo"], fill=SCHWARZ)

        p = f"{akku}%"
        x -= self._breite(p, "mo") + 10
        self.d.text((x, 8), p, font=self.f["mo"], fill=SCHWARZ)
        x -= 30
        self.d.rectangle([x, 9, x + 20, 20], outline=SCHWARZ)
        self.d.rectangle([x + 21, 12, x + 23, 17], fill=SCHWARZ)
        self.d.rectangle([x + 2, 11, x + 2 + max(1, int(16 * akku / 100)), 18], fill=SCHWARZ)

        x -= 26
        cx, cy = x + 8, 20                     # Fußpunkt der Bögen
        for r in (11, 7, 3):
            self.d.arc([cx - r, cy - r, cx + r, cy + r], 200, 340, fill=SCHWARZ)
        self.d.rectangle([cx - 1, cy - 1, cx + 1, cy + 1], fill=SCHWARZ)
        if not wlan:
            self.d.line([cx - 9, cy + 2, cx + 9, cy - 16], fill=SCHWARZ, width=2)

        if wartend:
            s = str(wartend)
            x -= self._breite(s, "mo") + 22
            for i in range(3):
                self.d.rectangle([x, 9 + i * 4, x + 9, 10 + i * 4], fill=SCHWARZ)
            self.d.text((x + 13, 8), s, font=self.f["mo"], fill=SCHWARZ)

    def fussleiste(self, mitte: str = "öffnen") -> None:
        y = HOEHE - FUSS_H
        self.d.line([0, y, BREITE, y], fill=SCHWARZ)
        for text, x in (("◀ zurück", 22), (f"● {mitte}", BREITE // 2 - 40),
                        ("weiter ▶", BREITE - 22 - self._breite("weiter ▶", "u"))):
            self.d.text((x, y + 9), text, font=self.f["u"], fill=SCHWARZ)

    # ── Ausgabe ──────────────────────────────────────────────────────────────

    def bytes(self) -> bytes:
        """1 Bit je Pixel, zeilenweise, 60 Byte je Zeile — 48000 Byte.

        PIL packt „1" bereits so; getdata() wäre 384000 Byte und würde die
        Übertragung ohne Not verachtfachen.
        """
        return self.bild.tobytes()

    def png(self, pfad: str | Path) -> Path:
        p = Path(pfad)
        self.bild.save(p)
        return p
