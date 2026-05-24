import serial
import time

# --- Constantes UART-VC ---
START_BYTE = 0x7E; ESCAPE_BYTE = 0x7D; XOR_BYTE = 0x20

def crc8(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8): crc = (crc << 1) ^ 0x07 if (crc & 0x80) else crc << 1
        crc &= 0xFF
    return crc

# Trama para disparar el test ('T' = 0x54 en el CH4)
raw_trig = bytearray([0x24, 1, 0x54]); raw_trig.append(crc8(raw_trig))
trigger_frame = bytearray([START_BYTE])
for b in raw_trig:
    if b in (START_BYTE, ESCAPE_BYTE): trigger_frame.extend([ESCAPE_BYTE, b ^ XOR_BYTE])
    else: trigger_frame.append(b)

def run_throughput_test(port, target_bytes=50000):
    print(f"🚀 Iniciando Test de Throughput en {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=3)
    except Exception as e:
        print(f"Error abriendo puerto: {e}"); return

    ser.reset_input_buffer()
    
    # 1. Disparamos el test y empezamos a contar
    print(f"Enviando señal de inicio. Esperando {target_bytes} bytes útiles...")
    ser.write(trigger_frame)
    t_start = time.perf_counter()

    state = 'ASCII'; escape = False
    payload = bytearray(); hdr = 0; length = 0
    
    bytes_recibidos = 0
    paquetes_recibidos = 0
    bytes_brutos_leidos = 0 # Para contar también las cabeceras y escapes

    # 2. Bucle de recepción a máxima velocidad
    while bytes_recibidos < target_bytes:
        chunk = ser.read(1024)
        if not chunk:
            print("⚠️ Timeout. La placa dejó de enviar datos.")
            break
        
        bytes_brutos_leidos += len(chunk)

        for b in chunk:
            if state == 'ASCII':
                if b == START_BYTE: state = 'HDR'
            else:
                if escape: b ^= XOR_BYTE; escape = False
                elif b == ESCAPE_BYTE: escape = True; continue
                elif b == START_BYTE: state = 'HDR'; continue 

                if state == 'HDR': hdr = b; state = 'LEN'
                elif state == 'LEN': 
                    length = b; payload = bytearray()
                    state = 'PAY' if length > 0 else 'CRC'
                elif state == 'PAY':
                    payload.append(b)
                    if len(payload) >= length: state = 'CRC'
                elif state == 'CRC':
                    buf = bytearray([hdr, length]) + payload
                    if crc8(buf) == b and (hdr & 0x0F) == 4:
                        bytes_recibidos += len(payload)
                        paquetes_recibidos += 1
                        
                        # Barra de progreso visual
                        if paquetes_recibidos % 50 == 0:
                            progreso = (bytes_recibidos / target_bytes) * 100
                            print(f"Descargando: {progreso:.1f}% ({bytes_recibidos} B)", end="\r")
                    state = 'ASCII'

    t_end = time.perf_counter()
    ser.close()
    
    tiempo_total = t_end - t_start
    return bytes_recibidos, bytes_brutos_leidos, tiempo_total

# --- EJECUCIÓN Y CÁLCULOS ---
puerto = 'COM5' # <--- CAMBIA EL COM AQUI
objetivo_payload = 50000 # 50 KB

utiles, brutos, segundos = run_throughput_test(puerto, objetivo_payload)

if utiles > 0:
    # Matemáticas de Redes
    goodput = utiles / segundos
    throughput_bruto = brutos / segundos
    limite_fisico = 115200 / 10  # 11520 B/s teóricos
    eficiencia = (goodput / limite_fisico) * 100

    print("\n\n=======================================")
    print("📊 RESULTADOS: RENDIMIENTO Y EFICIENCIA")
    print("=======================================")
    print(f"Tiempo total:          {segundos:.3f} segundos")
    print(f"Carga Útil Recibida:   {utiles} Bytes")
    print(f"Tráfico Bruto Leído:   {brutos} Bytes (Incluye cabeceras)")
    print("---------------------------------------")
    print(f"Límite Físico Cable:   {limite_fisico:.0f} B/s")
    print(f"Throughput Bruto:      {throughput_bruto:.2f} B/s")
    print(f"GOODPUT (Vel. Útil):   {goodput:.2f} B/s")
    print("---------------------------------------")
    print(f"⭐ EFICIENCIA DEL PROTOCOLO: {eficiencia:.2f} %")
    print("=======================================")