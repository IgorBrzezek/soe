# ==============================================================================
# Serial-to-TCP Bridge Server (SoE Server)
# Version: 0.0.53 [FIX - SSL HANDSHAKE & PACKET FRAGMENTATION]
# Date: 04.02.2026
# Author: Igor Brzezek
# ==============================================================================

import socket
import argparse
import threading
import time
import sys
import os
import ssl
import signal
import datetime
import glob
import re
import configparser

# --- Windows specific imports for keyboard handling ---
if sys.platform == "win32":
    import msvcrt
    import win32pipe
    import win32file
    import pywintypes
else:
    import tty
    import termios

# --- Dependencies Check ---
MISSING_LIBS = []
try:
    import serial # pip install pyserial
except ImportError:
    MISSING_LIBS.append("pyserial")

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    pass

if sys.platform == "win32":
    try:
        import win32pipe
        import win32file
        import pywintypes
        HAS_WIN32_PIPE = True
    except ImportError:
        HAS_WIN32_PIPE = False

if MISSING_LIBS or (not HAS_CRYPTO and any(arg in sys.argv for arg in ['--sec', '--secauto'])):
    print("\n[ERROR] Missing required Python libraries:")
    if "pyserial" in MISSING_LIBS:
        print("  - pyserial (Required for serial port communication)")
    if not HAS_CRYPTO:
        print("  - cryptography (Required for SSL/TLS features)")
    
    print("\nTo install missing dependencies, run:")
    install_cmd = "pip install " + " ".join(filter(None, [
        "pyserial" if "pyserial" in MISSING_LIBS else None,
        "cryptography" if not HAS_CRYPTO else None
    ]))
    print(f"  {install_cmd}\n")
    sys.exit(1)

if sys.platform == "win32" and '--namedpipe' in sys.argv and not HAS_WIN32_PIPE:
    print("\n[ERROR] Missing required Python library for named pipe support:")
    print("  - pywin32 (Required for Windows named pipe functionality)")
    print("\nTo install, run:")
    print("  pip install pywin32\n")
    sys.exit(1)

# --- Constants & Commands ---
__CODE_NAME__    = "Serial over Ethernet Server"
__CODE_AUTHOR__  = "Igor Brzezek"
__CODE_VERSION__ = "0.0.53"
__CODE_DATE__    = "04.02.2026"

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

class GlobalState:
    keep_running = True
    reload_requested = False
    disconnect_requested = False
    client_active = False
    client_type = "??"
    client_ver = ""
    stats = {"in": 0, "out": 0}
    args = None
    terminal_size = (0, 0)
    local_ip = "0.0.0.0"
    remote_ip = "???"
    remote_port = "???"
    remote_params = "?? ?? ??"
    failed_attempts = {}
    log_buffer = []
    transfer_buffer = []
    server_start_time = None
    total_sessions = 0
    session_stats = {"in": 0, "out": 0}
    active_window = 0
    scroll_offsets = [0, 0]
    # Transfer view settings
    transfer_mode = "ascii"
    transfer_filter = "all"

state = GlobalState()

# --- Named Pipe Wrapper Class ---
class NamedPipeWrapper:
    """Wrapper class to make Windows Named Pipe behave like pyserial Serial object"""
    def __init__(self, pipe_name):
        if not pipe_name.startswith('\\\\.\\pipe\\'):
            pipe_name = '\\\\.\\pipe\\' + pipe_name
        
        self.pipe_name = pipe_name
        self.pipe_handle = None
        self.connected = False
        
        # Try to connect to existing pipe first
        try:
            self.pipe_handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            self.connected = True
        except pywintypes.error:
            # Pipe doesn't exist, create it as server
            self.pipe_handle = win32pipe.CreateNamedPipe(
                pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
                1,  # max instances
                65536,  # output buffer size
                65536,  # input buffer size
                300,  # timeout in ms
                None
            )
            # Don't wait for connection here - it will be checked in in_waiting
            self.connected = False
    
    @property
    def in_waiting(self):
        """Check if data is available to read"""
        if not self.connected:
            try:
                # Try to connect if not connected yet (non-blocking check)
                win32pipe.ConnectNamedPipe(self.pipe_handle, None)
                self.connected = True
            except pywintypes.error as e:
                # ERROR_PIPE_CONNECTED means already connected
                if e.winerror == 535:  # ERROR_PIPE_CONNECTED
                    self.connected = True
                else:
                    return 0
        
        try:
            # Peek to see if data is available
            result, data, _ = win32pipe.PeekNamedPipe(self.pipe_handle, 0)
            return result
        except:
            return 0
    
    def read(self, size=1):
        """Read data from named pipe"""
        if not self.connected:
            return b""
        try:
            _, data = win32file.ReadFile(self.pipe_handle, size)
            return data
        except:
            return b""
    
    def write(self, data):
        """Write data to named pipe"""
        if not self.connected:
            return 0
        try:
            _, written = win32file.WriteFile(self.pipe_handle, data)
            return written
        except:
            return 0
    
    def close(self):
        """Close the named pipe"""
        if self.pipe_handle:
            try:
                win32pipe.DisconnectNamedPipe(self.pipe_handle)
                win32file.CloseHandle(self.pipe_handle)
            except:
                pass
            self.pipe_handle = None
            self.connected = False

def _get_term_size():
    try:
        sz = os.get_terminal_size()
        return sz.columns, sz.lines
    except: return 80, 24

def _rotate_logs(base_filename, max_files):
    if max_files <= 0: return
    files = sorted(glob.glob(f"{base_filename}*"), key=os.path.getmtime)
    while len(files) >= max_files:
        try: os.remove(files[0]); files.pop(0)
        except: break

