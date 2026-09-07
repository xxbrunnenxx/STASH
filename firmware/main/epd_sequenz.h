// ─────────────────────────────────────────────────────────────────────────────
//  Der Controller-Baustein des 3,97"-Panels ist im öffentlichen Datenblatt
//  nicht benannt. Alles, was unabhängig vom Controller ist — Reset-Timing,
//  BUSY-Warten, SPI-Übertragung, das Streamen des Bildpuffers — steht fertig
//  in panel_treiber.c. Was hier fehlt, sind die drei Bytefolgen, die nur der
//  jeweilige Controller kennt.
//
//  Sie stehen in Waveshares Demo-Code für dieses Board, üblicherweise in einer
//  Datei wie `EPD_3in97.c`, als Folge von EPD_SendCommand(...) / EPD_SendData(...).
//  Übertragen wird das hier als Paare: erst das Kommando, dann seine Daten.
//
//  Beispielform (die Werte sind NICHT die deines Panels — nichts abschreiben,
//  was hier steht, sondern aus dem Demo übernehmen):
//
//      static const uint8_t EPD_INIT[] = {
//          1, 0x12,                    // Länge inkl. Kommando, dann Kommando
//          2, 0x01, 0xF9,              // Kommando 0x01 mit einem Datenbyte
//          0xFF                        // Ende
//      };
//
//  Solange die Folgen leer sind, startet die Firmware trotzdem: Sie nimmt auf
//  und lädt hoch, das Panel bleibt schwarz, und im Log steht warum. Ein Gerät,
//  das wegen einer fehlenden Tabelle gar nicht bootet, hilft niemandem.
// ─────────────────────────────────────────────────────────────────────────────
#pragma once
#include <stdint.h>

#define EPD_SEQ_ENDE 0xFF

// Nach dem Hardware-Reset einmal ausgeführt.
static const uint8_t EPD_INIT[] = { EPD_SEQ_ENDE };

// Vor einem Vollbild. Danach schreibt der Treiber den Bildpuffer und löst aus.
static const uint8_t EPD_VOLL_VOR[] = { EPD_SEQ_ENDE };

// Vor einem Teilbild (Partial). Meist ein anderer Wellenform-Modus.
static const uint8_t EPD_TEIL_VOR[] = { EPD_SEQ_ENDE };

// Schlafen legen. Ohne das zieht das Panel dauerhaft Strom.
static const uint8_t EPD_SCHLAF[] = { EPD_SEQ_ENDE };

// Kommando, nach dem der Bildpuffer folgt, und das Kommando, das die
// Aktualisierung auslöst. Im Waveshare-Demo heißen sie oft WRITE_RAM und
// DISPLAY_REFRESH / MASTER_ACTIVATION.
#define EPD_CMD_BILDDATEN 0x00
#define EPD_CMD_AUSLOESEN 0x00
