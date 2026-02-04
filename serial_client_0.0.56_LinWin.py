# ==============================================================================
# Serial over Ethernet Client
# Version: 0.0.56 [NEW: --cfgfile option to read parameters from config file]
# Date: 03.02.2026
# Author: Igor Brzezek
# Change Log:
# - 0.0.56: Added --cfgfile option to read all CLI parameters from configuration file
#           Configuration file uses simple key=value format
#           CLI parameters override configuration file values
# - 0.0.55: Fixed protocol compliance - client now responds to __#GET_KA_TIMEOUT#__
#           Fixed get_server_info_ask() - now properly handles server requests first
#           Fixed Windows --echo crash when pressing arrow keys (ANSI sequences)
#           Fixed --count option - now accurately tracks raw bytes sent and received.
# - 0.0.54: Disabled ANSI filtering - RouterOS needs ANSI for colors and command history
#           Arrow keys now work perfectly with full colors and prompt preservation
# - 0.0.53: Fixed Windows extended key handling - now converts to ANSI escape sequences
#           Windows: \xe0\x48 -> ANSI: \x1b[A (Arrow Up), etc.
# - 0.0.52: Fixed Windows extended key handling (arrow keys, function keys, etc.)
#           Now properly sends 2-byte sequences for extended keys (e.g., \xe0\x48 for Up)
# - 0.0.51: Enhanced ANSI escape sequence filtering to fix RouterOS logout bug.
#           Added filtering for cursor home variations (\x1b[H, \x1b[;H, etc.)
#           Added filtering for alternate screen buffer switching (\x1b[?1049[hl])
# - 0.0.50: Initial version with TUI, ANSI filtering, and SSL support.
# ==============================================================================

import sys
import os
import socket
import ssl
import threading
import time
import argparse
import platform
import signal
import re
import select

# --- Platform Specific Keyboard Handling ---
if sys.platform == "win32":
    import msvcrt
else:
    import tty
    import termios

# --- Constants & Protocol Commands ---
__APP_NAME__    = "Serial over Ethernet Client"
__CODE_VERSION__ = "0.0.56"
__CODE_DATE__    = "03.02.2026"
__CODE_AUTHOR__ = "Igor Brzezek"
__CODE_GUTHUB__ = "https://github.com/igorbrzezek"

# --- Misc constants
__TXT_SUMMARY__ = "---=== Summary ===---"

ASK_CMD        = b"__#ASK_COM_PARAMS#__"
DISCONNECT_CMD = b"__#DISCONNECT#__"
KEEPALIVE_CMD  = b"__#KEEPALIVE#__"
RELOAD_CMD     = b"__#RELOAD#__"
SHUTDOWN_CMD   = b"__#SHUTDOWN#__"
GETVER_CMD     = b"__#GETVER#__"
GET_KA_TIMEOUT_CMD = b"__#GET_KA_TIMEOUT#__"
MY_KA_TIMEOUT_CMD  = b"__#MY_KA_TIMEOUT_"
SEC_ERROR_MSG  = b"__#SECERROR#__"
BAD_PWD_MSG    = b"__#BADPWD#__"
BLOCKED_MSG    = b"__#IPBLOCKED#__"

class Colors:
    RESET       = "\033[0m"
    RED         = "\033[91m"
    GREEN       = "\033[92m"
    YELLOW      = "\033[93m"
    CYAN        = "\033[96m"
    MAGENTA     = "\033[95m"
    WHITE       = "\033[97m"
    BG_BLUE     = "\033[44m"
    BG_RED      = "\033[41m"
    INVERSE     = "\033[7m"
    CLEAR_LINE  = "\033[K"
    CLEAR_SCR   = "\033[2J\033[H"
    SAVE_CUR    = "\033[s"
    RESTORE_CUR = "\033[u"

