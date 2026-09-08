# Firmware — ESP32-S3-ePaper-3.97

Der Teil, der auf dem Gerät läuft. Er tut vier Dinge und sonst nichts:

1. **Aufnehmen.** Seitliche BOOT-Taste gedrückt halten → Mikrofon über den ES8311, 16 kHz mono,
   16 Bit. Loslassen beendet die Aufnahme.
2. **Puffern.** Die Aufnahme geht als WAV auf die SD-Karte, in `/sd/stash/q/`. Erst danach wird
   ein Upload versucht. Das ist der Grund, warum das Gerät ohne WLAN funktioniert: Die Karte ist
   die Warteschlange, nicht der Arbeitsspeicher.
3. **Übertragen.** Sobald `pi5-brain.local` erreichbar ist, wandert die älteste Datei per HTTP
   zum Brain und wird nach bestätigtem Empfang von der Karte gelöscht.
4. **Anzeigen.** Das Brain schickt kein JSON, das das Gerät layouten müsste, sondern ein fertiges
   1-Bit-Bild, 480 × 800. Das Gerät holt es ab und schiebt es aufs Panel. Alle Schriftarbeit
   passiert auf dem Pi.

Der Drehknopf blättert durch die acht Ansichten (`◀ zurück · ● öffnen · ▶ weiter`). Ein Blättern
ist nur eine Zahl, die ans Brain geht — das nächste Bild kommt fertig zurück.

---

## Was du brauchst

| | |
|---|---|
| Board | Waveshare ESP32-S3-ePaper-3.97 (SKU 33552 / 33810 / 33811) |
| Kabel | USB-C, **Datenkabel** — reine Ladekabel melden sich nicht am Rechner |
| SD-Karte | microSD, **FAT32** formatiert. 8 GB reichen für Monate |
| Rechner | Linux, macOS oder Windows mit ESP-IDF **v5.2 oder neuer** |
| Netz | 2,4-GHz-WLAN. Das Board kann kein 5 GHz |

---

## Schritt 1 — ESP-IDF installieren

ESP-IDF ist Espressifs Entwicklungsumgebung: Compiler-Toolchain für den Xtensa-Kern, die
FreeRTOS-Basis, die Treiber und das Build-System. Ohne sie lässt sich für den Chip nichts bauen.

```bash
sudo apt install -y git wget flex bison gperf python3 python3-venv \
                    python3-pip cmake ninja-build ccache libffi-dev libssl-dev dfu-util

mkdir -p ~/esp && cd ~/esp
git clone -b v5.2.2 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32s3
```

`install.sh` lädt die Toolchain und legt ein eigenes Python-Environment an — es fasst dein System-
Python nicht an. Danach in **jeder neuen Shell**:

```bash
. ~/esp/esp-idf/export.sh
```

Das setzt `IDF_PATH` und den Pfad zum Compiler. Vergisst man es, sagt `idf.py` „command not found" —
das ist dann kein Fehler im Projekt.

---

## Schritt 2 — Pinbelegung prüfen

Die Pin-Nummern stehen nicht im öffentlichen Datenblatt, aber in Waveshares eigenem
Referenzprojekt für genau dieses Board (github.com/waveshareteam/ESP32-S3-ePaper-3.97,
ESP-IDF-Beispiel 08). Von dort stammen die Vorgabewerte, die in `Kconfig.projbuild` bereits
eingetragen sind — E-Paper-SPI, SD-Karte (SDMMC, 4-Bit), I2C-Bus, Audio, Bedienung und der
AXP2101-Akkubaustein. Nichts davon ist mehr geraten.

Trotzdem lohnt der Blick in `idf.py menuconfig`, bevor du baust — falls deine Revision des Boards
abweicht, oder du einen Pin bewusst umbelegen willst:

```bash
cd firmware
idf.py set-target esp32s3
idf.py menuconfig
#   → STASH Board  → E-Paper, SD-Karte, I2C-Bus, Audio, Bedienung, Akku (AXP2101)
#   → STASH Netz   → WLAN-SSID, WLAN-Passwort, Brain-Adresse
```

`menuconfig` schreibt eine Datei `sdkconfig` neben das Projekt. Die ist maschinenspezifisch und
gehört **nicht** ins Repo — `.gitignore` hält sie draußen. Die Vorgaben für alle anderen tausend
Optionen stehen in `sdkconfig.defaults` und sind eingecheckt.

