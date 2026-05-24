#ifndef UARTVC_LINK_H
#define UARTVC_LINK_H


#include <stdint.h>

void uartvc_send_packet(uint8_t channel, const uint8_t *data, uint16_t total_len, uint8_t require_ack);


#endif
