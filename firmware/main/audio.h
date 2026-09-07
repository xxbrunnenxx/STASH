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
esp_err_t audio_stop(char *datei, size_t len, float *sekunden);

bool  audio_laeuft(void);
float audio_sekunden(void);

// Grober Pegel der letzten Blöcke, 0..1 — für die Wellenform auf dem Panel.
float audio_pegel(void);
