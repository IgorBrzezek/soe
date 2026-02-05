# Serial Device Emulator (serial_emu)
**Version:** 0.0.7
**Author:** Igor Brzezek  
**Date:** 05.02.2026

## Overview

**Serial Device Emulator** (`serial_emu`) is a Python-based utility designed to simulate a physical serial device (specifically modeling a Cisco IOS console) on a standard PC. It allows developers and network engineers to test serial terminal software, bridges, and servers without needing physical hardware.

The emulator accepts connections via **Physical Serial Ports** (COM/tty) or **Windows Named Pipes**, providing a rich Text User Interface (TUI) and a realistic command-line environment that translates "Cisco-like" commands into actual underlying system commands (Windows/Linux).

## Key Features

*   **Cisco IOS-like CLI:** Simulates User Exec (`>`), Privileged Exec (`#`), and Configuration (`(config)#`) modes.
*   **Dual Connectivity:**
    *   **Serial Ports:** Works with standard COM ports (Windows) and `/dev/tty` (Linux).
    *   **Named Pipes:** Full support for Windows Named Pipes (client/server modes) for purely software-based testing.
*   **Real System Integration:** Translates simulated commands (e.g., `show interfaces`) into actual OS commands (e.g., `ipconfig` or `ip addr`), returning real-time data.
*   **Text User Interface (TUI):**
    *   Live status line showing port parameters, connection status, and byte counters.
    *   **Smart Resizing:** Automatically adapts to terminal window changes.
    *   **Peer Detection:** Automatically detects if a **Serial Bridge/Server** is connected (displays `CONNECTED BR` in green).
    *   **Monochrome Mode:** High-contrast inverse video mode for legacy terminals.
*   **Customizable:** Fully configurable via CLI arguments, `serial_emu.conf` file, and `emu_commands.txt` for custom command mapping.

## Requirements

*   **Python:** 3.6 or higher
*   **Dependencies:**
    *   `pyserial`
    *   `pywin32` (Windows only, for Named Pipe support)

### Installation

```bash
pip install pyserial
# If on Windows:
pip install pywin32
```

## Usage

### Basic Syntax

```bash
python serial_emu.py [options]
```

### Configuration Hierarchy

The application loads configuration in the following priority order (highest to lowest):
1.  **CLI Arguments** (e.g., `--baud 115200`)
2.  **Configuration File** (`serial_emu.conf` in the working directory)
3.  **Internal Defaults** (Hardcoded values)

### Command Line Options

| Category | Option | Description |
| :--- | :--- | :--- |
| **Connection** | `--comport PORT` | Physical serial port (e.g., `COM1`, `/dev/ttyUSB0`). |
| | `--namedpipe NAME` | Windows Named Pipe (e.g., `device-sim`). Mutually exclusive with comport. |
| | `--baud RATE` | Baud rate (default: 9600). |
| | `--line FORMAT` | Line settings, format: Data/Parity/Stop (default: `8N1N`). |
| **Device Sim** | `--hostname NAME` | Simulated hostname (default: `device-sim`). |
| | `--device-model` | Model string shown in `show version`. |
| | `--enable-password`| Password for `enable` command (default: `cisco`). |
| **Interface** | `--tui` / `--notui` | Enable or disable the status line interface. |
| | `--mono` | Enable monochrome mode (Black/White inverse video). |
| | `--count` | Show TX/RX byte counters in the status line. |
| | `--cmdfile FILE` | Path to CSV file for custom command mapping. |
| **Misc** | `--debug` | Enable verbose debug output. |
| | `--batch` | Batch mode (no interaction, strictly for automation). |

## Usage Examples

### 1. Simulating a Device on a Named Pipe (Windows)
This is ideal for testing with `serial_server` or `serial_bridge` on the same machine.

```bash
python serial_emu.py --namedpipe device-sim --tui
```
*   **Result:** Creates `\\.\pipe\device-sim`.
*   **Detection:** If you connect a compatible Serial Server to this pipe, the status line will change from `DISCONNECTED` to `CONNECTED BR` (Green).

### 2. Physical Serial Port with Custom Baud Rate
```bash
python serial_emu.py --comport COM3 --baud 115200 --hostname CoreRouter
```

### 3. Monochrome Mode (Accessible)
Useful for high-contrast requirements or terminals with poor color support.
```bash
python serial_emu.py --namedpipe testpipe --mono
```
*   **Result:** The status line renders in inverse video (black text on white background) instead of blue/red/green colors.

## Configuration Files

### `serial_emu.conf`
You can save persistent settings in this file.
```ini
[DEFAULT]
baud = 9600
line = 8N1N
hostname = Lab-Router-01
enable_password = secret
tui = True
mono = False
cmdfile = emu_commands.txt
```

### `emu_commands.txt`
Map simulated commands to real OS commands.
**Format:** `"simulated_command","linux_command","windows_command"`

```csv
# Example
"show ip interface brief","ip addr show","ipconfig"
"show processes","ps aux","tasklist"
"show version","uname -a","systeminfo | findstr OS"
```

## Simulated Command Reference

Once connected to the emulator's console, the following commands are available. Tab completion is supported.

### Built-in Cisco-like Commands
| Command | Description |
| :--- | :--- |
| `enable` | Enter Privileged Exec mode (password required). |
| `disable` | Return to User Exec mode. |
| `configure terminal` | Enter Configuration mode. |
| `hostname <name>` | Change the device hostname. |
| `show version` | Display simulated device version and uptime. |
| `show running-config` | Dump the current configuration. |
| `write memory` | Simulate saving configuration. |
| `history` | Show command history. |
| `exit` / `quit` | Disconnect or exit current mode. |

### System Mapped Commands (Examples)
These commands execute real OS commands on the host machine and return the output to the serial console.

| Simulated Command | Windows Execution | Linux Execution |
| :--- | :--- | :--- |
| `show interfaces` | `ipconfig` | `ip addr show` |
| `show arp` | `arp -a` | `arp -a` |
| `show routes` | `route print` | `ip route show` |
| `show processes` | `tasklist` | `ps aux` |
| `show memory` | `wmic OS get ...` | `free -h` |
| `show uptime` | `systeminfo ...` | `uptime` |

*(See `emu_commands.txt` for the full list of ~50 commands)*

## Troubleshooting

1.  **Named Pipe Error (Windows):**
    *   *Error:* `ImportError: No module named win32pipe`
    *   *Fix:* Run `pip install pywin32`.

2.  **Colors not showing / Weird characters:**
    *   Ensure your terminal supports ANSI escape codes.
    *   On Windows cmd.exe, the script attempts to enable VT100 mode automatically.
    *   Try using the `--mono` flag if colors are unreadable.

3.  **"Cannot use both --comport and --namedpipe":**
    *   Check your `serial_emu.conf`. If `comport` is defined there, and you try to use `--namedpipe` via CLI, the script handles this priority, but ensure you aren't passing both as CLI arguments.

4.  **Status Line Artifacts:**
    *   If the status line duplicates when resizing the window, the TUI `check_resize` logic will automatically detect the dimension change and perform a clean redraw of the entire screen to remove artifacts.
