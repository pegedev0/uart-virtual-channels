import sys
import serial
import struct
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

START_BYTE = 0x7E
ESCAPE_BYTE = 0x7D
XOR_BYTE = 0x20

class DualParser:
    def __init__(self, ui_cb):
        self.ui_cb = ui_cb
        self.state = 'ASCII'; self.escape_active = False; self.raw_frame_buffer = bytearray()
        self.hdr = 0; self.length = 0; self.seq = 0; self.payload = bytearray()
    def crc8(self, data):
        crc = 0; 
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
                    self.ui_cb(self.hdr & 0x0F, self.payload)
                self.state = 'ASCII'

class SerialThread(QtCore.QThread):
    new_data = QtCore.pyqtSignal(int, object)
    def __init__(self, port):
        super().__init__(); self.port = port; self.running = True
    def run(self):
        ser = serial.Serial(self.port, 115200, timeout=0.01)
        parser = DualParser(lambda ch, p: self.new_data.emit(ch, p))
        while self.running:
            data = ser.read(1024)
            for b in data: parser.process_byte(b)

class Window(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stress Test: QoS y Multiplexación")
        self.resize(900, 500)
        self.setStyleSheet("background-color: #11111b; color: #cdd6f4;")
        
        main_layout = QtWidgets.QHBoxLayout(self)

        # --- PANEL IZQUIERDO: CH1 (Botón) ---
        panel_btn = QtWidgets.QVBoxLayout()
        lbl_btn = QtWidgets.QLabel("CH1: Sensor Eventos (Prioridad 1)"); lbl_btn.setAlignment(QtCore.Qt.AlignCenter)
        self.btn_ui = QtWidgets.QLabel("REPOSO")
        self.btn_ui.setAlignment(QtCore.Qt.AlignCenter)
        self.btn_ui.setFixedSize(200, 200)
        self.btn_ui.setStyleSheet("background-color: #313244; color: white; border-radius: 100px; font-size: 24px; font-weight: bold; border: 5px solid #45475a;")
        panel_btn.addWidget(lbl_btn); panel_btn.addWidget(self.btn_ui); panel_btn.addStretch()
        main_layout.addLayout(panel_btn, stretch=1)

        # --- PANEL CENTRAL: CH2 (Temperatura) ---
        panel_temp = QtWidgets.QVBoxLayout()
        lbl_temp = QtWidgets.QLabel("CH2: Temperatura CPU (Prioridad 2)"); lbl_temp.setAlignment(QtCore.Qt.AlignCenter)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True)
        self.plot.setYRange(20, 50) # Rango de 20 a 50 grados
        self.curve = self.plot.plot(pen=pg.mkPen('#f38ba8', width=3))
        self.data_temp = [25.0]*100
        
        self.lbl_temp_val = QtWidgets.QLabel("25.0 °C")
        self.lbl_temp_val.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_temp_val.setStyleSheet("font-size: 30px; font-weight: bold; color: #f38ba8;")
        
        panel_temp.addWidget(lbl_temp); panel_temp.addWidget(self.plot); panel_temp.addWidget(self.lbl_temp_val)
        main_layout.addLayout(panel_temp, stretch=2)

        # --- PANEL DERECHO: CH3 (Ruido / Saturación) ---
        panel_ruido = QtWidgets.QVBoxLayout()
        lbl_ruido = QtWidgets.QLabel("CH3: Tráfico Fondo (Prioridad 3)"); lbl_ruido.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_bytes = QtWidgets.QLabel("0 KB")
        self.lbl_bytes.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_bytes.setStyleSheet("font-size: 24px; font-weight: bold; color: #89b4fa;")
        
        self.prog = QtWidgets.QProgressBar()
        self.prog.setTextVisible(False)
        self.prog.setStyleSheet("QProgressBar { border: 2px solid #585b70; border-radius: 5px; } QProgressBar::chunk { background-color: #89b4fa; }")
        
        panel_ruido.addWidget(lbl_ruido); panel_ruido.addWidget(self.lbl_bytes); panel_ruido.addWidget(self.prog); panel_ruido.addStretch()
        main_layout.addLayout(panel_ruido, stretch=1)

        self.total_basura = 0

        # ¡CAMBIA EL PUERTO COM AQUÍ!
        self.thread = SerialThread('COM13') 
        self.thread.new_data.connect(self.on_data)
        self.thread.start()

    def on_data(self, ch, payload):
        if ch == 1 and len(payload) == 1:
            if payload[0] == 1:
                self.btn_ui.setText("¡PULSADO!")
                self.btn_ui.setStyleSheet("background-color: #a6e3a1; color: black; border-radius: 100px; font-size: 24px; font-weight: bold; border: 5px solid white; box-shadow: 0 0 20px #a6e3a1;")
            else:
                self.btn_ui.setText("REPOSO")
                self.btn_ui.setStyleSheet("background-color: #313244; color: white; border-radius: 100px; font-size: 24px; font-weight: bold; border: 5px solid #45475a;")
        
        elif ch == 2 and len(payload) == 4:
            temp = struct.unpack('<f', payload)[0]
            self.lbl_temp_val.setText(f"{temp:.1f} °C")
            self.data_temp.append(temp); self.data_temp.pop(0)
            self.curve.setData(self.data_temp)
            
        elif ch == 3:
            self.total_basura += len(payload)
            self.lbl_bytes.setText(f"Descargando: {self.total_basura / 1024:.1f} KB")
            self.prog.setValue((self.total_basura % 10240) // 102) # Bucle visual

    def closeEvent(self, e): self.thread.running = False; self.thread.wait(); e.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())