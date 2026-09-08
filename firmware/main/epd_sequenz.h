// ─────────────────────────────────────────────────────────────────────────────
//  Der Controller-Baustein des 3,97"-Panels ist im öffentlichen Datenblatt
//  nicht benannt. Alles, was unabhängig vom Controller ist — Reset-Timing,
//  BUSY-Warten, SPI-Übertragung, das Streamen des Bildpuffers — steht fertig
//  in panel_treiber.c. Was hier fehlt, sind die drei Bytefolgen, die nur der
//  jeweilige Controller kennt.
//
//  Sie stehen in Waveshares Demo-Code für dieses Board
//  (github.com/waveshareteam/ESP32-S3-ePaper-3.97, Arduino-Beispiel
//  02_E-Paper_Example/EPD_3in97.cpp), als Folge von EPD_SendCommand(...) /
//  EPD_SendData(...). Übertragen wird das hier als Paare: erst das Kommando,
//  dann seine Daten.
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
//
//  ── Was aus dem Referenzcode bereits bestätigt ist (nicht übernommen, aber
//     verifiziert — als Orientierung beim Ausfüllen) ──────────────────────
//
//  Der Controller ist ein SSD16xx/UC8179-artiger 1-Bit-EPD-Controller mit
//  diesen Kommandobytes:
//    0x12  SWRESET (Soft-Reset)
//    0x0C  Booster-Softstart
//    0x01  Treiberausgangs-Kontrolle
//    0x3C  Rahmen-Wellenform (Border Waveform)
//    0x11  Data-Entry-Mode (Zählrichtung im RAM)
//    0x44  RAM-X-Fenster, 0x45  RAM-Y-Fenster
//    0x4E  RAM-X-Adresszähler, 0x4F  RAM-Y-Adresszähler
//    0x24  Bildpuffer ins Schwarz/Weiß-RAM schreiben
//    0x22  Update-Steuerung (welche Wellenform), 0x20  Master Activation
//          (löst das eigentliche Refresh aus) — das Trigger-Byte zu 0x22
//          unterscheidet drei Modi: 0xF7 Vollbild/normal, 0xD7 schnell/4-Gray,
//          0xFF Partial.
//    0x10  Deep Sleep
//
//  Zwei Fragen bleiben offen, weil sie sich aus dem Quellcode allein nicht
//  beantworten lassen — beide brauchen echte Hardware, kein Raten:
//
//  1. Moduswechsel. Das Referenzprojekt zeigt getrennte „Sessions" (Init vs.
//     Init_Fast) für Vollbild- und Schnellmodus, aber nicht, ob und wie man
//     zwischen ihnen wechselt, ohne jedes Mal die komplette Init-Sequenz neu
//     zu durchlaufen. Für STASH heißt das: EPD_VOLL_VOR und EPD_TEIL_VOR
//     müssen am echten Panel ausprobiert werden, nicht nur aus dem Demo
//     übernommen.
//  2. Drehung. Unser Bildpuffer ist hochkant (480 breit × 800 hoch), das
//     native RAM des Panels ist aber querformatig (800 × 480) organisiert —
//     eine Transposition ist strukturell nötig. In welche Richtung (im oder
//     gegen den Uhrzeigersinn) hängt davon ab, wie das Panel physisch im
//     Gehäuse sitzt, und steht in keiner Quelle — das lässt sich nur am
//     zusammengebauten Gerät sehen.
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
