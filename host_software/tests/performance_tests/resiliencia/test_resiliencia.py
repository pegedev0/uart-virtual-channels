import serial
import time
import random

START_BYTE = 0x7E; ESCAPE_BYTE = 0x7D; XOR_BYTE = 0x20

def crc8(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8): crc = (crc << 1) ^ 0x07 if (crc & 0x80) else crc << 1
        crc &= 0xFF
    return crc

# 1. Trama Válida Perfecta (PING)
raw_ping = bytearray([0x24, 1, 0x50])
raw_ping.append(crc8(raw_ping))
ping_frame = bytearray([START_BYTE])
for b in raw_ping:
    if b in (START_BYTE, ESCAPE_BYTE): ping_frame.extend([ESCAPE_BYTE, b ^ XOR_BYTE])
    else: ping_frame.append(b)

# 2. Trama con CRC Corrupto (Cambiamos el último byte a propósito)
ping_bad_crc = bytearray(ping_frame)
ping_bad_crc[-1] ^= 0xFF 

# 3. Trama Truncada (Faltan bytes de payload y el CRC)
ping_truncado = ping_frame[:-2] 

def test_resiliencia(port):
    print("🌩️ INICIANDO TEST DE RESILIENCIA (FUZZING) 🌩️")
    try:
        ser = serial.Serial(port, 115200, timeout=0.1)
    except Exception as e:
        print(f"Error: {e}"); return

    time.sleep(1)
    stats = {'enviados': 0, 'recuperados': 0, 'fallos_criticos': 0}

    for ronda in range(1, 21):
        print(f"\n--- Ronda {ronda}/20 ---")
        
        # Seleccionar un ataque al azar
        ataque = random.choice(['RUIDO', 'BAD_CRC', 'TRUNCADO'])
        
        if ataque == 'RUIDO':
            print("💥 Inyectando basura y falsos Starts (Pérdida de sincronismo)...")
            basura = bytearray([random.randint(0, 255) for _ in range(50)])
            basura[25] = START_BYTE # Un Start falso en medio del caos
            ser.write(basura)
            
        elif ataque == 'BAD_CRC':
            print("☢️ Enviando trama completa con CRC corrupto...")
            ser.write(ping_bad_crc)
            
        elif ataque == 'TRUNCADO':
            print("✂️ Cortando trama a la mitad (Corte de conexión)...")
            ser.write(ping_truncado)

        # Pequeña pausa para que la STM32 procese el ataque
        time.sleep(0.05)
        ser.reset_input_buffer()

        # LA PRUEBA DE FUEGO: Enviamos un paquete válido justo después del ataque
        print("✅ Enviando paquete válido para probar recuperación...")
        ser.write(ping_frame)
        stats['enviados'] += 1

        # Esperamos la respuesta
        respuesta = ser.read(10)
        
        if len(respuesta) > 0 and START_BYTE in respuesta:
            print("   -> 🟢 ¡RECUPERACIÓN EXITOSA! La STM32 respondió correctamente.")
            stats['recuperados'] += 1
        else:
            print("   -> 🔴 ¡FALLO CRÍTICO! La STM32 se ha bloqueado o perdido sincronismo.")
            stats['fallos_criticos'] += 1

        time.sleep(0.1)

    ser.close()
    
    print("\n=======================================")
    print("📊 RESULTADOS DEL TEST DE RESILIENCIA")
    print("=======================================")
    print(f"Ataques Inyectados:   20")
    print(f"Recuperaciones OK:    {stats['recuperados']} ({(stats['recuperados']/20)*100:.1f}%)")
    print(f"Fallos de Sistema:    {stats['fallos_criticos']}")
    print("=======================================")
    if stats['fallos_criticos'] == 0:
        print("🏆 Veredicto: MÁQUINA DE ESTADOS INDESTRUCTIBLE.")

test_resiliencia('COM13') # <-- Cambia a tu puerto