class UiColors:
    _UI_COL_VERSION_    = Colors.CYAN
    _UI_COL_CL_VERSION_ = Colors.CYAN
    _UI_COL_LIP_        = Colors.YELLOW
    _UI_COL_LPORT_      = Colors.CYAN
    _UI_COL_RIP_        = Colors.YELLOW
    _UI_COL_RPORT_      = Colors.CYAN
    _UI_COL_SPORTNAME_  = Colors.YELLOW
    _UI_COL_SPORTSPEED_ = Colors.WHITE
    _UI_COL_SPORTLINE_  = Colors.CYAN
    _UI_COL_RPORTNAME_  = Colors.YELLOW
    _UI_COL_RPORTSPEED_ = Colors.WHITE
    _UI_COL_RPORTLINE_  = Colors.CYAN
    _UI_COL_RAW_        = Colors.WHITE
    _UI_COL_RAW_BG_     = Colors.BG_RED
    _UI_COL_SEC_        = Colors.GREEN
    _UI_COL_BG_STATUSLINE_ = Colors.BG_BLUE
    _UI_COL_FG_STATUSLINE_ = Colors.WHITE
    _UI_COL_TAGS_       = Colors.YELLOW
    _UI_COL_BRACKETS_   = Colors.WHITE
    _UI_COL_DIR_IN_     = Colors.GREEN
    _UI_COL_DIR_OUT_    = Colors.MAGENTA
    _UI_COL_CMD_        = Colors.MAGENTA
    _UI_COL_ACTHEAD_    = Colors.BG_RED

