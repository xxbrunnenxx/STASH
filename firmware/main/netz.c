#include "netz.h"
#include "board.h"

#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "mdns.h"

static const char *TAG = "net";

#define BIT_VERBUNDEN BIT0
static EventGroupHandle_t ereignisse;
static char basis[128];
static char etag[64];

static void wifi_ereignis(void *arg, esp_event_base_t base, int32_t id, void *daten)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(ereignisse, BIT_VERBUNDEN);
        ESP_LOGW(TAG, "WLAN getrennt · Aufnahmen bleiben auf der Karte");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(ereignisse, BIT_VERBUNDEN);
        ESP_LOGI(TAG, "verbunden · RSSI %d dBm", netz_rssi());
    }
}

esp_err_t netz_init(void)
{
    if (strlen(CONFIG_STASH_WLAN_SSID) == 0) {
        ESP_LOGE(TAG, "Keine SSID gesetzt (idf.py menuconfig → STASH Netz).");
        ESP_LOGE(TAG, "Das Gerät nimmt trotzdem auf — alles bleibt auf der Karte.");
        return ESP_ERR_INVALID_STATE;
    }

    ereignisse = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                                        wifi_ereignis, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                                        wifi_ereignis, NULL, NULL));

    wifi_config_t wc = { 0 };
    strncpy((char *)wc.sta.ssid,     CONFIG_STASH_WLAN_SSID,     sizeof(wc.sta.ssid) - 1);
    strncpy((char *)wc.sta.password, CONFIG_STASH_WLAN_PASSWORT, sizeof(wc.sta.password) - 1);

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
    // Modem-Sleep: zwischen zwei Beacons schläft der Funkteil. Kostet ein paar
    // Millisekunden Reaktionszeit und spart den Großteil des Ruhestroms.
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_MIN_MODEM));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_ERROR_CHECK(mdns_init());   // damit pi5-brain.local auflösbar ist
    snprintf(basis, sizeof(basis), "http://%s:%d",
             CONFIG_STASH_BRAIN_HOST, CONFIG_STASH_BRAIN_PORT);
    ESP_LOGI(TAG, "verbinde mit %s …", CONFIG_STASH_WLAN_SSID);
    return ESP_OK;
}

bool netz_verbunden(void)
{
    if (!ereignisse) return false;
    return (xEventGroupGetBits(ereignisse) & BIT_VERBUNDEN) != 0;
}

int netz_rssi(void)
{
    wifi_ap_record_t ap;
    return esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
}

#define GRENZE "----stashgrenze7f3a"

esp_err_t netz_hochladen(const char *pfad)
{
    if (!netz_verbunden()) return ESP_ERR_INVALID_STATE;

    struct stat st;
    if (stat(pfad, &st) != 0) return ESP_ERR_NOT_FOUND;

    const char *name = strrchr(pfad, '/');
    name = name ? name + 1 : pfad;

    char kopf[256];
    const int kopf_len = snprintf(kopf, sizeof(kopf),
        "--" GRENZE "\r\n"
        "Content-Disposition: form-data; name=\"datei\"; filename=\"%s\"\r\n"
        "Content-Type: audio/wav\r\n\r\n", name);
    const char *fuss = "\r\n--" GRENZE "--\r\n";
    const int fuss_len = strlen(fuss);

    char url[192];
    snprintf(url, sizeof(url), "%s/v1/notiz", basis);

    esp_http_client_config_t cfg = { .url = url, .method = HTTP_METHOD_POST, .timeout_ms = 30000 };
    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    esp_http_client_set_header(c, "Content-Type", "multipart/form-data; boundary=" GRENZE);

    esp_err_t err = esp_http_client_open(c, kopf_len + st.st_size + fuss_len);
    if (err != ESP_OK) { esp_http_client_cleanup(c); return err; }

    esp_http_client_write(c, kopf, kopf_len);

    FILE *f = fopen(pfad, "rb");
    if (!f) { esp_http_client_cleanup(c); return ESP_FAIL; }
    char block[2048];
    size_t n;
    while ((n = fread(block, 1, sizeof(block), f)) > 0) {
        if (esp_http_client_write(c, block, n) < 0) { err = ESP_FAIL; break; }
    }
    fclose(f);
    if (err == ESP_OK) esp_http_client_write(c, fuss, fuss_len);

    if (err == ESP_OK) {
        esp_http_client_fetch_headers(c);
        const int status = esp_http_client_get_status_code(c);
        if (status == 200) {
            ESP_LOGI(TAG, "Upload %s · %lu kB", name, (unsigned long)(st.st_size / 1000));
        } else {
            ESP_LOGW(TAG, "Brain antwortet %d auf %s", status, name);
            err = ESP_FAIL;
        }
    }
    esp_http_client_cleanup(c);
    return err;
}

esp_err_t netz_bild_holen(unsigned char *puffer, bool *neu, int wartend, int sd_mb,
                          bool ruhe)
{
    if (neu) *neu = false;
    if (!netz_verbunden()) return ESP_ERR_INVALID_STATE;

    char url[224];
    snprintf(url, sizeof(url), "%s/v1/bild?wartend=%d&sd_mb=%d&ruhe=%d",
             basis, wartend, sd_mb, ruhe ? 1 : 0);

    esp_http_client_config_t cfg = { .url = url, .method = HTTP_METHOD_GET, .timeout_ms = 15000 };
    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    if (etag[0]) esp_http_client_set_header(c, "If-None-Match", etag);

    esp_err_t err = esp_http_client_open(c, 0);
    if (err != ESP_OK) { esp_http_client_cleanup(c); return err; }

    const int len = esp_http_client_fetch_headers(c);
    const int status = esp_http_client_get_status_code(c);

    if (status == 304) {                 // unverändert — nicht zeichnen
        esp_http_client_cleanup(c);
        return ESP_OK;
    }
    if (status != 200 || len != PANEL_BYTES) {
        ESP_LOGW(TAG, "Bild: Status %d, %d Byte (erwartet %d)", status, len, PANEL_BYTES);
        esp_http_client_cleanup(c);
        return ESP_FAIL;
    }

    int gelesen = 0;
    while (gelesen < PANEL_BYTES) {
        const int r = esp_http_client_read(c, (char *)puffer + gelesen, PANEL_BYTES - gelesen);
        if (r <= 0) break;
        gelesen += r;
    }
    if (gelesen == PANEL_BYTES) {
        char *wert = NULL;
        if (esp_http_client_get_header(c, "ETag", &wert) == ESP_OK && wert) {
            strncpy(etag, wert, sizeof(etag) - 1);
        }
        if (neu) *neu = true;
    } else {
        err = ESP_FAIL;
    }
    esp_http_client_cleanup(c);
    return err;
}

esp_err_t netz_bedienung(const char *was)
{
    if (!netz_verbunden()) return ESP_ERR_INVALID_STATE;

    char url[192], koerper[64];
    snprintf(url, sizeof(url), "%s/v1/bedienung", basis);
    const int len = snprintf(koerper, sizeof(koerper), "{\"taste\":\"%s\"}", was);

    esp_http_client_config_t cfg = { .url = url, .method = HTTP_METHOD_POST, .timeout_ms = 5000 };
    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    esp_http_client_set_header(c, "Content-Type", "application/json");
    esp_http_client_set_post_field(c, koerper, len);
    const esp_err_t err = esp_http_client_perform(c);
    esp_http_client_cleanup(c);
    return err;
}
