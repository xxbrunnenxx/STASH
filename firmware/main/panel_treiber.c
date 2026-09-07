#include "panel_treiber.h"
#include "board.h"
#include "epd_sequenz.h"

#include <string.h>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "epd";
static spi_device_handle_t spi;
static bool sequenzen_da;

static void dc(int wert)  { gpio_set_level(CONFIG_STASH_EPD_DC, wert); }

static void senden(const uint8_t *bytes, size_t len, bool ist_kommando)
{
    if (len == 0) return;
    dc(ist_kommando ? 0 : 1);
    spi_transaction_t t = { .length = len * 8, .tx_buffer = bytes };
    ESP_ERROR_CHECK(spi_device_polling_transmit(spi, &t));
}

static void befehl(uint8_t c)                        { senden(&c, 1, true); }
static void daten(const uint8_t *b, size_t n)        { senden(b, n, false); }

// BUSY ist bei E-Paper kein Nebenschauplatz: Ein Vollrefresh dauert über zwei
// Sekunden, und wer in der Zeit nachschiebt, bekommt ein zerrissenes Bild.
static void warte_busy(const char *was, int max_ms)
{
    const TickType_t bis = xTaskGetTickCount() + pdMS_TO_TICKS(max_ms);
    while (gpio_get_level(CONFIG_STASH_EPD_BUSY) == 1) {
        if (xTaskGetTickCount() > bis) {
            ESP_LOGW(TAG, "BUSY hängt bei %s (%d ms)", was, max_ms);
            return;
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void hardware_reset(void)
{
    gpio_set_level(CONFIG_STASH_EPD_RST, 1); vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(CONFIG_STASH_EPD_RST, 0); vTaskDelay(pdMS_TO_TICKS(5));
    gpio_set_level(CONFIG_STASH_EPD_RST, 1); vTaskDelay(pdMS_TO_TICKS(20));
    warte_busy("Reset", 2000);
}

// Eine Folge aus epd_sequenz.h abspielen: Länge, Kommando, dann seine Daten.
static bool folge(const uint8_t *seq)
{
    if (seq[0] == EPD_SEQ_ENDE) return false;
    size_t i = 0;
    while (seq[i] != EPD_SEQ_ENDE) {
        const uint8_t len = seq[i++];
        befehl(seq[i]);
        if (len > 1) daten(&seq[i + 1], len - 1);
        i += len;
    }
    return true;
}

esp_err_t epd_init(void)
{
    const uint64_t maske = (1ULL << CONFIG_STASH_EPD_DC) | (1ULL << CONFIG_STASH_EPD_RST);
    gpio_config_t aus = { .pin_bit_mask = maske, .mode = GPIO_MODE_OUTPUT };
    ESP_ERROR_CHECK(gpio_config(&aus));

    gpio_config_t ein = { .pin_bit_mask = 1ULL << CONFIG_STASH_EPD_BUSY,
                          .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE };
    ESP_ERROR_CHECK(gpio_config(&ein));

    if (CONFIG_STASH_EPD_PWR >= 0) {
        gpio_config_t pwr = { .pin_bit_mask = 1ULL << CONFIG_STASH_EPD_PWR,
                              .mode = GPIO_MODE_OUTPUT };
        ESP_ERROR_CHECK(gpio_config(&pwr));
        gpio_set_level(CONFIG_STASH_EPD_PWR, 1);
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    spi_bus_config_t bus = {
        .mosi_io_num = CONFIG_STASH_EPD_MOSI,
        .miso_io_num = -1,
        .sclk_io_num = CONFIG_STASH_EPD_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = PANEL_BYTES + 8,
    };
    const spi_host_device_t host = CONFIG_STASH_EPD_SPI_HOST == 2 ? SPI3_HOST : SPI2_HOST;
    esp_err_t err = spi_bus_initialize(host, &bus, SPI_DMA_CH_AUTO);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) return err;

    spi_device_interface_config_t geraet = {
        .clock_speed_hz = 10 * 1000 * 1000,
        .mode = 0,
        .spics_io_num = CONFIG_STASH_EPD_CS,
        .queue_size = 2,
    };
    ESP_ERROR_CHECK(spi_bus_add_device(host, &geraet, &spi));

    hardware_reset();
    sequenzen_da = folge(EPD_INIT);
    if (!sequenzen_da) {
        ESP_LOGE(TAG, "Init-Folge in epd_sequenz.h ist leer — Panel bleibt schwarz.");
        ESP_LOGE(TAG, "Aufnehmen und Hochladen läuft trotzdem.");
        return ESP_OK;
    }
    warte_busy("Init", 5000);
    ESP_LOGI(TAG, "Panel %dx%d · 1 Bit bereit", PANEL_BREITE, PANEL_HOEHE);
    return ESP_OK;
}

bool epd_bereit(void) { return sequenzen_da; }

static esp_err_t bild_schreiben(const uint8_t *puffer, const uint8_t *vorspiel,
                                const char *was, int max_ms)
{
    if (!sequenzen_da) return ESP_ERR_INVALID_STATE;
    folge(vorspiel);
    befehl(EPD_CMD_BILDDATEN);
    // In Blöcken, damit der DMA-Puffer nicht das ganze Bild fassen muss.
    dc(1);
    for (size_t off = 0; off < PANEL_BYTES; off += 4000) {
        const size_t n = (PANEL_BYTES - off) < 4000 ? (PANEL_BYTES - off) : 4000;
        spi_transaction_t t = { .length = n * 8, .tx_buffer = puffer + off };
        ESP_ERROR_CHECK(spi_device_polling_transmit(spi, &t));
    }
    befehl(EPD_CMD_AUSLOESEN);
    warte_busy(was, max_ms);
    return ESP_OK;
}

esp_err_t epd_vollbild(const uint8_t *puffer)
{
    return bild_schreiben(puffer, EPD_VOLL_VOR, "Vollrefresh", 8000);
}

esp_err_t epd_teilbild(const uint8_t *puffer)
{
    return bild_schreiben(puffer, EPD_TEIL_VOR, "Teilrefresh", 3000);
}

esp_err_t epd_schlafen(void)
{
    if (!sequenzen_da) return ESP_ERR_INVALID_STATE;
    folge(EPD_SCHLAF);
    return ESP_OK;
}

esp_err_t epd_wecken(void)
{
    if (!sequenzen_da) return ESP_ERR_INVALID_STATE;
    hardware_reset();
    folge(EPD_INIT);
    warte_busy("Wecken", 5000);
    return ESP_OK;
}
