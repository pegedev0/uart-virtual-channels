import serial
import time

# --- CONFIGURACIÓN ---
PUERTO_FTDI = 'COM13'  # <--- ¡Cámbialo!
BAUDIOS = 115200
MUESTRAS = 100

# Constantes del protocolo
START_BYTE = 0x7E
ESCAPE_BYTE = 0x7D
XOR_BYTE = 0x20

def crc8(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc << 1) ^ 0x07 if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc

def construir_ping():
    hdr = 0x24  # CH=4, sin ACKs
    length = 1
    payload = 0x50  # Letra 'P'
    
    # 1. Calculamos el CRC exacto
    buf_to_crc = bytearray([hdr, length, payload])
    mi_crc = crc8(buf_to_crc)
    
    # 2. Ensamblamos los datos puros
    raw_data = bytearray([hdr, length, payload, mi_crc])
    
    # 3. Aplicamos Byte Stuffing (por si el CRC o algo coincide con 0x7E)
    frame = bytearray([START_BYTE])
    for b in raw_data:
        if b in (START_BYTE, ESCAPE_BYTE):
            frame.extend([ESCAPE_BYTE, b ^ XOR_BYTE])
        else:
            frame.append(b)
            
    return frame

TRAMA_PING = construir_ping()

def test_latencia_rtt():
    print(f"🔌 Abriendo {PUERTO_FTDI} a {BAUDIOS} baudios...")
    print(f"📦 Trama PING generada matemáticamente: {TRAMA_PING.hex().upper()}")
    
    try:
        ser = serial.Serial(PUERTO_FTDI, BAUDIOS, timeout=1.0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        latencias = []
        perdidos = 0
        
        for i in range(1, MUESTRAS + 1):
            t_inicio = time.perf_counter()
            ser.write(TRAMA_PING)
            
            # Esperamos 5 bytes
            respuesta = ser.read(5)
            t_fin = time.perf_counter()
            
            if len(respuesta) == 5:
                latencia_ms = (t_fin - t_inicio) * 1000.0
                latencias.append(latencia_ms)
                print(f"[{i:03d}/{MUESTRAS}] RTT: {latencia_ms:.3f} ms | Datos: {respuesta.hex().upper()}")
            else:
                perdidos += 1
                print(f"[{i:03d}/{MUESTRAS}] TIMEOUT.")
            
            time.sleep(0.02)
            
        ser.close()
        
        # --- RESULTADOS ESTADÍSTICOS ---
        print("\n" + "="*45)
        print("📊 RESULTADOS DEL TEST RTT (LATENCIA Y JITTER)")
        print("="*45)
        if latencias:
            media = sum(latencias) / len(latencias)
            minima = min(latencias)
            maxima = max(latencias)
            
            # Cálculo del Jitter (Variación media absoluta entre muestras consecutivas)
            variaciones = []
            for j in range(1, len(latencias)):
                variaciones.append(abs(latencias[j] - latencias[j-1]))
            
            jitter = sum(variaciones) / len(variaciones) if variaciones else 0.0
            
            print(f"Paquetes enviados: {MUESTRAS}")
            print(f"Paquetes perdidos: {perdidos}")
            print(f"Latencia MÍNIMA:   {minima:.3f} ms")
            print(f"Latencia MEDIA:    {media:.3f} ms")
            print(f"JITTER (Fluctuación): {jitter:.3f} ms")
            print("="*45)
        else:
            print("❌ No se recibió ninguna respuesta válida.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_latencia_rtt()
    input("\nPresiona ENTER para salir...")