# STASH

**Muss ich nicht im Kopf haben.**

Ein sprachgesteuertes Notizsystem: Knopf drücken, drauflosreden, fertig. Ein E-Paper-Gerät im
Notizbuchformat nimmt auf, ein Raspberry Pi im Heimnetz transkribiert, räumt auf, sortiert ein und
schreibt Markdown in einen Obsidian-Vault. Zurück aufs Gerät kommt die saubere Fassung, plus
Kalender und Erinnerungen.

Alles läuft lokal. Kein Audio verlässt das Haus.

Gebaut als Alltagshilfe, nicht als Produktivitätswerkzeug: Es muss an schlechten Tagen genauso
funktionieren wie an guten. Was daraus folgt, steht unter
[Wofür das gebaut ist](#wofür-das-gebaut-ist).

*Ein Stash ist der Vorrat, den man sich weglegt.*

**Status:** Showcase steht, Firmware und Brain liegen als lauffähiger Code vor. Die Pin-Nummern des
Boards stehen im öffentlichen Datenblatt zwar nicht, sind aber über Waveshares eigenen
Referenzcode für dieses Board bestätigt und als Vorgaben in der Firmware hinterlegt — was noch
fehlt, ist echte Hardware unter dem Code, um das zu verifizieren: siehe
[firmware/README.md](firmware/README.md). Der Brain-Teil läuft ohne Gerät,
[brain/README.md](brain/README.md) zeigt wie.

---

## Inhalt

- [Wofür das gebaut ist](#wofür-das-gebaut-ist)
- [Wenn etwas schiefgeht](#wenn-etwas-schiefgeht)
- [Systemüberblick](#systemüberblick)
- [Stückliste](#stückliste)
- [Showcase erzeugen](#showcase-erzeugen)
- [Repo-Struktur](#repo-struktur)
- [Bauen und betreiben](#bauen-und-betreiben)
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

## Wofür das gebaut ist

STASH ist kein Produktivitätswerkzeug. Es ist eine Alltagshilfe, und die Regeln weiter unten sind
deshalb keine Geschmacksfragen — sie folgen alle aus einer Anforderung: **Es muss an schlechten
Tagen genauso funktionieren wie an guten.** Konkret:

- **Zwischen Gedanke und Ablage darf nichts liegen.** Entsperren, App suchen, Ordner wählen,
  tippen — jeder dieser Schritte ist eine Stelle, an der die Notiz verloren geht. Deshalb ein
  eigenes Gerät, das nichts anderes kann, und ein Knopf statt einer Oberfläche.
- **Einsortieren ist Maschinenarbeit.** „In welche Liste gehört das?" ist genau die Frage, an der
  eine Notiz liegen bleibt. Sie wird nicht gestellt.
- **Man muss nicht druckreif sprechen.** Abschweifen, neu ansetzen, Details nachschieben — das
  fängt die bereinigte Fassung auf. Die rohe bleibt daneben stehen, damit nichts wegfällt.
- **Das Gerät fordert nichts.** Keine Benachrichtigung, kein rotes Fälligkeitszeichen, keine
  Serie, die reißen kann. Ein Werkzeug, an dem man scheitern kann, wird irgendwann gemieden — und
  fehlt genau dann, wenn es gebraucht wird. Dieses hier wartet.
- **Liegengebliebenes geht von selbst.** Eingeschlafene Projekte dürfen sich nicht zu einer Wand
  aus offenen Posten stapeln. Listen verblassen und bieten ihre Archivierung an.
- **Protokolliert wird, was war — nicht, wie es war.** Gemacht, gewesen, aufgefallen. Ein
  sachlicher Nachweis des Tages ist nützlich, eine Benotung des Tages ist es nicht.
- **Es bleibt im Haus.** Frei reden kann man nur in etwas, das nichts weitergibt.

Diese Punkte sind der Grund für das Gerät. Wer einen davon wegverhandelt, baut ein anderes.

## Wenn etwas schiefgeht

Ein Werkzeug, das im Normalfall gut ist und im Fehlerfall nervt, wird nicht benutzt. Deshalb steht
das Verhalten bei Ausfällen hier und nicht im Kleingedruckten — und deshalb landet jede Aufnahme
zuerst auf der SD-Karte, bevor irgendetwas anderes damit passiert: Ab da kann in der Tabelle unten
nichts mehr in der Spalte „was du tun musst" außer Warten oder gar nichts stehen.

| Was passiert | Was das Gerät macht | Was du tun musst |
|---|---|---|
| Pi ist aus | Aufnahme bleibt auf der Karte, stiller Wiederholversuch. Nach einem Netzintervall (30 s) zeichnet das Panel seine eigene Ausfallanzeige — siehe [Was ein echter Ausfall wirklich zeigt](#die-pipeline) | nichts |
| WLAN weg | dasselbe | nichts |
| Akku leer | das letzte Bild bleibt stehen und lesbar; im Leerlauf ist das die Sperrseite **Heute** | laden, wenn du drankommst |
| Transkription unsicher | Notiz landet trotzdem im Eingang, Rohtext erhalten, keine Zuordnung wird erzwungen | irgendwann draufschauen — oder auch nicht |
| Falsch einsortiert | nichts, es ist eine Zeile in einer Markdown-Datei | am Rechner verschieben |
| Pi-Dienst abgestürzt | Warteschlange läuft voll, wird nach Neustart abgearbeitet | Dienst neu starten |
| **SD-Karte voll** | **der einzige Fall mit einer echten Meldung auf dem Gerät** | alte Aufnahmen löschen |

Merksatz für alle Zweifelsfälle: **im Zweifel behalten, im Zweifel still.**

**Zur SD-Karte:** `audio.c` erkennt einen kurzen Schreibvorgang (die Karte hat keinen Platz mehr
für den nächsten Block) und beendet die Aufnahme dort, statt weiter gegen die volle Karte
anzuschreiben — der bis dahin geschriebene Teil bleibt eine gültige, kürzere Datei, auch wenn er
unter der sonstigen 0,6-Sekunden-Grenze läge. `panel.c` zeigt dafür „KARTE VOLL", mit einem eigenen,
auf diese zwei Wörter beschränkten Buchstabensatz — die einzige Wortmeldung, die das Gerät ohne den
Pi zeigt, weil es der einzige Fall ist, der wirklich etwas blockiert.

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

Diese Angaben stammen aus dem Datenblatt. Nichts davon erfinden oder ändern. Die Spalte *Quelle*
sagt, was dort wörtlich steht und was Annahme ist — was nicht bestätigt ist, darf nirgends als
Tatsache auftauchen:

| Komponente | Details | Quelle |
|---|---|---|
| SoC | ESP32-S3-WROOM-1-N16R8, 16 MB Flash, 8 MB PSRAM, 240 MHz | bestätigt |
| Display | E-Paper 800 × 480 — **hochkant benutzt: 480 breit × 800 hoch** | bestätigt |
| Farbtiefe | 1 Bit, schwarz/weiß | **angenommen** — das Datenblatt sagt nur „high contrast" |
| Audio ein | Mikrofon, ES8311 Codec → **das Gerät nimmt selbst auf** („voice capture") | bestätigt |
| Audio aus | NS4150B Verstärker, MX1.25 Lautsprecher-Anschluss | bestätigt, **bislang ungenutzt** |
| Speicher | TF-Karten-Slot (FAT32) → **hier liegt die Warteschlange** | bestätigt |
| Uhr | PCF85063 RTC, mit eigenem Stützakku-Anschluss | bestätigt |
| Sensoren | SHTC3 (Temperatur/Luftfeuchte), QMI8658 6-Achsen-IMU | bestätigt |
| Strom | AXP2101 Power-Management (I2C 0x34, eigener Ladungszähler), 3,7 V Li-Akku über MX1.25, USB-C | bestätigt — korrigiert, siehe unten |
| Bedienung | Drehknopf mit drei Richtungen, seitlich PWR und BOOT | bestätigt |
| Funk | 2,4 GHz WLAN (b/g/n), BLE 5 (LE) | bestätigt |

**Belegung.** Der Drehknopf blättert und öffnet: `◀ zurück · ● öffnen · ▶ weiter`. Das Aufnehmen
liegt auf der seitlichen BOOT-Taste und ist dadurch aus jeder Ansicht erreichbar, ohne vorher
irgendwohin navigieren zu müssen — genau das verlangt „Knopf drücken, drauflosreden, fertig".
PWR bleibt der Stromversorgung vorbehalten.

**Korrektur „TG28" → AXP2101.** Das öffentliche Datenblatt nennt den Power-Management-Chip nicht
beim Namen; „TG28" stand hier ohne Beleg. Waveshares eigenes Referenzprojekt für dieses Board
(github.com/waveshareteam/ESP32-S3-ePaper-3.97) benutzt durchgängig einen AXP2101 auf I2C-Adresse
0x34 — das ist jetzt die bestätigte Angabe. Der Chip hat einen eigenen Ladungszähler und legt den
Akkustand direkt als Prozentzahl in ein Register, ohne dass eine Kapazitätsangabe nötig wäre (siehe
Issue #14).

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
├─ LICENSE                MIT
├─ showcase/
│  └─ stash-showcase.html bedienbare Simulation, ein File, kein Build
├─ firmware/              ESP-IDF-Projekt für den ESP32-S3
│  ├─ README.md           Installation, Pinbelegung, Flashen
│  └─ main/               Aufnahme · SD-Warteschlange · Upload · Panel
├─ brain/                 die Dienste auf dem Pi 5
│  ├─ README.md           Installation, Konfiguration, systemd
│  ├─ stash/              Transkription · Aufräumen · Einsortieren · Vault · Renderer
│  └─ systemd/            Dienst und Nacht-Timer
└─ gehaeuse/              STL/STEP, noch leer
```

**Die Arbeitsteilung.** Das Gerät kann vier Dinge: aufnehmen, auf die Karte puffern, hochladen,
anzeigen. Es layoutet nichts und entscheidet nichts — der Pi schickt ein fertiges 1-Bit-Bild,
480 × 800. Umbruch, Verdichtung und die Frage, was auf die Seite passt, gehören dorthin, wo der
ganze Bestand liegt, nicht auf einen Mikrocontroller.

Übertragen wird beides über WLAN, in eine Richtung die Aufnahme, in die andere das Bild. Der
Systemüberblick nennt WLAN *oder* BLE; gebaut ist ein Weg, der beides trägt, statt zweier halber.
BLE bleibt für den Fall interessant, dass kein WLAN da ist, aber ein Telefon — das ist eine eigene
Ausbaustufe.

## Bauen und betreiben

Zwei Teile, zwei Anleitungen. Jede sagt nicht nur, was einzutippen ist, sondern was der Schritt
bewirkt — Anleitungen, die man nur abschreibt, helfen beim nächsten Fehler nicht.

| Teil | Anleitung | Kurz |
|---|---|---|
| Gerät | [firmware/README.md](firmware/README.md) | ESP-IDF v5.2, Pin-Vorgaben in `idf.py menuconfig` prüfen, dann `idf.py flash monitor` |
| Brain | [brain/README.md](brain/README.md) | `python3 -m venv .venv && pip install -e .`, Konfiguration nach `~/.config/stash/stash.toml`, `systemctl enable --now stash-brain` |

Der Brain-Teil braucht das Gerät nicht. Eine beliebige Sprachaufnahme reicht, um den ganzen Weg zu
sehen:

```bash
curl -F "datei=@probe.wav" http://pi5-brain.local:8080/v1/notiz
curl -o heute.png "http://pi5-brain.local:8080/v1/bild?ansicht=heute&format=png"
```

Das zweite Bild ist genau das, was auf dem E-Paper landet — nur als PNG statt als Bitstrom.

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
│   aufnehmen  │   [WLAN aus]             │                    │
│              │   [Serif / Sans]         │                    │
└──────────────┴──────────────────────────┴────────────────────┘
```

Unter 1100 px darf die rechte Spalte unter das Gerät rutschen. Der Screen bleibt 480 × 800.

## Die acht Geräte-Ansichten

Jede hat oben eine dünne Statusleiste (STASH · Warteschlangen-Zähler · WLAN · Akku · Uhrzeit,
Symbole als winzige Inline-SVGs, nicht Unicode) und unten eine Leiste mit der Drehknopf-Belegung
`◀ zurück   ● öffnen   ▶ weiter`.

1. **Heute** — Datum groß in Literata, darunter durch Linien getrennt: nächste Kalendertermine,
   fällige Erinnerungen mit Kästchen, Eingangs-Zähler mit Anriss der letzten Notiz, Tagebuch-Zähler.
   Nach dem Nachtlauf steht hier stattdessen dessen verdichtete Seite. **Heute ist zugleich die
   Sperrseite** — siehe unten.
2. **Eingang** — Liste der Aufnahmen von heute: Uhrzeit, Länge, erste Zeile der bereinigten Fassung,
   Schlagwort-Chips, Status (verarbeitet / in Warteschlange). Anklickbar → Ansicht 5.
3. **Listen** — der Kern. Drei Blöcke:
   - *fest*: `#einkauf`, `#tagebuch`, `#ideen`, `#termine` — die verschwinden nie
   - *gewachsen*: `#überdachung`, `#pv-anlage`, `#gehäuse` (mit „neu"-Markierung), `#obsidian`,
     jeweils mit Anzahl und Anlagedatum
   - *verblasst*: eine Liste ohne Einträge seit 63 Tagen, mit Vorschlag zum Archivieren —
     Eingeschlafenes soll von selbst gehen, statt sich als offener Posten anzusammeln
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
   nächster Versuch in N Sekunden, belegter SD-Speicher und Restreichweite in Stunden. Das ist
   das Bild, das der Pi liefert, **solange das Gerät ihn noch erreichen kann** — im Showcase also
   immer. Ist der Pi wirklich nicht erreichbar, zeigt das echte Gerät stattdessen eine eigene,
   gröbere Anzeige: siehe „Was ein echter Ausfall wirklich zeigt" weiter unten.

## Die Pipeline

Der Weg einer Aufnahme, und im Showcase das Herzstück. Entscheidend ist, was *nicht* passiert:
Es wird nie gefragt, wohin die Notiz gehört. Einsortiert wird ohne Rückfrage, und die Ansichten 4
und 5 machen hinterher nachvollziehbar, warum es so ausgefallen ist.

```
Mikrofon → SD-Puffer → Upload → Transkription → Aufräumen → Schlagwörter
                                                                  │
                              Panel ← Rendern ← Vault ← Einsortieren
```

Der zweite Schritt ist der wichtige: **erst auf die Karte, dann alles andere.** Ab da kann nichts
mehr verloren gehen, egal was danach ausfällt.

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
14:07:36.610  whisper  faster-whisper small int8 · 4,2 s · 25 Wörter · conf 0.94
14:07:37.240  clean    11 Füllwörter raus · Sätze normalisiert
14:07:37.980  keys     überdachung · material · bestellen
14:07:37.984  route    #überdachung · Score 1.00 · feste Liste
14:07:38.090  tasks    2 Aufgaben → Apple Erinnerungen (CalDAV)
14:07:38.310  vault    ~/Obsidian/stash/Listen/überdachung.md (+1)
14:07:38.520  render   1-bit 480×800 · 47 kB
14:07:38.728  push     BLE → ESP32-S3 · 533 ms
14:07:39.070  epd      Partial-Refresh 340 ms · Zähler 7/12
```

> Alle Zeitwerte sind geschätzt und stehen als benannte Konstanten oben im Script, mit Kommentar.
> Die Zahlen sind voneinander abgeleitet — Dateigröße aus der Dauer, Upload aus dem Durchsatz,
> Whisper aus dem Echtzeitfaktor, die Wortzahl aus dem Transkript — damit sie zueinander passen.
> Sie werden ersetzt, sobald Whisper das erste Mal echt auf dem Pi läuft.

**Sechs Demo-Aufnahmen**, die bei wiederholtem Drücken durchrotieren — jede zeigt einen anderen Fall:

| Aufnahme | Was sie zeigt |
|---|---|
| Material für die Überdachung | bestehende feste Zuordnung, zwei Aufgaben erkannt |
| Idee zum Gehäuse (zweiteilig drucken, Frontplatte magnetisch) | **kein Treffer über Schwelle 0.62 → neue Liste `#gehäuse` wird angelegt**, sichtbar im Log und auf dem Screen |
| Feierabend-Rückblick in Erzählform | erkannt als Tagebuch, wird an den heutigen Eintrag angehängt |
| Einkauf, drei Sachen | `#einkauf` |
| Termin mit Uhrzeit | Apple Erinnerung + `#termine` |
| **Genuschelt, Nebengeräusche, halber Satz** | **conf 0.58 — bleibt trotzdem im Eingang, Rohtext erhalten, keine Zuordnung erzwungen, keine Fehlermeldung.** Der Fall, an dem sich zeigt, ob das System einen im Stich lässt: „im Zweifel behalten, im Zweifel still" als Bild. |

Zusätzlich ein Schalter **„WLAN aus"**: dann wandert die Aufnahme in die Warteschlange statt
durchzulaufen, und die Warteschlangen-Ansicht füllt sich. Die Aufnahme startet trotzdem sofort, ohne
Hinweis und ohne Nachfrage. Beim Wiedereinschalten läuft der Stau von allein ab.

**Was ein echter Ausfall wirklich zeigt.** Der Showcase simuliert „WLAN aus" mit einer live
mitzählenden JavaScript-Anzeige (Sekunden, Nächster-Versuch-Countdown, volle Warteschlangen-Liste)
— das geht dort, weil er im Browser lokal zeichnet. Das echte Gerät zeichnet sonst nie lokal, jede
Ansicht kommt fertig vom Pi — und genau die Ansicht „der Pi ist nicht erreichbar" kann der Pi in
dem Moment nicht liefern, in dem sie stimmen würde.

Deshalb zeichnet die Firmware für diesen einen Fall doch selbst, mit derselben Technik wie beim
Aufnahme-Overlay (eigener kleiner Ziffernsatz, kein Layout vom Pi nötig): Bleibt der Pi länger als
ein Netzintervall (Vorgabe 30 s) nicht erreichbar, zeigt das Panel groß und mittig die Minuten, die
er schon nicht erreichbar ist, mit einem gestrichelten Balken oben als Zustandsmarkierung. Das ist
bewusst gröber als der Showcase: Minuten statt Sekunden, aktualisiert höchstens alle 30 Sekunden
statt jede Sekunde — ein Live-Countdown auf die Sekunde bräuchte einen Teilrefresh pro Sekunde, und
das widerspräche der ganzen E-Ink-Philosophie hier (jeder Refresh kostet, das Bild soll stehen
bleiben). Die volle Warteschlangen-Ansicht mit Liste, SD-Belegung und Restreichweite bleibt dem Pi
vorbehalten und erscheint erst wieder, sobald er zurück ist — genau wie im Showcase, nur eben nicht
während des Ausfalls selbst.

## E-Ink-Echtheit

Die Details, an denen es hängt:

- **Vollrefresh**: kurz komplett invertieren, zurück, dann Inhalt. ~2,4 s. Eigener Button.
- **Partial-Refresh**: nur der geänderte Bereich, ~340 ms, mit kurzem grauen Wisch.
- **Geisterbilder**: nach mehreren Partial-Refreshes ganz schwacher Rückstand des vorherigen
  Inhalts, und ein Zähler `Partial 7/12 → Vollrefresh fällig`. Nach dem Vollrefresh ist er weg.
- **„Gerät aus"**: Statusleiste und Fußleiste verschwinden, der Inhalt bleibt stehen, kleiner
  Hinweis unten. E-Paper hält das Bild ohne Strom — das ist der Witz an der Sache, zeig ihn.
- **Sperrseite**: Nach drei Minuten ohne Tastendruck fällt das Gerät von selbst auf **Heute**
  zurück, zeichnet einmal komplett durch und legt das Panel stromlos. Damit ist dieselbe
  Eigenschaft nicht nur vorgeführt, sondern benutzt: Das Gerät ist im Leerlauf kein dunkler
  Schirm und kein Standbild von irgendwas, sondern ein Aushang, den man im Vorbeigehen liest.
  Ruhend fällt die Fußleiste weg — 34 Pixel mehr Inhalt —, und aus der Uhrzeit wird `Stand 06:12`:
  Auf einem Bild, das stundenlang steht, ist „von wann ist das hier" die nützlichste Angabe, und
  ohne das Wort davor hielte man sie für eine laufende Uhr. Die Seite wird ruhend voller gesetzt
  als bedient — was nur angeschaut und nicht durchgeblättert wird, hat nur das, was draufsteht.
- Auswahl/Markierung immer als invertierter Block, nie als Farbfläche.
- Akku in Prozent. Die geschätzten Tage Restlaufzeit stehen noch aus (siehe Fahrplan, Punkt 6) —
  eine seriöse Schätzung braucht entweder eine bestätigte Akkukapazität, die in der Stückliste
  nicht steht, oder eine echte Laufzeitmessung an der Hardware. Beides zu erfinden wäre genau die
  Art Annahme, die die Stückliste bewusst ausschließt.

## Demo-Inhalte

Deutsch, alltäglich, glaubwürdig. Projekte, die vorkommen dürfen: eine Gartenüberdachung im
Selbstbau, eine PV-Anlage mit Datenauswertung, 3D-Druck fürs Gehäuse, Obsidian, Einkauf, Ideen,
Termine.

Die rohen Transkripte müssen wirklich roh klingen — Ähms, Selbstkorrekturen, halbe Sätze,
Nachschieben von Details. Man soll nicht druckreif sprechen müssen, um verstanden zu werden: Genau
das nimmt die bereinigte Fassung ab, und das Rohe bleibt trotzdem stehen, damit nichts wegfällt.
Der Kontrast zwischen beiden ist der Punkt, an dem der Showcase überzeugt oder nicht.

Tagebucheinträge bleiben sachlich und beiläufig: was gemacht wurde, wo man war, was aufgefallen ist.

## Nicht machen

- Keine Stimmungs- oder Befindlichkeitserfassung, keine Punktzahlen fürs Wohlbefinden,
  keine Selbstoptimierungs-Anzeigen. Die eigene Verfassung täglich zu benoten hilft nicht, es hält
  nur fest. Das Tagebuch protokolliert, was war — bewertet wird nichts.
- Nichts, was mahnt: keine Benachrichtigung, kein rotes Fälligkeitszeichen, keine Serie, keine
  Erledigungsquote, kein Rückstands-Zähler. Das Gerät wartet, es fordert nicht.
- **Keine Rückfrage beim Erfassen.** Keine Dialogbox, die wissen will, wohin etwas gehört, und
  nichts, was die Aufnahme verzögert oder verhindert — außer einer physisch vollen Karte.
- Keine Farbe, kein Akzentton, kein flaches Grau auf dem Panel.
- Keine Einblend-Animationen beim Scrollen, keine Hover-Effekte auf allem. Bewegung nur da, wo sie
  etwas erklärt: Aufnahme, Refresh, Pipeline.
- Keine Karten-Optik mit gleichen Rundungen und Schatten für alles.
- Keine Großbuchstaben-Labels über jedem Abschnitt.
- Keine erfundenen Hardware-Eigenschaften. Was in der Stückliste nicht steht, hat das Board nicht.
- Kein `localStorage` / `sessionStorage`. Zustand nur in JS-Variablen.

## Abnahme

Geprüft gegen `showcase/stash-showcase.html`, Stand Commit `5510b08` (per Playwright, headless
Chromium). Ein `[x]` heißt: automatisiert nachgefahren und bestanden, nicht nur gelesen.

- [x] `showcase/stash-showcase.html` öffnet sich per Doppelklick, keine Konsolenfehler
- [x] alle acht Ansichten sind erreichbar und gefüllt
- [x] „Sprachnotiz aufnehmen" läuft alle sechs Demo-Aufnahmen durch, sechs unterschiedliche
      Ergebnisse, keine Dopplung durch die Rotation
- [x] dabei wird einmal sichtbar eine neue Liste angelegt und einmal ins Tagebuch angehängt
- [x] „WLAN aus" füllt die Warteschlange, „WLAN an" arbeitet sie ab
- [x] Voll- und Partial-Refresh sehen unterschiedlich aus, der Geisterbild-Zähler zählt
- [x] „Gerät aus" lässt den Inhalt stehen
- [x] eine Suche nach Farbwerten im File findet nur unbunte Werte (Kanalspreizung ≤ 12) —
      gilt für die ganze Werkbank; auf dem Panel selbst kommen ohnehin nur `--paper`/`--ink`
      vor (Spreizung 0). Die Werkbank-Palette selbst reicht bis 11 (`--mute` liegt bei 10)
- [x] das Panel ist bei jeder Fensterbreite 480 × 800, nur skaliert
- [x] nirgends eine Mahnung, eine Serie, eine Quote oder eine Stimmungsabfrage
- [x] Notiz und Listen-Detail sind allein mit Drehknopf und BOOT-Taste erreichbar
- [x] die sechste Aufnahme (conf 0.58, „Bohrgeräusch") geht nicht verloren und erzeugt keine
      Fehlermeldung — erscheint im Eingang, `konf` korrekt bei 0.58
- [x] alle sechs Aufnahmen starten ohne messbare Verzögerung (<50 ms), auch bei „WLAN aus"
- [x] bei „WLAN aus" erscheint keine Warnung, kein Dialog, keine Nachfrage (`page.on('dialog')`
      blieb während der ganzen Sitzung leer)
- [x] Statusleiste und Drehknopf-Leiste sitzen in allen acht Ansichten an exakt derselben Stelle
      (Position/Größe pixelgenau verglichen, nicht nur optisch)

Diese Liste gilt für den Showcase. Firmware und Brain haben ihre eigenen offenen Punkte —
siehe die [GitHub Issues](https://github.com/xxbrunnenxx/STASH/issues).

**Hinweis an den Coding-Agent:** Wenn du fertig bist, öffne das File selbst und klick es durch.
Dann in zwei, drei Sätzen sagen, was konkret drinsteckt — nicht „fertig" schreiben, sondern was
gebaut wurde.

## Fahrplan

1. **Showcase** — bedienbare Simulation, um das Konzept vor dem Löten zu prüfen ✓
2. **Firmware** — Aufnahme über ES8311, Puffer auf SD, Übertragung, Panel-Ansteuerung ✓ geschrieben,
   Pinbelegung und Akkuauslesung (AXP2101) über Waveshares Referenzcode bestätigt, aber ungetestet
   auf echter Hardware; die Kommandofolgen des E-Paper-Controllers (`epd_sequenz.h`) sind als
   Referenz dokumentiert, aber noch nicht eingetragen — zwei offene Fragen (Moduswechsel
   Vollbild/Schnell, Drehrichtung) lassen sich nur am zusammengebauten Gerät klären
3. **Brain** — faster-whisper, Aufräumen, Schlagwortextraktion, Einsortieren, Vault-Schreiber,
   Renderer, Nachtlauf ✓ läuft ← *hier*
4. **CalDAV** — Apple Kalender und Erinnerungen in beide Richtungen · Lesen und Schreiben sind
   jetzt verkabelt (`server.py` ruft `caldav_sync.Kalender` tatsächlich auf, nicht nur programmiert
   und ungenutzt daneben), Fehlerfälle und der "nicht konfiguriert"-Zustand gegen einen echten
   (unerreichbaren) Server geprüft — gegen einen echten Apple-Account weiterhin ungeprüft
5. **Gehäuse** — zweiteilig gedruckt, magnetische Frontplatte, SD ohne Demontage erreichbar
6. **Feinschliff** — Akkulaufzeit messen, Refresh-Strategie und Weckintervalle optimieren

## Lizenz

**MIT.** Jeder darf den Code nutzen, verändern und weitergeben, auch kommerziell — der einzige
Anspruch ist, den Copyright-Hinweis in `LICENSE` stehen zu lassen. Das passt zu einem Projekt,
das andere nachbauen können sollen.
