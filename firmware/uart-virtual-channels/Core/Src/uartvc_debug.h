#ifndef UARTVC_DEBUG
#define UARTVC_DEBUG

#include <stdio.h>

void uartvc_debug_dump_frame(const uint8_t *data, uint16_t len, uint8_t ch) {
    // Envía por ITM/SWO o acumula en buffer circular para inspección
    printf("[TX CH%d LEN=%d] ", ch, len);
    for (int i = 0; i < len; i++) {
        printf("%02X ", data[i]);
    }
    printf("\n");
}


#endif
