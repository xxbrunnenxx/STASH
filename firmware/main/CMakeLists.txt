idf_component_register(
  SRCS "stash_main.c"
       "board.c"
       "sdkarte.c"
       "audio.c"
       "netz.c"
       "panel.c"
       "panel_treiber.c"
       "bedienung.c"
  INCLUDE_DIRS "."
  REQUIRES driver esp_wifi esp_netif esp_event nvs_flash fatfs
           esp_http_client esp_timer esp_psram
)