Ein Pin auf `-1` (nur noch bei „E-Paper PWR" als Vorgabe, weil das Panel auf dem Referenzboard
dauerhaft versorgt wird) heißt: nicht verdrahtet. Fehlt ein Pin, den die Firmware zwingend
braucht, startet sie **absichtlich nicht** weiter, sondern schreibt auf die serielle Konsole,
welcher Pin das ist. Ein Gerät, das nicht sagt, was ihm fehlt, kostet einen Abend.

WLAN-SSID, WLAN-Passwort und Brain-Adresse trägst du weiterhin selbst ein — die stehen aus gutem
Grund in keinem Referenzcode.

### Der E-Paper-Treiber

Der Controller-Baustein des 3,97"-Panels ist im Datenblatt nicht benannt. Deshalb sitzt zwischen
Firmware und Panel eine schmale Schicht — `main/panel_treiber.c` — mit genau fünf Funktionen:
initialisieren, Vollbild schreiben, Teilbild schreiben, schlafen legen, aufwecken. Wer Waveshares
Demo-Treiber hat, füllt die fünf Funktionen damit aus; alles darüber (Warteschlange,
Geisterbild-Zähler, Refresh-Strategie) bleibt unverändert. Die Datei sagt oben, was jede Funktion
liefern muss.

Welche Kommandobytes der Controller versteht, ist inzwischen aus Waveshares Referenzcode für
dieses Board bestätigt (SWRESET, Data-Entry-Mode, RAM-Fenster, drei Trigger-Varianten für
Vollbild/Schnell/Partial) — nachzulesen in den Kommentaren in `main/epd_sequenz.h`. Zwei Fragen
bleiben trotzdem offen, weil sie sich nur an echter Hardware beantworten lassen, nicht aus dem
Quellcode: ob und wie zwischen Vollbild- und Schnellmodus innerhalb einer Sitzung gewechselt
werden kann, und in welche Richtung der Bildpuffer gedreht werden muss (unser Puffer ist hochkant
480 × 800, das native RAM des Panels ist querformatig 800 × 480 — die Drehrichtung hängt vom
physischen Einbau ab).

### Der Akku (AXP2101)

