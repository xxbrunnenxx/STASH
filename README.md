# STASH

**Muss ich nicht im Kopf haben.**

Ein sprachgesteuertes Notizsystem: Knopf drücken, drauflosreden, fertig. Ein E-Paper-Gerät im
Notizbuchformat nimmt auf, ein Raspberry Pi im Heimnetz transkribiert, räumt auf, sortiert ein und
schreibt Markdown in einen Obsidian-Vault. Zurück aufs Gerät kommt die saubere Fassung, plus
Kalender und Erinnerungen.

Alles läuft lokal. Kein Audio verlässt das Haus.

*Ein Stash ist der Vorrat, den man sich weglegt.*

**Status:** Spezifikation. Es gibt noch keinen lauffähigen Code — dieses Dokument beschreibt, was
gebaut wird, und dient zugleich als Bauauftrag für den Coding-Agent (siehe
[Showcase erzeugen](#showcase-erzeugen)).

---

## Inhalt

- [Systemüberblick](#systemüberblick)
- [Stückliste](#stückliste)
- [Showcase erzeugen](#showcase-erzeugen)
- [Repo-Struktur](#repo-struktur)
- [Harte Regeln](#harte-regeln)
- [Design](#design)
- [Die acht Geräte-Ansichten](#die-acht-geräte-ansichten)
- [Die Pipeline](#die-pipeline)
- [E-Ink-Echtheit](#e-ink-echtheit)
- [Demo-Inhalte](#demo-inhalte)
- [Nicht machen](#nicht-machen)
- [Abnahme](#abnahme)
- [Fahrplan](#fahrplan)
- [Lizenz](#lizenz)

---

## Systemüberblick

```
┌───────────────────────────┐            ┌──────────────────────────────┐
│  ESP32-S3-ePaper-3.97     │            │  Raspberry Pi 5 · „Brain"    │
│                           │            │  16 GB RAM · 1 TB NVMe       │
│  Mikrofon ─ ES8311        │  WLAN /    │                              │
│  E-Paper 480×800 s/w      │◄──────────►│  faster-whisper (lokal)      │
│  SD-Karte = Warteschlange │    BLE     │  Aufräumen + Schlagwörter    │
│  Drehknopf, 3 Richtungen  │            │  Einsortieren nach Regeln    │
│  RTC · IMU · Li-Akku      │            │  Renderer → 1-Bit-Bitmap     │
└───────────────────────────┘            └──────────────┬───────────────┘
                                                        │
                            ┌───────────────────────────┼───────────────────────────┐
                            ▼                           ▼                           ▼
                    Obsidian-Vault             Apple Erinnerungen           Apple Kalender
                    (Markdown, lokal)               (CalDAV)                   (CalDAV)
```

Die Warteschlange auf der SD-Karte ist der Grund, warum das Gerät auch ohne WLAN funktioniert:
Aufnahmen landen erst dort und werden abgearbeitet, sobald der Pi wieder erreichbar ist.

## Stückliste

**Gerät:** [Waveshare ESP32-S3-ePaper-3.97](https://docs.waveshare.com/ESP32-S3-ePaper-3.97)
(SKU 33552 / 33810 EN / 33811 Kit)

Diese Angaben stammen aus dem Datenblatt. Nichts davon erfinden oder ändern:

| Komponente | Details |
|---|---|
| SoC | ESP32-S3-WROOM-1-N16R8, 16 MB Flash, 8 MB PSRAM, 240 MHz |
| Display | E-Paper 800 × 480, schwarz/weiß — **hochkant benutzt: 480 breit × 800 hoch** |
| Audio | Mikrofon, ES8311 Codec, NS4150B Verstärker → **das Gerät nimmt selbst auf** |
| Speicher | TF-Karten-Slot (FAT32) → **hier liegt die Warteschlange** |
| Uhr | PCF85063 RTC, mit eigenem Stützakku-Anschluss |
| Sensoren | SHTC3 (Temperatur/Luftfeuchte), QMI8658 6-Achsen-IMU |
| Strom | TG28 Power-Management, 3,7 V Li-Akku über MX1.25, USB-C |
| Bedienung | Drehknopf mit drei Richtungen, seitlich PWR und BOOT |
| Funk | 2,4 GHz WLAN (b/g/n), BLE 5 |

Die drei Richtungen des Drehknopfs sind die komplette Bedienung.

**Brain:** Raspberry Pi 5, 16 GB RAM, 1 TB NVMe-SSD, aktive Kühlung.

**Gehäuse:** selbst gedruckt, zweiteilig, Frontplatte magnetisch abnehmbar, damit die SD-Karte ohne
Demontage erreichbar bleibt.

## Showcase erzeugen

Der erste Meilenstein ist ein bedienbarer Showcase — eine pixelgenaue Simulation des Panels in einer
Werkbank drumherum, damit man vor dem Löten sieht, wie sich das Ding anfühlt.

Dieses Dokument ist zugleich der Bauauftrag. Komplett kopieren und in Claude Code absetzen:

```bash
git clone https://github.com/xxbrunnenxx/stash.git
cd stash
claude
# dann README.md als Auftrag einfügen
```

Ergebnis: `showcase/stash-showcase.html` — ein einziges HTML-File, kein Build-Step, keine
Dependencies außer Google Fonts (mit Fallback). Per Doppelklick zu öffnen.

Der Showcase ist **nicht** die Firmware und **nicht** das Pi-Setup.

## Repo-Struktur

```
stash/
├─ README.md              dieses Dokument (Spezifikation + Bauauftrag)
├─ LICENSE
├─ showcase/
│  └─ stash-showcase.html
├─ firmware/              ESP-IDF, noch leer
├─ brain/                 Pi-Dienste, noch leer
└─ gehaeuse/              STL/STEP, noch leer
```

## Harte Regeln

1. **Reines Schwarz/Weiß.** Keine Farbe, nirgends — auch nicht in der Werkbank drumherum.
   Grautöne auf dem Gerätescreen nur als **Dither-Muster** (Schachbrett 2 px, Punktraster),
   niemals als flaches Grau. Das Panel kann kein Grau, also darf keins zu sehen sein.
2. **Hochkant, 480 × 800, pixelgenau.** Der Gerätescreen ist exakt so groß und wird per
   `transform: scale()` an die Fensterhöhe angepasst — nicht umlayouten, nicht strecken.
3. **Keine weichen Kanten auf dem Panel.** Kein `border-radius`, keine `box-shadow`, keine
   Verläufe innerhalb des Screens. Harte 1-px- und 2-px-Linien. Außerhalb des Panels (Gehäuse,
   Werkbank) darf Rundung und Schatten sein — das ist ja physisch.
4. **Deutsch.** Alle Texte, Labels, Log-Zeilen, Demo-Inhalte.
5. **Kein Framework.** Vanilla JS, ein `<style>`-Block, ein `<script>`-Block.

## Design

Werkbank-Ästhetik: dunkle Werkfläche, das Gerät liegt als physisches Objekt drauf, drumherum
Ableseinstrumente. Das Papier ist das Hellste im Bild — es leuchtet nicht, es reflektiert.

```
--void:   #0A0A0B   Werkfläche
--shell:  #17181A   Panels links/rechts
--edge:   #2A2C30   Trennlinien
--mute:   #6E7278   Sekundärtext
--chalk:  #D9DBDD   Primärtext auf dunkel
--paper:  #F4F4F2   E-Ink-Papier
--ink:    #14161A   E-Ink-Schwarz
```

Schrift:

- **Literata** für Notiztexte auf dem Gerät (wurde für E-Reader gemacht — passt inhaltlich)
- **IBM Plex Sans** für Bedienelemente, Überschriften, Werkbank
- **IBM Plex Mono** nur da, wo es wirklich Maschinenausgabe ist: Log, Zeitstempel, Schlagwort-Chips

Aufbau des Showcase-Fensters:

```
┌──────────────────────────────────────────────────────────────┐
│ STASH · muss ich nicht im Kopf haben      pi5-brain · online │
├──────────────┬──────────────────────────┬────────────────────┤
│ Ansichten    │        ┌──────────┐      │ Brain-Log          │
│  Heute       │        │          │      │ (mono, scrollt,    │
│  Eingang     │        │  480×800 │      │  Zeitstempel ms)   │
│  Listen      │        │  E-Ink   │      │                    │
│  #überdachung│        │  hochkant│      │ Pipeline-Stufen    │
│  Notiz       │        │          │      │ (aktive markiert)  │
│  Tagebuch    │        └──────────┘      │                    │
│  Kalender    │       ◉ Drehknopf        │ Hardware-Anzeige   │
│  Warteschl.  │                          │ Akku · Temp · RTC  │
│              │   [Vollrefresh]          │ SD · RSSI · Refresh│
│ ▸ Sprachnotiz│   [Gerät aus]            │                    │
│   aufnehmen  │   [Serif / Sans]         │                    │
└──────────────┴──────────────────────────┴────────────────────┘
```

Unter 1100 px darf die rechte Spalte unter das Gerät rutschen. Der Screen bleibt 480 × 800.

## Die acht Geräte-Ansichten

Jede hat oben eine dünne Statusleiste (STASH · Warteschlangen-Zähler · WLAN · Akku · Uhrzeit,
Symbole als winzige Inline-SVGs, nicht Unicode) und unten eine Leiste mit der Drehknopf-Belegung
`◀ zurück   ● aufnehmen   ▶ weiter`.

1. **Heute** — Datum groß in Literata, darunter durch Linien getrennt: nächste Kalendertermine,
   fällige Erinnerungen mit Kästchen, Eingangs-Zähler mit Anriss der letzten Notiz, Tagebuch-Zähler.
2. **Eingang** — Liste der Aufnahmen von heute: Uhrzeit, Länge, erste Zeile der bereinigten Fassung,
   Schlagwort-Chips, Status (verarbeitet / in Warteschlange). Anklickbar → Ansicht 5.
3. **Listen** — der Kern. Drei Blöcke:
   - *fest*: `#einkauf`, `#tagebuch`, `#ideen`, `#termine` — die verschwinden nie
   - *gewachsen*: `#überdachung`, `#pv-anlage`, `#gehäuse` (mit „neu"-Markierung), `#obsidian`,
     jeweils mit Anzahl und Anlagedatum
   - *verblasst*: eine Liste ohne Einträge seit 63 Tagen, mit Vorschlag zum Archivieren
4. **Listen-Detail** (`#überdachung`) — Einträge mit Datum, Aufgaben mit Kästchen. **Ganz unten die
   Trigger-Wörter, die in diese Liste einsortieren** — das ist die Transparenz-Anforderung, die darf
   nicht fehlen.
5. **Notiz** — eine einzelne Aufnahme. Umschalter *Bereinigt / Roh* (beides echt hinterlegt, das Rohe
   mit Ähms und Wiederholungen). Darunter ein Block „Erkannt": Schlagwörter, Zuordnung mit Score
   und Begründung, gefundene Aufgaben, Transkriptions-Vertrauen, Aufbewahrungsdatum der Audiodatei.
6. **Tagebuch** — ein Tag, zusammengesetzt aus mehreren Aufnahmen. Zeitgestempelte Absätze in
   Literata, unten Wortzahl und Zusammenführungszeit, darunter Blättern zum Vor-/Folgetag.
7. **Kalender** — Wochenagenda aus dem Apple-Kalender, heute invertiert (schwarzer Balken,
   Papierschrift) statt farbig markiert.
8. **Warteschlange** — offline seit X, Aufnahmen auf der SD-Karte mit Länge und Wartestatus,
   nächster Versuch in N Sekunden, belegter SD-Speicher und Restreichweite in Stunden.

## Die Pipeline

Der Weg einer Aufnahme, und im Showcase das Herzstück.

```
Mikrofon → SD-Puffer → Upload → Transkription → Aufräumen → Schlagwörter
                                                                  │
                              Panel ← Rendern ← Vault ← Einsortieren
```

Der Button **„Sprachnotiz aufnehmen"** startet den Ablauf zeitgesteuert. Der Gerätescreen zeigt
währenddessen ein Aufnahme-Overlay mit laufender Zeit und einer 1-Bit-Balken-Wellenform. Parallel
laufen Log-Zeilen rechts ein und die Pipeline-Stufen werden nacheinander aktiv.

Log-Format `HH:MM:SS.mmm  modul  text`, monospace:

```
14:07:22.104  vad      Sprachaktivität erkannt (−31 dBFS)
14:07:22.106  rec      Aufnahme läuft · 16 kHz mono · ES8311
14:07:31.880  rec      gestoppt · 9,7 s · 310 kB
14:07:31.884  queue    → /sd/stash/q/0f3a.wav
14:07:32.010  net      pi5-brain.local erreichbar · RSSI −54 dBm
14:07:32.402  net      Upload 310 kB in 392 ms
14:07:36.610  whisper  faster-whisper small int8 · 4,2 s · 47 Wörter · conf 0.94
14:07:37.240  clean    11 Füllwörter raus · Sätze normalisiert
14:07:37.980  keys     überdachung · material · bestellen
14:07:37.984  route    #überdachung · Score 1.00 · feste Liste
14:07:38.090  tasks    2 Aufgaben → Apple Erinnerungen (CalDAV)
14:07:38.310  vault    ~/Obsidian/stash/Listen/überdachung.md (+1)
14:07:38.520  render   1-bit 480×800 · 47 kB
14:07:38.728  push     BLE → ESP32-S3 · 208 ms
14:07:39.070  epd      Partial-Refresh 340 ms · Zähler 7/12
```

> Alle Zeitwerte sind geschätzt und stehen als benannte Konstanten oben im Script, mit Kommentar.
> Sie werden ersetzt, sobald Whisper das erste Mal echt auf dem Pi läuft.

**Mindestens fünf verschiedene Demo-Aufnahmen**, die bei wiederholtem Drücken durchrotieren — jede
zeigt einen anderen Fall:

| Aufnahme | Was sie zeigt |
|---|---|
| Material für die Überdachung | bestehende feste Zuordnung, zwei Aufgaben erkannt |
| Idee zum Gehäuse (zweiteilig drucken, Frontplatte magnetisch) | **kein Treffer über Schwelle 0.62 → neue Liste `#gehäuse` wird angelegt**, sichtbar im Log und auf dem Screen |
| Feierabend-Rückblick in Erzählform | erkannt als Tagebuch, wird an den heutigen Eintrag angehängt |
| Einkauf, drei Sachen | `#einkauf` |
| Termin mit Uhrzeit | Apple Erinnerung + `#termine` |

Zusätzlich ein Schalter **„WLAN aus"**: dann wandert die Aufnahme in die Warteschlange statt
durchzulaufen, und die Warteschlangen-Ansicht füllt sich. Beim Wiedereinschalten läuft der Stau ab.

## E-Ink-Echtheit

Die Details, an denen es hängt:

- **Vollrefresh**: kurz komplett invertieren, zurück, dann Inhalt. ~2,4 s. Eigener Button.
- **Partial-Refresh**: nur der geänderte Bereich, ~340 ms, mit kurzem grauen Wisch.
- **Geisterbilder**: nach mehreren Partial-Refreshes ganz schwacher Rückstand des vorherigen
  Inhalts, und ein Zähler `Partial 7/12 → Vollrefresh fällig`. Nach dem Vollrefresh ist er weg.
- **„Gerät aus"**: Statusleiste und Fußleiste verschwinden, der Inhalt bleibt stehen, kleiner
  Hinweis unten. E-Paper hält das Bild ohne Strom — das ist der Witz an der Sache, zeig ihn.
- Auswahl/Markierung immer als invertierter Block, nie als Farbfläche.
- Akku in Prozent **und** geschätzten Tagen Restlaufzeit.

## Demo-Inhalte

Deutsch, alltäglich, glaubwürdig. Projekte, die vorkommen dürfen: eine Gartenüberdachung im
Selbstbau, eine PV-Anlage mit Datenauswertung, 3D-Druck fürs Gehäuse, Obsidian, Einkauf, Ideen,
Termine.

Die rohen Transkripte müssen wirklich roh klingen — Ähms, Selbstkorrekturen, halbe Sätze,
Nachschieben von Details. Der Kontrast zur bereinigten Fassung ist der Punkt, an dem der Showcase
überzeugt oder nicht.

Tagebucheinträge bleiben sachlich und beiläufig: was gemacht wurde, wo man war, was aufgefallen ist.

## Nicht machen

- Keine Stimmungs- oder Befindlichkeitserfassung, keine Punktzahlen fürs Wohlbefinden,
  keine Selbstoptimierungs-Anzeigen. Ist nicht Teil des Produkts.
- Keine Farbe, kein Akzentton, kein flaches Grau auf dem Panel.
- Keine Einblend-Animationen beim Scrollen, keine Hover-Effekte auf allem. Bewegung nur da, wo sie
  etwas erklärt: Aufnahme, Refresh, Pipeline.
- Keine Karten-Optik mit gleichen Rundungen und Schatten für alles.
- Keine Großbuchstaben-Labels über jedem Abschnitt.
- Keine erfundenen Hardware-Eigenschaften. Was in der Stückliste nicht steht, hat das Board nicht.
- Kein `localStorage` / `sessionStorage`. Zustand nur in JS-Variablen.

## Abnahme

- [ ] `showcase/stash-showcase.html` öffnet sich per Doppelklick, keine Konsolenfehler
- [ ] alle acht Ansichten sind erreichbar und gefüllt
- [ ] „Sprachnotiz aufnehmen" läuft mindestens fünfmal mit unterschiedlichem Ergebnis durch
- [ ] dabei wird einmal sichtbar eine neue Liste angelegt und einmal ins Tagebuch angehängt
- [ ] „WLAN aus" füllt die Warteschlange, „WLAN an" arbeitet sie ab
- [ ] Voll- und Partial-Refresh sehen unterschiedlich aus, der Geisterbild-Zähler zählt
- [ ] „Gerät aus" lässt den Inhalt stehen
- [ ] eine Suche nach Farbwerten im File findet nur Grauwerte
- [ ] das Panel ist bei jeder Fensterbreite 480 × 800, nur skaliert

**Hinweis an den Coding-Agent:** Wenn du fertig bist, öffne das File selbst und klick es durch.
Dann in zwei, drei Sätzen sagen, was konkret drinsteckt — nicht „fertig" schreiben, sondern was
gebaut wurde.

## Fahrplan

1. **Showcase** — bedienbare Simulation, um das Konzept vor dem Löten zu prüfen ← *hier*
2. **Firmware** — Aufnahme über ES8311, Puffer auf SD, BLE-Übertragung, Panel-Ansteuerung
3. **Brain** — faster-whisper, Aufräumen, Schlagwortextraktion, Einsortieren, Vault-Schreiber
4. **CalDAV** — Apple Kalender und Erinnerungen in beide Richtungen
5. **Gehäuse** — zweiteilig gedruckt, magnetische Frontplatte, SD ohne Demontage erreichbar
6. **Feinschliff** — Akkulaufzeit messen, Refresh-Strategie und Weckintervalle optimieren

## Lizenz

*Noch festzulegen.* Ohne `LICENSE`-Datei gilt auf GitHub automatisch „alle Rechte vorbehalten" —
niemand darf den Code benutzen. MIT ist für so ein Projekt der übliche Weg, wenn andere es
nachbauen können sollen.
