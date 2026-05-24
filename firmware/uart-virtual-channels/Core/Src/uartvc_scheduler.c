#include "uartvc_scheduler.h"
#include "uartvc_hw.h"

#include <string.h>
#include <stdio.h>

#define QUEUE_SIZE 8

typedef struct {
    uint8_t data[UARTVC_MAX_FRAME];
    uint16_t len;
} frame_t;

typedef struct {
    frame_t queue[QUEUE_SIZE];
    uint8_t head;
    uint8_t tail;
} queue_t;

typedef enum {
    STATE_READY,
    STATE_WAITING_ACK
} chan_state_t;

static chan_state_t chan_state[UARTVC_MAX_CHANNELS];
static uint32_t chan_ack_timer[UARTVC_MAX_CHANNELS];
static uint8_t chan_retries[UARTVC_MAX_CHANNELS];
static uint8_t chan_expected_seq[UARTVC_MAX_CHANNELS];

static queue_t queues[UARTVC_MAX_CHANNELS];

static uint8_t burst_limit[UARTVC_MAX_CHANNELS];

static int8_t current_channel = -1;
static uint8_t current_burst_count = 0;

// CÓDIGO MODIFICACION PASSTHROUGH
// Búfer circular para el texto ASCII (printf)
#define RAW_BUFFER_SIZE 512
static uint8_t raw_buffer[RAW_BUFFER_SIZE];
static uint16_t raw_head = 0;
static uint16_t raw_tail = 0;

// Búfer estático para la transferencia DMA de texto
static uint8_t tx_raw_chunk[64];

// Extrae el n-ésimo byte real (sin escapar) de una trama ya empaquetada
static uint8_t get_unstuffed_byte(frame_t *frame, uint8_t target_idx)
{
    uint8_t unstuffed_pos = 0;
    // Empezamos en 1 para saltarnos siempre el UARTVC_START_BYTE
    for (uint16_t i = 1; i < frame->len; i++)
    {
        uint8_t byte = frame->data[i];
        if (byte == UARTVC_ESCAPE_BYTE)
        {
            i++; // Saltamos el byte de escape
            byte = frame->data[i] ^ UARTVC_XOR_BYTE; // Revertimos el XOR
        }

        if (unstuffed_pos == target_idx) return byte;
        unstuffed_pos++;
    }
    return 0;
}

void uartvc_scheduler_init(void)
{
    // Llenamos los cargadores de reintentos antes de empezar a trabajar
    for(int i = 0; i < UARTVC_MAX_CHANNELS; i++)
    {
        chan_retries[i] = UARTVC_MAX_RETRIES;
        chan_state[i] = STATE_READY;
    }
}


// Función para encolar texto crudo (será llamada por printf)
void uartvc_enqueue_raw(const uint8_t *data, uint16_t len)
{
    for(uint16_t i = 0; i < len; i++)
    {
        uint16_t next_head = (raw_head + 1) % RAW_BUFFER_SIZE;
        if(next_head != raw_tail) // Si no está lleno
        {
            raw_buffer[raw_head] = data[i];
            raw_head = next_head;
        }
    }
}


void uartvc_set_channel_burst(uint8_t ch, uint8_t burst)
{
    burst_limit[ch] = burst;
}


uint8_t queue_full(uint8_t ch)
{
    queue_t *q = &queues[ch];
    return ((q->head + 1) % QUEUE_SIZE) == q->tail;
}

void uartvc_enqueue(uint8_t ch, uint8_t *data, uint16_t len)
{
    queue_t *q = &queues[ch];

    if(queue_full(ch))
	{
    	// printf("QUEUE FULL CH %d\n", ch);
		return;
	}

    memcpy(q->queue[q->head].data, data, len);
    q->queue[q->head].len = len;

    q->head = (q->head + 1) % QUEUE_SIZE;
}

static int queue_empty(uint8_t ch)
{
    return queues[ch].head == queues[ch].tail;
}

int uartvc_dequeue(uint8_t ch, frame_t *out)
{
    queue_t *q = &queues[ch];

    if(queue_empty(ch)) return 0;

    *out = q->queue[q->tail];
    q->tail = (q->tail + 1) % QUEUE_SIZE;

    return 1;
}


static int find_best_channel(void)
{
	for(int ch = 0; ch < UARTVC_MAX_CHANNELS; ch++)
	{
		if(!queue_empty(ch))
		{
			// uint8_t hdr = queues[ch].queue[queues[ch].tail].data[1];
			uint8_t hdr = get_unstuffed_byte(&queues[ch].queue[queues[ch].tail], 0); // 0 = Posición del HDR

			if ((hdr & UARTVC_FLAG_ACK_PKT) || chan_state[ch] == STATE_READY)
			{
				return ch;
			}
		}
	}

	return -1;
}


