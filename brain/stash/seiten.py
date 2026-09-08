"""Die acht Ansichten des Geräts.

Jede bekommt denselben Rahmen: oben eine dünne Statusleiste, unten die
Drehknopf-Belegung. Dazwischen füllt jede Seite den Platz, den sie hat — was
nicht draufpasst, wird gezählt statt abgeschnitten („… und 14 weitere"), damit
nie der Eindruck entsteht, es gäbe nicht mehr.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .einsortieren import Liste
from .rendern import BREITE, FUSS_H, HOEHE, KURZ, MONAT, RAND, SCHWARZ, WOCHENTAG, Blatt
from .zustand import Notiz, Zustand

UNTERKANTE = HOEHE - FUSS_H - 12
# Ruhend fällt die Fußleiste weg — 34 Pixel, die dann Inhalt tragen.
UNTERKANTE_RUHE = HOEHE - 12


def _rahmen(z: Zustand) -> Blatt:
    b = Blatt()
    b.kopfleiste(z.akku, z.wlan, z.wartend, datetime.now().strftime("%H:%M"),
                 stempel=z.ruhe)
    return b


def _abschluss(b: Blatt, z: Zustand) -> Blatt:
    # Im Ruhezustand keine Fußleiste: „◀ zurück ● öffnen ▶ weiter" ist eine
    # Anleitung für eine Bedienung, die gerade nicht stattfindet.
    if not z.ruhe:
        b.fussleiste(z.mittentext)
    return b


def _boden(z: Zustand) -> int:
    return UNTERKANTE_RUHE if z.ruhe else UNTERKANTE


def _satz1(text: str) -> str:
    """Der erste Satz, mit genau einem Schlusspunkt."""
    kopf = text.split(". ")[0].rstrip()
    return kopf if kopf.endswith((".", "!", "?", "…")) else kopf + "."


def _datum_gross(b: Blatt, tag: date) -> None:
    b.text(WOCHENTAG[tag.weekday()], "d1")
    b.y += 34
    b.text(f"{tag.day}. {MONAT[tag.month - 1]}", "d1")
    b.y += 38


# ── 1 Heute ──────────────────────────────────────────────────────────────────

def heute(z: Zustand, listen: dict[str, Liste]) -> Blatt:
    """Ansicht 1 — und zugleich die Sperrseite.

    Im Ruhezustand fällt das Gerät hierher zurück. E-Paper hält sein Bild ohne
    Strom; die Seite steht also stundenlang und wird im Vorbeigehen gelesen,
    ohne dass jemand etwas drückt. Deshalb wird sie ruhend voller gesetzt als
    bedient: Sie wird nicht durchgeblättert, sie wird angeschaut, und leerer
    Platz auf einem Bild, das steht, ist verschenkt.
    """
    b = _rahmen(z)
    heute_ = date.today()
    boden = _boden(z)
    _datum_gross(b, heute_)
    b.regel(stark=True)

    # Der Abbinder steht unten und wird zuerst gesetzt, damit der Inhalt
    # darüber weiß, wo er aufhören muss.
    abbinder = _abbinder(z)
    if abbinder:
        boden -= 15 * len(abbinder) + 8

    if z.morgenseite:
        _morgen_inhalt(b, z, boden)
    else:
        _stand_inhalt(b, z, boden)

    if abbinder:
        b.y = boden + 8
        b.d.line([RAND, b.y, BREITE - RAND, b.y], fill=SCHWARZ)
        b.y += 6
        for zeile in abbinder:
            b.text(zeile, "m")
            b.y += 15

    return _abschluss(b, z)


def _abbinder(z: Zustand) -> list[str]:
    """Die zwei Zeilen ganz unten: was die Nacht getan hat, was der Tag war.

    Keine Quote und kein Rückstand — eine Feststellung, die nichts verlangt.
    """
    zeilen = []
    if z.tagebuch:
        worte = sum(len(t.split()) for _, t in z.tagebuch)
        zeilen.append(f"Im Tagebuch: {len(z.tagebuch)} Absätze · {worte} Wörter")
    if z.notizen or z.wartend:
        teil = f"{len(z.notizen)} Aufnahmen verarbeitet"
        if z.wartend:
            teil += f" · {z.wartend} noch auf der Karte"
        zeilen.append(teil)
    return zeilen


def _morgen_inhalt(b: Blatt, z: Zustand, boden: int) -> None:
    """Was der Nachtlauf verdichtet hat, plus was daraus zu tun ist."""
    absaetze = [a.strip() for a in z.morgenseite.split("\n") if a.strip()]
    for absatz in absaetze:
        if b.y > boden - 40:
            break
        b.absatz(absatz, "p_klein" if absatz.lower().startswith("offen") else "p")
        b.y += 4

    offen = [t for t, fertig in z.erinnerungen if not fertig]
    termine = [(tag, f"{uhr} {text}") for tag, uhr, text in _naechste_termine(z, 4)]
    if (offen or termine) and b.y < boden - 60:
        b.regel(eng=True)
        platz = max(1, (boden - b.y - 20) // 19)
        b.zweispaltig(("Zu tun", offen[:platz]), ("Diese Woche", termine[:platz]),
                      teiler=0.63)

    if z.geklaert and b.y < boden - 50:
        b.regel(eng=True)
        b.band("Seit gestern geklärt")
        for frage, antwort in z.geklaert:
            if b.y > boden - 20:
                break
            b.eintrag(frage, "", art="u", hoehe=19)
            b.y -= 19
            b.text(antwort, "m", rechts=True, dy=3)
            b.y += 19

    # Was danach an Papier übrig ist, bekommt das Zuletztgesagte. Auf einer
    # Seite, die stundenlang steht, ist weißer Platz verschenkt — und „was habe
    # ich heute eigentlich gesagt" ist das, was man im Vorbeigehen liest.
    if z.notizen and b.y < boden - 70:
        b.regel(eng=True)
        b.band("Zuletzt gesagt")
        for n in reversed(z.notizen):
            if b.y > boden - 34:
                break
            b.text(f"{n.wann:%H:%M}", "mo", dy=2)
            b.absatz(_satz1(n.rein), "u", einzug=48, zeilenhoehe=18)
            b.y += 3


def _stand_inhalt(b: Blatt, z: Zustand, boden: int) -> None:
    """Ohne Nachtlauf: der schlichte Stand. Was ansteht, was heute schon da war."""
    naechste = _naechste_termine(z, 4)
    if naechste:
        b.band("Nächste Termine")
        for tag, uhr, text in naechste:
            if b.y > boden - 24:
                break
            b.eintrag(text, f"{tag} {uhr}")
        b.regel()

    offen = [t for t, fertig in z.erinnerungen if not fertig]
    if offen and b.y < boden - 60:
        b.band("Fällig")
        for t in offen:
            if b.y > boden - 24:
                break
            b.eintrag(t, kasten=True)
        b.regel()

    if b.y > boden - 70:
        return

    b.band("Eingang")
    if z.notizen:
        # Nicht nur zählen: Der Anriss der letzten Notizen ist das, was man im
        # Vorbeigehen tatsächlich liest.
        for n in reversed(z.notizen):
            if b.y > boden - 46:
                break
            b.absatz("„" + _satz1(n.rein).rstrip(".") + " …\"", "p_klein")
            b.text(f"{n.wann:%H:%M} · #{n.ziel}", "m")
            b.y += 20
    else:
        b.absatz("Noch nichts aufgenommen. Seitentaste drücken, drauflosreden, fertig.", "p")


def _naechste_termine(z: Zustand, wieviele: int) -> list[tuple[str, str, str]]:
    heute_ = date.today()
    raus = []
    for d in range(0, 7):
        tag = heute_ + timedelta(days=d)
        for uhr, text in z.termine.get(tag.weekday(), []):
            if len(raus) < wieviele:
                marke = "heute" if d == 0 else "morgen" if d == 1 else KURZ[tag.weekday()]
                raus.append((marke, uhr, text))
    return raus


# ── 2 Eingang ────────────────────────────────────────────────────────────────

def eingang(z: Zustand) -> Blatt:
    b = _rahmen(z)
    b.text("Eingang", "d2")
    b.y += 26
    b.text(f"{len(z.notizen)} Aufnahmen heute"
           + (f" · {z.wartend} auf der Karte" if z.wartend else ""), "m")
    b.y += 16
    b.regel(stark=True)

    if not z.notizen:
        b.absatz("Noch nichts aufgenommen." if not z.wartend else
                 "Alles liegt noch auf der Karte, bis der Pi wieder erreichbar ist.", "p")
        return _abschluss(b, z)

    gezeigt = 0
    for n in reversed(z.notizen):
        if b.y > _boden(z) - 48:
            break
        b.eintrag(_satz1(n.rein), n.wann.strftime("%H:%M"), hoehe=19)
        chips = " ".join(f"[{s}]" for s in n.schlagworte[:3])
        b.text(f"{n.dauer_s:.1f} s   {chips}", "m")
        b.text("abgelegt", "mo", rechts=True)
        b.y += 18
        b.regel(eng=True)
        gezeigt += 1

    rest = len(z.notizen) - gezeigt
    if rest > 0:
        b.text(f"… und {rest} weitere im Vault", "m")
    return _abschluss(b, z)


# ── 3 Listen ─────────────────────────────────────────────────────────────────

def listen_seite(z: Zustand, listen: dict[str, Liste]) -> Blatt:
    b = _rahmen(z)
    gesamt = sum(l.anzahl for l in listen.values())
    b.text("Listen", "d2")
    b.y += 26
    b.text(f"{len(listen)} Listen · {gesamt} Einträge", "m")
    b.y += 16
    b.regel(stark=True)

    hoechste = max((l.anzahl for l in listen.values()), default=1) or 1

    def block(art: str, titel: str, grenze: int) -> int:
        nonlocal b
        gruppe = sorted(((n, l) for n, l in listen.items() if l.art == art),
                        key=lambda kv: -kv[1].anzahl)
        if not gruppe:
            return 0
        b.band(titel)
        for name, l in gruppe[:grenze]:
            if b.y > _boden(z) - 24:
                break
            breite = max(4, int(72 * l.anzahl / hoechste))
            y0 = b.y + 4
            b.d.rectangle([BREITE - RAND - 106, y0, BREITE - RAND - 34, y0 + 9], outline=SCHWARZ)
            if breite > 1:
                b.raster(BREITE - RAND - 105, y0 + 1, BREITE - RAND - 106 + breite, y0 + 9, anteil=50)
            b.eintrag(f"#{name}", str(l.anzahl))
        return max(0, len(gruppe) - grenze)

    block("fest", "fest", 4)
    b.regel()
    rest = block("gewachsen", f"gewachsen · {sum(1 for l in listen.values() if l.art == 'gewachsen')}", 6)
    if rest:
        b.text(f"… und {rest} weitere, die nicht auf die Seite passen", "m")
        b.y += 16

    still = [(n, l) for n, l in listen.items() if l.art == "verblasst"]
    if still and b.y < _boden(z) - 70:
        b.regel()
        b.band("verblasst")
        y0 = b.y
        for name, l in still[:2]:
            b.eintrag(f"#{name}", str(l.anzahl))
        b.verblassen(y0, b.y)
        b.absatz("Seit Langem nichts mehr dazugekommen. Archivieren? "
                 "Der Inhalt bleibt im Vault.", "m")
    return _abschluss(b, z)


# ── 4 Listen-Detail ──────────────────────────────────────────────────────────

def detail(z: Zustand, listen: dict[str, Liste], eintraege: list[tuple[str, str]],
           aufgaben: list[tuple[str, bool]]) -> Blatt:
    b = _rahmen(z)
    name = z.detail_liste
    l = listen.get(name)
    if not l:
        b.text("Diese Liste gibt es noch nicht.", "d2")
        b.y += 30
        b.regel(stark=True)
        b.absatz("Sie entsteht, sobald mehrfach über dasselbe Thema gesprochen wurde.")
        return _abschluss(b, z)

    b.text(f"#{name}", "d1")
    b.y += 36
    b.text(f"{l.anzahl} Einträge · angelegt {l.seit}", "m")
    b.y += 16
    b.regel(stark=True)

    for d, text in eintraege[:6]:
        if b.y > _boden(z) - 90:
            break
        b.text(d, "mo")
        b.absatz(text, "u", einzug=48)
        b.y += 2

    if aufgaben:
        b.regel()
        b.band("Aufgaben")
        for text, fertig in aufgaben[:5]:
            if b.y > _boden(z) - 60:
                break
            b.kaestchen(RAND, b.y + 2, fertig)
            b.text(text, "u", x=RAND + 18)
            if fertig:
                breite = b._breite(text, "u")
                b.d.line([RAND + 18, b.y + 9, RAND + 18 + breite, b.y + 9], fill=SCHWARZ)
            b.y += 21

    # Die Transparenz-Anforderung: Wer wissen will, warum etwas hier gelandet
    # ist, liest die Wörter nach, die hierher sortieren.
    if b.y < _boden(z) - 50:
        b.regel()
        b.text("Sortiert hierher bei", "kursiv")
        b.y += 18
        b.absatz(" · ".join(l.trigger[:12]), "m")
    return _abschluss(b, z)


# ── 5 Notiz ──────────────────────────────────────────────────────────────────

def notiz(z: Zustand) -> Blatt:
    b = _rahmen(z)
    n = next((x for x in z.notizen if x.nr == z.notiz_nr), None) or \
        (z.notizen[-1] if z.notizen else None)
    if not n:
        b.text("Noch keine Aufnahme da.", "d2")
        b.y += 30
        b.regel(stark=True)
        b.absatz("Sobald eine verarbeitet ist, steht sie hier — "
                 "mit Rohfassung und Zuordnung.")
        return _abschluss(b, z)

    b.text(n.wann.strftime("%H:%M"), "mo")
    b.text(f"{n.dauer_s:.1f} s · {int(n.dauer_s * 32)} kB", "m", x=RAND + 46)
    b.text("Roh" if z.roh_zeigen else "Bereinigt", "mo", rechts=True)
    b.y += 20
    b.regel(stark=True)
    b.absatz(n.roh if z.roh_zeigen else n.rein, "p")

    b.regel()
    b.text("Erkannt", "kursiv")
    b.y += 19
    b.absatz(" · ".join(n.schlagworte), "m")
    b.y += 4
    ziel = "Tagebuch, heutiger Eintrag" if n.art == "tagebuch" else f"#{n.ziel}"
    b.eintrag(ziel + (" · neu angelegt" if n.art == "neu" else ""), f"{n.score:.2f}")
    b.absatz(n.grund, "m")

    if n.aufgaben:
        b.y += 4
        b.text("Aufgaben", "kursiv")
        b.y += 18
        for t in n.aufgaben:
            b.eintrag(t, kasten=True, hoehe=19)

    if b.y < _boden(z) - 40:
        b.regel(eng=True)
        b.eintrag("Transkription", f"conf {n.vertrauen:.2f}", art="m", hoehe=17)
        b.eintrag("Audio wird gelöscht", n.audio_bis, art="m", hoehe=17)
    return _abschluss(b, z)


# ── 6 Tagebuch ───────────────────────────────────────────────────────────────

def tagebuch(z: Zustand) -> Blatt:
    b = _rahmen(z)
    heute_ = date.today()
    b.text(f"{WOCHENTAG[heute_.weekday()]}, {heute_.day}. {MONAT[heute_.month - 1]}", "d2")
    b.y += 28
    b.regel(stark=True)

    if not z.tagebuch:
        b.absatz("Noch nichts eingetragen.", "p")
        b.y += 6
        b.absatz("Erzähl abends, was war — daraus wird der Tageseintrag.", "m")
        return _abschluss(b, z)

    gezeigt = 0
    for uhr, text in z.tagebuch:
        if b.y > _boden(z) - 60:
            break
        b.text(uhr, "mo", dy=3)
        b.absatz(text, "p", einzug=48)
        b.y += 8
        gezeigt += 1

    rest = len(z.tagebuch) - gezeigt
    if rest:
        b.text(f"… und {rest} weitere Absätze", "m")
        b.y += 16
    b.regel()
    worte = sum(len(t.split()) for _, t in z.tagebuch)
    b.eintrag(f"{worte} Wörter · {len(z.tagebuch)} Absätze", art="m")
    b.y += 6
    b.eintrag("◀ Vortag", "Folgetag ▶", art="m")
    return _abschluss(b, z)


# ── 7 Kalender ───────────────────────────────────────────────────────────────

def kalender(z: Zustand) -> Blatt:
    b = _rahmen(z)
    heute_ = date.today()
    b.text("Woche", "d2")
    b.y += 26

    if not z.kalender_verbunden:
        # Eine leere Woche und ein Hinweis sehen auf dem Papier identisch aus,
        # wenn man beide zeigt, ohne zu sagen welcher Fall es ist — deshalb
        # ehrlich sagen, dass hier keine Quelle angeschlossen ist, statt eine
        # Woche ohne Termine zu behaupten.
        b.regel(stark=True)
        b.absatz("Noch nicht mit dem Apple-Kalender verbunden.", "p")
        b.y += 8
        b.absatz("Die Verbindung wird in der Konfiguration des Brain "
                 "eingerichtet, nicht auf dem Gerät.", "m")
        return _abschluss(b, z)

    b.text(f"KW {heute_.isocalendar().week} · aus dem Apple-Kalender", "m")
    b.y += 16
    b.regel(stark=True)

    montag = heute_ - timedelta(days=heute_.weekday())
    for i in range(7):
        tag = montag + timedelta(days=i)
        eintraege = z.termine.get(i, [])
        kopf = f"{KURZ[tag.weekday()]} {tag.day:02d}.{tag.month:02d}."
        zahl = f"{len(eintraege)} Termin{'e' if len(eintraege) != 1 else ''}" if eintraege else "—"

        if tag == heute_:
            # Heute wird invertiert markiert, nicht farbig. Das Panel kann
            # keine Farbe, und ein schwarzer Balken liest sich ohnehin klarer.
            b.invers(f"{kopf}      {zahl}", hoehe=22)
        else:
            b.eintrag(kopf, zahl)
        for uhr, text in eintraege:
            b.text(uhr, "mo", x=RAND + 8, dy=2)
            b.text(text, "u", x=RAND + 56)
            b.y += 19
        if i < 6:
            b.regel(eng=True)
    return _abschluss(b, z)


# ── 8 Warteschlange ──────────────────────────────────────────────────────────

def warteschlange(z: Zustand, sd_belegt_mb: int = 0, sd_gesamt_mb: int = 29800,
                  offline_seit: str = "", naechster_versuch_s: int = 30) -> Blatt:
    b = _rahmen(z)
    b.text("Warteschlange", "d2")
    b.y += 26
    b.text("verbunden mit pi5-brain.local" if z.wlan
           else (f"offline seit {offline_seit}" if offline_seit else "noch nie verbunden"), "m")
    b.y += 16
    b.regel(stark=True)

    if z.wlan and not z.wartend:
        b.absatz("Nichts wartet. Aufnahmen laufen direkt durch.", "p")
    elif not z.wlan:
        b.d.rectangle([RAND - 8, b.y, BREITE - RAND + 8, b.y + 52], outline=SCHWARZ, width=2)
        b.y += 9
        b.text(f"Nächster Versuch in {naechster_versuch_s} s", "u", x=RAND)
        b.y += 20
        b.absatz("Aufnahmen bleiben auf der SD-Karte, bis der Pi wieder erreichbar ist.",
                 "m", breite=BREITE - 2 * RAND - 8)
        b.y += 14

    if z.wartend:
        b.regel()
        b.band(f"{z.wartend} Aufnahmen auf der Karte")
        for i in range(min(z.wartend, 8)):
            b.eintrag(f"Aufnahme {i + 1}", "als nächstes" if i == 0 else "wartet", art="m", hoehe=18)
        if z.wartend > 8:
            b.text(f"… und {z.wartend - 8} weitere", "m")
            b.y += 16

    b.regel()
    b.band("SD-Karte")
    anteil = sd_belegt_mb / sd_gesamt_mb if sd_gesamt_mb else 0
    b.d.rectangle([RAND, b.y, BREITE - RAND, b.y + 10], outline=SCHWARZ)
    if anteil > 0:
        b.raster(RAND + 1, b.y + 1, RAND + 1 + int((BREITE - 2 * RAND - 2) * anteil),
                 b.y + 10, anteil=50)
    b.y += 18
    b.eintrag("belegt", f"{sd_belegt_mb / 1000:.1f} von {sd_gesamt_mb / 1000:.1f} GB", art="m")
    stunden = (sd_gesamt_mb - sd_belegt_mb) / (32 * 3.6)
    b.eintrag("Restreichweite", f"{stunden:.0f} h Aufnahme", art="m")
    b.eintrag("Format", "FAT32", art="m")
    return _abschluss(b, z)


# ── Verteiler ────────────────────────────────────────────────────────────────

def seite(z: Zustand, listen: dict[str, Liste], **kw) -> Blatt:
    # Ruhend gibt es nur eine Seite: „Heute". Was das Gerät stundenlang zeigt,
    # soll das sein, was man sehen will — nicht das, was zufällig zuletzt offen war.
    if z.ruhe:
        return heute(z, listen)
    if z.ansicht == "eingang":
        return eingang(z)
    if z.ansicht == "listen":
        return listen_seite(z, listen)
    if z.ansicht == "detail":
        return detail(z, listen, kw.get("eintraege", []), kw.get("aufgaben", []))
    if z.ansicht == "notiz":
        return notiz(z)
    if z.ansicht == "tagebuch":
        return tagebuch(z)
    if z.ansicht == "kalender":
        return kalender(z)
    if z.ansicht == "warteschlange":
        return warteschlange(z, **{k: v for k, v in kw.items()
                                   if k in ("sd_belegt_mb", "offline_seit", "naechster_versuch_s")})
    return heute(z, listen)