def _get_log_filename(arg_val, max_files):
    if not arg_val: return None
    parts = arg_val.split(',')
    fname = parts[0]
    if not os.path.splitext(fname)[1]: fname += ".log"
    if len(parts) > 1 and parts[1].lower() == 'new':
        base, ext = os.path.splitext(fname); counter = 1; new_fname = fname
        while os.path.exists(new_fname):
            new_fname = f"{base}_{counter}{ext}"; counter += 1
            fname = new_fname
    if max_files: _rotate_logs(os.path.splitext(fname)[0], max_files)
    return fname

def write_to_file(filename, data, is_binary=False, max_size_kb=0, max_files=0):
    if not filename: return
    if max_size_kb > 0 and os.path.exists(filename):
        if os.path.getsize(filename) > (max_size_kb * 1024):
            _rotate_logs(os.path.splitext(filename)[0], max_files)
            base, ext = os.path.splitext(filename)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            os.rename(filename, f"{base}_{timestamp}{ext}")
    mode = "ab" if is_binary else "a"
    try:
        with open(filename, mode) as f: f.write(data)
    except: pass

def update_top_header():
    if state.args.batch or state.args.notui: return
    cols, rows = _get_term_size()
    
    is_secure = state.args.secauto or state.args.sec
    if state.args.secauto: sec_mode = "SSL (A)"
    elif state.args.sec: sec_mode = "SSL (C)"
    else: sec_mode = "!! RAW !!"

    prefix = " ACTIVE -> " if state.args.showtransfer is not None and state.active_window == 0 else " "
    buf_len = len(state.log_buffer); cur_line = max(0, buf_len - state.scroll_offsets[0])
    line_info = f" (Lines: {cur_line}/{buf_len})"
    
    if state.args.color and not state.args.mono:
        bg = UiColors._UI_COL_ACTHEAD_ if state.active_window == 0 and state.args.showtransfer is not None else UiColors._UI_COL_BG_STATUSLINE_
        fg, v_col = UiColors._UI_COL_FG_STATUSLINE_, UiColors._UI_COL_VERSION_
        
        if is_secure:
            sec_display = f"{UiColors._UI_COL_SEC_}{sec_mode}{fg}"
        else:
            sec_display = f"{UiColors._UI_COL_RAW_BG_}{UiColors._UI_COL_RAW_}{sec_mode}{Colors.RESET}{bg}{fg}"
            
        header_text_plain = f"{prefix}{__CODE_NAME__} ({__CODE_VERSION__}) | {sec_mode} | Running on {socket.gethostname()} {line_info}"
        header_text_styled = f"{prefix}{__CODE_NAME__} ({v_col}{__CODE_VERSION__}{fg}) | {sec_display} | Running on {socket.gethostname()} {line_info}"
        full_line = f"{bg}{fg}{header_text_styled.ljust(cols + (len(header_text_styled) - len(header_text_plain)))}{Colors.RESET}"
    else:
        header_text = f"{prefix}{__CODE_NAME__} v{__CODE_VERSION__} | {sec_mode} | Running on {socket.gethostname()} {line_info}"
        full_line = f"{Colors.INVERSE}{header_text.ljust(cols)}{Colors.RESET}"
    
    sys.stdout.write(f"\033[s\033[H{full_line}\033[u"); sys.stdout.flush()

def update_mid_separator():
    if state.args.showtransfer is None or state.args.batch or state.args.notui: return
    cols, rows = _get_term_size(); mid = rows // 2
    prefix = " ACTIVE -> " if state.active_window == 1 else " "
    buf_len = len(state.transfer_buffer); cur_line = max(0, buf_len - state.scroll_offsets[1])
    line_info = f" (Lines: {cur_line}/{buf_len})"; sep_text = f"{prefix}DATA TRANSFER MONITOR [{state.transfer_mode.upper()}/{state.transfer_filter.upper()}]{line_info}"
    if state.args.color and not state.args.mono:
        bg = UiColors._UI_COL_ACTHEAD_ if state.active_window == 1 else Colors.BG_BLUE
        line = f"{bg}{Colors.WHITE}{sep_text.center(cols)}{Colors.RESET}"
    else: line = f"{Colors.INVERSE}{sep_text.center(cols)}{Colors.RESET}"
    sys.stdout.write(f"\033[s\033[{mid+1};1H{line}\033[u"); sys.stdout.flush()

def render_window_content(window_id):
    if state.args.batch or state.args.notui: return
    cols, rows = _get_term_size()
    if state.args.showtransfer is None:
        if window_id != 0: return
        start_row, height, buffer, offset = 2, rows - 2, state.log_buffer, state.scroll_offsets[0]
    else:
        mid = rows // 2
        if window_id == 0: start_row, height, buffer, offset = 2, mid - 1, state.log_buffer, state.scroll_offsets[0]
        else: start_row, height, buffer, offset = mid + 2, (rows - 1) - (mid + 2) + 1, state.transfer_buffer, state.scroll_offsets[1]
    for r in range(start_row, start_row + height):
        sys.stdout.write(f"\033[{r};1H{Colors.RESET}{' ' * cols}")
    sys.stdout.write(f"\033[{start_row + height - 1};1H>")
    if not buffer: return
    end_idx = len(buffer) - offset; start_idx = max(0, end_idx - height); display_lines = buffer[start_idx:end_idx]
    for i, line in enumerate(display_lines):
        sys.stdout.write(f"\033[{start_row + (height - len(display_lines)) + i};2H{line}")
    sys.stdout.flush()

def refresh_screen():
    if state.args.batch or state.args.notui: return
    cols, rows = _get_term_size(); state.terminal_size = (cols, rows)
    sys.stdout.write(Colors.CLEAR_SCR); update_top_header(); update_mid_separator(); update_status_line()
    render_window_content(0)
    if state.args.showtransfer is not None: render_window_content(1)

