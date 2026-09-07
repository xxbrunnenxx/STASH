#include "bedienung.h"
#include "board.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_timer.h"

static const char *TAG = "taste";
QueueHandle_t bedienung_queue;

// Mechanische Taster prellen. 40 ms sind lang genug für jeden Taster und kurz
// genug, dass niemand es merkt.
#define PRELL_US 40000

static int64_t zuletzt[GPIO_NUM_MAX];

static void IRAM_ATTR isr(void *arg)
{
    const int pin = (int)(intptr_t)arg;
    const int64_t jetzt = esp_timer_get_time();
    if (jetzt - zuletzt[pin] < PRELL_US) return;
    zuletzt[pin] = jetzt;

    taste_t t;
    const int pegel = gpio_get_level(pin);   // Taster gegen Masse: 0 = gedrückt

    if (pin == CONFIG_STASH_TASTE_REC) {
        t = pegel == 0 ? TASTE_REC_AN : TASTE_REC_AUS;
    } else if (pegel != 0) {
        return;                              // Drehknopf nur beim Drücken
    } else if (pin == CONFIG_STASH_KNOPF_LINKS) {
        t = TASTE_LINKS;
    } else if (pin == CONFIG_STASH_KNOPF_RECHTS) {
        t = TASTE_RECHTS;
    } else {
        t = TASTE_MITTE;
    }

    BaseType_t geweckt = pdFALSE;
    xQueueSendFromISR(bedienung_queue, &t, &geweckt);
    if (geweckt) portYIELD_FROM_ISR();
}

void bedienung_init(void)
{
    bedienung_queue = xQueueCreate(8, sizeof(taste_t));

    const int pins[] = {
        CONFIG_STASH_KNOPF_LINKS, CONFIG_STASH_KNOPF_MITTE,
        CONFIG_STASH_KNOPF_RECHTS, CONFIG_STASH_TASTE_REC,
    };

    for (size_t i = 0; i < sizeof(pins) / sizeof(pins[0]); i++) {
        gpio_config_t cfg = {
            .pin_bit_mask = 1ULL << pins[i],
            .mode = GPIO_MODE_INPUT,
            .pull_up_en = GPIO_PULLUP_ENABLE,
            // REC braucht beide Flanken: gedrückt halten nimmt auf, loslassen
            // beendet. Der Drehknopf nur die fallende.
            .intr_type = pins[i] == CONFIG_STASH_TASTE_REC ? GPIO_INTR_ANYEDGE
                                                           : GPIO_INTR_NEGEDGE,
        };
        ESP_ERROR_CHECK(gpio_config(&cfg));
    }

    ESP_ERROR_CHECK(gpio_install_isr_service(ESP_INTR_FLAG_IRAM));
    for (size_t i = 0; i < sizeof(pins) / sizeof(pins[0]); i++) {
        ESP_ERROR_CHECK(gpio_isr_handler_add(pins[i], isr, (void *)(intptr_t)pins[i]));
    }

    // Aufwachen aus dem Light-Sleep durch jeden der vier Taster.
    gpio_wakeup_enable(CONFIG_STASH_TASTE_REC, GPIO_INTR_LOW_LEVEL);
    gpio_wakeup_enable(CONFIG_STASH_KNOPF_LINKS, GPIO_INTR_LOW_LEVEL);
    gpio_wakeup_enable(CONFIG_STASH_KNOPF_MITTE, GPIO_INTR_LOW_LEVEL);
    gpio_wakeup_enable(CONFIG_STASH_KNOPF_RECHTS, GPIO_INTR_LOW_LEVEL);
    esp_sleep_enable_gpio_wakeup();

    ESP_LOGI(TAG, "Drehknopf und BOOT-Taste bereit");
}