Der Power-Management-Chip ist ein AXP2101 auf I2C-Adresse `0x34`, mit eigenem Ladungszähler
(„Fuel Gauge"): Der Chip berechnet den Akkustand selbst und legt ihn direkt als Prozentzahl in ein
Register — `main/akku.c` liest nur dieses eine Register. Bestätigt über Waveshares Referenzcode für
dieses Board (siehe Kommentar in `main/akku.h`); dort verwendet, nicht kopiert.

Unbestätigt bleibt, ob Register- und Bit-Semantik am echten Chip exakt wie dokumentiert reagieren
und ob I2C-Timing/Pull-ups auf dem gefertigten Board ohne Weiteres funktionieren — das lässt sich
nur an der Hardware selbst prüfen, nicht am Quellcode. Antwortet der Chip nicht, liefert
`akku_prozent()` `-1`, und das Gerät erfindet keinen Ersatzwert (siehe Issue #14).

### Das Offline-Overlay

Jede Ansicht kommt sonst fertig vom Pi — mit einer Ausnahme, die keine geben müsste, wenn sie
vermeidbar wäre: Ist der Pi wirklich nicht erreichbar, kann er auch nicht die Ansicht liefern, die
das anzeigen würde. `netz_task()` in `stash_main.c` misst deshalb selbst, seit wann der letzte
Versuch fehlschlägt, und `panel_offline()` in `panel.c` zeichnet ab einer vollen Netzintervall-Länge
(Vorgabe 30 s) die Minuten seit dem letzten Erfolg lokal aufs Panel — mit demselben kleinen
Ziffernsatz wie das Aufnahme-Overlay, kein Text vom Pi nötig. Aktualisiert wird höchstens im
Intervall des Netzversuchs, nicht jede Sekunde: Ein Live-Countdown auf die Sekunde bräuchte einen
Teilrefresh pro Sekunde, und das widerspräche der ganzen Refresh-sparenden Auslegung dieses Geräts.
Sobald der Pi wieder antwortet, holt sich das Gerät den echten Inhalt zurück (`panel_offline_ende()`)
— auch dann, wenn die Antwort ein `304 Not Modified` ist, weil sich der Pi-Inhalt seit dem Ausfall
gar nicht geändert hat (sonst bliebe das Overlay stehen, obwohl der Puffer längst wieder stimmt).

---

## Schritt 3 — Bauen und flashen

```bash
idf.py build                  # übersetzt; erstes Mal ~3 Minuten
idf.py -p /dev/ttyACM0 flash  # schreibt ins Flash des Boards
idf.py -p /dev/ttyACM0 monitor
```

Der Port heißt unter Linux meist `/dev/ttyACM0` oder `/dev/ttyUSB0`, unter macOS
`/dev/cu.usbmodem*`. `ls /dev/tty*` vor und nach dem Einstecken zeigt, welcher dazukam.

Fehlt die Berechtigung (`Permission denied`), einmalig:

```bash
sudo usermod -aG dialout $USER    # danach ab- und wieder anmelden
```

`monitor` verlassen: `Strg` + `]`.

Meldet sich das Board gar nicht: BOOT gedrückt halten, kurz PWR antippen, BOOT loslassen — das
zwingt den Chip in den Download-Modus. Danach nochmal flashen.

---

## Was beim ersten Start passiert

```
I stash      STASH Firmware 0.1.0 · ESP32-S3-WROOM-1-N16R8
I stash      Panel 480x800 · 1 Bit
I sd         /sd bereit · FAT32 · 29,8 GB frei · 0 Aufnahmen in der Warteschlange
I netz       verbinde mit <deine-ssid> …
I netz       verbunden · RSSI -54 dBm · pi5-brain.local erreichbar
I panel      Vollrefresh 2,4 s
```

Ohne WLAN steht dort stattdessen „nicht erreichbar · Aufnahmen bleiben auf der Karte", und das ist
kein Fehlerfall, sondern der Normalbetrieb unterwegs.

**Aufnehmen:** BOOT-Taste halten, sprechen, loslassen. Auf dem Panel läuft die Zeit mit. Danach
steht die Datei auf der Karte — nachprüfbar, indem man die Karte in den Rechner steckt:
`stash/q/0001.wav`.

---

## Was über die Leitung geht

Ein Weg, zwei Richtungen, beides HTTP:

| Wann | Was |
|---|---|
| Nach jeder Aufnahme | `POST /v1/notiz`, `multipart/form-data`, Feld `datei`, Inhalt die WAV. Gelöscht wird von der Karte **erst nach einer 200er-Antwort** — sonst wäre eine Notiz weg, weil das WLAN gewackelt hat. |
| Alle 30 s und nach jedem Tastendruck | `GET /v1/bild?akku=…&wartend=…&sd_mb=…&ruhe=…` mit `If-None-Match`. Kommt `304`, wird nicht gezeichnet. `akku` ist -1, wenn der AXP2101 nicht antwortet — der Pi behält dann seinen letzten bekannten Wert. |
| Bei Drehknopf | `POST /v1/bedienung`, `{"taste":"zurueck"\|"oeffnen"\|"weiter"}`. |

Der ETag ist nicht Feinschliff, sondern der Grund, warum das Gerät überhaupt regelmäßig fragen
darf: Jeder überflüssige Refresh kostet Strom und hinterlässt Geisterbild. Die vollständige
Beschreibung steht in [brain/README.md](../brain/README.md#die-schnittstelle).

## Wo was steht

| Datei | Zuständig für |
|---|---|
| `stash_main.c` | Der Ablauf: Tasten lesen, aufnehmen, Netz-Task anstoßen. |
| `board.h` / `board.c` | Maße, Grenzen, und die Prüfung, ob alle Pins gesetzt sind. |
| `audio.c` | ES8311 und I2S, WAV-Kopf, Pegel für die Wellenform. |
| `akku.c` | Akkustand über den AXP2101 (I2C), fertiges Prozent aus dem Fuel-Gauge-Register. |
| `sdkarte.c` | Die Warteschlange auf FAT32, über SDMMC im 4-Bit-Modus. Namen sind aufsteigend, damit alphabetisch = zeitlich. |
| `netz.c` | WLAN, mDNS, Upload, Bild holen, Tastendruck melden. |
| `panel.c` | Bildpuffer, Refresh-Strategie, Geisterbild-Zähler, Aufnahme- und Offline-Overlay. |
| `panel_treiber.c` | SPI, Reset, BUSY — alles, was **nicht** vom Controller-Typ abhängt. |
| `epd_sequenz.h` | Was vom Controller-Typ abhängt. Die eine Datei, die du füllen musst. |
| `bedienung.c` | Vier Taster, Entprellen, Aufwachen aus dem Light-Sleep. |
| `Kconfig.projbuild` | Alle 30 Einstellungen, die `idf.py menuconfig` zeigt. |

## Die Sperrseite

Nach `CONFIG_STASH_RUHE_NACH_S` Sekunden ohne Tastendruck (Vorgabe: 180) fällt das Gerät von selbst
auf **Heute** zurück, zeichnet einmal komplett durch und legt den Panel-Controller stromlos.

Das ist die wichtigste Eigenschaft der Hardware, und ohne diesen Schritt bliebe sie ungenutzt:
**E-Paper hält sein Bild ohne Strom.** Ein Gerät, das im Leerlauf stehen lässt, was zufällig zuletzt
offen war, ist zehn Stunden lang das Bild einer leeren Warteschlange. Eines, das zurückfällt, ist
zehn Stunden lang ein Aushang — man sieht ihn im Vorbeigehen, ohne etwas zu drücken, ohne
Benachrichtigung, ohne Wecken.

Drei Entscheidungen dahinter:

- **Vollrefresh beim Einschlafen, nicht beim Aufwachen.** Das Bild steht danach stundenlang, es
  soll das saubere sein. Und der Moment kostet nichts: Es sieht gerade niemand hin.
- **Die Fußleiste fällt weg.** `◀ zurück ● öffnen ▶ weiter` ist eine Anleitung für eine Bedienung,
  die gerade nicht stattfindet. Macht 34 Pixel für Inhalt frei.
- **Die Kopfleiste bleibt, die Uhr wird zum Stempel.** Auf einem stehenden Bild ist „von wann ist
  das hier" die nützlichste Information überhaupt. Damit man sie nicht für eine laufende Uhr hält,
  steht `Stand 06:12` da und nicht `06:12`.

Ob es ruht, weiß nur das Gerät — es zählt die Zeit seit dem letzten Tastendruck und schickt das als
`&ruhe=1` mit. Der Pi rät das nicht. Jeder Tastendruck beendet die Ruhe, auch der, mit dem eine
Aufnahme beginnt; der erste Druck weckt nur und blättert noch nicht.

Ändert sich der Inhalt, während das Gerät ruht, wird der Controller kurz geweckt, komplett neu
gezeichnet und wieder schlafen gelegt — nie ein Teilbild, weil das Ergebnis wieder stundenlang
stehen bleibt.

## Stromverbrauch

Zwischen zwei Bedienungen geht der Chip in Light-Sleep und wacht bei Tastendruck oder alle
`CONFIG_STASH_NETZ_INTERVALL_S` Sekunden (Vorgabe: 30) für den Netzcheck auf. Das Panel braucht dabei nichts — E-Paper hält sein Bild ohne Strom. Die
Laufzeit hängt fast nur daran, wie oft aufgenommen und wie oft neu gezeichnet wird.

Deep-Sleep ist bewusst nicht eingeschaltet: Der Aufwachvorgang dauert lang genug, dass der Anfang
eines Satzes verloren ginge. Ein Gerät, das die ersten zwei Sekunden verschluckt, benutzt man
nicht.

---

## Was hier noch nicht drin ist

- **BLE.** Der Systemüberblick nennt WLAN *oder* BLE. Gebaut ist WLAN — ein Weg, der auch das
  Bild überträgt, statt zweier halber. BLE wäre für den Fall interessant, dass kein WLAN da ist,
  aber ein Telefon; das ist eine eigene Ausbaustufe.
- **Lautsprecher.** Der NS4150B ist auf dem Board, wird aber nicht angesteuert. Es gibt nichts,
  das abzuspielen wäre.
- **IMU und SHTC3.** Ausgelesen, aber nur als Statuszeile. Eine Bewegungserkennung zum Wecken
  wäre möglich und ist nicht gebaut.
