import sys
import serial
from PyQt5 import QtWidgets, QtCore, QtGui

START_BYTE = 0x7E
ESCAPE_BYTE = 0x7D
XOR_BYTE = 0x20
UARTVC_FLAG_ACK_REQ = 0x80
UARTVC_FLAG_ACK_PKT = 0x40

# --- PARSER INTEGRADO ---
class DualParser:
    def __init__(self, serial_inst, ui_cb):
        self.serial = serial_inst; self.ui_cb = ui_cb
        self.state = 'ASCII'; self.escape_active = False; self.raw_frame_buffer = bytearray()
        self.hdr = 0; self.length = 0; self.seq = 0; self.payload = bytearray()
        self.last_rx_seq = [0xFF]*16; self.has_rx_seq = [False]*16
        self.ascii_buf = ""

    def crc8(self, data):
        crc = 0x00
        for b in data:
            crc ^= b
            for _ in range(8): crc = (crc << 1) ^ 0x07 if (crc & 0x80) else crc << 1
            crc &= 0xFF
        return crc

    def send_ack(self, ch, seq):
        if not self.serial or not self.serial.is_open: return
        raw = bytearray([(ch & 0x0F) | UARTVC_FLAG_ACK_PKT, 1, seq])
        raw.append(self.crc8(raw))
        stuffed = bytearray([START_BYTE])
        for b in raw:
            if b in (START_BYTE, ESCAPE_BYTE): stuffed.extend([ESCAPE_BYTE, b ^ XOR_BYTE])
            else: stuffed.append(b)
        self.serial.write(stuffed)

    def process_byte(self, b):
        if self.state == 'ASCII':
            if b == START_BYTE:
                if self.ascii_buf: self.ui_cb('LOG', self.ascii_buf); self.ascii_buf = ""
                self.state = 'READ_HDR'; self.raw_frame_buffer = bytearray([b]); self.escape_active = False
            else:
                c = bytes([b]).decode('ascii', errors='ignore')
                if c:
                    self.ascii_buf += c
                    if c == '\n': self.ui_cb('LOG', self.ascii_buf); self.ascii_buf = ""
        else:
            self.raw_frame_buffer.append(b)
            if self.escape_active: b ^= XOR_BYTE; self.escape_active = False
            elif b == ESCAPE_BYTE: self.escape_active = True; return
            elif b == START_BYTE and len(self.raw_frame_buffer)>1:
                self.state = 'READ_HDR'; self.raw_frame_buffer = bytearray([b]); self.escape_active = False; return

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
                if self.crc8(buf) == b:
                    ch = self.hdr & 0x0F
                    if self.hdr & UARTVC_FLAG_ACK_PKT:
                        # ¡ÉXITO! Recibimos el ACK del Ratón
                        self.ui_cb('ACK_SUCCESS', f"¡ACK RECIBIDO EN {ch}! El Elefante fue pausado y reanudado.")
                    else:
                        is_dup = False
                        if self.hdr & UARTVC_FLAG_ACK_REQ:
                            if self.has_rx_seq[ch] and self.last_rx_seq[ch] == self.seq: is_dup = True
                            else: self.last_rx_seq[ch] = self.seq; self.has_rx_seq[ch] = True
                            self.send_ack(ch, self.seq)
                        if not is_dup:
                            if ch == 2: self.ui_cb('ELEPHANT', self.length) # Es un trozo del elefante
                self.state = 'ASCII'

