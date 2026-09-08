#include "panel.h"
#include "board.h"
#include "panel_treiber.h"

#include <string.h>

#include "esp_heap_caps.h"
#include "esp_log.h"

static const char *TAG = "epd";

static uint8_t *puffer;        // 480 x 800, 1 Bit, 0 = schwarz
static uint8_t *vor_aufnahme;  // was vor dem Overlay auf dem Schirm stand
static bool gesichert;         // Overlay aktiv, Untergrund liegt in vor_aufnahme
static bool schlaeft;          // Panel stromlos, Bild steht
static int partial;

#define ZEILE_BYTES (PANEL_BREITE / 8)

// Ziffern 5x7, eine Zeile je Byte, oberstes Bit links. Nur so viel Schrift,
// wie das Gerät ohne den Pi braucht: die laufende Sekundenzahl.
static const uint8_t ZIFFER[11][7] = {
    {0x70,0x88,0x98,0xA8,0xC8,0x88,0x70}, // 0
    {0x20,0x60,0x20,0x20,0x20,0x20,0x70}, // 1
    {0x70,0x88,0x08,0x10,0x20,0x40,0xF8}, // 2
    {0xF8,0x10,0x20,0x10,0x08,0x88,0x70}, // 3
    {0x10,0x30,0x50,0x90,0xF8,0x10,0x10}, // 4
    {0xF8,0x80,0xF0,0x08,0x08,0x88,0x70}, // 5
    {0x30,0x40,0x80,0xF0,0x88,0x88,0x70}, // 6
    {0xF8,0x08,0x10,0x20,0x40,0x40,0x40}, // 7
    {0x70,0x88,0x88,0x70,0x88,0x88,0x70}, // 8
    {0x70,0x88,0x88,0x78,0x08,0x10,0x60}, // 9
    {0x00,0x00,0x00,0x00,0x00,0x20,0x40}, // Komma
};

static inline void pixel(int x, int y, bool schwarz)
{
    if (x < 0 || y < 0 || x >= PANEL_BREITE || y >= PANEL_HOEHE) return;
    const int i = y * ZEILE_BYTES + (x >> 3);
    const uint8_t m = 0x80 >> (x & 7);
    if (schwarz) puffer[i] &= ~m; else puffer[i] |= m;
}

static void rechteck(int x, int y, int b, int h, bool schwarz)
{
    for (int j = y; j < y + h; j++)
        for (int i = x; i < x + b; i++) pixel(i, j, schwarz);
}

// Ziffer, um `skala` vergrößert. Blockig — auf E-Paper ist das kein Nachteil.
static void ziffer(int x, int y, int z, int skala)
{
    if (z < 0 || z > 10) return;
    for (int zeile = 0; zeile < 7; zeile++)
        for (int spalte = 0; spalte < 5; spalte++)
            if (ZIFFER[z][zeile] & (0x80 >> spalte))
                rechteck(x + spalte * skala, y + zeile * skala, skala, skala, true);
}

esp_err_t panel_init(void)
{
    puffer       = heap_caps_malloc(PANEL_BYTES, MALLOC_CAP_SPIRAM);
    vor_aufnahme = heap_caps_malloc(PANEL_BYTES, MALLOC_CAP_SPIRAM);
    if (!puffer || !vor_aufnahme) return ESP_ERR_NO_MEM;
    memset(puffer, 0xFF, PANEL_BYTES);     // weiß

    esp_err_t err = epd_init();
    if (err == ESP_OK && epd_bereit()) epd_vollbild(puffer);
    return err;
}

uint8_t *panel_puffer(void)     { return puffer; }
int panel_partial_zaehler(void) { return partial; }

// Aus der Ruhe kommend ist der Controller stromlos; ohne Wecken ginge jedes
// Schreiben — Vollbild, Teilbild oder das Aufnahme-Overlay — ins Leere.
// Eine Stelle für den Check, damit sie nicht an einem der drei Aufrufer
// vorbeirutscht, so wie es panel_aufnahme() vor diesem Fix tat.
static void aufwachen(void)
{
    if (!schlaeft) return;
    epd_wecken();
    schlaeft = false;
    partial = 0;
}

