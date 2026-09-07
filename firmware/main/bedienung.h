// Drehknopf (drei Richtungen) und die seitliche BOOT-Taste. Die Aufnahme liegt
// auf BOOT und ist damit aus jeder Ansicht erreichbar, ohne vorher irgendwohin
// navigieren zu müssen — genau das verlangt „Knopf drücken, drauflosreden".
#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

typedef enum {
    TASTE_LINKS,
    TASTE_MITTE,
    TASTE_RECHTS,
    TASTE_REC_AN,
    TASTE_REC_AUS,
} taste_t;

// Warteschlange, in die Tastendrücke fallen. Nie aus der ISR gelesen.
extern QueueHandle_t bedienung_queue;

void bedienung_init(void);