def update_status_line():
    if state.args.batch or state.args.notui: return
    cols, rows = _get_term_size(); state.terminal_size = (cols, rows)
    cl_ver_str_plain = f"({state.client_ver})" if state.client_ver else ""
    prefix_type_plain = f"{state.client_type} {cl_ver_str_plain}"
    r_parts = state.remote_params.split()
    r_name = r_parts[0] if len(r_parts) > 0 else "??"
    r_speed = r_parts[1] if len(r_parts) > 1 else "??"
    r_line = r_parts[2] if len(r_parts) > 2 else "??"
    count_info = f" | IN:{state.session_stats['in']} OUT:{state.session_stats['out']}" if state.args.count else ""
    
    # Use 0.0.0.0 display if listening on all interfaces and no client is active
    disp_local_ip = state.local_ip
    if not state.client_active and (state.args.address == "0.0.0.0" or not state.args.address):
        disp_local_ip = "0.0.0.0"

    if state.args.color and not state.args.mono:
        bg, fg, v_cl_col = UiColors._UI_COL_BG_STATUSLINE_, UiColors._UI_COL_FG_STATUSLINE_, UiColors._UI_COL_CL_VERSION_
        cl_ver_str_styled = f"({v_cl_col}{state.client_ver}{fg})" if state.client_ver else ""
        line_text = (f" {state.client_type} {cl_ver_str_styled} | "
                f"L: {UiColors._UI_COL_LIP_}{disp_local_ip}{fg}:{UiColors._UI_COL_LPORT_}{state.args.port}{fg} | "
                f"R: {UiColors._UI_COL_RIP_}{state.remote_ip}{fg}:{UiColors._UI_COL_RPORT_}{state.remote_port}{fg} | "
                f"L: {UiColors._UI_COL_SPORTNAME_}{state.args.comport}{fg} {UiColors._UI_COL_SPORTSPEED_}{state.args.baud}{fg} {UiColors._UI_COL_SPORTLINE_}{state.args.line}{fg} | "
                f"R: {UiColors._UI_COL_RPORTNAME_}{r_name}{fg} {UiColors._UI_COL_RPORTSPEED_}{r_speed}{fg} {UiColors._UI_COL_RPORTLINE_}{r_line}{fg}{count_info} ")
        plain_len_text = f" {prefix_type_plain} | L: {disp_local_ip}:{state.args.port} | R: {state.remote_ip}:{state.remote_port} | L: {state.args.comport} {state.args.baud} {state.args.line} | R: {r_name} {r_speed} {r_line} | {count_info} "
        full_line = f"{bg}{fg}{line_text.ljust(cols + (len(line_text) - len(plain_len_text)))}{Colors.RESET}"
    else:
        line_text = (f" {prefix_type_plain} | L: {disp_local_ip}:{state.args.port} | R: {state.remote_ip}:{state.remote_port} | "
                     f"L: {state.args.comport} {state.args.baud} {state.args.line} | R: {r_name} {r_speed} {r_line}{count_info} ")
        full_line = f"{Colors.INVERSE}{line_text.ljust(cols)}{Colors.RESET}"
    sys.stdout.write(f"\033[s\033[{rows};1H{full_line}\033[u"); sys.stdout.flush()

def log_msg(msg, color=Colors.CYAN, is_debug=False, direction="TO_SRV"):
    if is_debug and not state.args.debug: return
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    c_brk, c_tag, c_res, c_msg = (UiColors._UI_COL_BRACKETS_ if state.args.color else ""), (UiColors._UI_COL_TAGS_ if state.args.color else ""), (Colors.RESET if state.args.color else ""), (color if state.args.color else "")
    if "SRV_TO_" in direction:
        dir_color, target = (UiColors._UI_COL_DIR_OUT_ if state.args.color else ""), ("BR" if direction == "SRV_TO_BR" else "CL")
        dir_tag_plain, dir_tag = f"[SRV->{target}]", f"{c_brk}[{dir_color}SRV->{target}{c_brk}]{c_res}"
    else:
        dir_color = UiColors._UI_COL_DIR_IN_ if state.args.color else ""
        dir_tag_plain, dir_tag = f"[{state.client_type}->SRV]", f"{c_brk}[{dir_color}{state.client_type}->SRV{c_brk}]{c_res}"
    debug_prefix_plain, debug_prefix = (" (DEBUG)" if is_debug else ""), (f" {c_brk}({c_tag}DEBUG{c_brk}){c_res}" if is_debug else "")
    full_log_line, plain_log_line = f"{ts} {dir_tag}{debug_prefix} {c_msg}{msg}{c_res}", f"{ts} {dir_tag_plain}{debug_prefix_plain} {msg}\n"
    if hasattr(state, 'log_file_path') and state.log_file_path: write_to_file(state.log_file_path, plain_log_line, max_size_kb=state.args.logsizemax, max_files=state.args.logmax)
    
    if not state.args.batch:
        if state.args.notui:
            sys.stdout.write(full_log_line + "\n")
            sys.stdout.flush()
        else:
            state.log_buffer.append(full_log_line)
            if len(state.log_buffer) > state.args.logbufferlines: state.log_buffer.pop(0)
            if state.scroll_offsets[0] == 0: render_window_content(0)
            update_top_header(); update_status_line()

