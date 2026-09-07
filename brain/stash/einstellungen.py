"""Konfiguration. Eine Datei, kurze Liste, jede Zeile eine Entscheidung."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PFAD = Path.home() / ".config" / "stash" / "stash.toml"


@dataclass
class Einstellungen:
    vault: Path = Path.home() / "Obsidian" / "stash"

    whisper_modell: str = "small"
    whisper_rechentyp: str = "int8"
    whisper_sprache: str = "de"

    llm_endpunkt: str = "http://localhost:11434/v1"
    llm_modell: str = "google/gemma-4-e2b"
    llm_zeitlimit_s: int = 900

    # Die Schwelle, unter der eine neue Liste entsteht. Sie tagsüber „richtig"
    # einzustellen ist aussichtslos — sie darf grob sein, weil nachts sortiert
    # wird. Genau dafür ist der Nachtlauf da.
    schwelle: float = 0.62
    archiv_ab_tage: int = 60
    audio_aufbewahrung_tage: int = 30

    adresse: str = "0.0.0.0"
    port: int = 8080

    caldav_url: str = ""
    caldav_benutzer: str = ""
    caldav_passwort: str = ""

    herkunft: str = "Vorgaben"

    @property
    def listen_datei(self) -> Path:
        return self.vault / ".stash" / "listen.json"

    @property
    def audio_ordner(self) -> Path:
        return self.vault / ".stash" / "audio"

    def ordner_anlegen(self) -> None:
        for p in (self.vault / "Listen", self.vault / "Tagebuch",
                  self.vault / "Notizen", self.audio_ordner):
            p.mkdir(parents=True, exist_ok=True)


def laden(pfad: Path | None = None) -> Einstellungen:
    """Liest die Konfiguration. Fehlt sie, gelten die Vorgaben oben — der
    Dienst startet also auch ohne, nur eben in den Standardvault."""
    pfad = pfad or PFAD
    e = Einstellungen()
    if not pfad.exists():
        return e

    roh = tomllib.loads(pfad.read_text(encoding="utf-8"))
    e.herkunft = str(pfad)

    v = roh.get("vault", {})
    if "pfad" in v:
        e.vault = Path(v["pfad"]).expanduser()

    w = roh.get("whisper", {})
    e.whisper_modell = w.get("modell", e.whisper_modell)
    e.whisper_rechentyp = w.get("rechentyp", e.whisper_rechentyp)
    e.whisper_sprache = w.get("sprache", e.whisper_sprache)

    l = roh.get("llm", {})
    e.llm_endpunkt = l.get("endpunkt", e.llm_endpunkt)
    e.llm_modell = l.get("modell", e.llm_modell)
    e.llm_zeitlimit_s = int(l.get("zeitlimit_s", e.llm_zeitlimit_s))

    s = roh.get("einsortieren", {})
    e.schwelle = float(s.get("schwelle", e.schwelle))
    e.archiv_ab_tage = int(s.get("archiv_ab_tage", e.archiv_ab_tage))

    a = roh.get("audio", {})
    e.audio_aufbewahrung_tage = int(a.get("aufbewahrung_tage", e.audio_aufbewahrung_tage))

    srv = roh.get("server", {})
    e.adresse = srv.get("adresse", e.adresse)
    e.port = int(srv.get("port", e.port))

    c = roh.get("caldav", {})
    e.caldav_url = c.get("url", "")
    e.caldav_benutzer = c.get("benutzer", "")
    e.caldav_passwort = c.get("passwort", "")

    return e
