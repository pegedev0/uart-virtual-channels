import sys
import serial
import struct
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

START_BYTE = 0x7E
ESCAPE_BYTE = 0x7D
XOR_BYTE = 0x20

# --- PARSER INTEGRADO (Versión Optimizada para Velocidad) ---
class DualParser:
    def __init__(self, serial_inst, ui_cb):
        self.serial = serial_inst; self.ui_cb = ui_cb
        self.state = 'ASCII'; self.escape_active = False; self.raw_frame_buffer = bytearray()
        self.hdr = 0; self.length = 0; self.seq = 0; self.payload = bytearray()
    def crc8(self, data):
        crc = 0x00
        for b in data:
            crc ^= b
            for _ in range(8): crc = (crc << 1) ^ 0x07 if (crc & 0x80) else crc << 1
            crc &= 0xFF
        return crc
    def process_byte(self, b):
        if self.state == 'ASCII':
            if b == START_BYTE: self.state = 'READ_HDR'; self.raw_frame_buffer = bytearray([b]); self.escape_active = False
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
                    if not (self.hdr & 0x40): # Si no es un ACK
                        self.ui_cb(ch, self.payload)
                self.state = 'ASCII'

# --- HILO SERIE ---
class SerialThread(QtCore.QThread):
    new_data = QtCore.pyqtSignal(int, object)
    def __init__(self, port):
        super().__init__(); self.port = port; self.running = True; self.ser = None
    def run(self):
        self.ser = serial.Serial(self.port, 115200, timeout=0.01)
        parser = DualParser(self.ser, lambda ch, p: self.new_data.emit(ch, p))
        while self.running:
            data = self.ser.read(1024)
            for b in data: parser.process_byte(b)
    
    def set_led(self, color_code):
        if not self.ser: return
        # Enviamos paquete a CH1, Sin ACK (0), flag FIN (0x20)
        raw = bytearray([1 | 0x20, 1, color_code])
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
        self.setWindowTitle("Control en Bucle Cerrado (Full-Duplex)")
        self.resize(800, 400)
        self.setStyleSheet("background-color: #1e1e2e; color: white;")
        layout = QtWidgets.QHBoxLayout(self)

        # Gráfica
        self.plot = pg.PlotWidget(title="Telemetría (Inclinación)")
        self.plot.setYRange(-110, 110)
        self.plot.showGrid(x=True, y=True)
        self.curve = self.plot.plot(pen=pg.mkPen('#a6e3a1', width=3))
        self.data_y = [0]*100
        layout.addWidget(self.plot, stretch=2)

        # Indicador visual
        v_layout = QtWidgets.QVBoxLayout()
        v_layout.setAlignment(QtCore.Qt.AlignCenter)
        self.label = QtWidgets.QLabel("LED STM32")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("font-size: 20px; font-weight: bold;")
        
        self.led_ui = QtWidgets.QLabel()
        self.led_ui.setFixedSize(150, 150)
        self.led_ui.setStyleSheet("background-color: gray; border-radius: 75px; border: 4px solid white;")
        
        v_layout.addWidget(self.label)
        v_layout.addWidget(self.led_ui)
        layout.addLayout(v_layout, stretch=1)

        self.last_color = 0
        self.thread = SerialThread('COM13') # <--- RECUERDA CAMBIAR EL COM
        self.thread.new_data.connect(self.on_telemetry)
        self.thread.start()

    def on_telemetry(self, ch, payload):
        if ch == 2 and len(payload) == 2:
            # Decodificamos el int16_t de C
            inclinacion = struct.unpack('<h', payload)[0]
            
            # Actualizamos la gráfica
            self.data_y.append(inclinacion)
            self.data_y.pop(0)
            self.curve.setData(self.data_y)

            # LÓGICA DE CONTROL (El Cerebro)
            color_cmd = 1 # Verde por defecto
            color_hex = "#a6e3a1"
            
            if inclinacion < -30:
                color_cmd = 2 # Azul
                color_hex = "#89b4fa"
            elif inclinacion > 30:
                color_cmd = 3 # Rojo
                color_hex = "#f38ba8"

            # ¡Solo enviamos por serie si el color HA CAMBIADO! (Evita saturar)
            if color_cmd != self.last_color:
                self.thread.set_led(color_cmd)
                self.led_ui.setStyleSheet(f"background-color: {color_hex}; border-radius: 75px; border: 4px solid white; box-shadow: 0 0 20px {color_hex};")
                self.curve.setPen(pg.mkPen(color_hex, width=3))
                self.last_color = color_cmd

    def closeEvent(self, e): self.thread.running = False; self.thread.wait(); e.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())