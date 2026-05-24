/*
Este archivo incluye los test de funcionamiento y rendimiento.

La información detallada de cada prueba se encuentra en el PDF del repositorio "TFG - Sistema de Conexión UART mediante canales virtuales",
en el apartado "2.3. Pruebas del sistema".

Uso:
  -> Copiar las variables del test dentro de USER CODE BEGIN WHILE (main.c)
  -> Copiar el código del test dentro del while(1), debajo de las funciones  uartvc_scheduler_run()  y  uartvc_parser_tick(&mi_parser)  (main.c)
  -> Si usa callback, copiar el código dentro de la función  void data_callback(uint8_t ch, const uint8_t *payload, uint16_t len)  (main.c)
*/

// uint32_t now = HAL_GetTick();


/*** PRUEBAS DE FUNCIONAMIENTO ***/

/* TEST COMPROBAR ENCOLADO PRIORITARIO
 	VARIABLES:
	int sent_big = 0;
	uint8_t big_buffer[200];


	for(int i=0;i<200;i++)
		big_buffer[i] = 'A' + (i % 26);

	----------------------------------------

 	CÓDIGO:
	if(!sent_big)
	{
	  sent_big = 1;

	  uartvc_send_packet(2, big_buffer, 200, 0);

	  uint8_t ctrl[] = "MENSAJE PRIORITARIO";
	  uartvc_send_packet(1, ctrl, sizeof(ctrl), 0);
	}
*/


/* TEST INTERRUPCIÓN DE CANAL MÁS PRIORITARIO
 	VARIABLES:
	  int test_state = 0;
	  uint32_t timer = 0;

	----------------------------------------

 	CÓDIGO:
	// Envío del paquete gigante por el canal 2
	if (test_state == 0)
	{
		uartvc_send_packet(2, big_buffer, 200, 0);
		timer = HAL_GetTick();
		test_state = 1;
	}

	// Espera de 20ms mientras el paquete gigante se está enviando por DMA en el canal 2 e inyección del paquete prioritario por el Canal 1.
	else if (test_state == 1 && (HAL_GetTick() - timer > 0))
	{
		uint8_t ctrl[] = "MENSAJE PRIORITARIO";
		uartvc_send_packet(1, ctrl, sizeof(ctrl), 0);
		test_state = 2; // Terminamos la prueba
	}
*/


/* TEST ELEFANTE Y RATÓN
	VARIABLES:
  	for(int i=0; i<64; i++) buffer_elefante[i] = 'E';

	----------------------------------------

	CÓDIGO:
	if (elefante_bytes_restantes > 0 && (now - timer_elefante >= 5))
	{
	  // ¡ESTA ES LA CLAVE! Solo intentamos enviar si el canal 2 tiene sitio
	  if (!queue_full(2))
	  {
		  timer_elefante = now;
		  uint16_t chunk = (elefante_bytes_restantes > 64) ? 64 : elefante_bytes_restantes;

		  uartvc_send_packet(2, buffer_elefante, chunk, 0);
		  elefante_bytes_restantes -= chunk;

		  if (elefante_bytes_restantes == 0) {
			  printf("\r\n[STM32] Envio finalizado con exito.\r\n");
		  }
	  }
	}

	----------------------------------------

	CALLBACK:
	// Si Python nos pide el Elefante por el CH2
	if (ch == 2 && payload[0] == 0x01)
	{
		elefante_bytes_restantes = 50000; // 50 KB de datos
		printf("\r\n[STM32] Iniciando envio del ELEFANTE (50KB) por CH2...\r\n");
	}
	// Si Python nos manda el Ratón (Emergencia) por el CH1
	else if (ch == 1 && payload[0] == 0x99)
	{
		printf("\r\n[STM32] ¡RATON RECIBIDO! Interrumpiendo para procesar...\r\n");
		HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_14);
	}
*/


/* TEST DEL CAOS
	CALLBACK:
	// Si el PC nos pide un reporte crítico
	else if (ch == 1 && payload[0] == 0xEE)
	{
		printf("\r\n[STM32] Preparando REPORTE CRITICO hacia el PC...\r\n");
		uint8_t reporte[] = "Fallo Motor";
		uartvc_send_packet(1, reporte, sizeof(reporte), 1);
	}
*/


/* TEST FULL DUPLEX
 	VARIABLES:
 	uint32_t timer_sensor = HAL_GetTick();

	----------------------------------------

	CÓDIGO:
	// Leemos el botón cada 20ms
	if (HAL_GetTick() - timer_sensor >= 20)
	{
	  timer_sensor = HAL_GetTick();

	  // En la Nucleo F7, el botón da 1 (SET) al pulsarse
	  uint8_t estado_boton = 0;
	  if(HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13) == GPIO_PIN_SET) {
		  estado_boton = 100; // Simula inclinación máxima (Pulsado)
	  } else {
		  estado_boton = 0;   // Reposo (Soltado)
	  }

	  // Lo enviamos como un entero de 16 bits (para que encaje con el Python actual)
	  int16_t valor_a_enviar = estado_boton;

	  if (!queue_full(2)) {
		  uartvc_send_packet(2, (uint8_t*)&valor_a_enviar, 2, 0);
	  }
	}

	----------------------------------------

	CALLBACK:
	// (Prueba full-duplex)
	else if (ch == 1 && len == 1)
	{
		uint8_t color = payload[0];

		// Apagamos los 3 LEDs por defecto (Verde=PB0, Azul=PB7, Rojo=PB14)
		HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0 | GPIO_PIN_7 | GPIO_PIN_14, GPIO_PIN_RESET);

		// Encendemos el que nos pida Python
		if (color == 1) HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_SET);      // Verde
		else if (color == 2) HAL_GPIO_WritePin(GPIOB, GPIO_PIN_7, GPIO_PIN_SET); // Azul
		else if (color == 3) HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_SET);// Rojo
	}
*/


