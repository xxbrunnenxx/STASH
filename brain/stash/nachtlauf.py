"""Der Nachtlauf.

Tagsüber entscheidet die Regel je Notiz und sieht nur diese eine. Nachts liegen
alle Listen nebeneinander, und erst dann lässt sich sehen, dass #wechselrichter
und #pv-anlage dasselbe meinen. Das ist der Unterschied zwischen abgelegt und
aufgeräumt.

Vier Durchgänge:

1. Zusammenlegen  — Listen mit gemeinsamen Trigger-Wörtern werden vereinigt.
2. Umbenennen     — die Verlegenheitsnamen von gestern bekommen ein Thema.
3. Verdichten     — aus den Notizen eines Tages wird die Seite von morgen früh.
4. Verblassen     — was seit 60 Tagen still ist, bietet seine Archivierung an.

Ohne Sprachmodell laufen 1 und 4. Das ist die Hälfte des Nutzens und
funktioniert an jedem Abend, an dem der Modellserver nicht läuft.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import date, timedelta

from .einsortieren import Liste
from .einstellungen import Einstellungen, laden
from .llm import GEKLAERT, NAMEN, VERDICHTEN, Modell
from .vault import Vault

log = logging.getLogger("stash.nachtlauf")


def zusammenlegen(listen: dict[str, Liste], mindestens: int = 1) -> list[tuple[str, str]]:
    """Gewachsene Listen mit gemeinsamen Trigger-Wörtern vereinigen.

    Ein einziges gemeinsames Wort genügt. Das klingt großzügig, ist es aber
    nicht: Zwei Listen entstehen überhaupt nur, wenn tagsüber der Anteil unter
    der Schwelle lag — ein geteiltes Wort heißt dann schon, dass sie sich
    berühren. Feste Listen werden nie eingesammelt, sie sind der Anker.
    """
    zusammen: list[tuple[str, str]] = []

    # Die kleinere geht in die größere. Wer wohin wandert, soll nicht davon
    # abhängen, wie das Wörterbuch sortiert ist.
    kandidaten = sorted(
        (n for n, l in listen.items() if l.art == "gewachsen"),
        key=lambda n: listen[n].anzahl,
    )

    for klein in kandidaten:
        if klein not in listen:
            continue
        meine = {t.lower() for t in listen[klein].trigger} | {klein.lower()}
        ziel, beste = None, 0
        for gross, l in listen.items():
            # Nur gewachsene Listen sind Ziel. In eine feste Liste wird nie
            # hineingelegt: #tagebuch würde sonst jedes Thema schlucken, dessen
            # Wörter zufällig auch abends vorkamen.
            if gross == klein or l.art != "gewachsen":
                continue
            if l.anzahl < listen[klein].anzahl:
                continue
            gemeinsam = len(meine & ({t.lower() for t in l.trigger} | {gross.lower()}))
            if gemeinsam > beste:
                beste, ziel = gemeinsam, gross
        if ziel and beste >= mindestens:
            listen[ziel].anzahl += listen[klein].anzahl
            for t in listen[klein].trigger:
                if t not in listen[ziel].trigger:
                    listen[ziel].trigger.append(t)
            del listen[klein]
            zusammen.append((klein, ziel))

    return zusammen


def umbenennen(listen: dict[str, Liste], modell: Modell) -> list[tuple[str, str]]:
    """Aus „#meter" wird „#überdachung" — wenn ein Modell da ist."""
    frisch = [n for n, l in listen.items() if l.art == "gewachsen" and l.anzahl >= 3]
    if not frisch:
        return []

    eingabe = "\n".join(f"{n}: {', '.join(listen[n].trigger[:8])}" for n in frisch)
    antwort = modell.frage(NAMEN, eingabe, hoechstens=200)
    if not antwort:
        return []

    neu = [z.strip().lstrip("#").lower() for z in antwort.splitlines() if z.strip()]
    umbenannt = []
    for alt, name in zip(frisch, neu):
        name = re.sub(r"[^a-zäöüß0-9\-]", "", name)
        if not name or name == alt or name in listen:
            continue
        listen[name] = listen.pop(alt)
        umbenannt.append((alt, name))
    return umbenannt


