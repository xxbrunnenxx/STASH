# Brain — Raspberry Pi 5

Der Teil, der denkt. Das Gerät nimmt auf und zeigt an; alles dazwischen passiert hier, im Haus,
ohne Netz nach außen.

Zwei Dienste:

**`stash-brain`** läuft ständig und arbeitet jede eingehende Aufnahme ab:

```
WAV rein → Transkription → Aufräumen → Schlagwörter → Einsortieren → Vault → Bild → ans Gerät
```

**`stash-nachtlauf`** läuft einmal nachts und sieht zum ersten Mal alles auf einmal. Tagsüber
entscheidet die billige Regel je Notiz und kennt nur diese eine; nachts liegen alle Listen
nebeneinander. Das ist der Unterschied zwischen *abgelegt* und *aufgeräumt*:

- Listen, die dasselbe meinen, werden zusammengelegt
- der Tag wird zu Absätzen verdichtet, aus denen morgens die Seite besteht
- offene Fragen von gestern, die heute beantwortet wurden, werden geschlossen
- Listen, aus denen seit 60 Tagen nichts mehr kam, bieten ihre Archivierung an

Danach ist die Morgenseite fertig, bevor jemand aufsteht.

---

## Was du brauchst

| | |
|---|---|
| Rechner | Raspberry Pi 5, 8 oder 16 GB RAM, SSD über NVMe |
| System | Raspberry Pi OS **Bookworm 64-Bit** (`aarch64`) |
| Platz | ~4 GB für Modelle, dazu der Vault |
| Netz | fest im Heimnetz, per `.local` erreichbar |

Warum SSD: faster-whisper lädt sein Modell beim Start von der Platte. Auf einer SD-Karte dauert
das eine gefühlte Ewigkeit und nutzt sie ab.

---

## Schritt 1 — System vorbereiten

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git ffmpeg libsndfile1 \
                    fonts-dejavu-core avahi-daemon
```

Was das ist:

- **ffmpeg / libsndfile** — liest und resampelt die WAV-Dateien vom Gerät.
- **avahi-daemon** — sorgt dafür, dass der Pi im Heimnetz als `pi5-brain.local` gefunden wird,
  ohne feste IP. Das Gerät sucht genau diesen Namen.
- **fonts-dejavu-core** — Notschrift für den Renderer, falls die richtigen Schriften fehlen.

Der Rechner sollte auch so heißen:

```bash
sudo hostnamectl set-hostname pi5-brain
```

### Schriften (empfohlen, nicht zwingend)

Das Panel liest sich mit Literata deutlich besser als mit DejaVu. Beide Familien sind frei:

```bash
mkdir -p ~/.local/share/fonts && cd ~/.local/share/fonts
# Literata und IBM Plex von Google Fonts bzw. github.com/IBM/plex herunterladen,
# die .ttf-Dateien hier ablegen, dann:
fc-cache -f
```

Fehlen sie, rendert STASH mit DejaVu weiter und schreibt einmal eine Zeile ins Log. Es bricht
nichts ab.

---

## Schritt 2 — STASH installieren

```bash
git clone https://github.com/xxbrunnenxx/stash.git ~/stash
cd ~/stash/brain
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Das `venv` ist eine abgeschottete Python-Umgebung. Ohne sie mischen sich die Pakete mit denen des
Systems, und ein `apt upgrade` kann dir den Dienst zerlegen. `pip install -e .` installiert STASH
so, dass Änderungen am Code sofort wirken — kein erneutes Installieren nach jeder Zeile.

Gezogen werden dabei: `faster-whisper`, `fastapi`, `uvicorn`, `pillow`, `httpx`, `caldav`.

---

## Schritt 3 — Konfigurieren

```bash
mkdir -p ~/.config/stash
cp beispiel.toml ~/.config/stash/stash.toml
nano ~/.config/stash/stash.toml
```

Die Datei ist kurz und jede Zeile darin ist eine Entscheidung. Vollständig — mehr Schalter gibt es
nicht, und was hier nicht steht, gilt in der Vorgabe:

