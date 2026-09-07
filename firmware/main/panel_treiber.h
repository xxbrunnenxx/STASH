// Die schmale Schicht zum Panel. Fünf Funktionen, mehr braucht die Firmware
// vom Display nicht.
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

esp_err_t epd_init(void);

// Bildpuffer: 1 Bit je Pixel, 0 = schwarz, zeilenweise, 60 Byte je Zeile.
esp_err_t epd_vollbild(const uint8_t *puffer);
esp_err_t epd_teilbild(const uint8_t *puffer);

esp_err_t epd_schlafen(void);
esp_err_t epd_wecken(void);

// false, wenn die Sequenzen in epd_sequenz.h noch nicht eingetragen sind.
bool epd_bereit(void);
