# Serial over Ethernet (SoE) Configuration Guide

**Applicable Versions:**
*   SoE Server v0.0.52b+
*   SoE Bridge v0.0.67+
*   SoE Client v0.0.56+

## 1. Introduction

The **Serial over Ethernet (SoE)** suite supports configuration via external `.conf` files. Using configuration files offers several advantages over command-line arguments:
*   **Persistence:** Save complex settings (like SSL paths, custom colors, or specific serial parameters) so you don't have to type them every time.
*   **Clarity:** Comment and organize your settings.
*   **Automation:** Easily switch between different profiles by loading different config files.

All three components (Server, Bridge, Client) support configuration files, though there are slight differences in how they are loaded.

---

## 2. General Syntax Rules

The configuration files use a standard, human-readable format.

*   **Comments:** Any line starting with `#` is treated as a comment and ignored.
*   **Key-Value Pairs:** Settings are assigned using the equals sign (`=`).
    ```ini
    port = 10001
    baud = 9600
    ```
*   **Booleans:** You can use various formats for true/false flags.
    *   **True:** `true`, `1`, `yes`, `on`
    *   **False:** `false`, `0`, `no`, `off`
*   **Case Insensitivity:** Keys are generally case-insensitive (e.g., `Port` is the same as `port`), but lowercase is recommended for consistency.
*   **Precedence:** **Command Line Arguments always take priority.** If a setting exists in the config file but a different value is provided via CLI (e.g., `--port 5555`), the CLI value is used.

---

## 3. SoE Server Configuration (`soeserver.conf`)

The Server uses a standard INI-style parser.

### Loading Priority
The Server looks for configuration files in this specific order. It loads the **first one found**:
1.  File specified via `--cfgfile <path>` argument.
2.  `/etc/soe/soeserver.conf` (Linux/Unix).
3.  `./soeserver.conf` (Current working directory).

### File Structure
The file is divided into sections, primarily `[DEFAULT]` for settings and `[COLORS]` for interface customization.

#### `[DEFAULT]` Section Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| **Connection** | | |
| `port` | Int | **Required.** TCP listening port. |
| `address` | IP | Interface to bind to. Default: `0.0.0.0` (All). |
| `keepalive` | Int | Protocol heartbeat interval in seconds. Default: `120`. |
| **Serial Port** | | |
| `comport` | String | Serial port (e.g., `COM1` or `/dev/ttyUSB0`). |
| `baud` | Int | Baud rate (e.g., `9600`, `115200`). |
| `line` | String | Line params: Bits/Parity/Stop/Flow (e.g., `8N1N`). |
| **Security** | | |
| `pwd` | String | Password required for clients. |
| `secauto` | Bool | Enable SSL with auto-generated certificate. |
| `sec` | String | Path to custom certs: `cert.pem,key.pem`. |
| **Logging** | | |
| `log` | Path | System log file. Append `,new` to rotate on start. |
| `logmax` | Int | Max rotated log files to keep. |
| `logdata` | Path | Raw binary traffic log file. |
| **Interface** | | |
| `debug` | Bool | Enable verbose debug output. |
| `color` | Bool | Enable ANSI colors. |
| `notui` | Bool | Disable the Text User Interface (simple stdout). |
| `showtransfer` | String | Monitor traffic. Format: `[ascii|hex],[in|out|all]`. |

#### `[COLORS]` Section
You can customize the TUI colors here.
*   **Values:** `RED`, `GREEN`, `YELLOW`, `BLUE`, `MAGENTA`, `CYAN`, `WHITE`.
*   **Backgrounds:** `BG_RED`, `BG_BLUE`, etc.

**Example:**
```ini
[COLORS]
version = CYAN
lip = YELLOW
dir_in = GREEN
dir_out = MAGENTA
bg_statusline = BG_BLUE
```

---

## 4. SoE Bridge Configuration (`soebridge.conf`)

The Bridge also uses the INI-style parser and follows the same loading priority as the Server.

### Loading Priority
1.  `--cfgfile <path>`
2.  `/etc/soe/soebridge.conf`
3.  `./soebridge.conf`

### File Structure

#### `[DEFAULT]` Section Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| **Network** | | |
| `host` | IP/DNS | **Required.** Remote Server Address. |
| `port` | Int | **Required.** Remote Server Port. |
| `keepalive` | Int | Heartbeat interval. Default: `30`. |
| **Local Interface** | | *Choose One* |
| `comport` | String | Physical serial port (e.g., `COM1`). |
| `namedpipe` | String | **(Windows)** Named pipe (e.g., `VM_Pipe`). |
| **Serial Params** | | |
| `baud` | Int | Baud rate. |
| `line` | String | Line params (e.g., `8N1N`). |
| **Security** | | |
| `pwd` | String | Auth password. |
| `secauto` | Bool | Enable SSL (Accept self-signed). |
| `sec` | String | Client cert paths: `cert.pem,key.pem`. |
| **Interface** | | |
| `notui` | Bool | Disable TUI. |
| `batch` | Bool | Silent mode (background service). |
| `ask` | Bool | Query server info and exit. |

The Bridge also supports the `[COLORS]` section identical to the Server.

---

## 5. SoE Client Configuration (`soeclient.conf`)

**Note:** The Client uses a simplified configuration parser (v0.0.56+). It does **not** automatically look in `/etc/` or the current directory by default. You **must** specify the config file explicitly.

### Loading
```bash
python serial_client_0.0.56_LinWin.py --cfgfile <path_to_file>
```

### File Structure
The Client configuration file is a flat list of `key = value` pairs. While it ignores lines starting with `[`, it does not strictly require `[DEFAULT]` or `[COLORS]` sections.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `host` | IP/DNS | **Required.** Remote Server Address. |
| `port` | Int | **Required.** Remote Server Port. |
| `keepalive` | Int | Heartbeat interval. |
| `pwd` | String | Auth password. |
| `secauto` | Bool | Enable SSL/TLS. |
| `sec` | String | Client certs (`cert,key`). |
| `color` | Bool | Enable status line colors. |
| `notui` | Bool | Disable TUI status lines. |
| `nohead` | Bool | Hide the top header bar. |
| `echo` | Bool | Enable local echo. |
| `count` | Bool | Show byte counters. |
| `ask` | Bool | Query info and exit. |

**Example `soeclient.conf`:**
```ini
# Client Configuration
host = 192.168.1.50
port = 10001
pwd = secret
secauto = true
color = true
echo = false
```

---

## 6. Common Troubleshooting

1.  **"Configuration file not found"**
    *   Ensure you provided the correct path to `--cfgfile`.
    *   For Client: You *must* use `--cfgfile`. It does not auto-load.

2.  **"Missing mandatory parameters"**
    *   Even with a config file, specific parameters are mandatory (e.g., `port` for Server, `host`+`port` for Bridge/Client). Ensure these are uncommented in the file or provided via CLI.

3.  **Settings not applying**
    *   Check if you are overriding them with CLI arguments.
    *   Check for typos in the config keys (e.g., `bauds` instead of `baud`).
    *   Ensure lines are not commented out (`#`).

4.  **SSL Errors**
    *   If using `secauto = true`, ensure `pwd` is also set (Server requirement).
    *   If using `sec`, ensure the paths to `.pem` files are absolute or correct relative to the script execution location.