def log_transfer(direction, data):
    if state.args.showtransfer is None: return
    # Apply filter
    if state.transfer_filter != "all" and direction.lower() != state.transfer_filter: return

    color = (UiColors._UI_COL_DIR_IN_ if direction == "IN" else UiColors._UI_COL_DIR_OUT_) if state.args.color else ""
    
    if state.transfer_mode == "hex":
        msg = f"Data {direction} (hex): {data.hex(' ')}"
    else:
        try: decoded = data.decode('utf-8', errors='replace'); msg = f"Data {direction}: {repr(decoded)}"
        except: msg = f"Data {direction} (hex): {data.hex()}"
        
    ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]; full_msg = f"{ts} {color}{msg}{Colors.RESET if state.args.color else ''}"
    
    if not state.args.batch:
        if state.args.notui:
            sys.stdout.write(full_msg + "\n")
            sys.stdout.flush()
        else:
            state.transfer_buffer.append(full_msg)
            if len(state.transfer_buffer) > state.args.transferbufferlines: state.transfer_buffer.pop(0)
            if state.scroll_offsets[1] == 0: render_window_content(1)
            update_mid_separator()

def kb_handler():
    def get_key():
        if sys.platform == "win32":
            if msvcrt.kbhit():
                k = msvcrt.getch()
                if k == b'\xe0': k += msvcrt.getch()
                return k
            return None
        else:
            fd = sys.stdin.fileno(); old_settings = termios.tcgetattr(fd)
            try: 
                tty.setraw(sys.stdin.fileno())
                import select
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    return ch.encode() if ch != '\x1b' else (ch + sys.stdin.read(2)).encode()
                return None
            finally: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    while state.keep_running:
        curr_c, curr_r = _get_term_size()
        if (curr_c, curr_r) != state.terminal_size: refresh_screen()
        key = get_key()
        if not key: 
            time.sleep(0.05); continue
        if (key == b'\t' or key == b'\x09') and state.args.showtransfer is not None:
            state.active_window = 1 - state.active_window; update_top_header(); update_mid_separator(); continue
        current_focus = state.active_window if state.args.showtransfer is not None else 0
        if key in [b'\xe0H', b'\x1b[A']:
            state.scroll_offsets[current_focus] += 1
            buf_len = len(state.log_buffer if current_focus == 0 else state.transfer_buffer)
            state.scroll_offsets[current_focus] = max(0, min(state.scroll_offsets[current_focus], buf_len - 5))
            if current_focus == 0: update_top_header()
            else: update_mid_separator()
            render_window_content(current_focus)
        elif key in [b'\xe0P', b'\x1b[B']:
            state.scroll_offsets[current_focus] = max(0, state.scroll_offsets[current_focus] - 1)
            if current_focus == 0: update_top_header()
            else: update_mid_separator()
            render_window_content(current_focus)
        elif key == b'\x03': handle_sigint(None, None)

def handle_sigint(signum, frame):
    if state.client_active: 
        log_msg(f"Soft disconnect initiated (CTRL-C).", Colors.YELLOW)
        state.disconnect_requested = True
    else: 
        uptime = datetime.timedelta(seconds=int(time.time() - state.server_start_time))
        log_msg("# --- SoE server is stopping ---", Colors.RED)
        log_msg(f"System shutdown initiated (CTRL-C detected). Total uptime: {uptime}", Colors.RED)
        state.keep_running = False

def handle_resize(signum, frame): refresh_screen()

signal.signal(signal.SIGINT, handle_sigint)
if sys.platform != "win32": signal.signal(signal.SIGWINCH, handle_resize)

def serial_to_socket(ser, client_conn, b_state):
    while state.keep_running and not state.reload_requested and not state.disconnect_requested:
        try:
            if not b_state['authorized']: time.sleep(0.01); continue
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting); state.stats["out"] += len(data); state.session_stats["out"] += len(data)
                if state.args.showtransfer is not None: log_transfer("OUT", data)
                if state.args.count: update_status_line()
                if hasattr(state, 'logdata_file_path') and state.logdata_file_path: write_to_file(state.logdata_file_path, data, is_binary=True, max_size_kb=state.args.logdatasizemax, max_files=state.args.logdatamax)
                client_conn.sendall(data)
            time.sleep(0.001)
        except: break

def generate_self_signed_cert():
    log_msg("Action: Generating self-signed SSL certificate...", Colors.WHITE, is_debug=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"serial-bridge")])
    cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.utcnow()).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365)).sign(key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.PEM), key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())


DEFAULT_CONFIG = {
    'port': None,
    'address': "0.0.0.0",
    'comport': "COM1" if sys.platform == "win32" else "/dev/ttyS0",
    'baud': 9600,
    'line': "8N1N",
    'keepalive': 120,
    'secauto': False,
    'sec': None,
    'pwd': None,
    'log': None,
    'logmax': 10,
    'logsizemax': 4096,
    'logdata': None,
    'logdatamax': 10,
    'logdatasizemax': 8192,
    'logbufferlines': 2000,
    'transferbufferlines': 2000,
    'color': False,
    'mono': False,
    'count': False,
    'debug': False,
    'showtransfer': None, 
    'cfgfile': None,
    'notui': False,
    'batch': False,
    'namedpipe': None,
    'h': False,
    'help': False,
    'version': False
}

