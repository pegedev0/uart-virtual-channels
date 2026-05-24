#include "uartvc_frame.h"
#include "uartvc_protocol.h"
#include "uartvc_crc.h"
#include "uartvc_protocol.h"

uint8_t uartvc_build_frame(uint8_t channel, const uint8_t *payload, uint8_t len, uint8_t require_ack, uint8_t seq, uint8_t fin, uint8_t *out_buffer) 
{
    // Validaciones
    if (channel > 15)
        return 0;

    if (len > UARTVC_MAX_PAYLOAD)
        return 0;


    /* Trama */
    uint8_t index = 0;

    uint8_t raw_frame[1 + 1 + UARTVC_MAX_PAYLOAD + 1];
    uint8_t raw_frame_index = 0;

    // START
    out_buffer[index++] = UARTVC_START_BYTE;

    // HDR
    uint8_t hdr = (channel & UARTVC_CHANNEL_MASK);
    
    if (require_ack)
        hdr |= UARTVC_FLAG_ACK_REQ;
    
    if (fin)
        hdr |= UARTVC_FLAG_FIN;

    raw_frame[raw_frame_index++] = hdr;

    // LEN
    raw_frame[raw_frame_index++] = len;
    
    // SEQ
    if (require_ack)
        raw_frame[raw_frame_index++] = seq; 

    // PAYLOAD
    for (uint8_t i = 0; i < len; i++) 
    {
        raw_frame[raw_frame_index++] = payload[i];
    }

    // CRC (hay que calcularlo antes del stuffing)
    uint8_t crc = uartvc_crc8(raw_frame, raw_frame_index);
    raw_frame[raw_frame_index++] = crc;

    // Stuffing (añado al buffer final los bytes del temporal escapando si es necesario)
    for(uint8_t i = 0; i < raw_frame_index; i++)
    {
        if(raw_frame[i] == UARTVC_START_BYTE || raw_frame[i] == UARTVC_ESCAPE_BYTE)
        {
            out_buffer[index++] = UARTVC_ESCAPE_BYTE;
            out_buffer[index++] = raw_frame[i] ^ UARTVC_XOR_BYTE;
        }
        else
        {
            out_buffer[index++] = raw_frame[i];
        }
    }

    // Devolver el tamaño para que DMA sepa cuantos bytes enviar por UART
    return index;
}
