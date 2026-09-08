// Aufnahme über das Bordmikrofon am ES8311. 16 kHz, mono, 16 Bit — das ist,
// was Whisper ohnehin verlangt; höher aufzunehmen kostet Karte und Upload,
// ohne ein Wort besser zu werden.
#pragma once
#include <stdbool.h>
#include "esp_err.h"

esp_err_t audio_init(void);

// Startet die Aufnahme in eine neue Datei der Warteschlange.
esp_err_t audio_start(void);

// Beendet sie, schreibt den WAV-Kopf fertig. Legt den Dateinamen in `datei` ab.
// Schreibt auch dann einen gültigen Kopf, wenn die Aufnahme durch eine volle
// Karte oder die Obergrenze AUDIO_MAX_S vorzeitig endete, statt an einer
// bereits gestoppten Aufnahme abzubrechen (siehe audio_karte_voll()).
esp_err_t audio_stop(char *datei, size_t len, float *sekunden);

// true, wenn die letzte Aufnahme wegen einer vollen Karte vorzeitig endete —
// einmalig abzufragen direkt nach audio_stop(), danach zurückgesetzt. Der
// bis dahin geschriebene Teil bleibt als gültige Datei erhalten.
bool audio_karte_voll(void);

bool  audio_laeuft(void);
float audio_sekunden(void);

// Grober Pegel der letzten Blöcke, 0..1 — für die Wellenform auf dem Panel.
float audio_pegel(void);
