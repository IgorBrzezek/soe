# Serial over Ethernet (SoE) - Complete Documentation

**Author:** Igor Brzezek  
**Latest Version:** 0.0.70  
**Last Updated:** February 4, 2026  
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

The SoE system consists of **three main components** that work together in different topologies:

1. server
2. bridge
3. standalone client
+ terminal app line putty, MobaXterm

### Simple Architecture of SoE:
```

		[Serial Device]
			  |
			  |
		 [serial port] (COM1, /dev/ttyS0, ...)
			  |
			  |
		<soeserver.py>
			/  \
		   /    \	
	 IPnetwork  IPnetwork
		 /        \ 
  <soeclient.py>  <soebridge.py>
					   /\
					  /  \
					 /    \
			[serial port]  [named pipe]
				  |              |
				  |              |
				  |              |
		<terminal> (putty)      <MobaXterm>

```

### Architecture Diagram 1: Three-Component System Overview

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

### Architecture Diagram 3: Data Flow - SoE CLIENT Path

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      DATA FLOW: SoE CLIENT PATH                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SCENARIO: User with SoE CLIENT accesses device on SoE SERVER            │
│                                                                          │
│  ┌──────────────────┐                                                    │
│  │ Physical Serial  │                                                    │
│  │ Device           │                                                    │
│  │ (PLC, Router,    │                                                    │
│  │  etc.)           │                                                    │
│  └────────┬─────────┘                                                    │
│           │                                                              │
│           │ RS-232 / RS-485 Signal                                       │
│           ▼                                                              │
│  ┌──────────────────┐                                                    │
│  │ Serial Port      │                                                    │
│  │ COM1 / ttyS0     │                                                    │
│  │ 9600 baud, 8N1   │                                                    │
│  └────────┬─────────┘                                                    │
│           │                                                              │
│           │ Bytes (bidirectional)                                        │
│           ▼                                                              │
│  ┌────────────────────────────────────────────┐                          │
│  │ SoE SERVER (0.0.53)                       │                          │
│  │                                            │                          │
│  │ ROLE:                                      │                          │
│  │ 1. Read data from serial port              │                          │
│  │ 2. Broadcast to connected clients          │                          │
│  │ 3. Forward client commands to device       │                          │
│  │ 4. Encrypt/decrypt (SSL/TLS)               │                          │
│  │ 5. Authenticate (password)                 │                          │
│  │                                            │                          │
│  │ Listen: 0.0.0.0:10001                      │                          │
│  └────────────────┬───────────────────────────┘                          │
│                   │                                                      │
└───────────────────┼──────────────────────────────────────────────────────┘
                    │
                    │ TCP/IP Packets (encrypted)
                    ▼
          ╔══════════════════════════════════╗
          ║  NETWORK (TCP/IP LAN/WAN/VPN)    ║
          ║  • SSL/TLS Encrypted             ║
          ║  • Custom Handshake              ║
          ║  • Password Authentication       ║
          ║  • Keepalive Heartbeat           ║
          ╚══════════════╤═══════════════════╝
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ MACHINE B: Client Side (User with SoE CLIENT)                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────┐                    │
│  │ SoE CLIENT (0.0.56)                      │                    │
│  │                                          │                    │
│  │ ROLE:                                    │                    │
│  │ 1. Connect to server (TCP client)        │                    │
│  │ 2. Authenticate (password)               │                    │
│  │ 3. Built-in terminal emulator            │                    │
│  │ 4. Read keyboard input                   │                    │
│  │ 5. Send commands to server               │                    │
│  │ 6. Receive data from server              │                    │
│  │ 7. Display output on screen              │                    │
│  │ 8. ANSI colors support                   │                    │
│  │ 9. Arrow key & function key support      │                    │
│  │                                          │                    │
│  │ Connect: 192.168.1.X:10001               │                    │
│  └────────────────────┬─────────────────────┘                    │
│                       │                                          │
│                       │ Keyboard input / Display output          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────┐                    │
│  │ USER AT BUILT-IN TERMINAL                │                    │
│  │                                          │                    │
│  │ • Types commands (keyboard)              │                    │
│  │ • Sees device output (display)           │                    │
│  │ • Feels like local serial connection     │                    │
│  │ • No external terminal needed            │                    │
│  └──────────────────────────────────────────┘                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
 
