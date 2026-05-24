import sys
import serial
from PyQt5 import QtWidgets, QtCore

START_BYTE = 0x7E
ESCAPE_BYTE = 0x7D
XOR_BYTE = 0x20
UARTVC_FLAG_ACK_REQ = 0x80
UARTVC_FLAG_ACK_PKT = 0x40

# --- PARSER INTEGRADO ---
class DualParser:
    def __init__(self, serial_inst, ui_cb, sabotage_cb):
        self.serial = serial_inst; self.ui_cb = ui_cb; self.sabotage_cb = sabotage_cb
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
        raw = bytearray([(ch & 0x0F) | UARTVC_FLAG_ACK_PKT, 0, seq]) # LEN=0
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
                        self.ui_cb('ACK_SUCCESS', f"¡🐭 ACK RECIBIDO EN {ch}!")
                    else:
                        is_dup = False
                        if self.hdr & UARTVC_FLAG_ACK_REQ:
                            
                            # --- PRUEBA DEL CAOS: DESTRUCCIÓN INTENCIONADA ---
                            if self.sabotage_cb():
                                self.ui_cb('LOG_HTML', f"<br><span style='color:#f9e2af; font-weight:bold; font-size:16px;'>[CAOS] 🌩️ TORMENTA SOLAR: Paquete CRÍTICO (SEQ {self.seq}) interceptado y DESTRUIDO. No se enviará ACK al STM32.</span>")
                                self.state = 'ASCII'
                                return # Abortamos. El STM32 se quedará esperando y hará Timeout.
                            # -------------------------------------------------

                            if self.has_rx_seq[ch] and self.last_rx_seq[ch] == self.seq: 
                                is_dup = True
                                self.ui_cb('LOG_HTML', f"<span style='color:#a6e3a1;'>[PC] Re-transmisión detectada (SEQ {self.seq}). Reenviando ACK...</span><br>")
                            else: 
                                self.last_rx_seq[ch] = self.seq; self.has_rx_seq[ch] = True
                            
                            self.send_ack(ch, self.seq)

                        if not is_dup:
                            if ch == 2: self.ui_cb('ELEPHANT', self.length)
                            elif ch == 1: self.ui_cb('CRITICAL_RX', self.payload) # Payload desde STM32
                self.state = 'ASCII'

# --- HILO SERIE ---
class SerialThread(QtCore.QThread):
    signal_data = QtCore.pyqtSignal(str, object)
    def __init__(self, port):
        super().__init__(); self.port = port; self.running = True; self.ser = None
        self.tx_seq = [0]*16
        self.sabotage_next = False # Variable mágica del caos
        
    def run(self):
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=0.01)
            parser = DualParser(self.ser, lambda t, p: self.signal_data.emit(t, p), self.check_sabotage)
            self.signal_data.emit('LOG', f" Conectado a {self.port}...\n")
            while self.running:
                data = self.ser.read(1024)
                for b in data: parser.process_byte(b)
        except Exception as e: self.signal_data.emit('LOG', f"Error: {e}\n")
    
    def check_sabotage(self):
        if self.sabotage_next:
            self.sabotage_next = False
            self.signal_data.emit('SABOTAGE_OFF', None) # Apaga el checkbox en la UI
            return True
        return False

    def send_raw(self, ch, req_ack, payload):
        if not self.ser: return
        hdr = (ch & 0x0F) | (UARTVC_FLAG_ACK_REQ if req_ack else 0) | 0x20
        raw = bytearray([hdr, len(payload)])
        if req_ack: 
            raw.append(self.tx_seq[ch])
            self.tx_seq[ch] = (self.tx_seq[ch] + 1) % 256
        raw += bytearray(payload)
        raw.append(DualParser(None,None,None).crc8(raw))
        frame = bytearray([START_BYTE])
        for b in raw:
            if b in (START_BYTE, ESCAPE_BYTE): frame.extend([ESCAPE_BYTE, b ^ XOR_BYTE])
            else: frame.append(b)
        self.ser.write(frame)

