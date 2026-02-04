# Serial over Ethernet Bridge (SoE Bridge)

**Program:** `serial_client.py`
**Version:** 0.0.70
**Platform:** Windows / Linux (Cross-platform)
**Author:** Igor Brzezek
**Release Date:** February 4, 2026

## Version History

### v0.0.70 (February 4, 2026) - [FIX: Proper DEFAULT_CONFIG Fallback]
**Major Improvements:**
- **Comprehensive Argument Validation**: Added extensive validation for all parameters with detailed error messages
- **Fixed Configuration Loading**: Corrected precedence handling (CLI > config file > defaults)
- **Enhanced Error Handling**: Improved socket error handling and more reliable shutdown procedures
- **Better Debugging**: Added enhanced debug logging for pipe connections and server status

**Bug Fixes:**
- Fixed critical DEFAULT_CONFIG fallback issue where CLI arguments incorrectly overrode config file defaults
- Resolved socket handling problems during application shutdown
- Improved server disconnect detection and handling
- Enhanced Named Pipe connection status reporting

**Stability Improvements:**
- Faster application exit on Ctrl+C (immediate socket closure instead of graceful disconnect)
- Better resource cleanup and error recovery
- More robust exception handling throughout the application
- Improved argument parsing with better unknown option detection

### v0.0.67 (February 2, 2026) - [NEW: Full Config Support + Custom Colors]
Previous version with configuration file support and customizable TUI colors

## 0. Suggestion: 

Rename the file to: soebridge.py

## 1. Description

**SoE Bridge** is the client-side counterpart to the *SoE Server*. It acts as a transparent bridge between a remote TCP Server and a local Serial interface. While the Server *listens* for connections, the Bridge *initiates* a connection to a remote host and maps that data stream to a local resource.

This enables scenarios such as:
*   Connecting a physical device on "Computer A" (running SoE Server) to a legacy application on "Computer B" (running SoE Bridge).
*   Connecting a VM (via Named Pipe) to a remote serial device.

The "LinWin" suffix indicates native support for both **Linux** (e.g., `/dev/ttyUSB0`) and **Windows** (e.g., `COM1` or `\\.\pipe\Name`).

### Key Features
*   **TCP Client Mode:** Actively connects to a remote TCP/IP server.
*   **Local Interfaces:**
    *   **Physical Serial Port:** Bridges network data to a real COM/TTY port.
    *   **Windows Named Pipes:** Creates a virtual pipe (e.g., `\\.\pipe\MyPipe`) for software that requires serial-like communication (common in Virtual Machines like QEMU/VMware).
*   **Advanced TUI:** Split-screen interface for monitoring system logs and raw data traffic simultaneously.
*   **Enhanced Security:** Full SSL/TLS client support with improved error handling and validation.
*   **Robust Protocol Handshake:** Automatically exchanges version info and serial parameters with SoE Server.
*   **Comprehensive Validation:** Extensive argument and parameter validation with detailed error messages.
*   **Enhanced Logging:** Robust file logging with rotation, improved debugging capabilities, and better error reporting.
*   **Stability Improvements:** Better socket handling, faster shutdown procedures, and more reliable resource cleanup.

---

## 2. Requirements & Installation

The application requires **Python 3.6+**.

### Dependencies
*   **pyserial** (Required): For serial port communication.
*   **pywin32** (Required **only** if using Named Pipes on Windows).
*   **cryptography** (Optional): For SSL/TLS security.

**Installation:**
```bash
pip install pyserial pywin32 cryptography
```

---

## 3. Usage & Quick Start

### Basic Usage (Physical Serial)
Connect local `COM17` to a server at `192.168.1.10:10001`:
```bash
python serial_client.py -H 192.168.1.10 -p 10001 --comport COM17
```

### Basic Usage (Named Pipe - Windows Only)
Create a pipe `\\.\pipe\VMSerial` and connect to the server:
```bash
python serial_client.py -H 192.168.1.10 -p 10001 --namedpipe VMSerial
```

### Modes of Operation
1.  **TUI Mode (Default):** Interactive split-screen interface with real-time monitoring.
2.  **Batch Mode (`-b` / `--batch`):** Silent background operation with enhanced error handling.
3.  **Query Mode (`--ask`):** Connects briefly to check the server's version and configured serial parameters, then exits.