---
 
### Architecture Diagram 5: Three Component Roles Matrix

```
╔═════════════════════════════════════════════════════════════════════════╗
║                    COMPONENT ROLES AND RESPONSIBILITIES                 ║
╠═════════════════════════════════════════════════════════════════════════╣
║                                                                         ║
║  COMPONENT          │ TYPE      │ ROLE          │ USE CASE              ║
║  ─────────────────────────────────────────────────────────────────────  ║
║                                                                         ║
║  SoE SERVER         │ Listener  │ Gateway       │ Where serial device   ║
║  (0.0.53)          │ (TCP)     │ to hardware   │ is physically         ║
║                     │           │               │ connected             ║
║  Where to run:      │           │               │                       ║
║  Computer A (with   │ • Listens on TCP port     │ Multiple users can    ║
║  physical serial)   │ • Serves many clients     │ access same device    ║
║                     │ • Bidirectional bridge    │                       ║
║                     │ • SSL/TLS server mode     │ Run as service/daemon ║
║                     │ • Password protection     │                       ║
║  ────────────────────────────────────────────────────────────────────   ║
║                                                                         ║
║  SoE CLIENT         │ Connector │ Terminal      │ Where you sit         │
║  (0.0.56)           │ (TCP)     │ emulator      │ interactively         ║
║                     │           │               │                       ║
║  Where to run:      │ • Connects to server      │ Single user at        ║
║  Computer B         │ • Presents terminal UI    │ a time                ║
║  (remote machine)   │ • Keyboard input ↔ output│ (unless sharing term)  │
║                     │ • ANSI color support     │                        ║
║                     │ • Arrow keys & F-keys    │ Interactive sessions   ║
║                     │ • SSL/TLS client mode    │                        ║
║  ────────────────────────────────────────────────────────────────────   ║
║                                                                         ║
║  SoE BRIDGE         │ Connector │ Virtual       │ Where legacy app      ║
║  (0.0.70)           │ (TCP)     │ serial device │ expects local serial  ║
║                     │           │               │ port/pipe             ║
║  Where to run:      │ • Connects to server      │                       ║
║  Computer C         │ • Creates local serial    │ Automates legacy      ║
║  (VM host or        │   port or named pipe     │ app integration        ║
║   legacy app host)  │ • Forwards data         │                         ║
║                     │ • SSL/TLS client mode    │ VM serial access       ║
║                     │ • Named pipe support     │ (QEMU, VMware, etc)    ║
║                     │ • Bi-directional bridge  │                        ║
║  ────────────────────────────────────────────────────────────────────   ║
║                                                                         ║
╚═════════════════════════════════════════════════════════════════════════╝


## Component Breakdown

### 1. **SoE Server** (`serial_server_0.0.53_LinWin.py`)

#### Purpose
Acts as a **TCP server** that listens for incoming connections and bridges a local serial port to remote clients.

#### What It Does
- **Listens** on a specified TCP port (e.g., 10001)
- **Accepts** multiple simultaneous client connections
- **Forwards** data bidirectionally between the local serial port (or Named Pipe) and each connected client
- **Authenticates** clients using optional password protection
- **Encrypts** communication using SSL/TLS
- **Monitors** the system with a rich text UI (TUI)
- **Logs** all events and traffic for debugging

#### Key Features
- **Multi-client Support:** Multiple remote clients can connect simultaneously
- **Advanced TUI:** Split-screen interface showing system logs and real-time traffic
- **Custom Protocol:** Handshake protocol (`__#...#__`) for version exchange and keepalive
- **Flexible Configuration:** CLI arguments or INI-style config file
- **Cross-platform:** Works on Windows (COM1, COM2, etc.) and Linux (/dev/ttyS0, /dev/ttyUSB0, etc.)
- **Named Pipe Support:** (Windows) Can use Named Pipes instead of physical serial ports.

#### When to Use
- A serial device (e.g., industrial PLC, network switch) is physically connected to **Computer A**
- You want multiple users/applications on **Computer B, C, D, etc.** to access this device remotely
- Example: Centralized server managing network switches in a data center

#### Example Configuration
```bash
python serial_server_0.0.53_LinWin.py \
  --port 10001 \
  --comport COM1 \
  --baud 9600 \
  --sec auto \
  --pwd MySecurePassword
```

