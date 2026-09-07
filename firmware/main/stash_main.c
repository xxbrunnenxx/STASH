// STASH · Firmware für das ESP32-S3-ePaper-3.97
//
// Das Gerät kann vier Dinge: aufnehmen, auf die Karte puffern, hochladen,
// anzeigen. Es layoutet nichts und entscheidet nichts — das Brain schickt ein
// fertiges 1-Bit-Bild. Der Grund ist nicht Bequemlichkeit: Schrift, Umbruch und
// Verdichtung gehören dorthin, wo der ganze Bestand liegt, nicht auf einen
// Mikrocontroller mit 8 MB.

#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "audio.h"
#include "bedienung.h"
#include "board.h"
#include "netz.h"
#include "panel.h"
#include "sdkarte.h"

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

static const char *TAG = "stash";
static TaskHandle_t netz_task_handle;

// Wann zuletzt jemand etwas gedrückt hat. Daraus entsteht die Ruhe: Nach
// CONFIG_STASH_RUHE_NACH_S Sekunden fällt das Gerät auf „Heute" zurück,
// zeichnet einmal sauber durch und legt das Panel stromlos. E-Paper hält das
// Bild ohne Strom — die Seite steht dann da wie ein Aushang, bis wieder jemand
// drückt. Das ist die einzige Eigenschaft, die dieses Gerät hat und ein
// Telefon nie haben wird; sie ungenutzt zu lassen wäre die Verschwendung.
static volatile int64_t letzte_bedienung_us;
static volatile bool ruht;

// Wie oft während der Aufnahme neu gezeichnet wird. Jeder Teilrefresh kostet
// ~340 ms und ein bisschen Geisterbild; 700 ms sieht flüssig genug aus, ohne
// dass das Panel die ganze Aufnahme über durchwischt.
#define OVERLAY_MS 700

// Arbeitet die Warteschlange ab und holt danach das aktuelle Bild.
static void netz_task(void *arg)
{
    const TickType_t intervall = pdMS_TO_TICKS(CONFIG_STASH_NETZ_INTERVALL_S * 1000);

    while (true) {
        // Wecken durch eine neue Aufnahme oder einen Tastendruck; sonst nach
        // Ablauf des Intervalls von selbst.
        ulTaskNotifyTake(pdTRUE, intervall);

        if (!netz_verbunden()) continue;

        char pfad[64];
        int hoch = 0;
        while (sd_aeltester(pfad, sizeof(pfad))) {
            if (netz_hochladen(pfad) != ESP_OK) break;   // beim nächsten Versuch weiter
            unlink(pfad);                                // erst nach bestätigtem Empfang
            hoch++;
        }
        if (hoch) {
            ESP_LOGI(TAG, "%d Aufnahme%s übertragen · %d warten noch",
                     hoch, hoch == 1 ? "" : "n", sd_warteschlange_anzahl());
        }

        // Nicht ins Panel schreiben, während das Aufnahme-Overlay läuft —
        // sonst kämpfen zwei Schreiber um denselben Puffer.
        if (audio_laeuft()) continue;

        const uint64_t frei = sd_frei_bytes();
        const int belegt_mb = (int)((29800ULL * 1000000ULL > frei)
                                    ? (29800ULL * 1000000ULL - frei) / 1000000ULL : 0);

        const bool soll_ruhen =
            (esp_timer_get_time() - letzte_bedienung_us) / 1000000 >= CONFIG_STASH_RUHE_NACH_S;

        bool neu = false;
        if (netz_bild_holen(panel_puffer(), &neu, sd_warteschlange_anzahl(),
                            belegt_mb, soll_ruhen) != ESP_OK) {
            continue;
        }
        if (soll_ruhen && !ruht) {
            // Übergang in die Ruhe: immer zeichnen, auch wenn der ETag gleich
            // wäre — die Fußleiste fällt weg und der Stempel kommt dazu.
            panel_ruhen(NULL);
            ruht = true;
        } else if (neu && !soll_ruhen) {
            panel_zeigen(NULL, false);
        } else if (neu && soll_ruhen) {
            // Ruhend hat sich der Inhalt geändert. Kein Teilbild: Das Bild
            // steht danach wieder stundenlang, es soll das saubere sein.
            panel_ruhen(NULL);
        }
    }
}