| Schlüssel | Vorgabe | Was er entscheidet |
|---|---|---|
| `vault.pfad` | `~/Obsidian/stash` | Wohin die Markdown-Dateien geschrieben werden. |
| `whisper.modell` | `small` | `tiny` · `base` · `small` · `medium`. Reicht `small` nicht, ist `base` der Schritt nach unten — nicht `medium` nach oben. |
| `whisper.rechentyp` | `int8` | Auf dem Pi 5 die einzig brauchbare Wahl. Mit `float32` rechnet er minutenlang. |
| `whisper.sprache` | `de` | Feste Sprache statt Erkennung: Das spart eine Runde und verhindert, dass ein genuscheltes „ähm" als Englisch durchgeht. |
| `llm.endpunkt` | `http://localhost:11434/v1` | Nur für den Nachtlauf. Jeder Server mit OpenAI-Schnittstelle: llama.cpp `--server`, Ollama, vLLM. |
| `llm.modell` | `google/gemma-4-e2b` | Der Modellname, den dein Server erwartet. |
| `llm.zeitlimit_s` | `900` | Wie lange eine einzelne Anfrage dauern darf. Großzügig, weil nachts niemand wartet — und weil ein Abbruch bei Minute vier den Morgen kostet. |
| `einsortieren.schwelle` | `0.62` | Darunter entsteht eine neue Liste. |
| `einsortieren.archiv_ab_tage` | `60` | Ab wann eine stille Liste ihre Archivierung anbietet. |
| `audio.aufbewahrung_tage` | `30` | Danach wird die WAV gelöscht, das Transkript bleibt. |
| `server.adresse` | `0.0.0.0` | Auf welchen Netzwerkkarten gehört wird. `127.0.0.1` sperrt das Gerät aus. |
| `server.port` | `8080` | Muss mit `STASH_BRAIN_PORT` in der Firmware übereinstimmen. |
| `caldav.url` | leer | Leer heißt: kein Kalender, kein Fehler. Siehe unten. |
| `caldav.benutzer` | leer | Bei Apple die Apple-ID. |
| `caldav.passwort` | leer | Bei Apple ein **app-spezifisches Passwort**, nicht das Kontopasswort. |

**Zur Schwelle 0.62:** Sie entscheidet, ob eine Notiz in eine bestehende Liste wandert oder eine
neue anlegt. Höher heißt mehr neue Listen, niedriger heißt, dass Fremdes zusammengeworfen wird.
Sie tagsüber „richtig" einzustellen ist aussichtslos — sie darf grob sein, weil nachts sortiert
wird. Genau dafür ist der Nachtlauf da.

### Das Modell für den Nachtlauf

Der Tagbetrieb braucht kein Sprachmodell; er braucht Whisper. Der Nachtlauf braucht eines, und
STASH bringt keines mit — es spricht mit dem, das du auf dem Pi laufen hast. Prüfen, ob es
antwortet:

```bash
curl -s http://localhost:11434/v1/models
```

Kommt nichts zurück, läuft der Nachtlauf trotzdem: Er legt dann Listen mit gemeinsamen
Trigger-Wörtern zusammen und verdichtet nicht. Das ist die Hälfte des Nutzens, aber es fällt
nichts aus.

### Kalender und Erinnerungen (optional)

Bleibt `caldav.url` leer, passiert nichts — STASH läuft ohne. Ein Dienst, der ohne Cloud-Zugang
nicht startet, wäre das Gegenteil von „es bleibt im Haus".

Für Apple:

```toml
[caldav]
url      = "https://caldav.icloud.com"
benutzer = "deine@apple-id.de"
passwort = "abcd-efgh-ijkl-mnop"     # appleid.apple.com → app-spezifisches Passwort
```

Gelesen wird die laufende Woche für die Kalenderansicht. Geschrieben werden erkannte Aufgaben als
Erinnerung. Der Schreibweg ist angelegt, aber nicht gegen einen echten Apple-Account geprüft —
wenn er klemmt, steht der Grund in `journalctl -u stash-brain`, und der Rest läuft weiter.

---

## Schritt 4 — Starten

Zum Ausprobieren im Vordergrund:

