#ifndef UARTVC_FRAME_H
#define UARTVC_FRAME_H


#include <stdint.h>

uint8_t uartvc_build_frame(uint8_t channel, const uint8_t *payload, uint8_t len, uint8_t require_ack, uint8_t seq, uint8_t fin, uint8_t *out_buffer);


#endif
