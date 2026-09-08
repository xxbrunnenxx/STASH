// Akkustand über den AXP2101 (I2C 0x34). Der Chip hat eine eigene
// Ladungszähler-Logik ("fuel gauge") und legt das Ergebnis direkt als
// Prozentzahl in ein Register — keine Kapazitätsangabe nötig, die wir nicht
// hätten, und keine Spannungskurve, die wir raten müssten.
//
// Woher die Registeradressen stammen: Waveshares eigener Referenzcode für
// dieses Board (waveshareteam/ESP32-S3-ePaper-3.97, ESP-IDF-Beispiel 08,
// components/axpPower), der auf die MIT-lizenzierte XPowersLib zurückgreift.
// Diese Datei ist keine Kopie dieser Bibliothek — nur die drei Registeradressen
// sind übernommen, der Code hier ist neu geschrieben und beschränkt sich auf
// das eine Register, das wir brauchen.
#pragma once
#include <stdbool.h>
#include "esp_err.h"

// Muss laufen, nachdem der I2C-Bus steht (audio_init() richtet ihn ein) —
// der AXP2101 hängt am selben Bus wie der ES8311, die RTC und der SHTC3.
esp_err_t akku_init(void);

// Prozent 0..100, oder -1 wenn kein Akku angeschlossen ist bzw. der Chip
// nicht antwortet. Wird nie erfunden — im Zweifel bleibt der Wert unbekannt.
int akku_prozent(void);
