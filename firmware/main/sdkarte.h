// Die SD-Karte ist die Warteschlange, nicht ein Zwischenspeicher. Eine Aufnahme
// ist erst dann sicher, wenn sie hier liegt — der Upload kommt danach und darf
// beliebig lange scheitern.
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#define SD_WURZEL "/sd"
#define SD_QUEUE  "/sd/stash/q"

esp_err_t sd_montieren(void);

// Nächster freier Dateiname in der Warteschlange, z. B. /sd/stash/q/0007.wav
void sd_naechster_name(char *aus, size_t len);

// Ältester Eintrag der Warteschlange. false, wenn nichts wartet.
bool sd_aeltester(char *aus, size_t len);

int      sd_warteschlange_anzahl(void);
uint64_t sd_frei_bytes(void);
