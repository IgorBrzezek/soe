# Serial over Ethernet Client (SoE Client)

**Program:** `serial_client.py`
**Version:** 0.0.56
**Platform:** Windows / Linux (Cross-platform)
**Author:** Igor Brzezek

## 0. Suggestion: 

Rename the file to: soeclient.py

## 1. Description

**SoE Client** is a specialized TCP terminal client designed to interact with the **SoE Server**. Unlike generic tools (like Telnet or PuTTY), this client implements the custom SoE handshake protocol (`__#...#__`), allowing it to:
*   Identify itself to the server as a human interface ("CL").
*   Exchange version information and keepalive settings.
*   Authenticate using a password hash.
*   **View Remote Serial Parameters:** Automatically fetch and display the baud rate and line settings of the remote physical serial port connected to the server.

It functions essentially as a "Remote Console" for the serial device attached to the server, handling input (keyboard) and output (screen) with support for ANSI colors and special keys (arrows, function keys).

### Key Features (v0.0.56)
*   **NEW:** Configuration File Support (`--cfgfile`) allows loading settings from a file instead of typing long command-line arguments.
*   **Smart Protocol Support:** Handles SoE handshakes hidden from the user view.
*   **Terminal Emulation:** Supports ANSI escape sequences, arrow keys, and function keys (F1-F12) for interacting with complex CLI devices (like Routers/Switches) remotely.
*   **TUI (Text User Interface):** Uses a "protected" scrolling region with a static status line at the bottom (and optionally top) to show connection stats without interfering with the terminal output.
*   **Cross-Platform:** Native support for Windows (`msvcrt`) and Linux (`termios/tty`) keyboard handling.
*   **Security:** Full SSL/TLS support (connects to secure SoE Servers).

---

## 2. Requirements & Installation

The application requires **Python 3.6+**.

### Dependencies
No external dependencies are strictly required for basic operation (uses standard library).
*   **cryptography** (Optional): Only required if using SSL/TLS features (`--sec` or `--secauto`).

**Installation:**
```bash
pip install cryptography
```

---

## 3. Usage & Quick Start

### Basic Connection
Connect to a server at `192.168.1.10` on port `10001`:
```bash
python serial_client.py -H 192.168.1.10 -p 10001
```

### Using Configuration File (New in 0.0.56)
Load all settings from `soeclient.conf`:
```bash
python serial_client.py --cfgfile soeclient.conf
```
*Note: CLI arguments override config file settings.*

### Secure Connection with Password
Connect using SSL (accepting self-signed certs) and a password:
```bash
python serial_client.py -H 192.168.1.10 -p 10001 --secauto --pwd MySecretPwd
```

### Query Mode
Check the status and serial parameters of a remote server without starting a session:
```bash
python serial_client.py -H 192.168.1.10 -p 10001 --ask
```
*Output:*
```
Querying 192.168.1.10:10001...
Server Version : 0.0.52b
Remote Serial  : COM1 9600 8N1N
```

---

## 4. Configuration

The client can be configured via Command Line Arguments or a Configuration File.

### Configuration File (`soeclient.conf`)
The file uses a simple `key = value` format. Lines starting with `#` are comments.

```ini
host = 192.168.53.99
port = 10001
secauto = true
pwd = zaq12wsx
color = true
count = true
```

### Connection Parameters
| Argument | Config Key | Description |
| :--- | :--- | :--- |
| `-H`, `--host` | `host` | **Required.** Remote Server IP address or hostname. |
| `-p`, `--port` | `port` | **Required.** Remote TCP port. |
| `--cfgfile` | N/A | Path to configuration file to load. |
| `--keepalive` | `keepalive` | Interval for sending heartbeat packets (default: 60s). |
| `--pwd` | `pwd` | Authentication password (if server requires it). |

### Security
| Argument | Config Key | Description |
| :--- | :--- | :--- |
| `--secauto` | `secauto` | Enable SSL/TLS (auto-negotiation/self-signed). |
| `--sec` | `sec` | Enable SSL with specific certs (format: `cert.pem,key.pem`). |

### Interface Options
| Argument | Config Key | Description |
| :--- | :--- | :--- |
| `--color` | `color` | Enable colors for the Status Line (TUI). |
| `--notui` | `notui` | Disable the TUI (Static status lines). Acts like a standard raw terminal. |
| `--nohead` | `nohead` | Hide the Top Status Bar (Hostname/Version info). |
| `--echo` | `echo` | Enable local echo (print characters as you type them). |
| `--count` | `count` | Show TX/RX byte counters in the bottom status line. |

### System Commands
| Argument | Config Key | Description |
| :--- | :--- | :--- |
| `--ask` | `ask` | Query the server for version and serial port settings, then exit. |
| `-h`, `--help` | N/A | Show help message. |

---

## 5. Interface (TUI) & Controls

When running in default mode (without `--notui`):

1.  **Top Bar (Optional):** Shows Client Version, Security Mode, and Local Hostname.
2.  **Central Area:** The scrolling terminal window. This area displays data received from the remote serial device.
3.  **Bottom Bar:**
    *   **SRV:** Remote Server Version.
    *   **L:** Local IP:Port.
    *   **R:** Remote IP:Port.
    *   **S:** Remote Serial Parameters (e.g., `COM1 9600 8N1N`).
    *   **IN/OUT:** (Optional with `--count`) Real-time byte counters.

### Keyboard Controls
*   **Standard Input:** All keystrokes are sent to the remote device.
*   **Special Keys:** Arrow keys, Home, End, PageUp/Down, Insert, Delete, and F1-F12 are translated into standard ANSI escape sequences (compatible with VT100/xterm) before sending.
*   **CTRL+C:** Disconnect and Exit.

---

## 6. Compatibility Notes

*   **RouterOS / Cisco / Linux Consoles:** The client includes specific handling for ANSI escape sequences to ensure compatibility with complex CLI interfaces, including color support and command history navigation (Up/Down arrows).
*   **Windows vs Linux:**
    *   **Windows:** Uses `msvcrt` for non-blocking input. Extended keys (arrows) are intercepted and converted to ANSI.
    *   **Linux:** Uses `termios/tty` raw mode.

---

## 7. Examples

### Example 1: Cisco Router Console
Access a Cisco router connected to a remote SoE Server, enabling counters to monitor traffic:
```bash
python serial_client.py -H 10.0.0.5 -p 2000 --color --count
```

### Example 2: Minimalist Raw Connection
Connect to a device with local echo enabled, hiding the UI bars:
```bash
python serial_client.py -H 10.0.0.5 -p 2000 --notui --echo
```
