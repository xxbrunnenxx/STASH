"""faster-whisper. Läuft lokal, das Audio verlässt das Haus nicht.

Das Modell wird beim ersten Aufruf geladen und bleibt im Speicher — auf dem Pi
dauert das Laden länger als das Transkribieren einer kurzen Notiz, und wer das
je Aufnahme neu macht, wartet umsonst.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .einstellungen import Einstellungen

log = logging.getLogger("stash.whisper")


class Transkribierer:
    def __init__(self, e: Einstellungen):
        self.e = e
        self._modell = None

    def _laden(self):
        if self._modell is not None:
            return self._modell
        from faster_whisper import WhisperModel   # spät, damit der Import den Start nicht blockiert

        t0 = time.monotonic()
        self._modell = WhisperModel(
            self.e.whisper_modell,
            device="cpu",
            compute_type=self.e.whisper_rechentyp,
            # Der Pi 5 hat vier Kerne. Alle vier hier zu belegen macht den
            # Dienst während einer Transkription unbedienbar.
            cpu_threads=3,
        )
        log.info("faster-whisper %s %s geladen (%.1f s)",
                 self.e.whisper_modell, self.e.whisper_rechentyp, time.monotonic() - t0)
        return self._modell

    def transkribieren(self, wav: Path) -> tuple[str, float, float]:
        """Gibt (Text, Vertrauen 0..1, Dauer der Aufnahme in Sekunden) zurück."""
        modell = self._laden()
        t0 = time.monotonic()
        segmente, info = modell.transcribe(
            str(wav),
            language=self.e.whisper_sprache,
            # Die Stilleerkennung schneidet Pausen weg, in denen sonst gern
            # Wörter halluziniert werden.
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            beam_size=5,
            condition_on_previous_text=False,
        )

        stuecke, wahrscheinlichkeiten = [], []
        for s in segmente:
            stuecke.append(s.text.strip())
            wahrscheinlichkeiten.append(getattr(s, "avg_logprob", -1.0))

        text = " ".join(t for t in stuecke if t)
        # avg_logprob ist ein Logarithmus; 0 wäre sicher, -1 sehr unsicher.
        mittel = sum(wahrscheinlichkeiten) / len(wahrscheinlichkeiten) if wahrscheinlichkeiten else -1.0
        vertrauen = max(0.0, min(1.0, 1.0 + mittel))

        log.info("%s · %.1f s Audio in %.1f s · %d Wörter · conf %.2f",
                 wav.name, info.duration, time.monotonic() - t0,
                 len(text.split()), vertrauen)
        return text, vertrauen, info.duration