/* TEST MULTIPLEXACION
	VARIABLES:
	uint32_t timer_boton = HAL_GetTick();
	uint32_t timer_temp  = HAL_GetTick();
	uint8_t buffer_basura[64];
	for (int i=0; i<64; i++) buffer_basura[i] = 0xAA;

	----------------------------------------

	CÓDIGO:
	// --- CH1 (PRIORIDAD ALTA): Botón Azul a 50Hz (cada 20ms) ---
	if (now - timer_boton >= 20)
	{
		timer_boton = now;
		// Leemos el botón (PC13)
		uint8_t estado_boton = (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13) == GPIO_PIN_SET) ? 1 : 0;

		if (!queue_full(1)) {
			uartvc_send_packet(1, &estado_boton, 1, 0); // 1 byte, sin ACK
		}
	}

	// --- CH2 (PRIORIDAD MEDIA): Temp Interna a 5Hz (cada 200ms) ---
	if (now - timer_temp >= 200)
	{
		timer_temp = now;

		// 1. Le disparas al ADC para que lea la temperatura
		HAL_ADC_Start(&hadc1);
		if (HAL_ADC_PollForConversion(&hadc1, 10) == HAL_OK)
		{
			uint32_t raw_adc = HAL_ADC_GetValue(&hadc1);

			// 2. Fórmula estándar del datasheet de STM32F7 para pasar a Grados Celsius
			// (Voltaje de referencia 3.3V, 12 bits de resolución)
			float voltaje = (raw_adc * 3.3f) / 4095.0f;
			float temp_celsius = ((voltaje - 0.76f) / 0.0025f) + 25.0f;

			// 3. Enviamos el float (4 bytes)
			if (!queue_full(2)) {
				uartvc_send_packet(2, (uint8_t*)&temp_celsius, sizeof(float), 0);
			}
		}
		HAL_ADC_Stop(&hadc1);
	}

	// --- CH3 (PRIORIDAD BAJA): Saturación intencionada de la red ---
	// Si la cola 3 tiene hueco, le metemos 64 bytes para molestar.
	// Esto estresa el cable a tope simulando la descarga de un archivo.
	if (!queue_full(3))
	{
		uartvc_send_packet(3, buffer_basura, 64, 0);
	}
	*/

	/*
	if (HAL_GetTick() - log_timer > 250)
	{
	 log_timer = HAL_GetTick();
	 if (test_state == 3) printf(".");
	}
*/


/*** PRUEBAS DE RENDIMIENTO ***/

/* TEST DE RENDIMIENTO 1: Ping-Pong de Latencia
	CALLBACK:
	else if (ch == 4 && len == 1 && payload[0] == 0x50)
	{
		uint8_t pong = 0x4F;
		uartvc_send_packet(4, &pong, 1, 0);
	}
*/


/* TEST RENDIMIENTO 2: Disparador de Throughput
	VARIABLES:
	volatile uint8_t flag_test_throughput = 0;

	----------------------------------------

	CÓDIGO:
	if (flag_test_throughput == 1)
	{
	  flag_test_throughput = 0;

	  // 1. Preparar un payload de 50 bytes.
	  // (Usamos la letra 'A' = 0x41 para evitar que necesite Byte Stuffing).
	  uint8_t payload[50];
	  for(int i=0; i<50; i++) payload[i] = 0x41;

	  // 2. Calcular CRC8 manualmente de la cabecera y el payload
	  uint8_t crc = 0;
	  uint8_t data_to_crc[52];
	  data_to_crc[0] = 0x24; // Cabecera: CH=4, FIN=1
	  data_to_crc[1] = 50;   // Longitud
	  for(int i=0; i<50; i++) data_to_crc[i+2] = payload[i];

	  for(int i=0; i<52; i++) {
		  crc ^= data_to_crc[i];
		  for(int j=0; j<8; j++) crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : (crc << 1);
	  }

	  // 3. Ensamblar la trama final (54 bytes en total)
	  uint8_t trama_final[60];
	  int idx = 0;
	  trama_final[idx++] = 0x7E; // START
	  trama_final[idx++] = 0x24; // HDR
	  trama_final[idx++] = 50;   // LEN
	  for(int i=0; i<50; i++) trama_final[idx++] = payload[i];

	  // Stuffing solo para el CRC por si diera la casualidad de que es un byte reservado
	  if(crc == 0x7E || crc == 0x7D) {
		  trama_final[idx++] = 0x7D;
		  trama_final[idx++] = crc ^ 0x20;
	  } else {
		  trama_final[idx++] = crc;
	  }

	  // 4. BLAST MODE: Enviar 1000 veces bloqueando el procesador.
	  for(int p = 0; p < 1000; p++)
	  {
		  // HAL_MAX_DELAY garantiza que no enviará el siguiente hasta que el cable esté libre.
		  // Esto exprime el cable al 100% de su capacidad sin colapsar la memoria.
		  HAL_UART_Transmit(&huart3, trama_final, idx, HAL_MAX_DELAY);
	  }
	}

	----------------------------------------

	CALLBACK
	else if (ch == 4 && len == 1 && payload[0] == 0x54)
	{
		flag_test_throughput = 1;
	}
*/