---

### 2. **SoE Client** (`serial_client_0.0.56_LinWin.py`)

#### Purpose
Acts as a **terminal emulator** that connects to an SoE Server and provides an interactive serial console.

#### What It Does
- **Connects** to a remote SoE Server via TCP
- **Authenticates** using optional password
- **Fetches** remote serial port parameters (baud rate, line settings)
- **Emulates** a terminal with ANSI color support
- **Handles** special keys (arrows, function keys F1-F12)
- **Displays** connection statistics and status information
- **Implements** custom handshake protocol for seamless interaction

#### Key Features
- **User-Friendly Interface:** TUI with status line showing connection stats
- **Terminal Emulation:** Full support for ANSI escape sequences
- **Keyboard Support:** Handles extended keys (arrow keys, function keys) on both Windows and Linux
- **Query Mode:** Check server status without opening a full session
- **Configuration File Support:** Load settings from `soeclient.conf`
- **SSL/TLS:** Secure connections with automatic certificate validation options

#### When to Use
- You are sitting at **Computer B** and need to access a serial device on **Computer A**
- You want an interactive terminal experience (like SSH but for serial ports)
- Example: Remotely managing router console, accessing serial debug ports, controlling industrial equipment

#### Example Usage
```bash
# Simple connection
python serial_client_0.0.56_LinWin.py -H 192.168.1.10 -p 10001

# Secure connection with password
python serial_client_0.0.56_LinWin.py -H 192.168.1.10 -p 10001 --secauto --pwd MyPwd

# Check server status (query mode)
python serial_client_0.0.56_LinWin.py -H 192.168.1.10 -p 10001 --ask

# Load from config file
python serial_client_0.0.56_LinWin.py --cfgfile soeclient.conf
```

---

### 3. **SoE Bridge** (`serial_bridge_0.0.70_LinWin.py`)

#### Purpose
Acts as a **TCP client** that connects to a remote SoE Server and bridges the connection to a local serial port or named pipe.

#### What It Does
- **Initiates** a connection to a remote SoE Server
- **Forwards** network traffic to a **local serial port** or **Windows named pipe**
- **Authenticates** with the server using optional password
- **Encrypts** communication using SSL/TLS
- **Monitors** system activity with TUI
- **Logs** events and traffic
- **Supports** both physical serial ports and virtual pipes

#### Key Features
- **Flexible Local Interface:** 
  - Physical serial ports (COM1, /dev/ttyS0, etc.)
  - Windows named pipes (`\\.\pipe\VMSerial`)
- **Server Role Agnostic:** Acts as a client to connect to SoE Server
- **Named Pipe Support:** Create virtual serial devices for VMs (QEMU, VMware)
- **Advanced Logging:** Binary traffic logging for debugging
- **Custom Handshake:** Protocol negotiation with SoE Server

#### When to Use
- A serial device is on **Computer A** (running SoE Server)
- A legacy application on **Computer B** expects a **local serial port** but it doesn't exist
- You want to make that remote device appear as a local port to the application
- Example: VM needs to access a physical serial port on the host machine; legacy industrial software expects COM1 but device is on network

#### Named Pipe Use Cases
Named pipes are a Windows feature that emulate serial ports for virtual machines:
- Create a pipe on the host (`\\.\pipe\SerialDevice`)
- VM connects to the pipe as if it were a serial port
- Ideal for QEMU, VMware, or other hypervisors

#### Example Usage
```bash
# Bridge to physical serial port
python serial_bridge_0.0.70_LinWin.py -H 192.168.1.10 -p 10001 --comport COM17

# Bridge to named pipe (Windows VM)
python serial_bridge_0.0.70_LinWin.py -H 192.168.1.10 -p 10001 --namedpipe VMSerial

# Secure connection
python serial_bridge_0.0.70_LinWin.py -H 192.168.1.10 -p 10001 --comport COM17 --secauto --pwd MyPwd

# Check server (query mode)
python serial_bridge_0.0.70_LinWin.py -H 192.168.1.10 -p 10001 --ask
```

---

## Use Cases

### Use Case 1: Remote Equipment Access
**Scenario:** Industrial PLC connected to Server PC via serial port; multiple engineers need access.

