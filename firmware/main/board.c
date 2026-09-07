#include "board.h"
#include "esp_log.h"

static const char *TAG = "board";

typedef struct { const char *name; int pin; } eintrag_t;

bool board_pins_vollstaendig(void)
{
    const eintrag_t pins[] = {
        {"E-Paper SCK",  CONFIG_STASH_EPD_SCK},
        {"E-Paper MOSI", CONFIG_STASH_EPD_MOSI},
        {"E-Paper CS",   CONFIG_STASH_EPD_CS},
        {"E-Paper DC",   CONFIG_STASH_EPD_DC},
        {"E-Paper RST",  CONFIG_STASH_EPD_RST},
        {"E-Paper BUSY", CONFIG_STASH_EPD_BUSY},
        {"SD SCK",       CONFIG_STASH_SD_SCK},
        {"SD MOSI",      CONFIG_STASH_SD_MOSI},
        {"SD MISO",      CONFIG_STASH_SD_MISO},
        {"SD CS",        CONFIG_STASH_SD_CS},
        {"I2C SDA",      CONFIG_STASH_I2C_SDA},
        {"I2C SCL",      CONFIG_STASH_I2C_SCL},
        {"I2S BCLK",     CONFIG_STASH_I2S_BCLK},
        {"I2S WS",       CONFIG_STASH_I2S_WS},
        {"I2S DIN",      CONFIG_STASH_I2S_DIN},
        {"Drehknopf links",  CONFIG_STASH_KNOPF_LINKS},
        {"Drehknopf drücken",CONFIG_STASH_KNOPF_MITTE},
        {"Drehknopf rechts", CONFIG_STASH_KNOPF_RECHTS},
    };

    int fehlen = 0;
    for (size_t i = 0; i < sizeof(pins) / sizeof(pins[0]); i++) {
        if (pins[i].pin < 0) {
            ESP_LOGE(TAG, "Pin fehlt: %s", pins[i].name);
            fehlen++;
        }
    }
    if (fehlen) {
        ESP_LOGE(TAG, "%d Pins nicht gesetzt. Nummern aus dem Waveshare-Schaltplan", fehlen);
        ESP_LOGE(TAG, "in `idf.py menuconfig` unter „STASH Board\" eintragen.");
        return false;
    }
    return true;
}
