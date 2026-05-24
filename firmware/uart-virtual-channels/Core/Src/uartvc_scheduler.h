#ifndef UARTVC_SCHEDULER_H
#define UARTVC_SCHEDULER_H


#include "uartvc_protocol.h"
#include <stdint.h>

void uartvc_scheduler_init(void);

void uartvc_enqueue_raw(const uint8_t *data, uint16_t len);
void uartvc_enqueue(uint8_t ch, uint8_t *data, uint16_t len);

uint8_t queue_full(uint8_t ch);

void uartvc_scheduler_run(void);

void uartvc_set_channel_priority(uint8_t ch, uint8_t priority);
void uartvc_set_channel_burst(uint8_t ch, uint8_t burst);

void uartvc_process_ack(uint8_t ch, uint8_t seq);


#endif
