#include "uartvc_parser.h"
#include "uartvc_crc.h"
#include "uartvc_scheduler.h"
#include "uartvc_link.h

#include <stdio.h>

void uartvc_parser_init(uartvc_parser_t *p, uartvc_frame_callback_t callback)
{
    p->escape_active = 0;
    p->state = WAIT_START;
    p->frame_callback = callback;
    p->payload_index = 0;

    for(int i = 0; i < UARTVC_MAX_CHANNELS; i++)
    {
        p->last_rx_seq[i] = 0xFF;
        p->expected_seq[i] = 0;
        p->has_rx_seq[i] = 0;

        p->reassembly_len[i] = 0;
        p->reassembly_timer[i] = 0;
    }
}

void uartvc_parser_tick(uartvc_parser_t *p)
{
    uint32_t now = HAL_GetTick();

    for (int ch = 0; ch < UARTVC_MAX_CHANNELS; ch++)
    {
        // Si hay un paquete a medio montar...
        if (p->reassembly_len[ch] > 0)
        {
            // Y ha pasado demasiado tiempo desde el último trozo...
            if (now - p->reassembly_timer[ch] > UARTVC_REASSEMBLY_TIMEOUT_MS)
            {
                printf("\r\n[SYS] Timeout de Reensamblaje CH%d. %d bytes descartados.\r\n",
                       ch, p->reassembly_len[ch]);

                // Lo borramos para evitar atascos
                p->reassembly_len[ch] = 0;
            }
        }
    }
}

void uartvc_parser_process_byte(uartvc_parser_t *p, uint8_t byte)
{
    if(p->escape_active)
    {
        byte ^= UARTVC_XOR_BYTE;
        p->escape_active = 0;
    }
    else if(byte == UARTVC_ESCAPE_BYTE)
    {
        p->escape_active = 1;
        return;
    }
    else if(byte == UARTVC_START_BYTE)
	{
		// Si entra un 0x7E puro, destruimos cualquier estado corrupto o bloqueado.
		// Asumimos que es el inicio de una nueva trama legítima.
		p->state = READ_HDR;
		p->payload_index = 0;
		p->escape_active = 0;
		return; // El byte ya ha cumplido su función como delimitador.
	}

    switch(p->state)
    {
        case WAIT_START:
            /*
        	if(byte == UARTVC_START_BYTE)
                p->state = READ_HDR;
            	p->escape_active = 0;
            */
            break;

        case READ_HDR:
            p->hdr = byte;
            p->state = READ_LEN;
            break;

        case READ_LEN:
            p->len = byte;
            p->payload_index = 0;

            if ((p->hdr & UARTVC_FLAG_ACK_REQ) || (p->hdr & UARTVC_FLAG_ACK_PKT)) {
				p->state = READ_SEQ;
			} else {
				p->state = (p->len > 0) ? READ_PAYLOAD : READ_CRC;
			}
			break;

        case READ_SEQ:
			p->seq = byte;
			p->state = (p->len == 0) ? READ_CRC : READ_PAYLOAD;
			break;

        case READ_PAYLOAD:
            p->payload[p->payload_index++] = byte;

            if(p->payload_index >= p->len)
                p->state = READ_CRC;
            break;

        case READ_CRC:
        {
            uint8_t buf[UARTVC_MAX_REASSEMBLY_BUFFER + 3];
            uint8_t idx = 0;

            buf[idx++] = p->hdr;
            buf[idx++] = p->len;

            if ((p->hdr & UARTVC_FLAG_ACK_REQ) || (p->hdr & UARTVC_FLAG_ACK_PKT)) {
				buf[idx++] = p->seq;
			}

            for(uint8_t i=0;i<p->len;i++)
                buf[idx++] = p->payload[i];

            uint8_t crc = uartvc_crc8(buf, idx);

            if(crc == byte)
            {
            	uint8_t ch = p->hdr & UARTVC_CHANNEL_MASK;

            	if (p->hdr & UARTVC_FLAG_ACK_PKT)
            	{
					// (-) El payload[0] contiene el número de secuencia (SEQ) que nos confirman
					// uint8_t seq_recibido = (p->len > 0) ? p->payload[0] : 0;

					// Llamamos al scheduler para que libere el canal bloqueado
					uartvc_process_ack(ch, p->seq);
				}
				else
				{
					uint8_t is_duplicate = 0;

					// Es un paquete normal. Si la cabecera nos exige confirmación, trae un número de secuencia
					if (p->hdr & UARTVC_FLAG_ACK_REQ)
					{
						// Comprobamos si ya habíamos recibido este mismo SEQ en este canal
						if (p->has_rx_seq[ch] && p->last_rx_seq[ch] == p->seq)
						{
							// ¡Es un duplicado!
							is_duplicate = 1;
							printf("\r\n[PARSER] CH%d SEQ %d Duplicado. Ignorando payload pero reenviando ACK.\r\n", ch, p->seq);
						}
						else
						{
							// Es un paquete nuevo. Registramos el SEQ en el historial.
							p->last_rx_seq[ch] = p->seq;
							p->has_rx_seq[ch] = 1;
						}

						// Disparamos el ACK de vuelta siempre (tanto si es nuevo como si es duplicado)
						uartvc_send_ack(ch, p->seq);
					}

					// Es un paquete normal no duplicado y con datos. Se lo pasamos a la aplicación (main)
					if (!is_duplicate)
					{
						// LÓGICA DE REENSAMBLAJE
						// Protección contra desbordamiento de memoria
						if (p->reassembly_len[ch] + p->len > UARTVC_MAX_REASSEMBLY_BUFFER)
						{
							printf("\r\n[SYS] Error: Desbordamiento de buffer en CH%d. Trama descartada.\r\n", ch);
							p->reassembly_len[ch] = 0; // Borramos todo
						}
						else
						{
							// 1. Pegamos el trozo nuevo al final de lo que ya teníamos guardado
							for(uint16_t i = 0; i < p->len; i++) {
								p->reassembly_buffer[ch][p->reassembly_len[ch] + i] = p->payload[i];
							}

							p->reassembly_len[ch] += p->len;
							p->reassembly_timer[ch] = HAL_GetTick(); // Reseteamos el temporizador

							// 2. Comprobamos si esta era la última pieza del puzzle
							if (p->hdr & UARTVC_FLAG_FIN)
							{
								// ¡Paquete completo! Se lo damos a la aplicación de golpe
								if(p->frame_callback) {
									p->frame_callback(ch, p->reassembly_buffer[ch], p->reassembly_len[ch]);
								}

								// Vaciamos el buffer para el siguiente mensaje gigante
								p->reassembly_len[ch] = 0;
							}
						}
					}
				}
            }

            p->state = WAIT_START;
            break;
        }
    }
}
