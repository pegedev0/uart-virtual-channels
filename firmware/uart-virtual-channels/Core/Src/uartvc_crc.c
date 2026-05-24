#include "uartvc_crc.h"

uint8_t uartvc_crc8(const uint8_t *data, uint8_t len)
{
    uint8_t crc = 0x00;

    for(uint8_t i = 0; i < len; i++)
    {
        crc ^= data[i];

        for(uint8_t j = 0; j < 8; j++)
        {
            if(crc & 0x80)
                crc = (crc << 1) ^ 0x07;
            else
                crc <<= 1;
        }
    }

    return crc;
}
