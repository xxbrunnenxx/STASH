"""Der Vault. Reines Markdown, kein Datenbankformat.

Das ist keine Bequemlichkeit: Wenn dieses Projekt eines Tages nicht mehr läuft,
liegen die Notizen trotzdem noch lesbar da. Der Vault ist das Ergebnis, STASH
nur der Weg dahin. Alles, was STASH zusätzlich braucht — Trigger-Wörter,
Zähler — liegt getrennt in .stash/ und ist jederzeit wegwerfbar.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from pathlib import Path

from .einsortieren import Liste, Zuordnung, frische_listen
from .einstellungen import Einstellungen


def _sicher(name: str) -> str:
    """Dateinamen dürfen alles, was ein Mensch lesen kann — außer Pfadtrennern."""
    return re.sub(r"[/\\\0:]+", "-", name).strip() or "unsortiert"


class Vault:
    def __init__(self, e: Einstellungen):
        self.e = e
        e.ordner_anlegen()
        self.listen: dict[str, Liste] = self._listen_laden()

    # ── Listenbestand ────────────────────────────────────────────────────────

    def _listen_laden(self) -> dict[str, Liste]:
        p = self.e.listen_datei
        if not p.exists():
            return frische_listen()
        try:
            roh = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Lieber neu anfangen als abstürzen: Der Inhalt steht im Markdown,
            # diese Datei ist nur der Index darüber.
            return frische_listen()
        listen = {n: Liste.from_dict(d) for n, d in roh.items()}
        for name, trigger in frische_listen().items():
            listen.setdefault(name, trigger)
        return listen

    def listen_sichern(self) -> None:
        p = self.e.listen_datei
        p.parent.mkdir(parents=True, exist_ok=True)
        # Erst daneben schreiben, dann umbenennen — ein Stromausfall mitten im
        # Schreiben darf den Index nicht zerreißen.
        tmp = p.with_suffix(".json.neu")
        tmp.write_text(json.dumps({n: l.as_dict() for n, l in self.listen.items()},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)

    # ── Schreiben ────────────────────────────────────────────────────────────

    def notiz_schreiben(self, nr: int, wann: datetime, dauer_s: float, roh: str,
                        rein: str, worte: list[str], zu: Zuordnung,
                        aufgaben: list[str]) -> Path:
        """Die einzelne Aufnahme, roh und bereinigt nebeneinander."""
        name = f"{wann:%Y-%m-%d-%H%M}-{_sicher(zu.ziel)}.md"
        p = self.e.vault / "Notizen" / name
        loeschen = date.fromtimestamp(wann.timestamp() + self.e.audio_aufbewahrung_tage * 86400)

        p.write_text(
            f"---\n"
            f"nr: {nr}\n"
            f"aufgenommen: {wann.isoformat(timespec='seconds')}\n"
            f"dauer_s: {dauer_s:.1f}\n"
            f"ziel: \"{zu.ziel}\"\n"
            f"score: {zu.score:.2f}\n"
            f"schlagworte: [{', '.join(worte)}]\n"
            f"audio_geloescht_am: {loeschen.isoformat()}\n"
            f"---\n\n"
            f"{rein}\n\n"
            f"## Erkannt\n\n"
            f"- Zuordnung: [[{zu.ziel}]] · Score {zu.score:.2f}\n"
            f"- Begründung: {zu.grund}\n"
            + ("".join(f"- [ ] {a}\n" for a in aufgaben) if aufgaben else "")
            + f"\n## Roh\n\n> {roh}\n",
            encoding="utf-8")
        return p

    def an_liste(self, ziel: str, wann: datetime, text: str, aufgaben: list[str]) -> Path:
        p = self.e.vault / "Listen" / f"{_sicher(ziel)}.md"
        neu = not p.exists()
        with p.open("a", encoding="utf-8") as f:
            if neu:
                f.write(f"# {ziel}\n\nAngelegt {wann:%d.%m.%Y}.\n\n")
            f.write(f"- **{wann:%d.%m.}** {text}\n")
            for a in aufgaben:
                f.write(f"- [ ] {a}\n")
        return p

    def an_tagebuch(self, wann: datetime, text: str) -> Path:
        p = self.e.vault / "Tagebuch" / f"{wann:%Y-%m-%d}.md"
        neu = not p.exists()
        with p.open("a", encoding="utf-8") as f:
            if neu:
                f.write(f"# {wann:%A, %d. %B %Y}\n\n")
            f.write(f"**{wann:%H:%M}** {text}\n\n")
        return p

    def tagebuch_lesen(self, tag: date) -> str:
        p = self.e.vault / "Tagebuch" / f"{tag:%Y-%m-%d}.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def liste_lesen(self, name: str) -> str:
        p = self.e.vault / "Listen" / f"{_sicher(name)}.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    # ── Aufräumen ────────────────────────────────────────────────────────────

    def audio_aufraeumen(self) -> int:
        """Audiodateien nach Ablauf löschen. Das Transkript bleibt — was gesagt
        wurde, ist der Inhalt; wie es klang, ist es nicht."""
        grenze = time.time() - self.e.audio_aufbewahrung_tage * 86400
        weg = 0
        for f in self.e.audio_ordner.glob("*.wav"):
            if f.stat().st_mtime < grenze:
                f.unlink()
                weg += 1
        return weg

    def stille_listen(self) -> list[tuple[str, int]]:
        """Listen, aus denen lange nichts mehr kam — mit der Zahl der Tage.

        Eingeschlafene Projekte dürfen sich nicht zu einer Wand aus offenen
        Posten stapeln. Sie bieten ihre Archivierung an, statt zu mahnen.
        """
        heute = date.today()
        still = []
        for name, l in self.listen.items():
            if l.art == "fest" or not l.zuletzt:
                continue
            try:
                tage = (heute - date.fromisoformat(l.zuletzt)).days
            except ValueError:
                continue
            if tage >= self.e.archiv_ab_tage:
                still.append((name, tage))
        return sorted(still, key=lambda x: -x[1])