```bash
stash-brain
# → Uvicorn running on http://0.0.0.0:8080
```

Als Dienst, damit er den Neustart überlebt:

```bash
sudo cp ~/stash/brain/systemd/stash-*.service ~/stash/brain/systemd/stash-*.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stash-brain.service
sudo systemctl enable --now stash-nachtlauf.timer
```

- `enable` heißt: startet beim Booten mit.
- `--now` heißt: und jetzt sofort.
- Der **Timer** feuert den Nachtlauf um 03:00. `systemctl list-timers stash-*` zeigt, wann das
  nächste Mal.

Nachsehen, was er tut:

```bash
journalctl -u stash-brain -f          # laufend mitlesen
journalctl -u stash-nachtlauf -n 50   # letzter Nachtlauf
```

Beim allerersten Start lädt faster-whisper sein Modell herunter (`small` ≈ 480 MB). Das dauert
einmalig ein paar Minuten und passiert danach nie wieder.

---

## Prüfen, ob es geht — ohne Gerät

Der Dienst braucht den ESP32 nicht. Eine beliebige Sprachaufnahme reicht:

```bash
curl -F "datei=@probe.wav" http://pi5-brain.local:8080/v1/notiz
```

Zurück kommt, was das Gerät auch bekäme:

```json
{
  "nr": 17,
  "roh": "Ähm, also für die Überdachung, ich brauch noch, warte, vier Pfosten …",
  "rein": "Für die Überdachung fehlen vier Pfosten 9 × 9 cm in 4 m Länge und acht verzinkte Winkel.",
  "schlagworte": ["überdachung", "material", "bestellen"],
  "ziel": "überdachung",
  "score": 0.93,
  "grund": "Trigger-Wort „pfosten\" trifft, „überdachung\" bestätigt",
  "aufgaben": ["Pfosten 9 × 9 und Winkel bestellen"],
  "datei": "~/Obsidian/stash/Listen/überdachung.md"
}
```

Und das gerenderte Panelbild ansehen:

```bash
curl -o heute.png "http://pi5-brain.local:8080/v1/bild?ansicht=heute&format=png"
```

Das ist dasselbe Bild, das auf dem E-Paper landet — nur als PNG statt als Bitstrom. Wenn es hier
gut aussieht, sieht es auf dem Gerät gut aus.

---

## Die Schnittstelle

Das ist die einzige Stelle, an der Gerät und Brain aneinanderhängen. Wer einen der beiden Teile
anfasst, muss diese Tabelle kennen.

| Weg | Was |
|---|---|
| `POST /v1/notiz` | WAV rein, verarbeitete Notiz zurück |
| `GET /v1/bild` | Panelbild, 480 × 800, 1 Bit, 48000 Byte |
| `GET /v1/zustand` | Akku, Warteschlange, Listenzähler — als JSON, zum Nachsehen |
| `POST /v1/bedienung` | Drehknopf: `zurueck` · `oeffnen` · `weiter` |
| `POST /v1/nachtlauf` | Nachtlauf sofort auslösen, statt auf 03:00 zu warten |

**`POST /v1/notiz`** nimmt eine `multipart/form-data`-Anfrage mit dem Feld **`datei`** entgegen,
Inhalt eine WAV, 16 kHz mono 16 Bit. Der Dienst antwortet erst, wenn die Aufnahme im Vault steht —
und das Gerät löscht sie erst nach einer 200er-Antwort von der Karte. Ginge es andersherum, wäre
eine Notiz weg, weil das WLAN im falschen Moment gewackelt hat.

**`GET /v1/bild`** kennt sechs Parameter:

| Parameter | Wer setzt ihn | Wofür |
|---|---|---|
| `ansicht` | Werkbank / Neugier | Eine bestimmte der acht Ansichten rendern, statt der aktuellen. |
| `format=png` | Mensch | PNG statt Bitstrom — dasselbe Bild, nur ansehbar. |
| `akku` | Gerät | Akkustand in Prozent. |
| `wartend` | Gerät | Wie viele Aufnahmen noch auf der Karte liegen. |
| `sd_mb` | Gerät | Wie voll die Karte ist. |
| `ruhe=1` | Gerät | Das Gerät wird gerade nicht bedient — die Seite wird als Sperrseite gesetzt. |

