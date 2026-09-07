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

Die Datei ist kurz und jede Zeile darin ist eine Entscheidung:

```toml
[vault]
pfad = "/home/pi/Obsidian/stash"     # wohin die Markdown-Dateien geschrieben werden

[whisper]
modell     = "small"                 # tiny · base · small · medium
rechentyp  = "int8"                  # int8 ist auf dem Pi 5 die brauchbare Wahl
sprache    = "de"

[llm]
# Für den Nachtlauf. Jeder Server, der die OpenAI-Schnittstelle spricht:
# llama.cpp --server, Ollama, vLLM. Nur nachts belastet, nicht im Tagbetrieb.
endpunkt = "http://localhost:11434/v1"
modell   = "google/gemma-4-e2b"

[einsortieren]
schwelle       = 0.62                # darunter entsteht eine neue Liste
archiv_ab_tage = 60                  # ab wann eine stille Liste ihre Archivierung anbietet
```

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

| Weg | Was |
|---|---|
| `POST /v1/notiz` | WAV rein, verarbeitete Notiz zurück |
| `GET /v1/bild?ansicht=…` | Panelbild, 480 × 800, 1 Bit, 48000 Byte |
| `GET /v1/zustand` | Akku, Warteschlange, Listenzähler — was in die Statusleiste gehört |
| `POST /v1/bedienung` | Drehknopf: `zurueck` · `oeffnen` · `weiter` |
| `POST /v1/nachtlauf` | Nachtlauf sofort auslösen, statt auf 03:00 zu warten |

Der Dienst hört auf dem Heimnetz und hat **keine Anmeldung**. Das ist Absicht und zugleich die
Bedingung: Er gehört nicht ins Internet. Kein Port-Forwarding, keine Freigabe im Router. Wer von
außen drankommen will, nimmt ein VPN ins eigene Netz.

---

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
