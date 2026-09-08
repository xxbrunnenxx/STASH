// Das Panel und die Refresh-Strategie. Alle Schriftarbeit passiert auf dem Pi;
// hier liegen nur der Bildpuffer, der Geisterbild-Zähler und zwei Overlays,
// die beide keine Runde übers Netz abwarten können: das Aufnahme-Overlay
// (die Runde wäre zu langsam) und das Offline-Overlay (die Runde ist in dem
// Moment schlicht nicht möglich).
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

// Wenn der Pi wirklich nicht erreichbar ist (nicht nur ein einzelner
// Fehlversuch): Minuten seit dem letzten erreichten Pi, lokal gezeichnet.
// `frisch` an panel_offline_ende(): true, wenn gerade ein neues Bild vom Pi
// im Puffer liegt (nur Zustand zurücksetzen); false bei „unverändert" laut
// ETag (dann den Inhalt von vor dem Overlay zurückholen, sonst bliebe das
// Overlay auf dem Schirm stehen, obwohl der Puffer wieder stimmt).
void panel_offline(int sekunden_offline);
void panel_offline_ende(bool frisch);

uint8_t *panel_puffer(void);