```
[Industrial PLC] ──COM1── [Server PC] ──[Network]── [Engineer Laptop 1]
                                       ──[Network]── [Engineer Laptop 2]
                                       ──[Network]── [Engineer Laptop 3]

Server PC:  python serial_server_0.0.53_LinWin.py --port 10001 --comport COM1
Laptop 1:   python serial_client_0.0.56_LinWin.py -H 192.168.1.100 -p 10001
Laptop 2:   python serial_client_0.0.56_LinWin.py -H 192.168.1.100 -p 10001
Laptop 3:   python serial_client_0.0.56_LinWin.py -H 192.168.1.100 -p 10001
```

### Use Case 2: Network Switch Management
**Scenario:** Network switch in data center, need centralized console access.

```
[Network Switch] ──RS-232── [Management PC] ──[Data Center Network]── [Admin Workstation]
                                                                      ──[Admin Workstation]
                                                                      ──[Monitoring System]

Management PC:   python serial_server_0.0.53_LinWin.py --port 9600 --comport COM1 --sec auto --pwd AdminPwd
Admin 1:         python serial_client_0.0.56_LinWin.py -H datacenter.local -p 9600 --secauto --pwd AdminPwd
```

### Use Case 3: Virtual Machine Serial Access
**Scenario:** VM needs access to physical serial device on host.

```
[Physical Device] ──COM1── [Host PC] ──[Virtual Network]── [QEMU VM]
                                                             (named pipe)

Host PC:   python serial_bridge_0.0.70_LinWin.py -H localhost -p 10001 --namedpipe VMSerial
Server PC: python serial_server_0.0.53_LinWin.py --port 10001 --comport COM1
VM:        (connect to \\.\pipe\VMSerial as /dev/ttyS0 equivalent)
```

### Use Case 4: Remote Lab Equipment
**Scenario:** Lab equipment at site A, testing software at site B across WAN.

```
[Test Equipment] ──COM2── [Site A Server] ──[WAN/Internet]── [Site B Testing PC]

Site A:   python serial_server_0.0.53_LinWin.py --port 10001 --comport COM2 --sec auto --pwd TestPwd
Site B:   python serial_client_0.0.56_LinWin.py -H siteA.example.com -p 10001 --secauto --pwd TestPwd
```

---

## Quick Start Guide

### Scenario: Connect to a Remote Serial Device

#### Step 1: Start SoE Server on the machine with the physical serial port
```bash
# On Computer A (which has the serial device on COM1)
python serial_server_0.0.53_LinWin.py \
  --port 10001 \
  --comport COM1 \
  --baud 9600 \
  --sec auto \
  --pwd MyPassword
```

#### Step 2: Start SoE Client on the remote machine
```bash
# On Computer B (where you want to access the device)
python serial_client_0.0.56_LinWin.py \
  -H 192.168.1.100 \
  -p 10001 \
  --secauto \
  --pwd MyPassword
```

#### Step 3: Interact with the device
Once connected, your keyboard input is sent to the serial port, and any output is displayed on your screen—just like a direct serial connection!

---

## Installation

### Prerequisites
- **Python 3.6 or later** (check with `python --version`)
- **pip** package manager (usually comes with Python)

### Step 1: Install Python Dependencies

#### For SoE Server:
```bash
pip install pyserial cryptography
```

#### For SoE Client:
```bash
pip install cryptography
```

#### For SoE Bridge:
```bash
pip install pyserial cryptography
```

#### For Windows Named Pipe Support (Bridge only):
```bash
pip install pywin32
```

### Step 2: Download the Scripts
All three scripts are standalone Python files. Simply place them in your working directory:
- `serial_server_0.0.53_LinWin.py`
- `serial_client_0.0.56_LinWin.py`
- `serial_bridge_0.0.70_LinWin.py`

### Step 3: Verify Installation
Test each script with the help command:
```bash
python serial_server_0.0.53_LinWin.py --help
python serial_client_0.0.56_LinWin.py --help
python serial_bridge_0.0.70_LinWin.py --help
```

---

## Security Features

### 1. SSL/TLS Encryption
All three components support SSL/TLS for encrypted communication:

**Auto-generate certificates (self-signed):**
```bash
python serial_server_0.0.53_LinWin.py --port 10001 --comport COM1 --secauto
```

