import sys
import serial
import time
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

# Constantes del Protocolo
START_BYTE = 0x7E; ESCAPE_BYTE = 0x7D; XOR_BYTE = 0x20
UARTVC_FLAG_ACK_REQ = 0x80; UARTVC_FLAG_ACK_PKT = 0x40

class PassiveSnifferParser:
    def __init__(self, packet_cb):
        self.packet_cb = packet_cb
        self.state = 'ASCII'; self.escape_active = False; self.raw_buffer = bytearray()
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
            if b == START_BYTE: 
                self.state = 'READ_HDR'; self.raw_buffer = bytearray([b]); self.escape_active = False
        else:
            self.raw_buffer.append(b)
            if self.escape_active: b ^= XOR_BYTE; self.escape_active = False
            elif b == ESCAPE_BYTE: self.escape_active = True; return
            elif b == START_BYTE and len(self.raw_buffer)>1:
                self.state = 'READ_HDR'; self.raw_buffer = bytearray([b]); self.escape_active = False; return

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
                
                is_valid = (self.crc8(buf) == b)
                ch = self.hdr & 0x0F
                is_ack = bool(self.hdr & UARTVC_FLAG_ACK_PKT)
                req_ack = bool(self.hdr & UARTVC_FLAG_ACK_REQ)
                
                # Reportamos el paquete capturado al Dashboard
                pkt_info = {
                    'time': time.time(),
                    'ch': ch,
                    'is_ack': is_ack,
                    'req_ack': req_ack,
                    'seq': self.seq if (is_ack or req_ack) else '-',
                    'len': self.length,
                    'payload': self.payload.hex().upper(),
                    'valid': is_valid,
                    'raw_len': len(self.raw_buffer)
                }
                self.packet_cb(pkt_info)
                self.state = 'ASCII'

class SerialThread(QtCore.QThread):
    new_packet = QtCore.pyqtSignal(object)
    
    def __init__(self, port):
        super().__init__(); self.port = port; self.running = True
        
    def run(self):
        try:
            ser = serial.Serial(self.port, 115200, timeout=0.01)
            parser = PassiveSnifferParser(lambda p: self.new_packet.emit(p))
            while self.running:
                data = ser.read(1024)
                for b in data: parser.process_byte(b)
        except Exception as e:
            print(f"Error abriendo puerto: {e}")

class AnalyzerWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UART-VC Protocol Dashboard")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #11111b; color: #cdd6f4; font-family: 'Segoe UI', Arial;")
        
        # Estructuras de datos para métricas
        self.ch_stats = [{'pkts': 0, 'bytes': 0} for _ in range(16)]
        self.global_bytes = 0
        self.throughput_history = [0]*60 # 60 segundos de historia
        self.last_time = time.time()
        
        self.setup_ui()
        
        # Timer para calcular el Throughput (B/s) cada 1 segundo
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_throughput)
        self.timer.start(1000)

        # ¡CAMBIA EL PUERTO COM AQUÍ SI ES NECESARIO!
        self.thread = SerialThread('COM13') 
        self.thread.new_packet.connect(self.on_packet_sniffed)
        self.thread.start()

    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # --- TOP: Gráfica y Tabla ---
        top_layout = QtWidgets.QHBoxLayout()
        
        # Izquierda: Matriz de 16 Canales
        group_matrix = QtWidgets.QGroupBox("Matriz de Multiplexación (16 Canales)")
        group_matrix.setStyleSheet("QGroupBox { border: 2px solid #585b70; border-radius: 5px; font-weight: bold; font-size: 14px; }")
        matrix_layout = QtWidgets.QVBoxLayout(group_matrix)
        
        self.table = QtWidgets.QTableWidget(16, 3)
        self.table.setHorizontalHeaderLabels(["Canal", "Paquetes", "Bytes Carga Útil"])
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("QTableWidget { background-color: #1e1e2e; gridline-color: #313244; border: none; } QHeaderView::section { background-color: #313244; color: white; font-weight: bold; }")
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        
        for i in range(16):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(f"CH {i}"))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem("0"))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem("0"))
            # Colorear canales comunes
            if i == 1: self.table.item(i, 0).setForeground(QtGui.QColor("#a6e3a1"))
            if i == 2: self.table.item(i, 0).setForeground(QtGui.QColor("#f38ba8"))
            if i == 3: self.table.item(i, 0).setForeground(QtGui.QColor("#89b4fa"))
            
        matrix_layout.addWidget(self.table)
        top_layout.addWidget(group_matrix, stretch=1)
        
        # Derecha: Gráfica de Throughput
        group_plot = QtWidgets.QGroupBox("Rendimiento del Enlace Físico (Bytes/seg)")
        group_plot.setStyleSheet("QGroupBox { border: 2px solid #585b70; border-radius: 5px; font-weight: bold; font-size: 14px; }")
        plot_layout = QtWidgets.QVBoxLayout(group_plot)
        
        self.lbl_throughput = QtWidgets.QLabel("0 B/s")
        self.lbl_throughput.setAlignment(QtCore.Qt.AlignRight)
        self.lbl_throughput.setStyleSheet("font-size: 24px; font-weight: bold; color: #f9e2af;")
        plot_layout.addWidget(self.lbl_throughput)
        
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True)
        self.plot.setYRange(0, 12000) # Máximo teórico aprox para 115200 baudios
        self.curve = self.plot.plot(pen=pg.mkPen('#f9e2af', width=3, fillLevel=0, brush=(249, 226, 175, 50)))
        plot_layout.addWidget(self.plot)
        
        top_layout.addWidget(group_plot, stretch=2)
        main_layout.addLayout(top_layout, stretch=3)
        
        # --- BOTTOM: Log Sniffer Raw ---
        group_log = QtWidgets.QGroupBox("Inspección Profunda de Tramas (Deep Packet Inspection)")
        group_log.setStyleSheet("QGroupBox { border: 2px solid #585b70; border-radius: 5px; font-weight: bold; font-size: 14px; }")
        log_layout = QtWidgets.QVBoxLayout(group_log)
        
        self.console = QtWidgets.QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #11111b; font-family: Consolas, monospace; font-size: 13px; border: none;")
        log_layout.addWidget(self.console)
        
        main_layout.addWidget(group_log, stretch=2)

    def on_packet_sniffed(self, p):
        # 1. Actualizar métricas globales para el Throughput
        self.global_bytes += p['raw_len']
        
        # 2. Actualizar Matriz del Canal
        ch = p['ch']
        self.ch_stats[ch]['pkts'] += 1
        self.ch_stats[ch]['bytes'] += p['len']
        self.table.item(ch, 1).setText(str(self.ch_stats[ch]['pkts']))
        self.table.item(ch, 2).setText(str(self.ch_stats[ch]['bytes']))
        
        # 3. Imprimir en el Log
        t_str = time.strftime('%H:%M:%S', time.localtime(p['time']))
        ms = int((p['time'] % 1) * 1000)
        
        color = "#a6e3a1" if p['valid'] else "#f38ba8"
        tipo = "ACK " if p['is_ack'] else ("DATA(ACK_REQ)" if p['req_ack'] else "DATA")
        seq = str(p['seq']).ljust(3)
        payload = p['payload'] if p['len'] > 0 else "(vacío)"
        
        # Truncar payload si es muy largo para no saturar la pantalla
        if len(payload) > 40: payload = payload[:37] + "..."
            
        crc_status = "OK" if p['valid'] else "FAIL"
        
        log_line = f"<span style='color:{color};'>[{t_str}.{ms:03d}] CH:{ch:02d} | TYPE:{tipo.ljust(13)} | SEQ:{seq} | LEN:{p['len']:03d} | CRC:{crc_status} | PAYLOAD: {payload}</span>"
        self.console.append(log_line)
        
        # Auto-scroll
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_throughput(self):
        # Se llama cada 1 segundo exacto
        bps = self.global_bytes
        self.global_bytes = 0 # Reset para el próximo segundo
        
        self.lbl_throughput.setText(f"{bps:,} Bytes/seg")
        
        self.throughput_history.append(bps)
        self.throughput_history.pop(0)
        self.curve.setData(self.throughput_history)

    def closeEvent(self, e): self.thread.running = False; self.thread.wait(); e.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = AnalyzerWindow()
    w.show()
    sys.exit(app.exec_())