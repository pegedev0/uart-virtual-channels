#ifndef UARTVC_PARSER_H
#define UARTVC_PARSER_H


#include <stdint.h>
#include <string.h>

#include "uartvc_protocol.h"

typedef void (*uartvc_frame_callback_t)(
    uint8_t channel,
    const uint8_t *payload,
    uint16_t len
);

typedef enum {
    WAIT_START,
    READ_HDR,
    READ_LEN,
	READ_SEQ,
    READ_PAYLOAD,
    READ_CRC
} parser_state_t;

typedef struct
{
    parser_state_t state;

    uint8_t escape_active;

    uint8_t hdr;
    uint8_t len;
    uint8_t seq;

    uint8_t payload[UARTVC_MAX_PAYLOAD];
    uint8_t payload_index;

    uint8_t last_rx_seq[UARTVC_MAX_CHANNELS];
    uint8_t expected_seq[UARTVC_MAX_CHANNELS];
    uint8_t has_rx_seq[UARTVC_MAX_CHANNELS];

    uint8_t reassembly_buffer[UARTVC_MAX_CHANNELS][UARTVC_MAX_REASSEMBLY_BUFFER];
    uint16_t reassembly_len[UARTVC_MAX_CHANNELS];
    uint32_t reassembly_timer[UARTVC_MAX_CHANNELS];

    uartvc_frame_callback_t frame_callback;
} uartvc_parser_t;

void uartvc_parser_init(uartvc_parser_t *p, uartvc_frame_callback_t callback);
void uartvc_parser_process_byte(uartvc_parser_t *p, uint8_t byte);

void uartvc_parser_tick(uartvc_parser_t *p);


#endif
