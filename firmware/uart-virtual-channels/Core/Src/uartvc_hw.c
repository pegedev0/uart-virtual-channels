#include "uartvc_hw.h"
#include "main.h"

extern UART_HandleTypeDef huart3;

static volatile uint8_t tx_busy = 0;

uint8_t uartvc_hw_tx_busy(void)
{
    return tx_busy;
}

void uartvc_hw_send(uint8_t *data, uint16_t len)
{
    tx_busy = 1;
    HAL_UART_Transmit_DMA(&huart3, data, len);

    // printf("TX FRAME\r\n");
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if(huart == &huart3)
    {
        tx_busy = 0;
    }
}
