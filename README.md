# Serial over Ethernet (SoE) - Complete Documentation

**Author:** Igor Brzezek  
**Latest Version:** 0.0.70  
**Last Updated:** February 5, 2026  
**Platform:** Windows / Linux (Cross-platform)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Component Breakdown](#component-breakdown)
4. [Use Cases](#use-cases)
5. [Quick Start Guide](#quick-start-guide)
6. [Installation](#installation)
7. [Security Features](#security-features)
8. [Protocol & Communication](#protocol--communication)
9. [Configuration](#configuration)
10. [Troubleshooting](#troubleshooting)

---

## Project Overview

**Serial over Ethernet (SoE)** is a robust, multi-threaded Python-based system designed to transparently bridge serial port communication over TCP/IP networks. It allows you to access serial devices (COM/TTY ports) from remote machines as if they were directly connected locally.

### What is Serial over Ethernet?

Serial over Ethernet encapsulates serial port data (typically used for connecting to legacy hardware like industrial controllers, network devices, and embedded systems) into standard TCP/IP packets, enabling:

- **Remote Access:** Connect to serial devices from anywhere on the network
- **Network Transparency:** Use standard networking infrastructure (LAN, WAN, VPN)
- **Bi-directional Communication:** Full-duplex data transfer
- **Security:** SSL/TLS encryption and password authentication
- **Multiple Clients:** Support for multiple simultaneous remote connections (SoE Server architecture)

### Why Use Serial over Ethernet?

Traditional serial ports are limited to short cable distances (typically ~50 meters for RS-232). Serial over Ethernet overcomes these limitations by:

✓ Extending serial device reach across entire networks  
✓ Eliminating expensive serial-to-fiber converters  
✓ Providing secure, encrypted communication  
✓ Enabling centralized device management  
✓ Supporting legacy hardware with modern networks  

---

## System Architecture

The SoE system consists of **four main components** that work together in different topologies:

1. **SoE Server**: Bridges physical serial port to network.
2. **SoE Bridge**: Connects network back to a local serial port/pipe.
3. **SoE Client**: Standalone terminal client.
4. **Serial Emulator**: Simulates a physical Cisco-like device for testing.

+ terminal apps like Putty, MobaXterm

### Architecture Diagram 1: System Overview

```
╔════════════════════════════════════════════════════════════════════════════╗
║                  SERIAL OVER ETHERNET (SoE) SYSTEM                         ║
╚════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────┐
│ MACHINE A: Server Side (Physical Serial Device Present)             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐                                               │
│  │ Physical Serial  │                                               │
│  │ Device           │                                               │
│  │ (PLC, Router,    │                                               │
│  │  Sensor, etc.)   │                                               │
│  └────────┬─────────┘                                               │
│           │                                                         │
│           │ Serial Connection (RS-232/RS-485)                       │
│           ▼                                                         │
│  ┌──────────────────┐                                               │
│  │ Serial Port      │                                               │
│  │ COM1 / ttyS0     │                                               │
│  └────────┬─────────┘                                               │
│           │                                                         │
│           │ Serial Data (bidirectional)                             │
│           ▼                                                         │
│  ┌───────────────────────────────────────────┐                      │
│  │ SoE SERVER (0.0.53)                       │                      │
│  │                                           │                      │
│  │ Listens on TCP port                       │                      │
│  │ Exposes IP:Port for clients               │                      │
│  │ Supports SSL/TLS encryption               │                      │
│  │ Password authentication                   │                      │
│  │ Supports Named Pipes (Windows)            │                      │
│  └────────────────┬──────────────────────────┘                      │
│                   │                                                 │
└───────────────────┼─────────────────────────────────────────────────┘
                    │
                    │ TCP/IP Connection (encrypted)
                    ▼
          ╔════════════════════════════════════╗
          ║   NETWORK (LAN/WAN/VPN)            ║
          ║   • SSL/TLS Encrypted              ║
          ║   • Password Protected             ║
          ║   • Custom Protocol Handshake      ║
          ╚═════════════╤══════════════════════╝
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│ MACHINE B      │ │ MACHINE C      │ │ MACHINE D      │
├────────────────┤ ├────────────────┤ ├────────────────┤
│                │ │                │ │                │
│ ┌────────────┐ │ │ ┌────────────┐ │ │ ┌────────────┐ │
│ │ SoE CLIENT │ │ │ │ SoE CLIENT │ │ │ │ SoE BRIDGE │ │
│ │ (0.0.56)   │ │ │ │ (0.0.56)   │ │ │ │ (0.0.70)   │ │
│ │            │ │ │ │            │ │ │ │            │ │
│ │ Connects   │ │ │ │ Connects   │ │ │ │ Connects   │ │
│ │ to server  │ │ │ │ to server  │ │ │ │ to server  │ │
│ │ IP:Port    │ │ │ │ IP:Port    │ │ │ │ IP:Port    │ │
│ └─────┬──────┘ │ │ └─────┬──────┘ │ │ └─────┬──────┘ │
│       │        │ │       │        │ │       │        │
│ ┌─────▼──────┐ │ │ ┌─────▼──────┐ │ │ ┌─────▼──────┐ │
│ │ Built-in   │ │ │ │ Built-in   │ │ │ │ Creates    │ │
│ │ Terminal   │ │ │ │ Terminal   │ │ │ │ Named Pipe │ │
│ │ Emulator   │ │ │ │ Emulator   │ │ │ │ or uses    │ │
│ │            │ │ │ │            │ │ │ │ COM port   │ │
│ │ User types │ │ │ │ User types │ │ │ │            │ │
│ │ directly   │ │ │ │ directly   │ │ │ └─────┬──────┘ │
│ └────────────┘ │ │ └────────────┘ │ │       │        │
└────────────────┘ └────────────────┘ │ ┌─────▼──────┐ │
                                      │ │ External   │ │
                                      │ │ Terminal   │ │
                                      │ │ (Putty/    │ │
                                      │ │ MobaXterm) │ │
                                      │ └────────────┘ │
                                      └────────────────┘

KEY:
  ──────────────────────────────────────────────────────────────────────────────
  • SoE SERVER: Connects to physical serial port, exposes TCP/IP port
  • SoE CLIENT: Connects to server, has built-in terminal (no external app)
  • SoE BRIDGE: Connects to server, creates named pipe/COM for external terminal
```

---

## Component Breakdown

### 1. **SoE Server** (`serial_server_0.0.53_LinWin.py`)

#### Purpose
Acts as a **TCP server** that listens for incoming connections and bridges a local serial port to remote clients.

#### Key Features
- **Multi-client Support:** Multiple remote clients can connect simultaneously.
- **Advanced TUI:** Split-screen interface showing system logs and real-time traffic.
- **Custom Protocol:** Handshake protocol (`__#...#__`) for version exchange and keepalive.
- **Flexible Configuration:** CLI arguments or INI-style config file (`soeserver.conf`).
- **Cross-platform:** Works on Windows (COM1) and Linux (/dev/ttyS0).
- **Named Pipe Support:** (Windows) Can use Named Pipes (`--namedpipe`) instead of physical serial ports.
- **Security:** SSL/TLS support and password protection.

#### Example Usage
```bash
# Physical Serial Port
python serial_server_0.0.53_LinWin.py --port 10001 --comport COM1 --baud 9600

# Windows Named Pipe
python serial_server_0.0.53_LinWin.py --port 10001 --namedpipe MyPipe
```

---

### 2. **SoE Client** (`serial_client_0.0.56_LinWin.py`)

#### Purpose
Acts as a **terminal emulator** that connects to an SoE Server and provides an interactive serial console.

#### Key Features
- **User-Friendly Interface:** TUI with status line showing connection stats.
- **Terminal Emulation:** Full support for ANSI escape sequences.
- **Keyboard Support:** Handles extended keys (arrow keys, function keys).
- **SSL/TLS:** Secure connections with automatic certificate validation options.
- **Configuration:** CLI arguments or config file (`soeclient.conf`).

#### Example Usage
```bash
python serial_client_0.0.56_LinWin.py -H 192.168.1.10 -p 10001 --secauto
```

---

### 3. **SoE Bridge** (`serial_bridge_0.0.70_LinWin.py`)

#### Purpose
Acts as a **TCP client** that connects to a remote SoE Server and bridges the connection to a **local** serial port or named pipe.

#### Key Features
- **Flexible Local Interface:** Physical serial ports or Windows named pipes.
- **Named Pipe Support:** Create virtual serial devices for VMs (QEMU, VMware).
- **Advanced Logging:** Binary traffic logging for debugging.
- **Custom Handshake:** Protocol negotiation with SoE Server.
- **Configuration:** CLI arguments or config file (`soebridge.conf`).

#### Example Usage
```bash
# Bridge to local named pipe (e.g., for VM)
python serial_bridge_0.0.70_LinWin.py -H 192.168.1.10 -p 10001 --namedpipe VMSerial
```

---

### 4. **Serial Emulator** (`serial_emu.py`) (v0.0.7)

#### Purpose
Simulates a Cisco-like physical device (router/switch) on a serial port or named pipe. Useful for testing without real hardware.

#### Key Features
- **Cisco-like CLI:** Supports `enable`, `configure terminal`, `show running-config`, etc.
- **System Integration:** Maps simulated commands to real OS commands (e.g., `show interfaces` -> `ipconfig`/`ip addr`).
- **Dual Mode:** Can act as a physical device on a COM port or a Named Pipe.
- **Configuration:** `serial_emu.conf` and `emu_commands.txt`.

#### Example Usage
```bash
# Simulate a device on a Named Pipe
python serial_emu.py --namedpipe device-sim --tui
```

---

## Installation

### Prerequisites
- **Python 3.6 or later**
- **pip** package manager

### Dependencies

#### Windows (Full Support)
```bash
pip install pyserial cryptography pywin32
```

#### Linux
```bash
pip install pyserial cryptography
```

---

## Quick Start Guide

### Scenario: Connect to a Remote Serial Device

1.  **Server Side (Computer A with Device on COM1):**
    ```bash
    python serial_server_0.0.53_LinWin.py --port 10001 --comport COM1 --secauto --pwd MySecret
    ```

2.  **Client Side (Computer B):**
    ```bash
    python serial_client_0.0.56_LinWin.py -H <IP_OF_A> -p 10001 --secauto --pwd MySecret
    ```

---

## Security Features

### 1. SSL/TLS Encryption
Use `--secauto` to automatically generate self-signed certificates or `--sec cert.pem,key.pem` for custom certificates.

### 2. Password Authentication
Use `--pwd <password>` on both Server and Client/Bridge to enforce authentication.

---

## Configuration Files

See `README_Config.md` for detailed configuration file syntax.

- **Server:** `soeserver.conf`
- **Client:** `soeclient.conf`
- **Bridge:** `soebridge.conf`
- **Emulator:** `serial_emu.conf`

---

## Troubleshooting

1.  **Named Pipe Error:** Ensure `pywin32` is installed (`pip install pywin32`).
2.  **Permission Denied:** Run as Administrator (Windows) or use `sudo`/dialout group (Linux).
3.  **Port in Use:** Check if another application (or instance) is using the COM port or TCP port.

---

**For more information, visit:** https://github.com/igorbrzezek