`akku`, `wartend` und `sd_mb` kommen vom Gerät, weil nur das Gerät sie kennt. Der Pi rät das nicht.
(Stand heute schickt die Firmware `akku` noch nicht mit — siehe #14, solange bleibt der Wert auf
der Vorgabe 100 stehen.)

**Der ETag ist der Kern des Ganzen.** Jede Antwort trägt einen `ETag` über den Bildinhalt. Das
Gerät schickt ihn beim nächsten Mal als `If-None-Match` mit und bekommt `304 Not Modified`, wenn
sich nichts geändert hat. Dann zeichnet es nicht.

Das ist keine Optimierung, sondern der Grund, warum das Gerät regelmäßig fragen darf: Jeder
überflüssige Refresh kostet Strom und hinterlässt Geisterbild. Ein Gerät, das jede Minute stur neu
zeichnet, müsste man ständig laden und hätte trotzdem ein schlechteres Bild.

```
Gerät                                  Brain
  │  GET /v1/bild?wartend=3&sd_mb=412    │
  │─────────────────────────────────────►│
  │  200 · 48000 Byte · ETag "8e2abf…"   │
  │◄─────────────────────────────────────│   → zeichnen
  │                                      │
  │  GET … · If-None-Match: "8e2abf…"    │
  │─────────────────────────────────────►│
  │  304 · leer                          │
  │◄─────────────────────────────────────│   → nichts tun
```

Die 48000 Byte sind 1 Bit je Pixel, zeilenweise, 60 Byte je Zeile, `0` = schwarz — genau das
Format, das der Panel-Controller erwartet. Es wird nichts umgerechnet.

Der Dienst hört auf dem Heimnetz und hat **keine Anmeldung**. Das ist Absicht und zugleich die
Bedingung: Er gehört nicht ins Internet. Kein Port-Forwarding, keine Freigabe im Router. Wer von
außen drankommen will, nimmt ein VPN ins eigene Netz.

---

## Die Sperrseite

Mit `ruhe=1` liefert `/v1/bild` dieselbe Seite in ihrer ruhenden Form. Drei Unterschiede, und alle
drei folgen daraus, dass dieses Bild stundenlang stehen wird:

- **Immer „Heute".** Ruhend gibt es keine acht Ansichten. Was das Gerät den halben Tag zeigt, soll
  das sein, was man sehen will, nicht das, was zufällig zuletzt offen war.
- **Keine Fußleiste.** Das sind 34 Pixel mehr für Inhalt.
- **Die Uhrzeit wird zum Stempel:** `Stand 06:12` statt `06:12`.

Und sie wird **voller gesetzt** als die bediente Fassung. Das ist kein Geschmack, sondern folgt aus
der Nutzung: Eine Seite, die durchgeblättert wird, darf Luft haben — man holt sich das Nächste
selbst. Eine Seite, die nur angeschaut wird, hat nur das, was draufsteht. Also: die verdichteten
Absätze des Nachtlaufs, darunter „Zu tun" und „Diese Woche" nebeneinander statt untereinander,
was seit gestern geklärt wurde, und der verbleibende Platz gefüllt mit dem Zuletztgesagten. Ganz
unten, als Abbinder, zwei Zeilen: wie viel im Tagebuch steht und wie viele Aufnahmen durch sind.

Der Abbinder ist eine Feststellung, kein Zähler. Kein Rückstand, keine Quote, keine Serie — die
Seite sagt, was ist, und verlangt nichts.

Ansehen kann man sie wie jede andere:

```bash
curl -o sperrseite.png "http://pi5-brain.local:8080/v1/bild?ruhe=1&format=png"
```

## Was im Vault landet