**Use custom certificates:**
```bash
python serial_server_0.0.53_LinWin.py --port 10001 --comport COM1 --sec /path/to/cert.pem
```

**Client connection (with auto certificate acceptance):**
```bash
python serial_client_0.0.56_LinWin.py -H 192.168.1.10 -p 10001 --secauto
```

### 2. Password Authentication
Protect access with a password:

**Server:**
```bash
python serial_server_0.0.53_LinWin.py --port 10001 --comport COM1 --pwd MySecretPassword
```

**Client:**
```bash
python serial_client_0.0.56_LinWin.py -H 192.168.1.10 -p 10001 --pwd MySecretPassword
```

### 3. Best Practices
- ✓ Always use `--secauto` or `--sec` in production
- ✓ Use strong passwords (mix uppercase, lowercase, numbers, special chars)
- ✓ Change default passwords regularly
- ✓ Run on trusted networks when possible
- ✓ Monitor logs for suspicious connection attempts
- ✓ Use VPN for WAN connections

---

## Protocol & Communication

### Custom SoE Handshake Protocol

The three components communicate using a custom protocol based on special command sequences. These are handled transparently but understanding them is useful for debugging:

#### Protocol Commands
| Command | Purpose |
|---------|---------|
| `__#ASK_COM_PARAMS#__` | Request serial port parameters |
| `__#DISCONNECT#__` | Gracefully disconnect |
| `__#KEEPALIVE#__` | Keep connection alive (heartbeat) |
| `__#RELOAD#__` | Reload configuration |
| `__#SHUTDOWN#__` | Shutdown the server |
| `__#GETVER#__` | Get version information |
| `__#GET_KA_TIMEOUT#__` | Request keepalive timeout value |
| `__#MY_KA_TIMEOUT_` | Send keepalive timeout value |
| `__#SECERROR#__` | SSL/TLS error notification |
| `__#BADPWD#__` | Authentication failure |

#### Example Handshake Flow
```
Client                              Server
  |                                   |
  |------- TCP CONNECT ------->       |
  |                                   |
  |<----- WELCOME MESSAGE -----       |
  |                                   |
  |--- __#GETVER#__ ------->          |
  |<---- VERSION INFO -----           |
  |                                   |
  |--- __#ASK_COM_PARAMS#__ ------>   |
  |<---- COM PARAMS (9600, 8N1) ---   |
  |                                   |
  |--- __#MY_KA_TIMEOUT_ 30 ------>   |
  |<---- ACK -----                    |
  |                                   |
  | <DATA STREAMING BEGINS>           |
  |<--------- SERIAL DATA -------->   |
  |<--------- SERIAL DATA -------->   |
  |                                   |
```

---

## Configuration

### Configuration Files
All three components support configuration files in INI format:

**Default search locations:**
1. `/etc/soe/soeserver.conf` (Linux)
2. `./soeserver.conf` (current directory)
3. `./soeclient.conf` (current directory)
4. `./soebridge.conf` (current directory)
5. Custom path via `--cfgfile` argument

### Example Configuration Files

**soeserver.conf:**
```ini
[DEFAULT]
port = 10001
address = 0.0.0.0
comport = COM1
baud = 9600
line = 8N1N
keepalive = 30
secauto = True
pwd = MySecurePassword
log = logs/server.log
debug = False
color = True
```

**soeclient.conf:**
```ini
[DEFAULT]
host = 192.168.1.10
port = 10001
secauto = True
pwd = MySecurePassword
echo = False
```

**soebridge.conf:**
```ini
[DEFAULT]
host = 192.168.1.10
port = 10001
comport = COM17
baud = 9600
secauto = True
pwd = MySecurePassword
```

### CLI Arguments vs Configuration Files
CLI arguments **override** configuration file values:
```bash
# Load from config but override port
python serial_server_0.0.53_LinWin.py --cfgfile soeserver.conf --port 9999
```

---

## Troubleshooting

### Common Issues

#### 1. "Port already in use" Error
**Problem:** Server fails to start with "Address already in use" error.

**Solution:**
```bash
# Change to a different port
python serial_server_0.0.53_LinWin.py --port 10002 --comport COM1

# On Linux, find and kill the process using the port:
lsof -i :10001
kill -9 <PID>

# On Windows, use netstat:
netstat -ano | findstr :10001
taskkill /PID <PID> /F
```

