#include "audio.h"
#include "board.h"
#include "sdkarte.h"

#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "driver/i2c.h"
#include "driver/i2s_std.h"
#include "es8311.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "rec";

#define BLOCK_SAMPLES 512
#define I2C_PORT      I2C_NUM_0

static i2s_chan_handle_t rx;
static es8311_handle_t   codec;

static FILE       *datei;
static char        pfad[64];
static uint32_t    datenbytes;
static int64_t     start_us;
static volatile bool laeuft;
static volatile float pegel;
static TaskHandle_t schreiber;

// 44-Byte-WAV-Kopf. Die beiden Längenfelder werden am Ende überschrieben —
// solange aufgenommen wird, weiß niemand, wie lang es wird.
static void wav_kopf(FILE *f, uint32_t daten)
{
    const uint32_t rate = AUDIO_RATE;
    const uint16_t kanaele = 1, bits = AUDIO_BITS;
    const uint32_t byte_rate = rate * kanaele * bits / 8;
    const uint16_t block = kanaele * bits / 8;
    const uint32_t riff = 36 + daten;

    fwrite("RIFF", 1, 4, f);            fwrite(&riff, 4, 1, f);
    fwrite("WAVEfmt ", 1, 8, f);
    const uint32_t fmt_len = 16; const uint16_t pcm = 1;
    fwrite(&fmt_len, 4, 1, f);          fwrite(&pcm, 2, 1, f);
    fwrite(&kanaele, 2, 1, f);          fwrite(&rate, 4, 1, f);
    fwrite(&byte_rate, 4, 1, f);        fwrite(&block, 2, 1, f);
    fwrite(&bits, 2, 1, f);
    fwrite("data", 1, 4, f);            fwrite(&daten, 4, 1, f);
}

static void schreiber_task(void *arg)
{
    int16_t *puffer = heap_caps_malloc(BLOCK_SAMPLES * sizeof(int16_t), MALLOC_CAP_SPIRAM);
    if (!puffer) { ESP_LOGE(TAG, "kein Puffer"); vTaskDelete(NULL); return; }

    while (laeuft) {
        size_t gelesen = 0;
        if (i2s_channel_read(rx, puffer, BLOCK_SAMPLES * sizeof(int16_t),
                             &gelesen, pdMS_TO_TICKS(200)) != ESP_OK || gelesen == 0) {
            continue;
        }
        fwrite(puffer, 1, gelesen, datei);
        datenbytes += gelesen;

        // Effektivwert für die Wellenform. Reicht für einen Balken, ist kein Messgerät.
        double summe = 0;
        const size_t n = gelesen / sizeof(int16_t);
        for (size_t i = 0; i < n; i++) summe += (double)puffer[i] * puffer[i];
        pegel = (float)(sqrt(summe / n) / 32768.0);

        if (datenbytes > (uint32_t)AUDIO_MAX_S * AUDIO_RATE * 2) {
            ESP_LOGW(TAG, "Obergrenze %d s erreicht · Aufnahme beendet", AUDIO_MAX_S);
            laeuft = false;
        }
    }
    free(puffer);
    schreiber = NULL;
    vTaskDelete(NULL);
}

esp_err_t audio_init(void)
{
    const i2c_config_t i2c = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = CONFIG_STASH_I2C_SDA,
        .scl_io_num = CONFIG_STASH_I2C_SCL,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = 100000,
    };
    ESP_ERROR_CHECK(i2c_param_config(I2C_PORT, &i2c));
    ESP_ERROR_CHECK(i2c_driver_install(I2C_PORT, I2C_MODE_MASTER, 0, 0, 0));

    i2s_chan_config_t kanal = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&kanal, NULL, &rx));

    i2s_std_config_t std = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,
                                                        I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = CONFIG_STASH_I2S_MCLK,
            .bclk = CONFIG_STASH_I2S_BCLK,
            .ws   = CONFIG_STASH_I2S_WS,
            .dout = I2S_GPIO_UNUSED,
            .din  = CONFIG_STASH_I2S_DIN,
            .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false },
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx, &std));

    codec = es8311_create(I2C_PORT, ES8311_ADDRRES_0);
    if (!codec) {
        ESP_LOGE(TAG, "ES8311 meldet sich nicht — I2C-Pins prüfen");
        return ESP_FAIL;
    }
    const es8311_clock_config_t takt = {
        .mclk_inverted = false,
        .sclk_inverted = false,
        .mclk_from_mclk_pin = true,
        .mclk_frequency = AUDIO_RATE * 256,
        .sample_frequency = AUDIO_RATE,
    };
    ESP_ERROR_CHECK(es8311_init(codec, &takt, ES8311_RESOLUTION_16, ES8311_RESOLUTION_16));
    ESP_ERROR_CHECK(es8311_microphone_config(codec, false));   // analoges Mikrofon
    ESP_ERROR_CHECK(es8311_microphone_gain_set(codec, (es8311_mic_gain_t)(CONFIG_STASH_MIC_GAIN_DB / 6)));

    ESP_LOGI(TAG, "ES8311 bereit · %d Hz mono %d Bit", AUDIO_RATE, AUDIO_BITS);
    return ESP_OK;
}

esp_err_t audio_start(void)
{
    if (laeuft) return ESP_ERR_INVALID_STATE;

    sd_naechster_name(pfad, sizeof(pfad));
    datei = fopen(pfad, "wb");
    if (!datei) {
        ESP_LOGE(TAG, "%s nicht schreibbar", pfad);
        return ESP_FAIL;
    }
    wav_kopf(datei, 0);
    datenbytes = 0;
    start_us = esp_timer_get_time();
    laeuft = true;
    pegel = 0;

    ESP_ERROR_CHECK(i2s_channel_enable(rx));
    xTaskCreate(schreiber_task, "audio", 4096, NULL, 6, &schreiber);

    ESP_LOGI(TAG, "Aufnahme läuft · %d kHz mono · ES8311", AUDIO_RATE / 1000);
    return ESP_OK;
}

esp_err_t audio_stop(char *aus, size_t len, float *sekunden)
{
    if (!laeuft) return ESP_ERR_INVALID_STATE;
    laeuft = false;
    while (schreiber) vTaskDelay(pdMS_TO_TICKS(10));
    i2s_channel_disable(rx);

    // Kopf mit den jetzt bekannten Längen überschreiben.
    fseek(datei, 0, SEEK_SET);
    wav_kopf(datei, datenbytes);
    fclose(datei);
    datei = NULL;

    const float s = datenbytes / (float)(AUDIO_RATE * 2);
    if (sekunden) *sekunden = s;
    if (aus) strncpy(aus, pfad, len - 1);

    ESP_LOGI(TAG, "gestoppt · %.1f s · %lu kB", s, (unsigned long)(datenbytes / 1000));
    ESP_LOGI(TAG, "→ %s", pfad);
    return ESP_OK;
}

bool  audio_laeuft(void)   { return laeuft; }
float audio_pegel(void)    { return pegel; }
float audio_sekunden(void) { return laeuft ? (esp_timer_get_time() - start_us) / 1e6f : 0.0f; }
