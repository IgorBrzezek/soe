# Serial over Ethernet Server (SoE Server)

**Program:** `serial_server.py`
**Version:** 0.0.52b
**Platform:** Windows / Linux (Cross-platform)
**Author:** Igor Brzezek

## 0. Suggestion: 

Rename the file to: soeserver.py

## 1. Description

**SoE Server** is a robust, multi-threaded Python application designed to act as a transparent bridge between a local Serial Port (COM/TTY) and a TCP/IP network. It operates as a **TCP Server**, listening for incoming connections from remote clients (such as the corresponding *SoE Client* or generic terminal software) and bidirectional forwarding data between the serial interface and the network socket.

The "LinWin" suffix indicates native support for both **Linux** (e.g., `/dev/ttyUSB0`) and **Windows** (e.g., `COM1`) environments, with automatic OS detection for specific features like keyboard handling and color support.

### Key Features
*   **Bidirectional Bridging:** Full-duplex communication between Serial and TCP.
*   **Advanced TUI (Text User Interface):** Split-screen terminal interface showing system logs and real-time data traffic simultaneously.
*   **Security:** Built-in SSL/TLS encryption (auto-generated or custom certificates) and password-based authorization.
*   **Protocol Handshake:** Supports a custom handshake protocol to exchange version info, keepalives, and serial port parameters with compatible clients (e.g., `serial_client`).
*   **Logging:** Comprehensive rotation-based logging for system events and raw binary data traffic.
*   **Cross-Platform:** unified codebase for Windows and Linux.
*   **Configurable:** Fully controllable via command-line arguments or a hierarchical configuration file (`soeserver.conf`).

---

## 2. Requirements & Installation

The application requires **Python 3.6+**.

### Dependencies
The program checks for missing libraries on startup.
*   **pyserial** (Required): For serial port communication.
*   **cryptography** (Optional): Required only if using SSL/TLS features (`--sec` or `--secauto`).

**Installation:**
```bash
pip install pyserial cryptography
```

---

## 3. Usage & Quick Start

### Basic Usage
To start the server bridging `COM1` to TCP port `10001`:

```bash
python serial_server.py --port 10001 --comport COM1 --baud 9600
```

### Modes of Operation
1.  **TUI Mode (Default):** displays a rich interface with split windows.
2.  **Batch Mode (`-b` or `--batch`):** No output to stdout/interface (useful for background services/daemons).
3.  **No-TUI Mode (`--notui`):** Prints simple line-by-line logs to stdout without the complex interface.

---

## 4. Configuration File (`soeserver.conf`)

The program looks for a configuration file in the following order:
1.  `/etc/soe/soeserver.conf`
2.  `./soeserver.conf` (Current directory)
3.  File specified by `--cfgfile` argument.

The configuration file uses standard INI format. Below is a detailed explanation of all supported parameters.

### `[DEFAULT]` Section
This section controls the core functionality.

#### Communication Settings
| Parameter | Description | Default |
| :--- | :--- | :--- |
| `port` | **Required.** TCP port to listen on. | `None` (Must be set) |
| `address` | IP address to bind to. `0.0.0.0` listens on all interfaces. | `0.0.0.0` |
| `comport` | Serial port identifier (e.g., `COM1` or `/dev/ttyS0`). | OS Dependent |
| `baud` | Serial baud rate (speed). | `9600` |
| `line` | Connection parameters in format `8N1N` (Bits/Parity/Stop/Flow). | `8N1N` |
| `keepalive` | Interval (in seconds) for protocol heartbeat messages. | `120` |

#### Security
| Parameter | Description | Default |
| :--- | :--- | :--- |
| `pwd` | Password required for client connection. If empty, auth is open. | `None` |
| `secauto` | `True/False`. Enable SSL with auto-generated self-signed cert. | `False` |
| `sec` | Path to custom certs: `cert.pem,key.pem`. | `None` |

#### Logging
| Parameter | Description | Default |
| :--- | :--- | :--- |
| `log` | Filename for system event logs. Append `,new` to rotate on start. | `None` |
| `logmax` | Max number of rotated log files to keep. | `10` |
| `logsizemax` | Max size (KB) before rotating log files. | `4096` |
| `logdata` | Filename for **RAW** binary traffic dump. | `None` |
| `logdatamax` | Max number of data log files. | `10` |
| `logdatasizemax` | Max size (KB) of data log files. | `8192` |