# --- HILO SERIE ---
class SerialThread(QtCore.QThread):
    signal_data = QtCore.pyqtSignal(str, object)
    def __init__(self, port):
        super().__init__(); self.port = port; self.running = True; self.ser = None; self.tx_seq = [0] * 16
    def run(self):
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=0.01)
            parser = DualParser(self.ser, lambda t, p: self.signal_data.emit(t, p))
            self.signal_data.emit('LOG', f" Conectado a {self.port}...\n")
            while self.running:
                data = self.ser.read(1024)
                for b in data: parser.process_byte(b)
        except Exception as e: self.signal_data.emit('LOG', f"Error: {e}\n")
    
    def send_raw(self, ch, req_ack, payload):
        if not self.ser: return
        
        hdr = (ch & 0x0F) | (UARTVC_FLAG_ACK_REQ if req_ack else 0) | 0x20
        raw = bytearray([hdr, len(payload)])
        
        if req_ack: 
            # ¡MAGIA AQUÍ! Usamos el SEQ actual de este canal
            raw.append(self.tx_seq[ch]) 
            
            # Y preparamos el SEQ para el siguiente clic (vuelve a 0 si llega a 255)
            self.tx_seq[ch] = (self.tx_seq[ch] + 1) % 256
            
        raw += bytearray(payload)
        raw.append(DualParser(None,None).crc8(raw))
        frame = bytearray([START_BYTE])
        for b in raw:
            if b in (START_BYTE, ESCAPE_BYTE): frame.extend([ESCAPE_BYTE, b ^ XOR_BYTE])
            else: frame.append(b)
        self.ser.write(frame)

# --- UI PRINCIPAL ---
class Window(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Demostración QoS: El Elefante y el Ratón")
        self.resize(800, 500)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
        self.elefante_total = 50000; self.elefante_rx = 0

        layout = QtWidgets.QVBoxLayout(self)

        # Controles
        h_layout = QtWidgets.QHBoxLayout()
        self.btn_elefante = QtWidgets.QPushButton("🐘 SOLICITAR ELEFANTE (Baja Prioridad - CH2)")
        self.btn_elefante.setStyleSheet("background-color: #89b4fa; color: black; font-weight: bold; font-size: 16px; padding: 20px;")
        self.btn_elefante.clicked.connect(self.pedir_elefante)
        
        self.btn_raton = QtWidgets.QPushButton("🐭 ENVIAR RATÓN (Alta Prioridad - CH1)")
        self.btn_raton.setStyleSheet("background-color: #f38ba8; color: black; font-weight: bold; font-size: 16px; padding: 20px;")
        self.btn_raton.clicked.connect(self.enviar_raton)
        
        h_layout.addWidget(self.btn_elefante)
        h_layout.addWidget(self.btn_raton)
        layout.addLayout(h_layout)

        # Progress Bar
        self.prog = QtWidgets.QProgressBar()
        self.prog.setMaximum(self.elefante_total)
        self.prog.setStyleSheet("QProgressBar { border: 2px solid #585b70; border-radius: 5px; text-align: center; font-weight: bold; } QProgressBar::chunk { background-color: #a6e3a1; }")
        layout.addWidget(self.prog)

        # Consola
        self.console = QtWidgets.QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #11111b; font-family: Consolas; font-size: 14px;")
        layout.addWidget(self.console)

        # Iniciar Serie (¡CAMBIA EL COM!)
        self.thread = SerialThread('COM13')
        self.thread.signal_data.connect(self.on_data)
        self.thread.start()

    def pedir_elefante(self):
        self.elefante_rx = 0
        self.prog.setValue(0)
        self.console.append("<span style='color:#89b4fa;'>[PC] Pidiendo archivo gigante (50KB) al STM32...</span>")
        self.thread.send_raw(ch=2, req_ack=False, payload=[0x01])

    def enviar_raton(self):
        self.console.append("<br><span style='color:#f38ba8; font-weight:bold;'>[PC] >>> DISPARANDO COMANDO CRÍTICO CH1 (Requiere ACK)...</span>")
        self.thread.send_raw(ch=1, req_ack=True, payload=[0x99])

    def on_data(self, mtype, data):
        if mtype == 'LOG':
            self.console.insertPlainText(data)
            self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
        elif mtype == 'ELEPHANT':
            self.elefante_rx += data
            self.prog.setValue(self.elefante_rx)
        elif mtype == 'ACK_SUCCESS':
            self.console.append(f"<span style='color:#a6e3a1; font-weight:bold;'>[PC] {data}</span><br>")
            self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def closeEvent(self, e): self.thread.running = False; self.thread.wait(); e.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())