def validate_args(args):
    """Validate command line arguments and configuration values"""
    
    # Check port is provided and valid
    if args.port is None:
        print("[ERROR] Port is mandatory. Use -p PORT or port in config file.")
        return False
    if not isinstance(args.port, int) or args.port <= 0 or args.port > 65535:
        print(f"[ERROR] Invalid port number: {args.port}. Must be between 1 and 65535.")
        return False
    
    # Check address is valid
    if args.address:
        import socket as sock_check
        try:
            sock_check.inet_aton(args.address)
        except sock_check.error:
            print(f"[ERROR] Invalid IP address: {args.address}")
            return False
    
    # Check that either --comport or --namedpipe is provided, but not both
    has_comport = args.comport is not None
    has_namedpipe = args.namedpipe is not None
    
    if has_comport and has_namedpipe:
        print("[ERROR] Cannot use both --comport and --namedpipe simultaneously. Choose one.")
        return False
    
    if not has_comport and not has_namedpipe:
        print("[ERROR] Either --comport or --namedpipe must be specified.")
        return False
    
    # Validate --namedpipe on Windows only
    if has_namedpipe and sys.platform != "win32":
        print("[ERROR] --namedpipe is only available on Windows. Use --comport on Linux/Mac.")
        return False
    
    # Validate baud rate
    valid_bauds = [300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
    if args.baud not in valid_bauds:
        print(f"[ERROR] Invalid baud rate: {args.baud}. Valid values: {valid_bauds}")
        return False
    
    # Validate line format (should be 4 chars: DataBits[5-8], Parity[N/O/E], StopBits[1/2], Flow[N/X/H])
    if not isinstance(args.line, str) or len(args.line) != 4:
        print(f"[ERROR] Invalid line format: {args.line}. Must be 4 characters (e.g., 8N1N).")
        return False
    
    data_bits = args.line[0]
    parity = args.line[1]
    stop_bits = args.line[2]
    flow = args.line[3]
    
    if data_bits not in ['5', '6', '7', '8']:
        print(f"[ERROR] Invalid data bits in line format: {data_bits}. Must be 5, 6, 7, or 8.")
        return False
    
    if parity not in ['N', 'O', 'E', 'M', 'S']:
        print(f"[ERROR] Invalid parity in line format: {parity}. Must be N(one), O(dd), E(ven), M(ark), or S(pace).")
        return False
    
    if stop_bits not in ['1', '2']:
        print(f"[ERROR] Invalid stop bits in line format: {stop_bits}. Must be 1 or 2.")
        return False
    
    if flow not in ['N', 'X', 'H', 'R']:
        print(f"[ERROR] Invalid flow control in line format: {flow}. Must be N(one), X(on/Xoff), H(ardware RTS/CTS), or R(TS/CTS).")
        return False
    
    # Validate keepalive
    if not isinstance(args.keepalive, int) or args.keepalive < 0:
        print(f"[ERROR] Invalid keepalive value: {args.keepalive}. Must be non-negative integer.")
        return False
    
    # Validate SSL options
    if args.secauto and args.sec:
        print("[ERROR] Cannot use both --secauto and --sec simultaneously. Choose one SSL method.")
        return False
    
    # Validate logmax and logsizemax
    if not isinstance(args.logmax, int) or args.logmax < 1:
        print(f"[ERROR] Invalid logmax: {args.logmax}. Must be at least 1.")
        return False
    
    if not isinstance(args.logsizemax, int) or args.logsizemax < 1:
        print(f"[ERROR] Invalid logsizemax: {args.logsizemax}. Must be at least 1.")
        return False
    
    # Validate logdatamax and logdatasizemax
    if not isinstance(args.logdatamax, int) or args.logdatamax < 1:
        print(f"[ERROR] Invalid logdatamax: {args.logdatamax}. Must be at least 1.")
        return False
    
    if not isinstance(args.logdatasizemax, int) or args.logdatasizemax < 1:
        print(f"[ERROR] Invalid logdatasizemax: {args.logdatasizemax}. Must be at least 1.")
        return False
    
    # Validate buffer lines
    if not isinstance(args.logbufferlines, int) or args.logbufferlines < 10:
        print(f"[ERROR] Invalid logbufferlines: {args.logbufferlines}. Must be at least 10.")
        return False
    
    if not isinstance(args.transferbufferlines, int) or args.transferbufferlines < 10:
        print(f"[ERROR] Invalid transferbufferlines: {args.transferbufferlines}. Must be at least 10.")
        return False
    
    # Validate showtransfer format if provided
    if args.showtransfer:
        parts = args.showtransfer.split(',')
        if len(parts) > 0:
            fmt = parts[0].lower()
            if fmt not in ['ascii', 'hex']:
                print(f"[ERROR] Invalid showtransfer format: {fmt}. Must be 'ascii' or 'hex'.")
                return False
        if len(parts) > 1:
            direction = parts[1].lower()
            if direction not in ['in', 'out', 'all']:
                print(f"[ERROR] Invalid showtransfer direction: {direction}. Must be 'in', 'out', or 'all'.")
                return False
    
    # Validate color options
    if args.color and args.mono:
        print("[ERROR] Cannot use both --color and --mono. Choose one.")
        return False
    
    return True

def load_hierarchical_config():
    config = DEFAULT_CONFIG.copy()
    temp_parser = argparse.ArgumentParser(add_help=False)
    temp_parser.add_argument("--cfgfile")
    temp_args, _ = temp_parser.parse_known_args()
    config_paths = []
    if temp_args.cfgfile: config_paths.append(temp_args.cfgfile)
    
    for path in config_paths:
        if os.path.exists(path):
            cp = configparser.ConfigParser()
            try:
                with open(path, 'r') as f: file_content = f.read()
                try: cp.read_string(file_content)
                except configparser.MissingSectionHeaderError: cp.read_string('[DEFAULT]\n' + file_content)

                # 1. Parse Standard Options (from DEFAULT or other sections)
                int_keys = ['port', 'baud', 'keepalive', 'logmax', 'logsizemax', 'logdatamax', 'logdatasizemax', 'logbufferlines', 'transferbufferlines']
                
                # List of sections to scan (DEFAULT + others, skipping COLORS)
                sections_to_scan = []
                if 'DEFAULT' in cp: sections_to_scan.append(cp['DEFAULT'])
                for sec_name in cp.sections():
                    if sec_name == 'COLORS': continue
                    sections_to_scan.append(cp[sec_name])

                for section_data in sections_to_scan:
                    for key in config:
                        if key == 'showtransfer': continue
                        # Check keys regardless of case
                        for k in section_data:
                            if k.lower() == key.lower():
                                val = section_data[k]
                                # Remove inline comments
                                if '#' in val: val = val.split('#')[0].strip()
                                
                                if key in int_keys: 
                                    try: config[key] = int(val)
                                    except: pass
                                elif isinstance(DEFAULT_CONFIG[key], bool): 
                                    try: 
                                        v_lower = str(val).strip().lower()
                                        if v_lower in ['true', '1', 'yes', 'on']: config[key] = True
                                        elif v_lower in ['false', '0', 'no', 'off']: config[key] = False
                                    except: pass
                                elif isinstance(DEFAULT_CONFIG[key], int): 
                                    try: config[key] = int(val)
                                    except: pass
                                else: 
                                    config[key] = str(val).strip()
                                break
                
                # 2. Parse Custom Colors (from [COLORS] section)
                if 'COLORS' in cp:
                    for key in cp['COLORS']:
                        col_val_name = cp['COLORS'][key]
                        if '#' in col_val_name: col_val_name = col_val_name.split('#')[0].strip()
                        attr_name = f"_UI_COL_{key.upper()}_"
                        col_code = getattr(Colors, col_val_name.upper(), Colors.WHITE)
                        if hasattr(UiColors, attr_name):
                            setattr(UiColors, attr_name, col_code)
            
            except Exception as e:
                pass

    # Override with command line arguments
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-p', '--port', type=int)
    parser.add_argument('-a', '--address')
    parser.add_argument('--comport')
    parser.add_argument('--baud', type=int)
    parser.add_argument('--line')
    parser.add_argument('--keepalive', type=int)
    parser.add_argument('--secauto', action='store_true', default=None)
    parser.add_argument('--sec')
    parser.add_argument('--color', action='store_true', default=None)
    parser.add_argument('--mono', action='store_true', default=None)
    parser.add_argument('--count', action='store_true', default=None)
    parser.add_argument('--showtransfer', nargs='?', const='ascii,all', default=None)
    parser.add_argument('--debug', action='store_true', default=None)
    parser.add_argument('--pwd')
    parser.add_argument('--version', action='store_true', default=False)
    parser.add_argument('-h', action='store_true', default=False)
    parser.add_argument('--help', action='store_true', default=False)
    parser.add_argument('--log')
    parser.add_argument('--logmax', type=int)
    parser.add_argument('--logsizemax', type=int)
    parser.add_argument('--logdata')
    parser.add_argument('--logdatamax', type=int)
    parser.add_argument('--logdatasizemax', type=int)
    parser.add_argument('-b', '--batch', action='store_true', default=None)
    parser.add_argument('--notui', action='store_true', default=None)
    parser.add_argument('--logbufferlines', type=int)
    parser.add_argument('--transferbufferlines', type=int)
    parser.add_argument("--cfgfile") # Added to avoid unrecognized argument error
    parser.add_argument('--namedpipe')
    
    cli_args, _ = parser.parse_known_args()
    for key, value in vars(cli_args).items():
        if value is not None: config[key] = value
        
    return argparse.Namespace(**config)

def main():
    args = load_hierarchical_config(); state.args = args
    
    if args.h:
        print(f"{__CODE_NAME__} v{__CODE_VERSION__} ({__CODE_DATE__}) by {__CODE_AUTHOR__}")
        print("Usage: [-p PORT] [-a ADDR] [--comport COM | --namedpipe NAME] [--baud BAUD] [--line LINE] [--pwd PWD] [--sec|--secauto] [--log FILE[,new]] [--logmax N] [--logsizemax N] [--logdata FILE[,new]] [--logdatamax N] [--logdatasizemax N] [--debug] [--color] [--mono] [--count] [--showtransfer [ascii|hex[,in|out|all]]] [-b|--batch] [--notui] [--logbufferlines M] [--transferbufferlines N]")
        sys.exit(0)

    if args.help:
        print(f"\n{__CODE_NAME__} v{__CODE_VERSION__}")
        print(f"Author: {__CODE_AUTHOR__} | Date: {__CODE_DATE__}\n")
        print("COMMUNICATION SETTINGS:")
        print(f"  -p, --port PORT      TCP listening port (required)")
        print(f"  -a, --address ADDR   IP address to bind (default: 0.0.0.0)")
        print(f"  --comport COM        Serial port name (default: {'COM1' if sys.platform == 'win32' else '/dev/ttyS0'})")
        print(f"  --namedpipe NAME     Windows Named Pipe name (Windows only, instead of --comport)")
        print(f"                       If pipe exists, connects to it; otherwise creates it")
        print(f"                       Example: --namedpipe mypipe or --namedpipe \\\\.\\pipe\\mypipe")
        print(f"  --baud BAUD          Baud rate (default: 9600)")
        print(f"  --line LINE          Serial params: [DataBits][Parity][StopBits][Flow] (default: 8N1N)")
        print(f"                       (e.g. 8N1N - 8 bits, None, 1 stop, No flow)")
        print(f"  --keepalive SEC      Keepalive interval in seconds (default: 120)")
        print("\nSECURITY:")
        print(f"  --pwd PASSWORD       Password required for client connection (default: None)")
        print(f"  --secauto            Enable SSL with auto-generated certificate (default: False)")
        print(f"  --sec CERT,KEY       Enable SSL using provided files (default: None)")
        print("\nLOGGING:")
        print(f"  --log FILE[,new]     Log system messages to FILE (default: None)")
        print(f"  --logmax N           Max number of rotated system logs (default: 10)")
        print(f"  --logsizemax N       Max size of system log file in kB (default: 4096)")
        print(f"  --logdata FILE[,new] Log raw serial data to FILE (default: None)")
        print(f"  --logdatamax N       Max number of rotated data logs (default: 10)")
        print(f"  --logdatasizemax N   Max size of data log file in kB (default: 8192)")
        print("\nINTERFACE & DEBUG:")
        print(f"  --debug              Enable verbose debug messages (default: False)")
        print(f"  --color              Enable rich color interface (default: False)")
        print(f"  --mono               Disable colors even if --color is set (default: False)")
        print(f"  --count              Display Data Counters in status line (default: False)")
        print(f"  --showtransfer [ARG] Display real-time IO data transfer in logs (default: None)")
        print(f"                       Arguments: [ascii|hex[,in|out|all]] (default const: ascii,all)")
        print(f"  -b, --batch          Batch mode: no screen output (default: False)")
        print(f"  --notui              Disable TUI interface (default: False)")
        print(f"  --logbufferlines M   Max lines in system log buffer (default: 2000)")
        print(f"  --transferbufferlines N Max lines in data monitor buffer (default: 2000)")
        print(f"  --version            Show program version and exit")
        print(f"  -h                   Show simple usage one-liner")
        print(f"  --help               Show this detailed help information")
        sys.exit(0)

    if args.showtransfer:
        parts = args.showtransfer.split(',')
        if len(parts) >= 1:
            m = parts[0].lower()
            if m in ['ascii', 'hex']: state.transfer_mode = m
        if len(parts) >= 2:
            f = parts[1].lower()
            if f in ['in', 'out', 'all']: state.transfer_filter = f

    state.log_file_path, state.logdata_file_path = _get_log_filename(args.log, args.logmax), _get_log_filename(args.logdata, args.logdatamax)
    if args.version: print(f"{__CODE_NAME__} ({__CODE_VERSION__})"); sys.exit(0)
    if sys.platform == "win32" and not args.batch: os.system('color')

    # Comprehensive argument validation
    if not validate_args(args):
        sys.exit(1)
    
    # Validate named pipe usage
    state.server_start_time = time.time(); refresh_screen()
    log_msg("# --- SoE server is starting ---", Colors.GREEN)
    
    ssl_status = "DISABLED"
    if args.secauto: ssl_status = "ENABLED (Auto-Self-Signed)"
    elif args.sec: ssl_status = "ENABLED (Certificate File)"
    log_msg(f"Config: SSL={ssl_status} | Port={args.port} | ComPort={args.comport}", Colors.YELLOW)

    startup_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg(f"Action: Server started at {startup_ts} (Version: {__CODE_VERSION__})", Colors.GREEN)
    
    if not args.batch and not args.notui:
        threading.Thread(target=kb_handler, daemon=True).start()

    # --- SSL Setup (Once) ---
    ctx = None
    if args.secauto or args.sec:
        try:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            if args.secauto:
                c_bytes, k_bytes = generate_self_signed_cert()
                with open("temp.crt", "wb") as f: f.write(c_bytes); f.flush(); os.fsync(f.fileno())
                with open("temp.key", "wb") as f: f.write(k_bytes); f.flush(); os.fsync(f.fileno())
                ctx.load_cert_chain(certfile="temp.crt", keyfile="temp.key")
            elif args.sec:
                cp, kp = args.sec.split(',')
                ctx.load_cert_chain(certfile=cp.strip(), keyfile=kp.strip())
        except Exception as e:
            log_msg(f"Fatal Error: SSL Setup Failed: {e}", Colors.RED)
            sys.exit(1)

    try:
        while state.keep_running:
            try:
                # Initialize serial port or named pipe
                if args.namedpipe:
                    log_msg(f"Action: Opening Named Pipe: {args.namedpipe}", Colors.GREEN, is_debug=True)
                    ser = NamedPipeWrapper(args.namedpipe)
                    log_msg(f"Success: Named Pipe opened: {args.namedpipe}", Colors.GREEN)
                    # Update comport display name for status line
                    args.comport = f"PIPE:{args.namedpipe}"
                else:
                    ser = serial.Serial(port=args.comport, baudrate=args.baud, timeout=0.1)
                
                listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); listen_sock.bind((args.address, args.port)); listen_sock.listen(5); listen_sock.settimeout(0.5)
                while state.keep_running and not state.reload_requested:
                    state.client_active, state.disconnect_requested, state.client_type, state.client_ver, state.remote_params, state.session_stats = False, False, "??", "", "?? ?? ??", {"in": 0, "out": 0}
                    state.local_ip = args.address if (args.address and args.address != "0.0.0.0") else "0.0.0.0"
                    state.remote_ip, state.remote_port = "???", "???"
                    update_status_line(); conn = None
                    log_msg("Status: Waiting for connection...", Colors.WHITE)
                    while state.keep_running and not state.reload_requested:
                        try: 
                            conn, addr = listen_sock.accept(); state.remote_ip, state.remote_port = addr
                            state.local_ip = conn.getsockname()[0]
                            state.client_active, state.total_sessions = True, state.total_sessions + 1; break
                        except socket.timeout: continue
                    if not conn: break
                    session_start = time.time()
                    
                    # Reset timeout for handshake/initial communication (blocking mode recommended for SSL handshake)
                    conn.settimeout(None) 
                    
                    if ctx:
                        try: 
                            log_msg("Action: Initiating SSL Handshake...", Colors.WHITE, is_debug=True)
                            conn = ctx.wrap_socket(conn, server_side=True)
                            log_msg("Success: SSL Handshake completed.", Colors.GREEN, is_debug=True)
                        except Exception as e: log_msg(f"Error: SSL Handshake Failed: {e}", Colors.RED); conn.close(); continue
                    
                    log_msg(f"Action: Outgoing GETVER to {state.remote_ip}", Colors.MAGENTA, is_debug=True, direction="SRV_TO_CL")
                    conn.sendall(GETVER_CMD); conn.sendall(GET_KA_TIMEOUT_CMD)
                    b_state = {'authorized': not args.pwd}
                    threading.Thread(target=serial_to_socket, args=(ser, conn, b_state), daemon=True).start()
                    
                    conn.settimeout(0.1)
                    packet_buffer = b""
                    while state.keep_running and not state.reload_requested and not state.disconnect_requested:
                        try:
                            data = conn.recv(16384)
                            if not data: break
                            
                            if packet_buffer:
                                data = packet_buffer + data
                                packet_buffer = b""

                            if b"__#" in data:
                                if b"#__" not in data:
                                    packet_buffer = data
                                    continue
                                
                                decoded_str = data.decode(errors='replace')
                                if KEEPALIVE_CMD in data:
                                    log_msg("Status: Received KEEPALIVE", Colors.WHITE, is_debug=True)
                                if b"_VER_" in data:
                                    try:
                                        for part in decoded_str.split('__#'):
                                            if 'BR_VER_' in part or 'CL_VER_' in part:
                                                state.client_type = "CL" if "CL_VER" in part else "BR"; state.client_ver = part.split("VER_")[1].split('#')[0]
                                                log_msg(f"Status: Client Identified as {state.client_type} (v{state.client_ver})", Colors.GREEN)
                                                if not args.pwd:
                                                    b_state['authorized'] = True
                                                    if state.client_type == "BR":
                                                        srv_params = f"__#COM_PARAMS_{state.args.comport} {state.args.baud} {state.args.line}#__"
                                                        conn.sendall(srv_params.encode()); conn.sendall(ASK_CMD)
                                    except: pass
                                if GETVER_CMD in data: conn.sendall(f"__#SRV_VER_{__CODE_VERSION__}#__".encode())
                                if GET_KA_TIMEOUT_CMD in data: conn.sendall(f"__#MY_KA_TIMEOUT_{state.args.keepalive}#__".encode())
                                if ASK_CMD in data: 
                                    srv_params = f"__#COM_PARAMS_{state.args.comport} {state.args.baud} {state.args.line}#__"
                                    conn.sendall(srv_params.encode())
                                
                                # --- PARSING COM_PARAMS FROM BRIDGE ---
                                if b"__#COM_PARAMS_" in data:
                                    try:
                                        param_content = decoded_str.split("__#COM_PARAMS_")[1].split("#__")[0]
                                        state.remote_params = param_content.strip()
                                        log_msg(f"Status: Received Remote Params: {state.remote_params}", Colors.GREEN, is_debug=True)
                                    except: pass

                                if b"__#PWD_" in data:
                                    try:
                                        received_pwd = decoded_str.split("__#PWD_")[1].split("#")[0]
                                        if received_pwd == args.pwd:
                                            b_state['authorized'] = True; log_msg("Status: Password Correct. Access Granted.", Colors.GREEN)
                                            if state.client_type == "BR":
                                                srv_params = f"__#COM_PARAMS_{state.args.comport} {state.args.baud} {state.args.line}#__"
                                                conn.sendall(srv_params.encode()); conn.sendall(ASK_CMD)
                                        else: log_msg(f"Security: Invalid Password attempt from {state.remote_ip}", Colors.RED); conn.sendall(BAD_PWD_MSG); time.sleep(0.5); break
                                    except: pass
                                if DISCONNECT_CMD in data: break
                            else:
                                if not b_state['authorized'] and args.pwd:
                                    # Buffer potential fragmented command start (e.g. "_")
                                    if len(data) < 20 and not packet_buffer:
                                        packet_buffer = data
                                        continue
                                    log_msg(f"Security: Raw data rejected (Unauthorized) from {state.remote_ip}", Colors.RED); break
                                else:
                                    state.stats["in"] += len(data); state.session_stats["in"] += len(data)
                                    if state.args.showtransfer is not None: log_transfer("IN", data)
                                    if state.args.count: update_status_line()
                                    if hasattr(state, 'logdata_file_path') and state.logdata_file_path: write_to_file(state.logdata_file_path, data, is_binary=True, max_size_kb=state.args.logdatasizemax, max_files=state.args.logdatamax)
                                    ser.write(data) 
                            update_status_line()
                        except socket.timeout:
                            if state.disconnect_requested or not state.keep_running: break
                            continue
                        except: break
                    
                    if state.disconnect_requested:
                        try: conn.sendall(DISCONNECT_CMD)
                        except: pass
                        time.sleep(0.2)

                    log_msg(f"Session ended. Duration: {datetime.timedelta(seconds=int(time.time()-session_start))} | IN: {state.session_stats['in']} OUT: {state.session_stats['out']}", Colors.RED)
                    conn.close(); state.client_active = False
                    state.remote_ip, state.remote_port = "???", "???"
                    state.local_ip = args.address if (args.address and args.address != "0.0.0.0") else "0.0.0.0"
                    update_status_line()
            except Exception as e:
                if state.keep_running: log_msg(f"Error: {e}", Colors.RED); time.sleep(2)
            finally:
                try: ser.close()
                except: pass
                try: listen_sock.close()
                except: pass
    finally:
        if not args.batch:
            if not args.notui:
                cols, rows = _get_term_size(); sys.stdout.write(f"\033[{rows+1};1H\n")
            total_duration = datetime.timedelta(seconds=int(time.time() - state.server_start_time))
            print(f"\n{__TXT_SUMMARY__}\n{__CODE_NAME__}")
            if not state.keep_running:
                print(f"Server shutdown initiated by user (CTRL-C detected).")
            print(f"Server uptime: {total_duration}")
            print(f"Total sessions: {state.total_sessions} | Data IN: {state.stats['in']}, OUT: {state.stats['out']}")
            print(f"End time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        for f in ["temp.crt", "temp.key"]:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__": main()