### Validation & Error Handling
Version 0.0.70 includes comprehensive validation of all configuration parameters:

**Parameter Validation:**
- **Port Range**: Validates TCP ports are within 1-65535 range
- **Baud Rates**: Ensures standard baud rates (300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 230400, 460800, 921600)
- **Line Format**: Validates 4-character serial parameter format (DataBits[5-8] + Parity[N/O/E/M/S] + StopBits[1/2] + Flow[N/X/H/R])
- **SSL Options**: Prevents conflicting SSL mode selections
- **Interface Selection**: Ensures only one of `--comport` or `--namedpipe` is specified
- **Value Ranges**: Validates all numeric parameters (keepalive, buffer sizes, etc.)

**Enhanced Error Messages:**
- Clear, descriptive error messages for validation failures
- Specific guidance for correcting configuration errors
- Unknown argument detection with helpful suggestions
- Better error context for troubleshooting

**Stability Improvements:**
- Faster application shutdown with immediate socket closure on Ctrl+C
- Improved server disconnect detection and handling
- Better resource cleanup and error recovery
- Enhanced debugging for Named Pipe connections

---

## 4. Configuration File (`soebridge.conf`)

The program looks for `soebridge.conf` in `/etc/soe/`, the current directory, or via `--cfgfile`.

### `[DEFAULT]` Section

#### Connection Parameters (Network)
| Parameter | Description | Default |
| :--- | :--- | :--- |
| `host` | **Required.** IP/Hostname of the remote server. | `None` |
| `port` | **Required.** TCP port of the remote server. | `None` |
| `pwd` | Password for authentication (if server requires it). | `None` |
| `keepalive` | Heartbeat interval (in seconds). | `30` |

#### Serial Port Parameters (Local)
*Note: You must choose either `comport` OR `namedpipe`.*

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `comport` | Physical serial port (e.g., `COM1`, `/dev/ttyUSB0`). | `None` |
| `namedpipe` | **(Windows Only)** Name of the pipe to create. | `None` |
| `baud` | Baud rate for the physical port. | `9600` |
| `line` | Parameters: [Bits][Parity][Stop][Flow] (e.g., `8N1N`). | `8N1N` |

#### Security
| Parameter | Description | Default |
| :--- | :--- | :--- |
| `secauto` | `True/False`. Auto-negotiate SSL (accept self-signed). | `False` |
| `sec` | Path to client certs: `cert.pem,key.pem`. | `None` |

#### Logging & Interface
| Parameter | Description | Default |
| :--- | :--- | :--- |
| `log` | System log filename. Append `,new` to rotate on start. | `None` |
| `logmax` | Max number of log files. | `10` |
| `logdata` | Raw binary traffic dump filename. | `None` |
| `debug` | Enable verbose debug output. | `False` |
| `showtransfer`| Real-time monitor: `ascii` or `hex` + `in`/`out`/`all`. | `None` |
| `notui` | Disable windowed interface (simple stdout). | `False` |
| `batch` | Silent mode (no output). | `False` |
| `ask` | Query mode (connect, fetch info, exit). | `False` |

### `[COLORS]` Section
Customizes the TUI colors (e.g., `lip = YELLOW`, `err = RED`). See config file for full list.

---

## 5. Command Line Arguments

CLI arguments override the config file.

| Argument | Description |
| :--- | :--- |
| `-H`, `--host` | Remote Server IP/Hostname. |
| `-p`, `--port` | Remote Server Port. |
| `--comport` | Local Physical Serial Port. |
| `--namedpipe` | **(Win)** Create a Local Named Pipe (e.g. `MyPipe`). |
| `--baud`, `--line`| Serial parameters. |
| `--pwd` | Connection password. |
| `--secauto` | Enable automatic SSL. |
| `--sec CERT,KEY` | Enable SSL with specific certs. |
| `--ask` | Query server info and exit. |
| `--log`, `--logdata`| File logging paths. |
| `--showtransfer` | Monitor traffic (e.g., `--showtransfer hex,all`). |
| `-b`, `--batch` | Run silently. |

---

## 6. Interface (TUI) & Controls

