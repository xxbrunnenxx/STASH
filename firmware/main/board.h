// Board-Belegung. Alle Werte kommen aus Kconfig (idf.py menuconfig), keiner
// steht hier fest verdrahtet: Im öffentlichen Datenblatt des Boards stehen
// keine Pin-Nummern (die Vorgaben in Kconfig.projbuild stammen stattdessen
// aus Waveshares eigenem Referenzcode für dieses Board). Für eine
// abweichende Revision oder einen eigenen Umbau bleibt menuconfig der Ort
// zum Überschreiben — geratene Pins wären schlimmer als gar keine: der
// Build liefe durch, das Gerät bliebe schwarz, und man suchte den Fehler in
// der Software.
#pragma once
#include <stdbool.h>
#include "sdkconfig.h"

#define STASH_VERSION "0.1.0"

// Panel: 800 x 480 hochkant benutzt.
#define PANEL_BREITE  480
#define PANEL_HOEHE   800
#define PANEL_BYTES   (PANEL_BREITE * PANEL_HOEHE / 8)   // 48000

// Aufnahme
#define AUDIO_RATE      16000
#define AUDIO_BITS      16
#define AUDIO_MAX_S     300      // harte Obergrenze, damit eine klemmende
                                 // Taste nicht die Karte vollschreibt

// Nach so vielen Teilbildern ist ein Vollrefresh fällig (Geisterbild).
#define PANEL_PARTIAL_MAX 12

// Prüft, ob alle Pins gesetzt sind. Gibt false zurück und schreibt die
// fehlenden auf die Konsole — ein Gerät, das nicht sagt was ihm fehlt,
// kostet einen Abend.
bool board_pins_vollstaendig(void);
