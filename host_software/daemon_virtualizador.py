import serial
import threading
import time
import sys

# --- Constantes de tu protocolo ---
START_BYTE = 0x7E; ESCAPE_BYTE = 0x7D; XOR_BYTE = 0x20
UARTVC_FLAG_ACK_REQ = 0x80; UARTVC_FLAG_ACK_PKT = 0x40

# --- Parser Optimizado ---
class UartVcParser:
    def __init__(self, callback):
        self.cb = callback
        self.state = 'ASCII'; self.escape_active = False; self.raw = bytearray()
        self.hdr = 0; self.length = 0; self.seq = 0; self.payload = bytearray()
        
    def crc8(self, data):
        crc = 0
        for b in data:
            crc ^= b
            for _ in range(8): crc = (crc << 1) ^ 0x07 if (crc & 0x80) else crc << 1
            crc &= 0xFF
        return crc

    def process_byte(self, b):
        if self.state == 'ASCII':
            if b == START_BYTE: self.state = 'READ_HDR'; self.raw = bytearray([b]); self.escape_active = False
        else:
            self.raw.append(b)
            if self.escape_active: b ^= XOR_BYTE; self.escape_active = False
            elif b == ESCAPE_BYTE: self.escape_active = True; return
            elif b == START_BYTE and len(self.raw)>1:
                self.state = 'READ_HDR'; self.raw = bytearray([b]); self.escape_active = False; return

            if self.state == 'READ_HDR': self.hdr = b; self.state = 'READ_LEN'
            elif self.state == 'READ_LEN':
                self.length = b; self.payload = bytearray()
                self.state = 'READ_SEQ' if (self.hdr & 0xC0) else ('READ_PAYLOAD' if self.length > 0 else 'READ_CRC')
            elif self.state == 'READ_SEQ': self.seq = b; self.state = 'READ_PAYLOAD' if self.length > 0 else 'READ_CRC'
            elif self.state == 'READ_PAYLOAD':
                self.payload.append(b)
                if len(self.payload) >= self.length: self.state = 'READ_CRC'
            elif self.state == 'READ_CRC':
                buf = bytearray([self.hdr, self.length])
                if (self.hdr & 0xC0): buf.append(self.seq)
                buf += self.payload
                
                if self.crc8(buf) == b and not (self.hdr & UARTVC_FLAG_ACK_PKT):
                    ch = self.hdr & 0x0F
                    self.cb(ch, self.payload)
                self.state = 'ASCII'

# --- Función para empaquetar de vuelta hacia la STM32 ---
def send_to_stm32(stm32_serial, ch, data):
    # Cogemos chunks de 250 bytes max para no saturar tu buffer length de 1 byte
    for i in range(0, len(data), 250):
        chunk = data[i:i+250]
        raw = bytearray([(ch & 0x0F) | 0x20, len(chunk)]) + bytearray(chunk)
        raw.append(UartVcParser(None).crc8(raw))
        
        frame = bytearray([START_BYTE])
        for b in raw:
            if b in (START_BYTE, ESCAPE_BYTE): frame.extend([ESCAPE_BYTE, b ^ XOR_BYTE])
            else: frame.append(b)
        stm32_serial.write(frame)

# --- EL DAEMON PRINCIPAL ---
class UartVcDaemon:
    def __init__(self, port_físico, port_v1, port_v2):
        print("🔌 Iniciando Daemon de Virtualización UART-VC...")
        
        # 1. Abrimos el Hardware Real
        try:
            self.stm32 = serial.Serial(port_físico, 115200, timeout=0.1)
            print(f"✅ Conectado a Placa Física: {port_físico}")
        except Exception as e:
            print(f"❌ Error en {port_físico}: {e}"); sys.exit(1)

        # 2. Abrimos la parte oculta de los cables virtuales
        try:
            self.v1 = serial.Serial(port_v1, 115200, timeout=0.1)
            self.v2 = serial.Serial(port_v2, 115200, timeout=0.1)
            print(f"✅ Canales Virtualizados: CH1 -> {port_v1} (Ruta a COM11) | CH2 -> {port_v2} (Ruta a COM21)")
        except Exception as e:
            print(f"❌ Error abriendo puertos virtuales. ¿Has instalado com0com? {e}"); sys.exit(1)

        self.parser = UartVcParser(self.on_stm32_rx)
        self.running = True

    # EVENTO: STM32 -> PC (Desempaquetar y repartir)
    def on_stm32_rx(self, ch, payload):
        if ch == 1: self.v1.write(payload)
        elif ch == 2: self.v2.write(payload)

    # HILO: COM Virtual 1 -> STM32 (Leer y empaquetar en CH1)
    def thread_v1_rx(self):
        while self.running:
            data = self.v1.read(1024)
            if data: send_to_stm32(self.stm32, 1, data)

    # HILO: COM Virtual 2 -> STM32 (Leer y empaquetar en CH2)
    def thread_v2_rx(self):
        while self.running:
            data = self.v2.read(1024)
            if data: send_to_stm32(self.stm32, 2, data)

    # HILO PRINCIPAL: Leer STM32
    def run(self):
        print("\n🚀 DAEMON EN LÍNEA. Ejecutando en segundo plano (Ctrl+C para salir)...")
        threading.Thread(target=self.thread_v1_rx, daemon=True).start()
        threading.Thread(target=self.thread_v2_rx, daemon=True).start()
        
        try:
            while self.running:
                data = self.stm32.read(1024)
                for b in data: self.parser.process_byte(b)
        except KeyboardInterrupt:
            print("\nApagando Daemon...")
            self.running = False
            self.stm32.close(); self.v1.close(); self.v2.close()

if __name__ == '__main__':
    # (Hardware Real, Virtual Oculto 1, Virtual Oculto 2)
    daemon = UartVcDaemon('COM13', 'COM10', 'COM20')
    daemon.run()