class SoEClient:
    def __init__(self, args):
        self.args = args
        self.sock = None
        self.keep_running = True
        self.remote_params = "?? ?? ??"
        self.server_version = "?.?.?"
        self.local_ip = "0.0.0.0"
        self.local_port = 0
        self.sec_mode = "!! RAW !!"
        self.sent_count = 0
        self.recv_count = 0
        self.cols, self.rows = self._get_term_size()
        self.hostname = platform.node()
        self.param_pattern = re.compile(r"([a-zA-Z0-9/._-]+\s+\d+\s+[5-8][NOE][12][NX])")
        self.stdout_lock = threading.Lock()
        
        # Debug logging for filter (optional)
        self.debug_filter = False

        signal.signal(signal.SIGINT, self.shutdown)
        if platform.system() != "Windows":
            signal.signal(signal.SIGWINCH, self._handle_sigwinch)

    def _get_term_size(self):
        try:
            sz = os.get_terminal_size()
            return sz.columns, sz.lines
        except:
            return 80, 24

    def _handle_sigwinch(self, signum, frame):
        self._on_resize()

    def _on_resize(self):
        new_cols, new_rows = self._get_term_size()
        if new_cols != self.cols or new_rows != self.rows:
            self.cols, self.rows = new_cols, new_rows
            if not self.args.notui:
                # Recalculate and reapply scrolling region on resize
                self._setup_scrolling_region()
                self.update_status_line()

    def _terminal_monitor(self):
        while self.keep_running:
            self._on_resize()
            # FIX: Force status line update periodically if counters are enabled
            if self.args.count:
                self.update_status_line()
            time.sleep(0.1)

    def _setup_scrolling_region(self):
        """Setup scrolling region to protect status lines"""
        with self.stdout_lock:
            # Clear screen
            sys.stdout.write(Colors.CLEAR_SCR)
            
            # Set scrolling region
            # If --nohead: scrolling region is from line 1 to (rows-1)
            # If not --nohead: scrolling region is from line 2 to (rows-1)
            top_margin = 1 if self.args.nohead else 2
            sys.stdout.write(f"\033[{top_margin};{self.rows-1}r")
            
            # Move cursor to first line of scrolling region
            sys.stdout.write(f"\033[{top_margin};1H")
            sys.stdout.flush()

    def _keepalive_thread(self):
        while self.keep_running:
            time.sleep(self.args.keepalive)
            try:
                if self.sock:
                    self.sock.sendall(KEEPALIVE_CMD)
            except:
                break

    def update_status_line(self):
        if self.args.notui:
            return
        
        with self.stdout_lock:
            # Build and write status lines using absolute positioning
            # Scrolling region protects these lines from being overwritten
            
            # --- TOP STATUS LINE ---
            top_line = ""
            if not self.args.nohead:
                top_plain = f" {__APP_NAME__} ({__CODE_VERSION__}) | {self.sec_mode} | Running on {self.hostname} "
                if self.args.color:
                    s_col = UiColors._UI_COL_SEC_ if "SSL" in self.sec_mode or "SEC" in self.sec_mode else UiColors._UI_COL_RAW_
                    s_bg = UiColors._UI_COL_BG_STATUSLINE_ if "SSL" in self.sec_mode or "SEC" in self.sec_mode else UiColors._UI_COL_RAW_BG_
                    top_styled = (f" {UiColors._UI_COL_FG_STATUSLINE_}{__APP_NAME__} ({UiColors._UI_COL_CL_VERSION_}{__CODE_VERSION__}{UiColors._UI_COL_FG_STATUSLINE_}) | "
                                  f"{s_bg}{s_col}{self.sec_mode}{UiColors._UI_COL_BG_STATUSLINE_}{UiColors._UI_COL_FG_STATUSLINE_} | "
                                  f"Running on {UiColors._UI_COL_LIP_}{self.hostname}{UiColors._UI_COL_FG_STATUSLINE_} ")
                    top_line = f"{UiColors._UI_COL_BG_STATUSLINE_}{top_styled.ljust(self.cols + (len(top_styled) - len(top_plain)))}{Colors.RESET}"
                else:
                    top_line = f"{Colors.INVERSE}{top_plain.ljust(self.cols)}{Colors.RESET}"

            # --- BOTTOM STATUS LINE ---
            l_ip, l_port = self.local_ip, self.local_port
            r_ip, r_port = self.args.host, self.args.port
            
            bot_plain = (f" SRV ({self.server_version}) | L: {l_ip}:{l_port} | "
                          f"R: {r_ip}:{r_port} | S: {self.remote_params} ")
            
            if self.args.count:
                bot_plain += f"| IN:{self.recv_count} OUT:{self.sent_count} "
            
            # FIX: Always show status line even with --notui if --count is used
            if not self.args.notui or self.args.count:
                if self.args.color:
                    t_col = UiColors._UI_COL_FG_STATUSLINE_
                    bot_styled = (f" {t_col}SRV ({UiColors._UI_COL_CL_VERSION_}{self.server_version}{t_col}) | "
                                   f"L: {UiColors._UI_COL_LIP_}{l_ip}{t_col}:{UiColors._UI_COL_LPORT_}{l_port}{t_col} | "
                                   f"R: {UiColors._UI_COL_RIP_}{r_ip}{t_col}:{UiColors._UI_COL_RPORT_}{r_port}{t_col} | "
                                   f"S: {UiColors._UI_COL_RPORTSPEED_}{self.remote_params}{t_col} ")
                    
                    if self.args.count:
                        bot_styled += f"| IN:{self.recv_count} OUT:{self.sent_count} "
                    
                    bot_line = f"{UiColors._UI_COL_BG_STATUSLINE_}{t_col}{bot_styled.ljust(self.cols + (len(bot_styled) - len(bot_plain)))}{Colors.RESET}"
                else:
                    bot_line = f"{Colors.INVERSE}{bot_plain.ljust(self.cols)}{Colors.RESET}"
            else:
                bot_line = f"{Colors.INVERSE}{bot_plain.ljust(self.cols)}{Colors.RESET}"

            # Save current cursor position (using DEC method which is more reliable)
            sys.stdout.write("\0337")
            
            # Write top status line (outside scrolling region)
            if not self.args.nohead:
                sys.stdout.write(f"\033[1;1H{top_line}")
            
            # Write bottom status line (outside scrolling region)
            sys.stdout.write(f"\033[{self.rows};1H{bot_line}")
            
            # Restore cursor position (back to scrolling region)
            sys.stdout.write("\0338")
            
            sys.stdout.flush()

    def shutdown(self, signum=None, frame=None):
        self.keep_running = False
        if self.sock:
            try:
                self.sock.sendall(DISCONNECT_CMD)
                self.sock.close()
            except:
                pass
        
        # Reset scrolling region and move cursor to bottom
        if not self.args.notui:
            with self.stdout_lock:
                sys.stdout.write("\033[r")  # Reset scrolling region
                sys.stdout.write(f"\033[{self.rows};1H\n")  # Move to bottom
                sys.stdout.flush()
        
        sys.exit(0)

    def _receive_thread(self):
        while self.keep_running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                
                # FIX: Count raw traffic before protocol filtering
                self.recv_count += len(data)
                
                if b"__#" in data:
                    decoded_part = data.decode('utf-8', errors='ignore')
                    
                    # Respond to server's GETVER request
                    if GETVER_CMD in data:
                        self.sock.sendall(f"__#CL_VER_{__CODE_VERSION__}#__".encode())
                    
                    # FIX: Respond to server's GET_KA_TIMEOUT request
                    if GET_KA_TIMEOUT_CMD in data:
                        self.sock.sendall(f"__#MY_KA_TIMEOUT_{self.args.keepalive}#__".encode())
                    
                    if "SRV_VER_" in decoded_part:
                        try:
                            self.server_version = decoded_part.split("SRV_VER_")[1].split("#")[0]
                        except: pass

                    if BAD_PWD_MSG in data:
                        sys.stdout.write(f"\n{Colors.RED}[ERROR] Invalid password.{Colors.RESET}\n")
                        self.shutdown()
                    if DISCONNECT_CMD in data:
                        self.shutdown()

                    if "__#COM_PARAMS_" in decoded_part:
                        try:
                            param_content = decoded_part.split("__#COM_PARAMS_")[1].split("#__")[0]
                            self.remote_params = param_content.strip()
                        except: pass

                    remaining_data = re.sub(r'__#.*?#__', '', decoded_part)
                    if not remaining_data.strip():
                        self.update_status_line()
                        continue
                    data = remaining_data.encode('utf-8', errors='replace')

                # self.recv_count += len(data) # Moved to top
                
                # Use lock when writing to stdout to prevent corruption
                with self.stdout_lock:
                    sys.stdout.write(data.decode(errors='replace'))
                    sys.stdout.flush()
                
                # Don't update status line here - let _terminal_monitor do it periodically
                # to avoid interrupting ANSI escape sequences from remote device

            except Exception:
                break
        self.shutdown()

    def _convert_windows_key(self, key):
        """Convert Windows extended key sequences to ANSI escape sequences"""
        # Windows extended keys: \xe0\x<code> or \x00\x<code>
        if len(key) != 2 or key[0] not in (0x00, 0xe0):
            return key
        
        key_code = key[1]
        key_map = {
            # Arrow keys
            0x48: b'\x1b[A',  # Up
            0x50: b'\x1b[B',  # Down
            0x4B: b'\x1b[D',  # Left
            0x4D: b'\x1b[C',  # Right
            
            # Home/End
            0x47: b'\x1b[H',  # Home
            0x4F: b'\x1b[F',  # End
            
            # Insert/Delete
            0x52: b'\x1b[2~',  # Insert
            0x53: b'\x1b[3~',  # Delete
            
            # Page Up/Down
            0x49: b'\x1b[5~',  # Page Up
            0x51: b'\x1b[6~',  # Page Down
            
            # Function keys (F1-F10 with \x00 prefix)
            0x3B: b'\x1bOP',  # F1
            0x3C: b'\x1bOQ',  # F2
            0x3D: b'\x1bOR',  # F3
            0x3E: b'\x1bOS',  # F4
            0x3F: b'\x1b[15~',  # F5
            0x40: b'\x1b[17~',  # F6
            0x41: b'\x1b[18~',  # F7
            0x42: b'\x1b[19~',  # F8
            0x43: b'\x1b[20~',  # F9
            0x44: b'\x1b[21~',  # F10
        }
        
        return key_map.get(key_code, key)

    def _send_thread(self):
        if sys.platform != "win32":
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setraw(sys.stdin.fileno())

        try:
            while self.keep_running:
                if sys.platform == "win32":
                    if msvcrt.kbhit():
                        char = msvcrt.getch()
                        if char in (b'\x00', b'\xe0'):
                            char2 = msvcrt.getch()
                            char = char + char2
                            # Convert Windows extended keys to ANSI escape sequences
                            char = self._convert_windows_key(char)
                        if self.args.echo:
                            # FIX: Use sys.stdout.write for multi-byte sequences
                            # msvcrt.putch() only accepts single byte
                            if len(char) == 1:
                                msvcrt.putch(char)
                            else:
                                sys.stdout.write(char.decode('latin-1', errors='replace'))
                                sys.stdout.flush()
                        self.sock.sendall(char)
                        self.sent_count += len(char)
                        # Don't update status line here - let _terminal_monitor do it
                    else:
                        time.sleep(0.01)
                else:
                    char = sys.stdin.read(1)
                    if not char: break
                    if char == '\x03':
                        self.shutdown()
                        break
                    if self.args.echo:
                        sys.stdout.write(char)
                        sys.stdout.flush()
                    self.sock.sendall(char.encode())
                    self.sent_count += len(char.encode())
                    # Don't update status line here - let _terminal_monitor do it
        finally:
            if sys.platform != "win32":
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _handle_server_requests(self, sock, data):
        """Handle protocol requests from server and respond appropriately"""
        if GETVER_CMD in data:
            sock.sendall(f"__#CL_VER_{__CODE_VERSION__}#__".encode())
        if GET_KA_TIMEOUT_CMD in data:
            sock.sendall(f"__#MY_KA_TIMEOUT_{self.args.keepalive}#__".encode())

    def get_server_info_ask(self):
        res = {"version": "Unknown", "params": "Unknown"}
        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.settimeout(5)
            raw_sock.connect((self.args.host, self.args.port))
            
            sock = raw_sock
            if self.args.secauto or self.args.sec:
                ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                if self.args.sec:
                    cp, kp = self.args.sec.split(',')
                    ctx.load_cert_chain(certfile=cp.strip(), keyfile=kp.strip())
                sock = ctx.wrap_socket(raw_sock, server_hostname=self.args.host)
            
            # FIX: First read and respond to server's initial requests
            # Server sends __#GETVER#__ and __#GET_KA_TIMEOUT#__ immediately after connection
            sock.setblocking(False)
            time.sleep(0.3)  # Give server time to send initial commands
            try:
                r, _, _ = select.select([sock], [], [], 1.0)
                if r:
                    initial_data = sock.recv(4096)
                    if initial_data:
                        self._handle_server_requests(sock, initial_data)
            except:
                pass
            sock.setblocking(True)
            sock.settimeout(5)
            
            # Now send our credentials and requests
            sock.sendall(f"__#CL_VER_{__CODE_VERSION__}#__".encode())
            if self.args.pwd:
                sock.sendall(f"__#PWD_{self.args.pwd}#__".encode())
                
            sock.sendall(GETVER_CMD)
            sock.sendall(ASK_CMD)
            
            start_t = time.time()
            while time.time() - start_t < 3:
                r, _, _ = select.select([sock], [], [], 0.5)
                if r:
                    data = sock.recv(4096)
                    if not data: break
                    
                    # Handle any additional server requests
                    self._handle_server_requests(sock, data)
                    
                    decoded = data.decode(errors='replace')
                    if "SRV_VER_" in decoded:
                        res["version"] = decoded.split("SRV_VER_")[1].split("#")[0]
                    if "__#COM_PARAMS_" in decoded:
                        res["params"] = decoded.split("__#COM_PARAMS_")[1].split("#__")[0].strip()
                    
                    if res["version"] != "Unknown" and res["params"] != "Unknown":
                        break
            sock.close()
        except Exception as e:
            print(f"Error during --ask: {e}")
        return res

    def run(self):
        if self.args.ask:
            print(f"Querying {self.args.host}:{self.args.port}...")
            info = self.get_server_info_ask()
            print(f"Server Version : {info['version']}")
            print(f"Remote Serial  : {info['params']}")
            sys.exit(0)

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(5)
        
        try:
            raw_sock.connect((self.args.host, self.args.port))
            self.local_ip, self.local_port = raw_sock.getsockname()
            
            if self.args.secauto or self.args.sec:
                ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                if self.args.sec:
                    cert_file, key_file = self.args.sec.split(',')
                    ctx.load_cert_chain(certfile=cert_file.strip(), keyfile=key_file.strip())
                    self.sec_mode = "SEC(C)"
                else:
                    self.sec_mode = "SEC(A)"
                self.sock = ctx.wrap_socket(raw_sock, server_hostname=self.args.host)
            else:
                self.sock = raw_sock
                self.sec_mode = "!! RAW !!"

            self.sock.setblocking(True)
            self.sock.sendall(f"__#CL_VER_{__CODE_VERSION__}#__".encode())
            if self.args.pwd:
                self.sock.sendall(f"__#PWD_{self.args.pwd}#__".encode())
            
            self.sock.sendall(GETVER_CMD)
            self.sock.sendall(ASK_CMD)

            if not self.args.notui:
                # Setup scrolling region to protect status lines
                self._setup_scrolling_region()
                # Display initial status
                self.update_status_line()
                # Start terminal monitor thread
                threading.Thread(target=self._terminal_monitor, daemon=True).start()

            threading.Thread(target=self._keepalive_thread, daemon=True).start()
            threading.Thread(target=self._receive_thread, daemon=True).start()
            self._send_thread()

        except Exception as e:
            print(f"Connection failed: {e}")
            self.shutdown()

