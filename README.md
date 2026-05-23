# UART-VC: Sistema de Conexión UART mediante Canales Virtuales

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![C - Firmware](https://img.shields.io/badge/C-Bare--Metal-A8B9CC?logo=c&logoColor=white)]()
[![Python - Middleware](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)]()
[![Hardware - STM32](https://img.shields.io/badge/Hardware-STM32-03234B?logo=stmicroelectronics&logoColor=white)]()

UART-VC es un protocolo de red ligero y un *middleware* diseñado para dotar a las interfaces asíncronas tradicionales (UART) de capacidades avanzadas de multiplexación, fiabilidad y comportamiento en tiempo real.

Este proyecto permite que una única conexión física serie se comporte como múltiples canales lógicos independientes (hasta 16), aislando el tráfico crítico de control de la telemetría masiva y los *logs* de depuración. Es una solución ideal para la modernización de maquinaria industrial, robótica y sistemas empotrados con recursos de I/O limitados.

## 📋 Tabla de Contenidos
- [Características Principales](#-características-principales)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Estructura del Protocolo](#-estructura-del-protocolo)
- [Instalación y Despliegue](#-instalación-y-despliegue)
- [Uso y Herramientas](#-uso-y-herramientas)
- [Trabajo Futuro](#-trabajo-futuro)
- [Contribución](#-contribución)
- [Licencia](#-licencia)

## 🚀 Características Principales

- **Multiplexación de Canales (QoS):** Soporta hasta 16 canales virtuales con un planificador (*Scheduler*) basado en *Round-Robin* ponderado por ráfagas.
- **Preempción en Tiempo Real:** Los comandos de alta prioridad pueden interrumpir instantáneamente la transmisión de flujos masivos de baja prioridad (latencia media RTT de ~0.5 ms).
- **Alta Fiabilidad (ARQ):** Implementa un esquema de control de flujo *Stop-and-Wait* con números de secuencia (SEQ) y retransmisión automática para recuperar paquetes perdidos.
- **Integridad y Transparencia:** Uso de *Byte-Stuffing* continuo al vuelo y validación matemática de tramas mediante el algoritmo CRC8.
- **Compatibilidad Dual-Mode:** Permite entrelazar paquetes binarios multiplexados con texto ASCII tradicional para mantener la depuración nativa activa.

## 🏗 Arquitectura del Sistema

El ecosistema UART-VC se divide de forma estricta en dos dominios:

1. **Firmware Embebido (C / STM32):** Diseñado bajo el paradigma *Bare-Metal*. Delega la recepción asíncrona al controlador DMA y procesa la información mediante una Máquina de Estados Finitos (FSM) de alta eficiencia.
2. **Demonio Enrutador (Python):** Un *middleware* concurrente que actúa como *Gateway* en el ordenador anfitrión. Ingiere el flujo de datos físicos, lo demultiplexa y enruta las cargas útiles hacia puertos COM virtuales (o *pseudoterminales* PTY), haciéndolo 100% transparente para las aplicaciones cliente.

## 📦 Estructura del Protocolo

El encapsulamiento se realiza mediante una trama de longitud variable (hasta 64 bytes de *payload* por defecto):

| START | HDR | LEN | SEQ (Opcional) | PAYLOAD | CRC8 |
| :---: | :---: | :---: | :---: | :---: | :---: |
| `0x7E` | `Control + Channel ID` | `0-255` | `Ack Sequence` | `Datos brutos` | `Firma` |

## 🛠 Instalación y Despliegue

### Prerrequisitos
- **Hardware:** Placa de desarrollo de la familia STM32 (Validado en STM32F746ZG Nucleo-144).
- **Software Host:** Python 3.x y emuladores de puertos *Null-Modem* (ej. VSPE en Windows).

### Compilación del Firmware (STM32)
1. Clona el repositorio: `git clone https://github.com/pegedev0/uart-virtual-channels.git`.
2. Abre el proyecto situado en la carpeta `/firmware` utilizando **STM32CubeIDE**.
3. Compila el proyecto y carga (*flash*) el código binario en la placa.

### Configuración del Host (Python)
1. Instala las dependencias del *middleware* y el *Dashboard*:
```bash
pip install pyserial PyQt5 matplotlib pyqtgraph
```
2. Crea los túneles virtuales en tu sistema operativo (por ejemplo, emparejando COM10 con COM11).

## 💻 Uso y Herramientas

El proyecto incluye herramientas nativas para visualizar y diagnosticar el flujo de red.

### 1. Demonio Enrutador (Gateway transparente)
Ejecuta el script principal para iniciar la demultiplexación desde el puerto físico hacia los puertos virtuales. Asegúrate de modificar los argumentos para que coincidan con tu configuración de hardware y tu software *Null-Modem*:

```bash
python daemon_enrutador.py --port COM3 --vport1 COM10 --vport2 COM20
```

### 2. Dashboard de Diagnóstico (PyQt5)
Para monitorizar el estado de la red en tiempo real, auditar el ancho de banda útil (Goodput) y visualizar la telemetría interactiva de los 16 canales:  
```bash
python dashboard.py
```

## 🤝 Contribución
¡Las contribuciones son bienvenidas! El objetivo de hacer público este proyecto es que la comunidad académica y el sector industrial puedan auditar la arquitectura, adaptar el protocolo a sus placas o proponer mejoras. Siéntete libre de abrir un Issue o enviar un Pull Request.  

## 📄 Licencia
Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo LICENSE para más información.Este proyecto fue desarrollado originalmente como Trabajo de Fin de Grado en Ingeniería de Computadores (Universidad de Sevilla).
