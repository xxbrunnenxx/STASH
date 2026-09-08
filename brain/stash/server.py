"""Der Dienst. Nimmt Aufnahmen an, gibt Bilder zurück.

Er hört auf dem Heimnetz und hat keine Anmeldung. Das ist Absicht und zugleich
die Bedingung: Er gehört nicht ins Internet. Frei reden kann man nur in etwas,
das nichts weitergibt — und was nicht erreichbar ist, gibt auch nichts weiter.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, File, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from . import seiten
from .aufraeumen import bereinigen, zaehle_fueller
from .einsortieren import aufgaben as aufgaben_finden
from .einsortieren import einsortieren, uebernehmen
from .einstellungen import Einstellungen, laden
from .schlagworte import schlagworte
from .transkript import Transkribierer
from .vault import Vault
from .zustand import ANSICHTEN, Notiz, Zustand

log = logging.getLogger("stash")

# openapi_url=None zusätzlich zu docs_url/redoc_url: Sonst bleibt das
# vollständige Schema unter /openapi.json erreichbar, obwohl die Absicht
# offensichtlich war, die API-Struktur nicht öffentlich zu machen.
app = FastAPI(title="STASH Brain", docs_url=None, redoc_url=None, openapi_url=None)

E: Einstellungen
VAULT: Vault
Z: Zustand
WHISPER: Transkribierer
NUMMER = 0
SD_BELEGT_MB = 0


def aufsetzen(e: Einstellungen | None = None) -> None:
    global E, VAULT, Z, WHISPER
    E = e or laden()
    VAULT = Vault(E)
    Z = Zustand()
    WHISPER = Transkribierer(E)
    _morgenseite_aktualisieren()

    log.info("Vault %s · %d Listen · Konfiguration aus %s",
             E.vault, len(VAULT.listen), E.herkunft)


def _morgenseite_aktualisieren() -> None:
    """Verdichtete Seite und geklärte Fragen von der Platte lesen, nicht nur
    einmal beim Start.

    stash-brain ist ein langlaufender Dienst; stash-nachtlauf (der
    dokumentierte Weg über den systemd-Timer) ist ein eigener, kurzlebiger
    Prozess, der .stash/morgen-{datum}.md und .stash/geklaert-{datum}.json
    schreibt und danach wieder endet. Ohne diesen erneuten Lesevorgang bei
    jeder Anfrage würde der laufende Server nie erfahren, dass die Nacht
    etwas hinterlassen hat — die Seite bliebe leer, bis der Dienst zufällig
    neu startet. Zwei kleine Dateien zu lesen kostet auf einer NVMe nichts;
    das bei jeder Anfrage zu tun ist billiger als das Risiko, die
    Morgenseite zu verpassen.
    """
    heute = date.today().isoformat()
    morgen = E.vault / ".stash" / f"morgen-{heute}.md"
    Z.morgenseite = morgen.read_text(encoding="utf-8") if morgen.exists() else ""

    geklaert_datei = E.vault / ".stash" / f"geklaert-{heute}.json"
    if geklaert_datei.exists():
        try:
            paare = json.loads(geklaert_datei.read_text(encoding="utf-8"))
            Z.geklaert = [tuple(p) for p in paare]
        except (json.JSONDecodeError, OSError, ValueError):
            Z.geklaert = []
    else:
        Z.geklaert = []


# ── Die Pipeline ─────────────────────────────────────────────────────────────

@app.post("/v1/notiz")
async def notiz_annehmen(datei: UploadFile = File(...)):
    global NUMMER
    NUMMER += 1
    jetzt = datetime.now()

    # Erst wegschreiben, dann arbeiten. Wenn die Verarbeitung scheitert, ist
    # die Aufnahme trotzdem da — das Gerät hat sie bereits von der Karte
    # gelöscht, sobald wir 200 antworten.
    ziel = E.audio_ordner / f"{jetzt:%Y-%m-%d-%H%M%S}-{NUMMER:04d}.wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        shutil.copyfileobj(datei.file, tmp)
        zwischen = Path(tmp.name)
    shutil.move(str(zwischen), ziel)

    roh, vertrauen, dauer = WHISPER.transkribieren(ziel)
    if not roh.strip():
        log.warning("%s enthält keine erkennbare Sprache", ziel.name)
        return JSONResponse({"nr": NUMMER, "leer": True}, status_code=200)

    fueller = zaehle_fueller(roh)
    rein = bereinigen(roh)
    worte = schlagworte(rein)
    zu = einsortieren(rein, worte, VAULT.listen, E.schwelle)
    aufg = aufgaben_finden(rein)

    log.info("clean   %d Füllwörter raus · Sätze normalisiert", fueller)
    log.info("keys    %s", " · ".join(worte))
    log.info("route   #%s · Score %.2f · %s", zu.ziel, zu.score, zu.grund)

    uebernehmen(zu, worte, VAULT.listen)
    VAULT.listen_sichern()

    if zu.art == "tagebuch":
        pfad = VAULT.an_tagebuch(jetzt, rein)
        Z.tagebuch.append((jetzt.strftime("%H:%M"), rein))
    else:
        pfad = VAULT.an_liste(zu.ziel, jetzt, rein, aufg)
    VAULT.notiz_schreiben(NUMMER, jetzt, dauer, roh, rein, worte, zu, aufg)
    log.info("vault   %s (+1)", pfad)

    for a in aufg:
        Z.erinnerungen.append((a, False))

    Z.notizen.append(Notiz(
        nr=NUMMER, wann=jetzt, dauer_s=dauer, roh=roh, rein=rein,
        schlagworte=worte, ziel=zu.ziel, art=zu.art, score=zu.score,
        grund=zu.grund, aufgaben=aufg, vertrauen=vertrauen,
        audio_bis=(date.today() + timedelta(days=E.audio_aufbewahrung_tage)).strftime("%d.%m."),
    ))
    # Nach einer Aufnahme zeigt das Gerät die Aufnahme. Alles andere wäre eine
    # Rückfrage: „willst du sie sehen?"
    Z.ansicht = "notiz"
    Z.notiz_nr = NUMMER
    Z.roh_zeigen = False

    return {
        "nr": NUMMER, "roh": roh, "rein": rein, "schlagworte": worte,
        "ziel": zu.ziel, "art": zu.art, "score": round(zu.score, 2),
        "grund": zu.grund, "aufgaben": aufg,
        "vertrauen": round(vertrauen, 2), "dauer_s": round(dauer, 1),
        "datei": str(pfad),
    }


# ── Anzeige ──────────────────────────────────────────────────────────────────

def _blatt(ansicht: str | None):
    # Nur eine der acht bekannten Ansichten wird übernommen. Ohne diese Prüfung
    # landet ein beliebiger Query-String direkt im geteilten Zustand und wird
    # später ungefiltert in den Antwort-Header X-Stash-Ansicht gespiegelt —
    # ein Wert mit \r\n dort bringt die HTTP-Schicht zum Absturz (per h11
    # LocalProtocolError nachgewiesen, siehe Issue #8).
    if ansicht and ansicht in ANSICHTEN:
        Z.ansicht = ansicht
    _morgenseite_aktualisieren()
    eintraege, aufgaben = _detail_daten()
    return seiten.seite(Z, VAULT.listen, eintraege=eintraege, aufgaben=aufgaben,
                        sd_belegt_mb=SD_BELEGT_MB, offline_seit="")


def _detail_daten() -> tuple[list[tuple[str, str]], list[tuple[str, bool]]]:
    """Die Einträge einer Liste kommen aus dem Markdown selbst — nicht aus einer
    Nebenbuchhaltung, die auseinanderlaufen kann."""
    if not Z.detail_liste:
        return [], []
    eintraege, aufgaben = [], []
    for zeile in VAULT.liste_lesen(Z.detail_liste).splitlines():
        z = zeile.strip()
        if z.startswith("- [ ]"):
            aufgaben.append((z[5:].strip(), False))
        elif z.startswith("- [x]"):
            aufgaben.append((z[5:].strip(), True))
        elif z.startswith("- **"):
            datum, _, text = z[4:].partition("**")
            eintraege.append((datum.strip(), text.strip()))
    return list(reversed(eintraege)), aufgaben


@app.get("/v1/bild")
async def bild(anfrage: Request, ansicht: str | None = None, format: str = "roh",
               akku: int | None = None, wartend: int | None = None,
               sd_mb: int | None = None, ruhe: int | None = None):
    # Was nur das Gerät weiß, sagt das Gerät: Akkustand, wie viel noch auf der
    # Karte liegt, wie voll sie ist. Der Pi rät das nicht.
    if akku is not None:
        Z.akku = max(0, min(100, akku))
    if wartend is not None:
        Z.wartend = max(0, wartend)
    if sd_mb is not None:
        global SD_BELEGT_MB
        SD_BELEGT_MB = max(0, sd_mb)
    # Ob es ruht, weiß nur das Gerät — es zählt die Zeit seit dem letzten
    # Tastendruck. Der Pi soll das nicht raten.
    if ruhe is not None:
        Z.ruhe = bool(ruhe)

    b = _blatt(ansicht)
    daten = b.bytes()
    # ETag statt Abfrageintervall: Das Gerät fragt regelmäßig, zeichnet aber
    # nur, wenn sich wirklich etwas geändert hat. Jeder überflüssige Refresh
    # kostet Strom und hinterlässt Geisterbild.
    marke = '"' + hashlib.sha1(daten).hexdigest()[:16] + '"'

    if anfrage.headers.get("if-none-match") == marke:
        return Response(status_code=304, headers={"ETag": marke})

    if format == "png":
        import io
        puffer = io.BytesIO()
        b.bild.save(puffer, format="PNG")
        return Response(puffer.getvalue(), media_type="image/png",
                        headers={"ETag": marke})

    return Response(daten, media_type="application/octet-stream",
                    headers={"ETag": marke, "X-Stash-Ansicht": Z.ansicht})


@app.get("/v1/zustand")
async def zustand():
    _morgenseite_aktualisieren()
    return {
        "ansicht": Z.ansicht,
        "akku": Z.akku,
        "wlan": Z.wlan,
        "wartend": Z.wartend,
        "notizen_heute": len(Z.notizen),
        "listen": {n: l.anzahl for n, l in VAULT.listen.items()},
        "tagebuch_absaetze": len(Z.tagebuch),
        "morgenseite": bool(Z.morgenseite),
    }


@app.post("/v1/bedienung")
async def bedienung(daten: dict):
    taste = daten.get("taste", "")
    Z.ruhe = False          # wer drückt, bedient — dann gilt wieder die Fußleiste
    if taste == "zurueck":
        Z.blaettern(-1)
    elif taste == "weiter":
        Z.blaettern(1)
    elif taste == "oeffnen":
        Z.oeffnen(VAULT.listen)
    else:
        return JSONResponse({"fehler": f"unbekannte Taste: {taste}"}, status_code=400)
    return {"ansicht": Z.ansicht}


@app.post("/v1/nachtlauf")
async def nachtlauf_jetzt():
    from .nachtlauf import lauf
    bericht = lauf(E)
    VAULT.listen = Vault(E).listen
    # lauf() hat verdichtet/geklaert bereits auf die Platte geschrieben —
    # derselbe Weg, über den auch der systemd-Timer-Prozess dem Server seine
    # Ergebnisse mitteilt (Issue #12). Ein Ladepfad für beide Fälle, damit
    # nichts auseinanderlaufen kann.
    _morgenseite_aktualisieren()
    return {k: v for k, v in bericht.items() if k != "verdichtet"} | {
        "verdichtet": bool(bericht["verdichtet"])}


def hauptprogramm() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s.%(msecs)03d  %(name)-14s  %(message)s",
                        datefmt="%H:%M:%S")
    aufsetzen()
    import uvicorn
    uvicorn.run(app, host=E.adresse, port=E.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(hauptprogramm())