def read_config_file(cfgfile):
    """Read configuration file and return dictionary of parameters"""
    config = {}
    try:
        with open(cfgfile, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse key=value or key = value format
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    # Convert boolean strings
                    if value.lower() in ('true', 'yes', 'on', '1'):
                        value = True
                    elif value.lower() in ('false', 'no', 'off', '0'):
                        value = False
                    # Convert integer strings
                    elif value.isdigit():
                        value = int(value)
                    config[key] = value
    except FileNotFoundError:
        print(f"Error: Configuration file '{cfgfile}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading configuration file: {e}")
        sys.exit(1)
    return config

def parse_args():
    # First, create a parser to handle --cfgfile option
    initial_parser = argparse.ArgumentParser(add_help=False)
    initial_parser.add_argument("--cfgfile")
    initial_args, _ = initial_parser.parse_known_args()
    
    # Read config file if specified
    config = {}
    if initial_args.cfgfile:
        config = read_config_file(initial_args.cfgfile)
        print(f"Loaded configuration from: {initial_args.cfgfile}")
    
    # Create main parser with defaults from config file
    parser = argparse.ArgumentParser(add_help=False)
    
    # Define argument defaults from config
    host_default = config.get('host')
    port_default = config.get('port')
    keepalive_default = config.get('keepalive', 60)
    secauto_default = config.get('secauto', False)
    sec_default = config.get('sec')
    pwd_default = config.get('pwd')
    color_default = config.get('color', False)
    notui_default = config.get('notui', False)
    nohead_default = config.get('nohead', False)
    echo_default = config.get('echo', False)
    count_default = config.get('count', False)
    ask_default = config.get('ask', False)
    cfgfile_default = initial_args.cfgfile
    
    parser.add_argument("--cfgfile", default=cfgfile_default, 
                        help="Read configuration from specified file")
    parser.add_argument("-H", "--host", default=host_default)
    parser.add_argument("-p", "--port", type=int, default=port_default)
    parser.add_argument("--keepalive", type=int, default=keepalive_default)
    parser.add_argument("--secauto", action="store_true", default=secauto_default)
    parser.add_argument("--sec", default=sec_default)
    parser.add_argument("--pwd", default=pwd_default)
    parser.add_argument("--color", action="store_true", default=color_default)
    parser.add_argument("--notui", action="store_true", default=notui_default)
    parser.add_argument("--nohead", action="store_true", default=nohead_default)
    parser.add_argument("--echo", action="store_true", default=echo_default)
    parser.add_argument("--count", action="store_true", default=count_default)
    parser.add_argument("--ask", action="store_true", default=ask_default)
    parser.add_argument("-h", action="store_true")
    parser.add_argument("--help", action="store_true")
    
    # Parse arguments and handle unknown options with descriptive error
    try:
        # Suppress argparse's default error output by redirecting stderr temporarily
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            args = parser.parse_args()
        finally:
            sys.stderr = old_stderr
    except SystemExit as e:
        # argparse exits with code 2 for argument errors
        if e.code == 2:
            # Extract the problematic argument name from sys.argv
            unknown_arg = None
            for i, arg in enumerate(sys.argv[1:]):
                if arg.startswith('-') and not arg.startswith('--'):
                    # Check short options
                    if arg not in ['-H', '-p', '-h']:
                        unknown_arg = arg
                        break
                elif arg.startswith('--'):
                    # Check long options
                    option_name = arg.split('=')[0]
                    valid_options = [
                        '--host', '--port', '--cfgfile', '--keepalive', '--secauto', '--sec', '--pwd',
                        '--color', '--notui', '--nohead', '--echo', '--count', '--ask', '--help'
                    ]
                    if option_name not in valid_options:
                        unknown_arg = option_name
                        break
            
            if unknown_arg:
                print(f"[ERROR] Unrecognized option: {unknown_arg}")
            else:
                print("[ERROR] Invalid command line argument.")
            print("Use: --help for full help or -h for usage summary")
            sys.exit(1)
        raise
    
    if args.h or args.help:
        print(f"{__APP_NAME__} v{__CODE_VERSION__} ({__CODE_DATE__})")
        print(f"Author: {__CODE_AUTHOR__} | GitHub: {__CODE_GUTHUB__}")

        if args.h:
            print(f"\nUsage: python client.py -H <host> -p <port> [--cfgfile FILE] [--keepalive SEC] [--pwd PWD] [--secauto] [--sec CERT,KEY] [--color] [--notui] [--nohead] [--echo] [--count] [--ask]")
            sys.exit(0)
            
        if args.help:
            print("\nCONNECTION PARAMETERS:")
            print("  -H, --host ADDR      Remote IP address")
            print("  -p, --port PORT      Remote port")
            print("  --cfgfile FILE       Read configuration from specified file")
            print("  --keepalive SEC      Heartbeat interval in seconds (default: 60)")
            print("  --pwd PASSWORD       Authentication password")
            print("\nSECURITY:")
            print("  --secauto            Enable SSL (auto-generated/standard)")
            print("  --sec CERT,KEY       Enable SSL with specific certificate and key files")
            print("\nINTERFACE:")
            print("  --color              Enable TUI status line colors")
            print("  --notui              Disable TUI (status line and screen clearing)")
            print("  --nohead             Hide the top status line (Host info)")
            print("  --echo               Enable local echo of transmitted characters")
            print("  --count              Show sent/received byte counters in status line")
            print("\nSYSTEM COMMANDS:")
            print("  --ask                Query remote server version and serial parameters")
            print("\nCONFIGURATION FILE FORMAT:")
            print("  The configuration file uses simple key=value format.")
            print("  Boolean values: true/false, yes/no, on/off, 1/0")
            print("  Example: host = 192.168.1.1")
            print("           port = 10001")
            print("           secauto = true")
            sys.exit(0)

    if not args.host or not args.port:
        print(f"{__APP_NAME__} v{__CODE_VERSION__}")
        print("Error: The following arguments are required: -H/--host, -p/--port")
        print("Use -h for short usage or --help for details.")
        sys.exit(1)
        
    return args

if __name__ == "__main__":
    if platform.system() == "Windows":
        os.system('color')
        
    cli_args = parse_args()
    client = SoEClient(cli_args)
    client.run()