#### 2. "Permission Denied" for Serial Port
**Problem:** Cannot open serial port.

**Solution:**
```bash
# On Linux, add user to dialout group:
sudo usermod -a -G dialout $USER
newgrp dialout

# On Windows, ensure no other application is using the port
# Check Device Manager for serial port usage
```

#### 3. "ModuleNotFoundError: No module named 'serial'"
**Problem:** pyserial not installed.

**Solution:**
```bash
pip install pyserial
```

#### 4. "ModuleNotFoundError: No module named 'cryptography'"
**Problem:** cryptography library not installed (needed for SSL).

**Solution:**
```bash
pip install cryptography
```

#### 5. SSL Certificate Errors
**Problem:** "SSL: CERTIFICATE_VERIFY_FAILED" when connecting.

**Solution:**
Use `--secauto` on client side to accept self-signed certificates:
```bash
python serial_client_0.0.56_LinWin.py -H 192.168.1.10 -p 10001 --secauto
```

#### 6. "Connection Refused" from Client
**Problem:** Client cannot connect to server.

**Checklist:**
- Server is running: `python serial_server_0.0.53_LinWin.py --port 10001 ...`
- Server IP address is correct (use `ipconfig` on Windows, `ifconfig` on Linux)
- Server port matches client port
- Firewall allows the port (port 10001 must be open)
- Network connectivity exists between machines: `ping 192.168.1.10`

**Solution:**
```bash
# Temporarily disable firewall for testing (not recommended for production)
# Or allow the specific port in firewall settings

# Linux:
sudo firewall-cmd --add-port=10001/tcp --permanent
sudo firewall-cmd --reload

# Windows Firewall: Allow Python through Windows Defender
```

#### 7. Slow or Laggy Connection
**Problem:** Data transfer is slow or has high latency.

**Diagnostics:**
```bash
# Check network latency
ping 192.168.1.10

# Monitor server logs with debug mode
python serial_server_0.0.53_LinWin.py --debug ...

# Check for packet loss on network
```

**Solutions:**
- Reduce network overhead (turn off unnecessary logging)
- Increase keepalive timeout: `--keepalive 60`
- Check network bandwidth availability
- Consider reducing TUI update frequency in batch mode: `--batch`

#### 8. Data Corruption
**Problem:** Received data appears corrupted.

**Diagnosis:**
- Enable logging with `--logdata` to capture raw traffic
- Check serial port baud rate matches: `--baud 9600`
- Verify line settings: `--line 8N1N`
- Check for flow control issues

**Solution:**
```bash
# Verify baud rate and settings match device
python serial_server_0.0.53_LinWin.py \
  --port 10001 \
  --comport COM1 \
  --baud 115200 \
  --line 8N1N \
  --logdata traffic.log
```

### Getting Help

For detailed component-specific documentation, see:
- `README_SoEServer.md` - SoE Server detailed guide
- `README_SoEClient.md` - SoE Client detailed guide
- `README_SoEBridge.md` - SoE Bridge detailed guide
- `README_Config.md` - Configuration file detailed reference
- `SoE_SSL.md` - SSL/TLS security details

### Reporting Issues

When reporting issues, include:
1. Component name and version
2. Operating system (Windows 10, Ubuntu 20.04, etc.)
3. Python version
4. Steps to reproduce the issue
5. Error messages (run with `--debug` for verbose output)
6. Configuration being used
7. Logs from `--logdata` if applicable

---

## Summary

**Serial over Ethernet** is a complete solution for extending serial port communication over networks. The three components work together to enable:

- **SoE Server:** Listens and shares a serial port with multiple remote clients
- **SoE Client:** Interactive terminal client for accessing remote serial devices
- **SoE Bridge:** Bridges network connection to local serial port or named pipe

Perfect for:
✓ Remote equipment management  
✓ Centralized device access  
✓ Legacy hardware integration  
✓ Virtual machine serial access  
✓ WAN/Internet serial communication  
✓ Secure encrypted serial tunneling  

---

**For more information, visit:** https://github.com/igorbrzezek

**Author:** Igor Brzezek  
**License:** See included LICENSE file
