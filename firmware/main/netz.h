// WLAN und die Verbindung zum Brain. Ein einziger Weg für beide Richtungen:
// Aufnahme hoch, fertiges Bild zurück. Kein zweiter halber Kanal.
#pragma once
#include <stdbool.h>
#include "esp_err.h"

esp_err_t netz_init(void);
bool      netz_verbunden(void);
int       netz_rssi(void);

// Lädt eine WAV-Datei hoch. Bei ESP_OK darf sie von der Karte gelöscht werden —
// vorher nicht, sonst ist die Notiz weg, weil das WLAN gewackelt hat.
esp_err_t netz_hochladen(const char *pfad);

// Holt das Panelbild. `neu` sagt, ob sich seit dem letzten Mal etwas geändert
// hat — unverändert heißt: nicht zeichnen. Jeder Refresh kostet Strom und
// hinterlässt Geisterbild.
//
// `akku`, `wartend` und `sd_mb` gehen mit: Was nur das Gerät weiß, sagt das
// Gerät — der Pi rät weder den Akkustand noch, wie viel noch auf der Karte
// liegt. `akku` ist -1, wenn der AXP2101 nicht antwortet; der Pi behält dann
// seinen letzten bekannten Wert.
esp_err_t netz_bild_holen(unsigned char *puffer, bool *neu, int akku, int wartend,
                          int sd_mb, bool ruhe);

// „zurueck" · „oeffnen" · „weiter" — das Brain entscheidet, was daraus wird.
esp_err_t netz_bedienung(const char *was);