esp_err_t panel_zeigen(const uint8_t *bild, bool voll_erzwingen)
{
    if (bild) memcpy(puffer, bild, PANEL_BYTES);
    if (!epd_bereit()) return ESP_ERR_INVALID_STATE;

    if (schlaeft) {
        aufwachen();
        voll_erzwingen = true;
    }

    if (voll_erzwingen || partial >= PANEL_PARTIAL_MAX) {
        esp_err_t e = epd_vollbild(puffer);
        partial = 0;
        ESP_LOGI(TAG, "Vollrefresh · Geisterbild gelöscht");
        return e;
    }
    esp_err_t e = epd_teilbild(puffer);
    partial++;
    ESP_LOGI(TAG, "Partial-Refresh · Zähler %d/%d", partial, PANEL_PARTIAL_MAX);
    if (partial >= PANEL_PARTIAL_MAX) ESP_LOGI(TAG, "Vollrefresh fällig");
    return e;
}

esp_err_t panel_ruhen(const uint8_t *bild)
{
    if (bild) memcpy(puffer, bild, PANEL_BYTES);
    if (!epd_bereit()) return ESP_ERR_INVALID_STATE;

    // Ruhend, aber der Inhalt hat sich geändert: wecken, neu zeichnen,
    // wieder schlafen legen. Ein stromloser Controller nimmt nichts an.
    aufwachen();

    esp_err_t e = epd_vollbild(puffer);
    partial = 0;
    epd_schlafen();
    schlaeft = true;
    ESP_LOGI(TAG, "Sperrseite · Vollrefresh · Panel stromlos, Bild steht");
    return e;
}

void panel_schlafen(void) { epd_schlafen(); schlaeft = true; }

// Das Overlay wird lokal gezeichnet: Auf den Beginn einer Aufnahme darf man
// nicht warten, und eine Runde zum Pi und zurück wären hunderte Millisekunden.
void panel_aufnahme(float sekunden, float pegel)
{
    // Wird die BOOT-Taste aus der Sperrseiten-Ruhe heraus gedrückt, muss der
    // Controller vor dem ersten Overlay-Frame wach sein — sonst schreibt
    // epd_teilbild() unten ins Leere, und der Aufnahmebeginn zeigt nichts an.
    aufwachen();

    if (!gesichert) { memcpy(vor_aufnahme, puffer, PANEL_BYTES); gesichert = true; }

    memset(puffer, 0xFF, PANEL_BYTES);

    // Laufende Zeit, groß: SS,S — erst die Glyphen sammeln, dann mittig setzen.
    const int zehntel = (int)(sekunden * 10 + 0.5f);
    int ganz = zehntel / 10;
    if (ganz > 999) ganz = 999;
    int glyphen[6], n = 0;
    if (ganz >= 100) glyphen[n++] = (ganz / 100) % 10;
    if (ganz >= 10)  glyphen[n++] = (ganz / 10) % 10;
    glyphen[n++] = ganz % 10;
    glyphen[n++] = 10;                 // Komma
    glyphen[n++] = zehntel % 10;

    const int skala = 8, breite = 6 * skala, y = 300;
    int x = (PANEL_BREITE - n * breite) / 2;
    for (int i = 0; i < n; i++) { ziffer(x, y, glyphen[i], skala); x += breite; }

    // Wellenform aus Balken, 1 Bit — genau das, was das Panel kann.
    const int mitte = 460, bars = 46, bb = 4, luecke = 2;
    const int start = (PANEL_BREITE - bars * (bb + luecke)) / 2;
    for (int i = 0; i < bars; i++) {
        // Der Pegel füllt von der Mitte nach außen ab; die Form kommt aus dem
        // Index, damit stehende Balken nicht wie ein eingefrorenes Bild wirken.
        const float f = pegel * (0.35f + 0.65f * ((i * 37 % 23) / 23.0f));
        int h = (int)(f * 70.0f);
        if (h < 2) h = 2;
        rechteck(start + i * (bb + luecke), mitte - h, bb, h, true);
    }
    rechteck(60, mitte + 24, PANEL_BREITE - 120, 2, true);
    rechteck(0, 0, PANEL_BREITE, 6, true);   // Balken oben = es läuft

    if (epd_bereit()) { epd_teilbild(puffer); partial++; }
}

void panel_aufnahme_ende(void)
{
    if (!gesichert) return;
    memcpy(puffer, vor_aufnahme, PANEL_BYTES);
    gesichert = false;
    // Das Overlay hat viele Teilbilder in Folge erzeugt; einmal ganz sauber
    // machen ist hier billiger als der Rückstand, der sonst stehen bliebe.
    panel_zeigen(NULL, true);
}
