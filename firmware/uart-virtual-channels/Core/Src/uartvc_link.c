#include "uartvc_link.h"
#include "uartvc_frame.h"
#include "uartvc_scheduler.h"
#include "uartvc_protocol.h"
#include "uartvc_crc.h"

static uint8_t seq[UARTVC_MAX_CHANNELS];

void uartvc_send_packet(uint8_t ch, const uint8_t *data, uint16_t len, uint8_t require_ack)
{
    uint16_t offset = 0;

    while(offset < len)
    {
        uint8_t chunk = (len - offset > UARTVC_MAX_PAYLOAD) ? UARTVC_MAX_PAYLOAD : (len - offset);
        uint8_t fin = (offset + chunk >= len);

        uint8_t frame[UARTVC_MAX_FRAME];

        uint8_t size = uartvc_build_frame(ch, &data[offset], chunk, require_ack, seq[ch]++, fin, frame);

        if(size == 0 || size > UARTVC_MAX_FRAME) return;

        uartvc_enqueue(ch, frame, size);

        offset += chunk;
    }
}

void uartvc_send_ack(uint8_t ch, uint8_t seq)
{
	uint8_t raw_buf[3];

	// 1. Cabecera (Canal + Flag de paquete ACK)
	raw_buf[0] = (ch & UARTVC_CHANNEL_MASK) | UARTVC_FLAG_ACK_PKT;
	// 2. Longitud (1 byte)
	raw_buf[1] = 0;
	// 3. Payload (El número de secuencia que estamos confirmando)
	raw_buf[2] = seq;

	// 4. Calculamos el CRC de esos 3 bytes
	uint8_t crc = uartvc_crc8(raw_buf, 3);

	// 5. Preparamos la trama final con Byte Stuffing
	uint8_t stuffed_frame[10];
	uint16_t idx = 0;

	stuffed_frame[idx++] = UARTVC_START_BYTE;

	// Escapamos los 3 bytes de datos
	for(int i = 0; i < 3; i++)
	{
		if(raw_buf[i] == UARTVC_START_BYTE || raw_buf[i] == UARTVC_ESCAPE_BYTE)
		{
			stuffed_frame[idx++] = UARTVC_ESCAPE_BYTE;
			stuffed_frame[idx++] = raw_buf[i] ^ UARTVC_XOR_BYTE;
		}
		else
		{
			stuffed_frame[idx++] = raw_buf[i];
		}
	}

	// Escapamos el CRC
	if(crc == UARTVC_START_BYTE || crc == UARTVC_ESCAPE_BYTE)
	{
		stuffed_frame[idx++] = UARTVC_ESCAPE_BYTE;
		stuffed_frame[idx++] = crc ^ UARTVC_XOR_BYTE;
	}
	else
	{
		stuffed_frame[idx++] = crc;
	}

	// Lo metemos en la cola de su canal
	if (!queue_full(ch))
	{
		uartvc_enqueue(ch, stuffed_frame, idx);
	}
}
