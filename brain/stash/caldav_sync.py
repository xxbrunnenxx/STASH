"""Apple Kalender und Erinnerungen über CalDAV.

Optional. Ist keine URL gesetzt, passiert nichts — STASH funktioniert ohne,
und ein Dienst, der ohne Cloud-Zugang nicht startet, wäre das Gegenteil von
„es bleibt im Haus".
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from .einstellungen import Einstellungen

log = logging.getLogger("stash.caldav")


class Kalender:
    def __init__(self, e: Einstellungen):
        self.e = e
        self._client = None

    @property
    def aktiv(self) -> bool:
        return bool(self.e.caldav_url and self.e.caldav_benutzer)

    def _verbinden(self):
        if self._client is not None:
            return self._client
        import caldav
        self._client = caldav.DAVClient(url=self.e.caldav_url,
                                        username=self.e.caldav_benutzer,
                                        password=self.e.caldav_passwort)
        return self._client

    def woche(self) -> dict[int, list[tuple[str, str]]]:
        """Termine der laufenden Woche, nach Wochentag (0 = Montag)."""
        if not self.aktiv:
            return {}
        try:
            haupt = self._verbinden().principal()
            montag = date.today() - timedelta(days=date.today().weekday())
            raus: dict[int, list[tuple[str, str]]] = {}
            for k in haupt.calendars():
                for e in k.date_search(start=datetime.combine(montag, datetime.min.time()),
                                       end=datetime.combine(montag + timedelta(days=7),
                                                            datetime.min.time())):
                    v = e.instance.vevent
                    beginn = v.dtstart.value
                    uhr = beginn.strftime("%H:%M") if isinstance(beginn, datetime) else "ganztags"
                    tag = beginn.weekday() if hasattr(beginn, "weekday") else 0
                    raus.setdefault(tag, []).append((uhr, str(v.summary.value)))
            for tag in raus:
                raus[tag].sort()
            return raus
        except Exception as f:                      # noqa: BLE001 — Netz, Auth, Format
            log.warning("Kalender nicht lesbar: %s", f)
            return {}

    def aufgabe_anlegen(self, text: str, faellig: date | None = None) -> bool:
        if not self.aktiv:
            return False
        try:
            for k in self._verbinden().principal().calendars():
                if "VTODO" in k.get_supported_components():
                    k.save_todo(summary=text,
                                due=faellig or (date.today() + timedelta(days=1)))
                    return True
        except Exception as f:                      # noqa: BLE001
            log.warning("Erinnerung nicht angelegt: %s", f)
        return False
