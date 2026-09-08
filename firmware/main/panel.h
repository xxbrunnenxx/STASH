// Das Panel und die Refresh-Strategie. Alle Schriftarbeit passiert auf dem Pi;
// hier liegt nur der Bildpuffer, der Geisterbild-Zähler und das
// Aufnahme-Overlay, das keine Runde übers Netz warten kann.
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

esp_err_t panel_init(void);

// Bild vom Brain übernehmen und zeichnen. Nach PANEL_PARTIAL_MAX Teilbildern
// wird von selbst ein Vollrefresh daraus — sonst bleibt der Rückstand stehen.
esp_err_t panel_zeigen(const uint8_t *bild, bool voll_erzwingen);

int  panel_partial_zaehler(void);

// In die Ruhe gehen: einmal sauber durchzeichnen, dann das Panel stromlos
// machen. Der Vollrefresh kostet hier nichts — es sieht gerade niemand hin,
// und danach steht das Bild stundenlang.
esp_err_t panel_ruhen(const uint8_t *bild);
void panel_schlafen(void);

// Während der Aufnahme: laufende Zeit und Pegel, ohne Netz.
void panel_aufnahme(float sekunden, float pegel);
void panel_aufnahme_ende(void);

uint8_t *panel_puffer(void);