#### Interface & Debug
| Parameter | Description | Default |
| :--- | :--- | :--- |
| `debug` | Enable verbose internal debug messages. | `False` |
| `color` | Force enable ANSI colors. | `False` |
| `count` | Show byte counters (IN/OUT) in the status bar. | `False` |
| `showtransfer`| Show data in TUI. Format: `mode,filter` (e.g., `ascii,all` or `hex,in`). | `None` |
| `notui` | Disable the TUI window manager (simple text output). | `False` |
| `batch` | Silent mode (no output). | `False` |
| `logbufferlines`| Number of lines to keep in the System Log scrollback. | `2000` |
| `transferbufferlines`| Number of lines to keep in the Data Monitor scrollback. | `2000` |

### `[COLORS]` Section
Allows customization of the TUI colors.
*   **Keys:** `version`, `lip`, `rip`, `dir_in`, `dir_out`, `bg_statusline`, etc.
*   **Values:** `RED`, `GREEN`, `YELLOW`, `BLUE`, `MAGENTA`, `CYAN`, `WHITE`, `BG_RED`, `BG_BLUE`, etc.

---

## 5. Command Line Arguments

CLI arguments override settings in the config file.

| Argument | Description |
| :--- | :--- |
| `-p`, `--port` | TCP Listening Port. |
| `-a`, `--address` | Interface IP to bind (default 0.0.0.0). |
| `--comport` | Serial port name. |
| `--baud` | Serial baud rate. |
| `--line` | Serial parameters (e.g., `8N1N`). |
| `--pwd` | Set connection password. |
| `--secauto` | Enable automatic SSL (requires `cryptography`). |
| `--sec CERT,KEY` | Enable SSL with specific cert/key files. |
| `--log FILE[,new]` | Enable system logging to file. |
| `--logdata FILE` | Enable raw data logging to file. |
| `--showtransfer` | Enable data visualization (e.g., `--showtransfer ascii,all`). |
| `--color`, `--mono` | Force color on/off. |
| `-b`, `--batch` | Run without any console output. |
| `--notui` | Run with standard stdout output (no window management). |
| `--cfgfile FILE` | Load specific configuration file. |

---

## 6. Interface (TUI) & Controls

When running in default mode, the screen is divided into sections:

1.  **Header:** Shows status, SSL mode, version, and buffer usage.
2.  **Window 0 (Top):** System Logs (connections, errors, status changes).
3.  **Window 1 (Bottom):** Data Transfer Monitor (real-time ASCII/HEX view of traffic).
4.  **Status Line (Bottom):** Connection details, IP/Ports, Baud rates, Counters.

### Keyboard Shortcuts
*   `TAB`: Switch focus between **System Log** and **Data Monitor** windows.
*   `UP` / `DOWN` Arrows: Scroll the text in the currently active window.
*   `CTRL+C`: Graceful shutdown (closes ports/sockets and exits).

---

## 7. Protocol & Security

### Handshake Protocol
The server uses a custom handshake (starting with `__#`) to negotiate with compatible clients (`serial_client`). This allows:
*   Version checking (`GETVER`).
*   Keepalive synchronization (`KEEPALIVE`).
*   Remote serial parameter display (Server can see Client's COM settings and vice versa).

### Security Modes
1.  **RAW (Default):** Plain TCP. Data is sent as-is.
2.  **Protected (`--pwd`):** Client must send a password hash immediately upon connection. If the password fails, the server sends `__#BADPWD#__` and disconnects.
3.  **SSL/TLS (`--sec` / `--secauto`):** The TCP socket is wrapped in SSL.
    *   `--secauto`: Generates a temporary self-signed certificate in memory.
    *   Ensure the client is configured to accept self-signed certs or verify against the CA if using real certificates.

---

## 8. Examples

### Example 1: Simple Debug Server
Listen on port 5000, bridge to Windows COM3, show hex data on screen.
```bash
python serial_server.py -p 5000 --comport COM3 --showtransfer hex,all
```

### Example 2: Secure Linux Server
Listen on all interfaces, port 8888, bridge to `/dev/ttyUSB0`, use SSL auto-generation, require password `secret`, and log everything to files.
```bash
python serial_server.py \
  --port 8888 \
  --comport /dev/ttyUSB0 \
  --baud 115200 \
  --secauto \
  --pwd secret \
  --log /var/log/soe_sys.log \
  --logdata /var/log/soe_data.bin
```

### Example 3: Using Configuration File
```bash
python serial_server.py --cfgfile ./mysettings.conf
```
*(Where `mysettings.conf` contains the override parameters)*.