def verdichten(vault: Vault, modell: Modell, tag: date) -> str:
    """Aus den Notizen eines Tages die Seite für den Morgen."""
    roh = vault.tagebuch_lesen(tag)
    themen = []
    for name, l in sorted(vault.listen.items(), key=lambda kv: -kv[1].anzahl):
        if l.art == "fest" or l.zuletzt != tag.isoformat():
            continue
        text = vault.liste_lesen(name)
        if text:
            themen.append(f"## {name}\n{text[-2000:]}")
        if len(themen) >= 4:
            break

    if not themen and not roh:
        return ""

    eingabe = "\n\n".join(themen + ([f"## Tagebuch\n{roh[-2000:]}"] if roh else []))
    return modell.frage(VERDICHTEN, eingabe, hoechstens=600) or ""


def geklaert(vault: Vault, modell: Modell, tag: date) -> list[tuple[str, str]]:
    """Offene Fragen von gestern, die heute beantwortet wurden."""
    gestern = vault.tagebuch_lesen(tag - timedelta(days=1))
    heute = vault.tagebuch_lesen(tag)
    if not gestern or not heute:
        return []

    offen = [z.strip("- ").strip() for z in gestern.splitlines() if "Offen:" in z]
    if not offen:
        return []

    antwort = modell.frage(GEKLAERT, "Gestern offen:\n" + "\n".join(offen)
                           + "\n\nHeute:\n" + heute[-2000:], hoechstens=300)
    if not antwort:
        return []
    paare = []
    for z in antwort.splitlines():
        if "|" in z:
            frage, loesung = z.split("|", 1)
            paare.append((frage.strip(), loesung.strip()))
    return paare


def lauf(e: Einstellungen | None = None) -> dict:
    e = e or laden()
    vault = Vault(e)
    modell = Modell(e)
    heute = date.today()

    vorher = len(vault.listen)
    zusammen = zusammenlegen(vault.listen)

    bericht = {"listen_vorher": vorher, "zusammengelegt": zusammen,
               "umbenannt": [], "verdichtet": "", "geklaert": [],
               "verblasst": vault.stille_listen(),
               "audio_geloescht": vault.audio_aufraeumen(),
               "llm": modell.erreichbar()}

    if bericht["llm"]:
        bericht["umbenannt"] = umbenennen(vault.listen, modell)
        bericht["verdichtet"] = verdichten(vault, modell, heute)
        bericht["geklaert"] = geklaert(vault, modell, heute)
    else:
        log.warning("kein LLM erreichbar — es wurde nur zusammengelegt")

    for name, tage in bericht["verblasst"]:
        vault.listen[name].art = "verblasst"

    vault.listen_sichern()
    bericht["listen_nachher"] = len(vault.listen)

    if bericht["verdichtet"]:
        p = e.vault / ".stash" / f"morgen-{heute.isoformat()}.md"
        p.write_text(bericht["verdichtet"], encoding="utf-8")

    log.info("Nachtlauf · %d → %d Listen · %d zusammengelegt · %d umbenannt · "
             "%d verblasst · %d Audiodateien gelöscht",
             vorher, bericht["listen_nachher"], len(zusammen),
             len(bericht["umbenannt"]), len(bericht["verblasst"]),
             bericht["audio_geloescht"])
    return bericht


def hauptprogramm() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-14s  %(message)s")
    b = lauf()
    for alt, neu in b["zusammengelegt"]:
        print(f"  #{alt} → #{neu}")
    for alt, neu in b["umbenannt"]:
        print(f"  #{alt} heißt jetzt #{neu}")
    for name, tage in b["verblasst"]:
        print(f"  #{name} still seit {tage} Tagen · archivieren?")
    return 0


if __name__ == "__main__":
    sys.exit(hauptprogramm())
