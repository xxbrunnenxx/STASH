#include "sdkarte.h"
#include "board.h"

#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statvfs.h>

#include "driver/sdmmc_host.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"

static const char *TAG = "sd";
static sdmmc_card_t *karte;

esp_err_t sd_montieren(void)
{
    esp_vfs_fat_sdmmc_mount_config_t opt = {
        .format_if_mount_failed = false,   // eine unlesbare Karte wird nicht
        .max_files = 4,                    // formatiert — da könnten Aufnahmen
        .allocation_unit_size = 16 * 1024, // drauf sein
    };

    // Waveshares Referenzcode nutzt SDMMC im 4-Bit-Modus, keine SPI — die
    // ESP32-S3-SDMMC-Peripherie hängt über die GPIO-Matrix an beliebigen
    // Pins, nicht an feste IOMUX-Leitungen wie beim klassischen ESP32.
    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    sdmmc_slot_config_t slot = SDMMC_SLOT_CONFIG_DEFAULT();
    slot.width = 4;
    slot.clk = CONFIG_STASH_SD_CLK;
    slot.cmd = CONFIG_STASH_SD_CMD;
    slot.d0  = CONFIG_STASH_SD_D0;
    slot.d1  = CONFIG_STASH_SD_D1;
    slot.d2  = CONFIG_STASH_SD_D2;
    slot.d3  = CONFIG_STASH_SD_D3;
    slot.flags |= SDMMC_SLOT_FLAG_INTERNAL_PULLUP;

    esp_err_t err = esp_vfs_fat_sdmmc_mount(SD_WURZEL, &host, &slot, &opt, &karte);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Karte nicht lesbar (%s). FAT32 formatiert?", esp_err_to_name(err));
        return err;
    }

    mkdir("/sd/stash", 0775);
    mkdir(SD_QUEUE, 0775);

    ESP_LOGI(TAG, "%s bereit · %.1f GB · %d Aufnahmen warten",
             SD_WURZEL, (double)karte->csd.capacity * karte->csd.sector_size / 1e9,
             sd_warteschlange_anzahl());
    return ESP_OK;
}

// Fortlaufend nummeriert, vierstellig. Aufsteigende Namen heißen: sortiert man
// alphabetisch, hat man die zeitliche Reihenfolge — ohne eine Uhr zu befragen.
void sd_naechster_name(char *aus, size_t len)
{
    int hoechste = 0;
    DIR *d = opendir(SD_QUEUE);
    if (d) {
        struct dirent *e;
        while ((e = readdir(d)) != NULL) {
            int n = atoi(e->d_name);
            if (n > hoechste) hoechste = n;
        }
        closedir(d);
    }
    snprintf(aus, len, SD_QUEUE "/%04d.wav", hoechste + 1);
}

bool sd_aeltester(char *aus, size_t len)
{
    char beste[32] = {0};
    DIR *d = opendir(SD_QUEUE);
    if (!d) return false;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (e->d_type == DT_DIR) continue;
        if (!strstr(e->d_name, ".wav")) continue;
        if (beste[0] == 0 || strcmp(e->d_name, beste) < 0) {
            strncpy(beste, e->d_name, sizeof(beste) - 1);
        }
    }
    closedir(d);
    if (beste[0] == 0) return false;
    snprintf(aus, len, SD_QUEUE "/%s", beste);
    return true;
}

int sd_warteschlange_anzahl(void)
{
    int n = 0;
    DIR *d = opendir(SD_QUEUE);
    if (!d) return 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (e->d_type != DT_DIR && strstr(e->d_name, ".wav")) n++;
    }
    closedir(d);
    return n;
}

uint64_t sd_frei_bytes(void)
{
    FATFS *fs;
    DWORD cluster_frei;
    if (f_getfree("0:", &cluster_frei, &fs) != FR_OK) return 0;
    return (uint64_t)cluster_frei * fs->csize * fs->ssize;
}
