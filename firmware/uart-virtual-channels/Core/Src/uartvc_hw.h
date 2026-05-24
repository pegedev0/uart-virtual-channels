#ifndef UARTVC_HW_H
#define UARTVC_HW_H


#include <stdint.h>
#include "stm32f7xx_hal.h"

uint8_t uartvc_hw_tx_busy(void);
void uartvc_hw_send(uint8_t *data, uint16_t len);


#endif