static void netz_anstossen(void)
{
    if (netz_task_handle) xTaskNotifyGive(netz_task_handle);
}

// Jeder Tastendruck beendet die Ruhe — auch der, mit dem die Aufnahme beginnt.
static void bedient(void)
{
    letzte_bedienung_us = esp_timer_get_time();
    ruht = false;
}

static void aufnahme_beginnen(void)
{
    if (audio_laeuft()) return;
    if (audio_start() != ESP_OK) return;

    // Solange die Taste gehalten wird, zeichnet das Gerät selbst. Auf eine
    // Runde zum Pi zu warten hieße, den Anfang des Satzes zu verlieren.
    while (audio_laeuft()) {
        taste_t t;
        if (xQueueReceive(bedienung_queue, &t, pdMS_TO_TICKS(OVERLAY_MS)) == pdTRUE) {
            if (t == TASTE_REC_AUS) break;
            continue;                       // alles andere zählt jetzt nicht
        }
        panel_aufnahme(audio_sekunden(), audio_pegel());
    }

    char datei[64];
    float sekunden = 0;
    audio_stop(datei, sizeof(datei), &sekunden);
    panel_aufnahme_ende();

    // Sehr kurze Drücker sind Versehen, keine Notizen.
    if (sekunden < 0.6f) {
        ESP_LOGI(TAG, "unter 0,6 s · verworfen");
        unlink(datei);
        return;
    }
    netz_anstossen();
}

void app_main(void)
{
    ESP_LOGI(TAG, "STASH Firmware %s · ESP32-S3-WROOM-1-N16R8", STASH_VERSION);
    ESP_LOGI(TAG, "Panel %dx%d · 1 Bit", PANEL_BREITE, PANEL_HOEHE);

    esp_err_t nvs = nvs_flash_init();
    if (nvs == ESP_ERR_NVS_NO_FREE_PAGES || nvs == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    if (!board_pins_vollstaendig()) {
        // Nicht weiterlaufen und so tun als ob: Ohne Pins wäre jede folgende
        // Meldung eine Lüge. Der Fehler steht oben, mit Namen.
        while (true) vTaskDelay(pdMS_TO_TICKS(10000));
    }

    ESP_ERROR_CHECK(panel_init());

    if (sd_montieren() != ESP_OK) {
        ESP_LOGE(TAG, "Ohne Karte gibt es keine Warteschlange. Gerät hält an.");
        while (true) vTaskDelay(pdMS_TO_TICKS(10000));
    }

    ESP_ERROR_CHECK(audio_init());
    bedienung_init();
    netz_init();          // darf scheitern: dann bleibt alles auf der Karte

    letzte_bedienung_us = esp_timer_get_time();
    xTaskCreate(netz_task, "netz", 8192, NULL, 5, &netz_task_handle);
    netz_anstossen();

    ESP_LOGI(TAG, "bereit · Seitentaste drücken");

    while (true) {
        taste_t t;
        if (xQueueReceive(bedienung_queue, &t, portMAX_DELAY) != pdTRUE) continue;

        bedient();

        switch (t) {
        case TASTE_REC_AN:
            aufnahme_beginnen();
            break;
        case TASTE_LINKS:
            netz_bedienung("zurueck");
            netz_anstossen();
            break;
        case TASTE_MITTE:
            netz_bedienung("oeffnen");
            netz_anstossen();
            break;
        case TASTE_RECHTS:
            netz_bedienung("weiter");
            netz_anstossen();
            break;
        default:
            break;   // REC_AUS ohne laufende Aufnahme: nichts zu tun
        }
    }
}
