#include "akku.h"
#include "board.h"

#include "driver/i2c.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"

static const char *TAG = "akku";

// Registeradressen des AXP2101, aus Waveshares Referenzcode für dieses Board
// (siehe akku.h). Nur diese drei — keine vollständige Treiberportierung.
#define AXP2101_REG_STATUS1     0x00   // Bit 3: Akku erkannt
#define AXP2101_REG_FUEL_GAUGE  0xA2   // Bit 0: Ladungszähler an/aus
#define AXP2101_REG_PROZENT     0xA4   // 0..100, direkt vom Chip berechnet

static bool bereit;

static esp_err_t lese_register(uint8_t reg, uint8_t *wert)
{
    return i2c_master_write_read_device(I2C_NUM_0, CONFIG_STASH_AXP2101_ADDR,
                                        &reg, 1, wert, 1, pdMS_TO_TICKS(100));
}

static esp_err_t setze_bit(uint8_t reg, int bit)
{
    uint8_t alt;
    esp_err_t err = lese_register(reg, &alt);
    if (err != ESP_OK) return err;
    const uint8_t neu = alt | (1 << bit);
    const uint8_t schreiben[2] = { reg, neu };
    return i2c_master_write_to_device(I2C_NUM_0, CONFIG_STASH_AXP2101_ADDR,
                                      schreiben, 2, pdMS_TO_TICKS(100));
}

esp_err_t akku_init(void)
{
    // Ladungszähler einschalten. Auf den meisten Boards ab Werk schon aktiv,
    // aber das kostet nichts zu prüfen — ohne ihn bliebe das Prozent-Register
    // auf einem alten oder ungültigen Wert stehen.
    esp_err_t err = setze_bit(AXP2101_REG_FUEL_GAUGE, 0);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "AXP2101 antwortet nicht (I2C 0x%02X) · kein Akkustand",
                CONFIG_STASH_AXP2101_ADDR);
        bereit = false;
        return err;
    }
    bereit = true;
    ESP_LOGI(TAG, "AXP2101 bereit");
    return ESP_OK;
}

int akku_prozent(void)
{
    if (!bereit) return -1;

    uint8_t status;
    if (lese_register(AXP2101_REG_STATUS1, &status) != ESP_OK) return -1;
    if (!(status & (1 << 3))) return -1;   // kein Akku angeschlossen

    uint8_t prozent;
    if (lese_register(AXP2101_REG_PROZENT, &prozent) != ESP_OK) return -1;
    return prozent > 100 ? 100 : prozent;
}