# --- UI PRINCIPAL ---
class Window(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Demostración ARQ: La Prueba del Caos")
        self.resize(900, 600)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
        self.elefante_rx = 0

        layout = QtWidgets.QVBoxLayout(self)

        # Controles
        h_layout = QtWidgets.QHBoxLayout()
        
        # Grupo QoS
        group_qos = QtWidgets.QGroupBox("1. Tráfico (QoS)")
        group_qos.setStyleSheet("QGroupBox { border: 2px solid #89b4fa; border-radius: 5px; margin-top: 1ex; font-weight: bold;} QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        l_qos = QtWidgets.QVBoxLayout(group_qos)
        self.btn_elefante = QtWidgets.QPushButton("🐘 SOLICITAR ELEFANTE (Baja Pri)")
        self.btn_elefante.setStyleSheet("background-color: #89b4fa; color: black; font-weight: bold; padding: 10px;")
        self.btn_elefante.clicked.connect(lambda: self.thread.send_raw(2, False, [0x01]))
        l_qos.addWidget(self.btn_elefante)
        
        # Grupo ARQ y Caos
        group_arq = QtWidgets.QGroupBox("2. Fiabilidad (ARQ y Timeouts)")
        group_arq.setStyleSheet("QGroupBox { border: 2px solid #f38ba8; border-radius: 5px; margin-top: 1ex; font-weight: bold;} QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        l_arq = QtWidgets.QVBoxLayout(group_arq)
        
        self.chk_caos = QtWidgets.QCheckBox("🌩️ Sabotear el PRÓXIMO paquete entrante")
        self.chk_caos.setStyleSheet("font-size: 14px; font-weight: bold; color: #f9e2af;")
        self.chk_caos.stateChanged.connect(self.toggle_caos)
        
        self.btn_reporte = QtWidgets.QPushButton("🚨 PEDIR REPORTE CRÍTICO AL STM32 (Requiere ACK)")
        self.btn_reporte.setStyleSheet("background-color: #f38ba8; color: black; font-weight: bold; padding: 10px;")
        self.btn_reporte.clicked.connect(self.pedir_reporte)
        
        l_arq.addWidget(self.chk_caos)
        l_arq.addWidget(self.btn_reporte)
        
        h_layout.addWidget(group_qos)
        h_layout.addWidget(group_arq)
        layout.addLayout(h_layout)

        # Consola
        self.console = QtWidgets.QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #11111b; font-family: Consolas; font-size: 15px;")
        layout.addWidget(self.console)

        # Iniciar Serie (¡CAMBIA EL COM!)
        self.thread = SerialThread('COM13') # <--- ASEGURATE DEL PUERTO COM
        self.thread.signal_data.connect(self.on_data)
        self.thread.start()

    def toggle_caos(self, state):
        self.thread.sabotage_next = (state == QtCore.Qt.Checked)

    def pedir_reporte(self):
        self.console.append("<br><span style='color:#f38ba8;'>[PC] Solicitando Reporte de Daños al STM32...</span>")
        self.thread.send_raw(ch=1, req_ack=False, payload=[0xEE])

    def on_data(self, mtype, data):
        if mtype == 'LOG':
            self.console.insertPlainText(data)
            self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
        elif mtype == 'LOG_HTML':  # <--- ¡AÑADE ESTAS TRES LÍNEAS!
            self.console.append(data)
            self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
        elif mtype == 'SABOTAGE_OFF':
            self.chk_caos.setChecked(False) # Auto-desmarcamos
        elif mtype == 'ELEPHANT':
            pass # Oculto la barra para que el log se vea mejor
        elif mtype == 'CRITICAL_RX':
            texto = bytes(data).decode('ascii', errors='ignore')
            self.console.append(f"<span style='color:#a6e3a1; font-weight:bold;'>[PC] ¡REPORTE RECIBIDO PERFECTAMENTE!: '{texto}'</span><br>")
            self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def closeEvent(self, e): self.thread.running = False; self.thread.wait(); e.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())