void uartvc_process_ack(uint8_t ch, uint8_t seq)
{
	// Si estábamos esperando un ACK en este canal...
	if (chan_state[ch] == STATE_WAITING_ACK)
	{
		// VALIDACIÓN DE SECUENCIA
		if (chan_expected_seq[ch] == seq)
		{
			chan_state[ch] = STATE_READY;

			// Borramos la trama de la cola original
			queue_t *q = &queues[ch];
			q->tail = (q->tail + 1) % QUEUE_SIZE;

			chan_retries[ch] = UARTVC_MAX_RETRIES;

			printf("[SISTEMA] ACK procesado (SEQ %d). CH%d liberado.\r\n", seq, ch);
		}
		else
		{
			printf("[SISTEMA] ACK ignorado CH%d. Esperaba SEQ %d, llego %d.\r\n", ch, chan_expected_seq[ch], seq);
		}
	}
}


void uartvc_scheduler_run(void)
{
    if (uartvc_hw_tx_busy()) return;

    uint32_t now = HAL_GetTick();

    // 0. GESTIÓN DE TIMEOUTS (Stop and Wait)
	for (int ch = 0; ch < UARTVC_MAX_CHANNELS; ch++)
	{
		if (chan_state[ch] == STATE_WAITING_ACK)
		{
			if (now - chan_ack_timer[ch] > UARTVC_ACK_TIMEOUT_MS)
			{
				if (chan_retries[ch] > 0)
				{
					chan_retries[ch]--;
					chan_state[ch] = STATE_READY; // Lo liberamos para que vuelva a enviarse
					printf("[SISTEMA] Timeout CH%d. Reintentos: %d\r\n", ch, chan_retries[ch]);
				}
				else
				{
					// Se agotaron los reintentos. Descartamos el paquete.
					printf("[SISTEMA] Error crítico: CH%d inaccesible. Descartando.\r\n", ch);
					frame_t dummy;
					uartvc_dequeue(ch, &dummy); // Lo borramos por fin
					chan_state[ch] = STATE_READY;
					chan_retries[ch] = UARTVC_MAX_RETRIES;
				}
			}
		}
	}

    int best = find_best_channel();

    // 1. Si el canal actual se ha vaciado, lo liberamos
    if (current_channel != -1 && queue_empty(current_channel))
    {
        current_channel = -1;
    }

    // 2. Gestión de turnos (Prioridades y Burst)
    if (current_channel == -1)
    {
        // Estábamos libres y alguien quiere transmitir
        if (best != -1)
        {
            current_channel = best;
            current_burst_count = 0;
        }
    }
    else if (best != -1 && best != current_channel)
    {
        // Solo dejamos que le quiten el puesto si ya ha cumplido su ráfaga
        if (current_burst_count >= burst_limit[current_channel])
        {
            current_channel = best;
            current_burst_count = 0;
        }
    }

    // 3. Fase de Transmisión
	if (current_channel != -1)
	{
		static frame_t frame;
		queue_t *q = &queues[current_channel];

		// Hacemos un "Peek" manual (leemos sin avanzar el tail)
		frame = q->queue[q->tail];

		// Enviamos a la UART
		uartvc_hw_send(frame.data, frame.len);
		current_burst_count++;

		// Analizamos la cabecera (byte 1) para ver si requiere ACK
		// uint8_t hdr = frame.data[1];
		// Analizamos la cabecera usando el lector seguro (Posición 0 es HDR)
		uint8_t hdr = get_unstuffed_byte(&frame, 0);

		if (hdr & UARTVC_FLAG_ACK_REQ)
		{
			// Bloqueamos el canal y empezamos la cuenta atrás
			chan_state[current_channel] = STATE_WAITING_ACK;
			chan_ack_timer[current_channel] = HAL_GetTick();

			// Si tiene ACK_REQ, sabemos que el Byte 1 es LEN, y el Byte 2 es SEQ.
			chan_expected_seq[current_channel] = get_unstuffed_byte(&frame, 2);

			current_channel = -1; // Obligamos al planificador a elegir otro canal en la sig iteración
			current_burst_count = 0;
		}
		else
		{
			// No requiere ACK, lo borramos de la cola de forma normal
			q->tail = (q->tail + 1) % QUEUE_SIZE;
		}
	}
	else
	{
		//  4. MODO PASSTHROUGH ASCII
		// SOLO enviamos texto si no hay ningún canal binario transmitiendo
		if (raw_head != raw_tail)
		{
			uint16_t count = 0;

			// Extraemos un chunk del ring buffer para enviar por DMA
			while(raw_head != raw_tail && count < sizeof(tx_raw_chunk))
			{
				tx_raw_chunk[count++] = raw_buffer[raw_tail];
				raw_tail = (raw_tail + 1) % RAW_BUFFER_SIZE;
			}

			// Enviamos el texto crudo por UART
			uartvc_hw_send(tx_raw_chunk, count);
		}
	}
}