The screen is divided into:
1.  **System Log (Top):** Connection events, errors, protocol status.
2.  **Data Monitor (Bottom):** Real-time ASCII or HEX view of data passing through the bridge.
3.  **Status Line:** Local/Remote IPs, Port settings, Byte counters.

### Keyboard Shortcuts
*   `TAB`: Switch active window (scroll focus).
*   `UP` / `DOWN`: Scroll history in the active window.
*   `CTRL+C`: Disconnect and Exit.

---

## 7. Protocol & Handshake

When connecting to a **SoE Server**, the Bridge performs a handshake:
1.  **Version Exchange:** Sends `__#BR_VER_...` and waits for `SRV_VER_...`.
2.  **Authentication:** If `--pwd` is set, sends `__#PWD_...`.
3.  **Parameter Sync:** Exchanges serial port settings (Baud/Line) so they can be displayed on both ends (Remote Params).
4.  **KeepAlive:** Sends periodic `__#KEEPALIVE#__` packets to prevent timeouts.

If connecting to a **Generic TCP Server** (non-SoE), the handshake commands will likely appear as raw text in the stream. The bridge is transparent enough to work with generic servers, though handshake strings should be ignored by the recipient.

---

## 8. Examples

### Example 1: Virtual Machine Connection (Windows)
You want to connect a legacy DOS program running in a VM to a real serial device on another computer.
1.  **Server:** Runs on the machine with the device.
2.  **Bridge (This PC):**
    ```bash
    python serial_bridge.py -H 192.168.1.50 -p 5000 --namedpipe DOSPipe --showtransfer hex,all
    ```
3.  **VM Configuration:** Map the VM's COM1 to Named Pipe `\\.\pipe\DOSPipe`.

### Example 2: Secure Link over Internet
Connect local `/dev/ttyS0` to a remote secure server.
```bash
python serial_bridge.py \
  --host my.server.com \
  --port 8888 \
  --comport /dev/ttyS0 \
  --baud 115200 \
  --secauto \
  --pwd MySecretPassword
```

### Example 3: Check Server Status
Quickly check if a remote server is up and what COM port it's using.
```bash
python serial_bridge.py -H 192.168.1.50 -p 5000 --ask
```
*Output:* `Server version: 0.0.52b, Params: COM1 9600 8N1N`

### Example 4: Debugging with Enhanced Validation
Start bridge with debug output to see validation and connection details:
```bash
python serial_bridge.py -H 192.168.1.50 -p 5000 --comport COM1 --debug --showtransfer ascii,all
```

---

## 9. Migration Guide (v0.0.67 → v0.0.70)

### Breaking Changes
None - v0.0.70 maintains full backward compatibility.

### Configuration Loading Fix
**Critical Fix**: v0.0.67 had incorrect fallback behavior where CLI arguments would override config file values even when not explicitly provided. v0.0.70 implements proper precedence:
1. **Command Line Arguments** (highest priority)
2. **Configuration File** 
3. **DEFAULT_CONFIG** (fallback)

### New Validation Features
- **Comprehensive Parameter Checking**: All parameters are now validated with detailed error messages
- **Standard Baud Rate Validation**: Only standard baud rates are accepted
- **Port Range Validation**: TCP ports must be within 1-65535
- **Serial Line Format**: Validates 4-character format (DataBits/Parity/Stop/Flow)
- **Mutual Exclusion Checks**: Prevents conflicting options

### Enhanced Error Handling
- **Better Error Messages**: Clear, descriptive errors with specific guidance
- **Unknown Argument Detection**: Helpful suggestions for typos in CLI arguments
- **Improved Socket Handling**: Better disconnect detection and recovery
- **Faster Shutdown**: Ctrl+C now exits immediately without graceful disconnect attempt

### Stability Improvements
- **Resource Cleanup**: More reliable cleanup of sockets, pipes, and events
- **Server Disconnect Detection**: Improved detection and logging of server disconnections
- **Enhanced Debugging**: Better debug messages for Named Pipe connections and protocol issues

### Recommended Actions
1. **Test Existing Configurations** - All should work unchanged but benefit from better validation
2. **Review Error Messages** - New validation may reveal previously unnoticed configuration issues
3. **Update Scripts** - Consider using the enhanced error messages for better troubleshooting
4. **Debug Mode** - Use `--debug` flag for detailed connection and validation information