```
~/Obsidian/stash/
├─ Listen/
│  ├─ überdachung.md
│  ├─ pv-anlage.md
│  └─ einkauf.md
├─ Tagebuch/
│  └─ 2026-09-07.md
├─ Notizen/
│  └─ 2026-09-07-1418-überdachung.md    ← roh und bereinigt, nebeneinander
└─ .stash/
   ├─ listen.json                        ← Trigger-Wörter, Zähler, Anlagedatum
   └─ audio/                             ← WAVs, nach 30 Tagen gelöscht
```

Reines Markdown. Kein Datenbankformat, keine Sonderdateien, die nur STASH lesen kann. Das ist
kein Zufall: Wenn dieses Projekt eines Tages nicht mehr läuft, liegen die Notizen trotzdem noch
lesbar da. Der Vault ist das Ergebnis, STASH nur der Weg dahin.

Die Audiodateien werden nach 30 Tagen automatisch gelöscht. Das Transkript bleibt.

---

## Wenn etwas klemmt

**Das Gerät findet den Pi nicht.** `ping pi5-brain.local` vom Rechner aus. Antwortet nichts, fehlt
Avahi oder der Hostname stimmt nicht. Notfalls im Gerät (`idf.py menuconfig`) die feste IP
eintragen statt des Namens.

**Whisper ist quälend langsam.** `rechentyp = "int8"` prüfen. Mit `float32` rechnet der Pi bei
jeder Aufnahme minutenlang. Reicht `small` nicht, ist `base` der nächste Schritt nach unten —
nicht `medium` nach oben.

**Der Nachtlauf lief, aber nichts hat sich geändert.** `journalctl -u stash-nachtlauf` ansehen.
Steht dort „kein LLM erreichbar", lief nur das Zusammenlegen. Das ist der Normalfall, wenn der
Modellserver nachts nicht läuft.

**Alles neu.** Der Vault überlebt jedes Zurücksetzen — dort steht nichts, was STASH nicht auch
wieder einlesen könnte:

```bash
sudo systemctl stop stash-brain
rm ~/Obsidian/stash/.stash/listen.json
sudo systemctl start stash-brain
```

---

## Wo was steht

Jede Datei sagt oben selbst, wofür sie da ist. Diese Karte sagt, welche man aufmacht:

| Datei | Zuständig für |
|---|---|
| `einstellungen.py` | Die Konfiguration oben. Vorgaben stehen hier, nicht in der TOML. |
| `transkript.py` | faster-whisper. Modell wird einmal geladen und bleibt im Speicher. |
| `aufraeumen.py` | Füllwörter raus, Sätze normalisieren. Regelbasiert, ohne Modell. |
| `schlagworte.py` | Die drei Wörter, an denen einsortiert wird. |
| `einsortieren.py` | Die Regel mit der Schwelle. Wohin die Notiz gehört, ohne Rückfrage. |
| `vault.py` | Markdown schreiben und den Listenindex führen. |
| `rendern.py` | Zeichenwerkzeug fürs Panel: Linien, Raster, Umbruch, Schriften. |
| `seiten.py` | Die acht Ansichten. Hier ändert man, was auf einer Seite steht. |
| `zustand.py` | Was gerade gezeigt wird und was der Drehknopf daraus macht. |
| `llm.py` | Der Draht zum Sprachmodell, samt der Aufträge, die es bekommt. |
| `nachtlauf.py` | Zusammenlegen, umbenennen, verdichten, verblassen lassen. |
| `server.py` | Die Schnittstelle oben. Bindet alles zusammen. |
| `caldav_sync.py` | Kalender lesen, Erinnerungen schreiben. Optional. |

Zwei Dinge lohnen sich zu wissen, bevor man etwas ändert:

- **Der Vault ist die Wahrheit, nicht `listen.json`.** Der Index unter `.stash/` ist jederzeit
  wegwerfbar — die Einträge einer Liste liest `server.py` aus dem Markdown selbst, damit beides
  nicht auseinanderlaufen kann.
- **Die Schwelle 0.62 darf grob sein.** Sie tagsüber „richtig" einzustellen ist aussichtslos: Bei
  drei Schlagwörtern gibt es nur 0 · 0,33 · 0,67 · 1,00, dazwischen ändert sie nichts. Dafür gibt
  es den Nachtlauf.
