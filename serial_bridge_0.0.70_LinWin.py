# ==============================================================================
# Serial over Ethernet Bridge
# Version: 0.0.70 [FIX: Proper DEFAULT_CONFIG Fallback]
# Date: 04.02.2026
# Author: Igor Brzezek
# ==============================================================================

import sys
import os
import socket
import ssl
import threading
import time
import argparse
import platform
import select
import datetime
import signal
import glob
import configparser
import re

if sys.platform == "win32":
    import msvcrt
    try:
        import win32pipe
        import win32file
        import win32event
        import win32api
        import winerror
        import pywintypes
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
else:
    import tty
    import termios

try:
    import serial
except ImportError:
    if "--batch" not in sys.argv and "-b" not in sys.argv:
        print("\n[ERROR] Missing 'pyserial' library.")
    else:
        sys.stderr.write("[ERROR] Missing 'pyserial' library.\n")
    sys.exit(1)

__APP_NAME__    = "Serial over Ethernet Bridge"
__CODE_AUTHOR__  = "Igor Brzezek"
__CODE_VERSION__ = "0.0.70"
__CODE_DATE__    = "04.02.2026"

# Protocol Constants
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

# Application Default Configuration
DEFAULT_CONFIG = {
    'host': None,
    'port': None,
    'comport': None,
    'namedpipe': None,
    'baud': 9600,
    'line': "8N1N",
    'keepalive': 30,
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
    'count': False,
    'debug': False,
    'showtransfer': None, 
    'cfgfile': None,
    'notui': False,
    'batch': False,
    'ask': False,
    'h': False,
    'help': False,
    'version': False
}

class Colors:
    RESET       = "\033[0m"
    RED         = "\033[91m"
    GREEN       = "\033[92m"
    YELLOW      = "\033[93m"
    BLUE        = "\033[94m"
    MAGENTA     = "\033[95m"
    CYAN        = "\033[96m"
    WHITE       = "\033[97m"
    BG_BLACK    = "\033[40m"
    BG_RED      = "\033[41m"
    BG_GREEN    = "\033[42m"
    BG_YELLOW   = "\033[43m"
    BG_BLUE     = "\033[44m"
    BG_MAGENTA  = "\033[45m"
    BG_CYAN     = "\033[46m"
    BG_WHITE    = "\033[47m"
    INVERSE     = "\033[7m"
    BOLD        = "\033[1m"
    CLEAR_LINE  = "\033[K"
    CLEAR_SCR   = "\033[2J\033[H"

    @staticmethod
    def get_by_name(name):
        return getattr(Colors, name.upper(), Colors.WHITE)

class UiColors:
    _UI_COL_TIME_    = Colors.WHITE
    _UI_COL_INFO_    = Colors.GREEN
    _UI_COL_OK_      = Colors.GREEN
    _UI_COL_ERR_     = Colors.RED
    _UI_COL_CMD_     = Colors.MAGENTA
    _UI_COL_CMD_RESP_= Colors.WHITE
    _UI_COL_VERSION_    = Colors.CYAN
    _UI_COL_SRV_VERSION_ = Colors.CYAN
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
    _UI_COL_SEC_        = Colors.GREEN
    _UI_COL_BG_STATUSLINE_ = Colors.BG_BLUE
    _UI_COL_FG_STATUSLINE_ = Colors.WHITE
    _UI_COL_DIR_IN_     = Colors.GREEN
    _UI_COL_DIR_OUT_    = Colors.MAGENTA
    _UI_COL_ACTHEAD_    = Colors.BG_RED
    _UI_COL_LASTLINE_   = Colors.GREEN

def get_server_info_full_handshake(args):
    res = {"version": "Unknown", "params": "Unknown"}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((args.host, args.port))
        
        if args.secauto or args.sec:
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            if args.sec:
                cp, kp = args.sec.split(',')
                ctx.load_cert_chain(certfile=cp.strip(), keyfile=kp.strip())
            sock = ctx.wrap_socket(sock, server_hostname=args.host)
        
        sock.sendall(f"__#BR_VER_{__CODE_VERSION__}#__".encode())
        
        if (args.secauto or args.sec) and args.pwd:
            sock.sendall(f"__#PWD_{args.pwd}#__".encode())
            
        sock.sendall(GETVER_CMD)
        sock.sendall(ASK_CMD)
        
        start_t = time.time()
        while time.time() - start_t < 3:
            r, _, _ = select.select([sock], [], [], 0.5)
            if r:
                data = sock.recv(4096)
                if not data: break
                decoded = data.decode(errors='replace')
                if "SRV_VER_" in decoded:
                    res["version"] = decoded.split("SRV_VER_")[1].split("#")[0]
                if "__#COM_PARAMS_" in decoded:
                    res["params"] = decoded.split("__#COM_PARAMS_")[1].split("#__")[0].strip()
                
                if res["version"] != "Unknown" and res["params"] != "Unknown":
                    break
        sock.close()
    except Exception as e:
        if getattr(args, 'debug', False): print(f"DEBUG: Ask Error: {e}")
    return res

class SerialBridgeNode:
    def __init__(self, args):
        self.args = args
        self.keep_running = True
        self.serial_ready = False
        self.awaiting_params = False
        self.net_conn = None
        self.ser_obj = None
        self.pipe_connected = False
        self.pipe_overlapped_read = None
        self.pipe_overlapped_write = None
        self.is_sec = False
        self.sec_mode_str = "RAW"
        self.remote_params = "?? ?? ??"
        self.__SRV_VER__ = "???"
        self.local_ip = "0.0.0.0"
        self.local_port = 0
        self.in_count = 0
        self.out_count = 0
        self.session_start = None
        self.log_buffer = []
        self.transfer_buffer = []
        self.active_window = 0 
        self.scroll_offsets = [0, 0]
        self.cols, self.rows = self._get_term_size()
        
        self.tm_format = "ascii"
        self.tm_direction = "all"
        self._parse_showtransfer()

        self.log_file_path = self._get_log_filename(args.log, args.logmax)
        self.logdata_file_path = self._get_log_filename(args.logdata, args.logdatamax)
        
        # Modem Status Tracking
        self.prev_modem_signals = {}

        # Screen update lock to prevent thread race conditions
        self.screen_lock = threading.RLock()
        
        signal.signal(signal.SIGINT, self.signal_handler)
        if platform.system() != "Windows" and not self.args.notui and not self.args.batch:
            signal.signal(signal.SIGWINCH, self.handle_resize)

    def _parse_showtransfer(self):
        val = getattr(self.args, 'showtransfer', None)
        if val:
            parts = val.split(',')
            if len(parts) >= 1: self.tm_format = parts[0].lower()
            if len(parts) >= 2: self.tm_direction = parts[1].lower()

    def _get_log_filename(self, arg_val, max_files):
        if not arg_val: return None
        parts = arg_val.split(',')
        fname = parts[0]
        if not os.path.splitext(fname)[1]: fname += ".log"
        if len(parts) > 1 and parts[1].lower() == 'new':
            base, ext = os.path.splitext(fname); counter = 1; new_fname = fname
            while os.path.exists(new_fname):
                new_fname = f"{base}_{counter}{ext}"; counter += 1
            fname = new_fname
        if max_files: self._rotate_logs(os.path.splitext(fname)[0], max_files)
        return fname

    def _rotate_logs(self, base_filename, max_files):
        if max_files <= 0: return
        files = sorted(glob.glob(f"{base_filename}*"), key=os.path.getmtime)
        while len(files) >= max_files:
            try: os.remove(files[0]); files.pop(0)
            except: break

    def _strip_ansi_codes(self, data):
        """Remove ALL ANSI/SGR codes from binary data."""
        if not isinstance(data, bytes):
            return data
        
        cleaned = data
        # Remove SGR patterns
        cleaned = re.sub(rb'\[[0-9;]*[0-9A-Za-z]', b'', cleaned)
        cleaned = re.sub(rb'\[K', b'', cleaned)
        cleaned = re.sub(rb'\[m', b'', cleaned)
        cleaned = re.sub(rb'\[\[', b'', cleaned)
        cleaned = re.sub(rb'^\[+', b'', cleaned)
        
        # Remove control characters (0-31, 127) except TAB (9), LF (10), CR (13)
        cleaned = bytes(b for b in cleaned if (32 <= b <= 126) or b in (9, 10, 13))
        
        return cleaned

    def _sanitize_for_tui(self, text):
        """Sanitize text for TUI display to prevent layout breakage."""
        if not isinstance(text, str): return str(text)
        
        # 1. Strip ANSI CSI codes (enhanced to include private modes '?' and other common chars)
        text = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', text)
        
        # 2. Replace common formatting characters with safe alternatives
        text = text.replace('\n', ' ').replace('\r', '').replace('\t', '    ')
        
        # 3. Remove ALL remaining control characters (ASCII 0-31), including stray \x1b
        # This ensures no command sequences can leak through to the terminal
        text = ''.join(ch for ch in text if ord(ch) >= 32)
        
        return text

    def _write_to_file(self, filename, data, is_binary=False, max_size_kb=0, max_files=0, strip_ansi=False):
        if not filename: return
        if max_size_kb > 0 and os.path.exists(filename):
            if os.path.getsize(filename) > (max_size_kb * 1024):
                self._rotate_logs(os.path.splitext(filename)[0], max_files)
                base, ext = os.path.splitext(filename)
                os.rename(filename, f"{base}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
        
        if strip_ansi and isinstance(data, bytes):
            data = self._strip_ansi_codes(data)
        
        mode = "ab" if is_binary else "a"
        try:
            with open(filename, mode) as f: f.write(data)
        except: pass

    def _get_term_size(self):
        try:
            sz = os.get_terminal_size()
            return sz.columns, sz.lines
        except: return 80, 24

    def handle_resize(self, signum, frame):
        with self.screen_lock:
            self.refresh_screen()

    def refresh_screen(self):
        if self.args.batch or self.args.notui: return
        with self.screen_lock:
            self.cols, self.rows = self._get_term_size()
            sys.stdout.write(Colors.CLEAR_SCR)
            self.update_top_header()
            if self.args.showtransfer:
                self.update_mid_separator()
            self.render_windows()
            self.update_status_line()

    def update_top_header(self):
        if self.args.batch or self.args.notui: return
        with self.screen_lock:
            cols, _ = self._get_term_size()
            cols = max(1, cols - 1)  # Reduce width by 1 to prevent auto-wrap
            hostname = socket.gethostname()[:15] # Truncate hostname
            sec_color = UiColors._UI_COL_SEC_ if self.is_sec else UiColors._UI_COL_RAW_
            sec_info = f" | {sec_color}{self.sec_mode_str}{Colors.RESET if self.args.color else ''}"
            
            total = len(self.log_buffer)
            current = total - self.scroll_offsets[0]
            scroll_info = f" (Lines: {current}/{total})"
            prefix = " ACTIVE -> " if self.active_window == 0 and self.args.showtransfer else " "

            if self.args.color:
                bg = UiColors._UI_COL_ACTHEAD_ if self.active_window == 0 and self.args.showtransfer else UiColors._UI_COL_BG_STATUSLINE_
                fg = UiColors._UI_COL_FG_STATUSLINE_
                v_col = UiColors._UI_COL_VERSION_
                
                sec_info_plain = f" | {self.sec_mode_str}"
                header_text_plain = f"{prefix}{__APP_NAME__} ({__CODE_VERSION__}){sec_info_plain} | Running on {hostname}{scroll_info} | "
                
                # Check for overflow
                if len(header_text_plain) > cols:
                    # Emergency truncation of info to fit
                    available = max(0, cols - len(prefix) - len(__APP_NAME__) - 10)
                    header_text_styled = f"{prefix}{__APP_NAME__} {bg}{fg}(...){Colors.RESET}"
                    header_text_plain = f"{prefix}{__APP_NAME__} (...)"
                else:
                    header_text_styled = f"{prefix}{__APP_NAME__} ({v_col}{__CODE_VERSION__}{fg}){sec_info}{bg}{fg} | Running on {hostname}{scroll_info} | "
                
                full_line = f"{bg}{fg}{header_text_styled.ljust(cols + (len(header_text_styled) - len(header_text_plain)))}{Colors.RESET}"
            else:
                header_text = f"{prefix}{__APP_NAME__} v{__CODE_VERSION__} | {self.sec_mode_str} | Running on {hostname}{scroll_info} | "
                if len(header_text) > cols: header_text = header_text[:cols]
                full_line = f"{Colors.INVERSE}{header_text.ljust(cols)}{Colors.RESET}"
            sys.stdout.write(f"\033[s\033[H{full_line}\033[u"); sys.stdout.flush()

    def update_mid_separator(self):
        if self.args.batch or self.args.notui: return
        with self.screen_lock:
            if self.args.showtransfer:
                cols, rows = self._get_term_size()
                cols = max(1, cols - 1) # Reduce width
                mid = rows // 2
                total = len(self.transfer_buffer)
                current = total - self.scroll_offsets[1]
                scroll_info = f" (Lines: {current}/{total})"
                prefix = " ACTIVE -> " if self.active_window == 1 else " "
                sep_text = f"{prefix}DATA TRANSFER MONITOR ({self.tm_format.upper()}, {self.tm_direction.upper()}){scroll_info}"
                
                if len(sep_text) > cols: sep_text = sep_text[:cols]

                if self.args.color:
                    bg = UiColors._UI_COL_ACTHEAD_ if self.active_window == 1 else Colors.BG_BLUE
                    line = f"{bg}{Colors.WHITE}{sep_text.center(cols)}{Colors.RESET}"
                else:
                    line = f"{Colors.INVERSE}{sep_text.center(cols)}{Colors.RESET}"
                sys.stdout.write(f"\033[s\033[{mid+1};1H{line}\033[u"); sys.stdout.flush()

    def render_windows(self):
        if self.args.batch or self.args.notui: return
        with self.screen_lock:
            cols, rows = self._get_term_size()
            if not self.args.showtransfer:
                self.draw_buffer(self.log_buffer, 2, rows - 2, self.scroll_offsets[0])
            else:
                mid = rows // 2
                self.draw_buffer(self.log_buffer, 2, mid - 1, self.scroll_offsets[0])
                self.draw_buffer(self.transfer_buffer, mid + 2, (rows - 1) - (mid + 2) + 1, self.scroll_offsets[1])

    def draw_buffer(self, buffer, start_row, height, offset):
        with self.screen_lock:
            cols, _ = self._get_term_size()
            cols = max(1, cols - 1) # Reduce width
            end_idx = len(buffer) - offset
            start_idx = max(0, end_idx - height)
            display_lines = buffer[start_idx:end_idx]
            
            marker_color = UiColors._UI_COL_LASTLINE_ if self.args.color else ""
            reset = Colors.RESET if self.args.color else ""
            
            for i in range(height):
                current_row = start_row + i
                line_idx = i - (height - len(display_lines))
                # Clear line cautiously to avoid wrap
                sys.stdout.write(f"\033[{current_row};1H{reset}{' ' * cols}\033[{current_row};1H")
                
                if line_idx >= 0:
                    line = display_lines[line_idx]
                    is_last_visible = (line_idx == len(display_lines) - 1 and offset == 0)
                    prefix = f"{marker_color}>{reset}" if is_last_visible else " "
                    # Ensure we don't print beyond col width (including prefix)
                    # Prefix length is 1 char (visible)
                    max_content_len = max(0, cols - 2)
                    sys.stdout.write(f"{prefix}{line[:max_content_len]}")
            sys.stdout.flush()

    def signal_handler(self, sig, frame):
        self.keep_running = False
        use_named_pipe = getattr(self.args, 'namedpipe', None) is not None
        if use_named_pipe and hasattr(self, 'pipe_read_event'):
            try:
                win32event.SetEvent(self.pipe_read_event)
            except: pass
        if use_named_pipe and hasattr(self, 'pipe_event'):
            try:
                win32event.SetEvent(self.pipe_event)
            except: pass
        if self.net_conn:
            try:
                self.net_conn.setblocking(True)
                self.net_conn.sendall(DISCONNECT_CMD)
                # Force close socket to interrupt select() call immediately
                self.net_conn.close()
            except:
                pass

    def count_data(self, direction, size):
        if direction == "IN": self.in_count += size
        else: self.out_count += size
        if self.args.count: self.update_status_line()

    def update_status_line(self):
        if self.args.batch or self.args.notui: return
        with self.screen_lock:
            cols, rows = self._get_term_size()
            cols = max(1, cols - 1)  # Reduce width to prevent auto-wrap on last line
            
            r_parts = self.remote_params.split()
            r_name, r_speed, r_line = (r_parts[0], r_parts[1], r_parts[2]) if len(r_parts) >= 3 else ("??", "??", "??")
            count_info = f" | IN:{self.in_count} OUT:{self.out_count}" if self.args.count else ""
            
            is_named_pipe = getattr(self.args, 'namedpipe', None) is not None
            port_display = f"PIPE:{self.args.namedpipe}" if is_named_pipe else self.args.comport
            
            sv_ver_str_plain = f"({self.__SRV_VER__})"
            prefix_type_plain = f"SRV {sv_ver_str_plain}"

            if self.args.color:
                bg, fg = UiColors._UI_COL_BG_STATUSLINE_, UiColors._UI_COL_FG_STATUSLINE_
                v_sv_col = UiColors._UI_COL_SRV_VERSION_
                sv_ver_str_styled = f"({v_sv_col}{self.__SRV_VER__}{fg})"
                prefix_type_styled = f"SRV {sv_ver_str_styled}"

                line_text = (f" {prefix_type_styled} | "
                        f"L: {UiColors._UI_COL_LIP_}{self.local_ip}{fg}:{UiColors._UI_COL_LPORT_}{self.local_port}{fg} | "
                        f"R: {UiColors._UI_COL_RIP_}{self.args.host}{fg}:{UiColors._UI_COL_RPORT_}{self.args.port}{fg} | "
                        f"L: {UiColors._UI_COL_SPORTNAME_}{port_display}{fg} {UiColors._UI_COL_SPORTSPEED_}{self.args.baud}{fg} {UiColors._UI_COL_SPORTLINE_}{self.args.line}{fg} | "
                        f"R: {UiColors._UI_COL_RPORTNAME_}{r_name}{fg} {UiColors._UI_COL_RPORTSPEED_}{r_speed}{fg} {UiColors._UI_COL_RPORTLINE_}{r_line}{fg}{count_info} ")
                plain_len_text = (f" {prefix_type_plain} | L: {self.local_ip}:{self.local_port} | "
                                f"R: {self.args.host}:{self.args.port} | L: {port_display} {self.args.baud} {self.args.line} | "
                                f"R: {r_name} {r_speed} {r_line}{count_info} ")
                
                # Check for overflow and fall back to compact mode if needed
                if len(plain_len_text) > cols:
                     # Compact mode
                    line_text = f" {prefix_type_styled} | R: {r_name} {r_speed} {r_line} | {count_info}"
                    plain_len_text = f" {prefix_type_plain} | R: {r_name} {r_speed} {r_line} | {count_info}"
                    if len(plain_len_text) > cols:
                        # Ultra compact
                        line_text = f" {prefix_type_styled} | {count_info}"
                        plain_len_text = f" {prefix_type_plain} | {count_info}"

                full_line = f"{bg}{fg}{line_text.ljust(cols + (len(line_text) - len(plain_len_text)))}{Colors.RESET}"
            else:
                line_text = (f" {prefix_type_plain} | L: {self.local_ip}:{self.local_port} | "
                        f"R: {self.args.host}:{self.args.port} | L: {port_display} {self.args.baud} {self.args.line} | "
                        f"R: {r_name} {r_speed} {r_line}{count_info} ")
                if len(line_text) > cols: line_text = line_text[:cols]
                full_line = f"{Colors.INVERSE}{line_text.ljust(cols)}{Colors.RESET}"
            sys.stdout.write(f"\033[s\033[{rows};1H{full_line}\033[u"); sys.stdout.flush()

    def log(self, msg, color=Colors.CYAN, is_debug=False):
        if is_debug and not self.args.debug: return
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        
        display_msg = self._sanitize_for_tui(msg)

        if self.args.color:
            c = color; r = Colors.RESET
            t_col = UiColors._UI_COL_TIME_
            debug_tag = f" {Colors.YELLOW}(DEBUG){r}" if is_debug else ""
            line = f"{t_col}{ts}{r}{debug_tag} {c}{display_msg}{r}"
        else:
            debug_tag = " (DEBUG)" if is_debug else ""
            line = f"{ts}{debug_tag} {display_msg}"
        
        with self.screen_lock:
            self.log_buffer.append(line)
            if len(self.log_buffer) > self.args.logbufferlines: self.log_buffer.pop(0)
            
            plain_line = f"{ts}{' (DEBUG)' if is_debug else ''} {msg}\n"
            if self.log_file_path:
                self._write_to_file(self.log_file_path, plain_line, max_size_kb=self.args.logsizemax, max_files=self.args.logmax)
            
            if not self.args.batch:
                if self.args.notui:
                    sys.stdout.write(line + "\n")
                    sys.stdout.flush()
                else:
                    if self.scroll_offsets[0] == 0:
                        self.render_windows()
                        self.update_top_header()
                        self.update_status_line()
                    elif self.args.showtransfer:
                        self.update_mid_separator()
                    if self.args.showtransfer:
                        self.update_mid_separator()

    def log_transfer(self, direction, data):
        if not self.args.showtransfer: return
        if self.tm_direction != "all" and direction.lower() != self.tm_direction: return
        
        ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        if self.tm_format == "hex":
            hex_data = data.hex()
            formatted_hex = " ".join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
            msg = f"Data {direction} (hex): {formatted_hex}"
        else:
            decoded = data.decode('utf-8', errors='replace')
            msg = decoded
        
        display_msg = self._sanitize_for_tui(msg)

        if self.args.color:
            color = UiColors._UI_COL_DIR_IN_ if direction == "IN" else UiColors._UI_COL_DIR_OUT_
            full_msg = f"{ts} {color}[{direction}]{Colors.RESET} {display_msg}"
        else:
            full_msg = f"{ts} [{direction}] {display_msg}"
   
        with self.screen_lock:
            self.transfer_buffer.append(full_msg)
            if len(self.transfer_buffer) > self.args.transferbufferlines: self.transfer_buffer.pop(0)
            
            if not self.args.batch:
                if self.args.notui:
                    sys.stdout.write(full_msg + "\n")
                    sys.stdout.flush()
                else:
                    if self.scroll_offsets[1] == 0:
                        self.render_windows()
                    self.update_mid_separator()

    def _kb_handler(self):
        if self.args.batch or self.args.notui: return
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
                    r, _, _ = select.select([sys.stdin], [], [], 0.1)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch == '\x1b': ch += sys.stdin.read(2)
                        return ch.encode()
                    return None
                finally: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        while self.keep_running:
            time.sleep(0.05)
            key = get_key()
            if not key: continue
            if (key == b'\t' or key == b'\x09') and self.args.showtransfer:
                self.active_window = 1 - self.active_window
                self.refresh_screen()
            elif key in [b'\xe0H', b'\x1b[A']: # UP
                idx = self.active_window
                buf_len = len(self.log_buffer if idx == 0 else self.transfer_buffer)
                self.scroll_offsets[idx] = min(self.scroll_offsets[idx] + 1, max(0, buf_len - 1))
                self.render_windows(); self.update_top_header(); self.update_mid_separator(); self.update_status_line()
            elif key in [b'\xe0P', b'\x1b[B']: # DOWN
                idx = self.active_window
                self.scroll_offsets[idx] = max(0, self.scroll_offsets[idx] - 1)
                self.render_windows(); self.update_top_header(); self.update_mid_separator(); self.update_status_line()
            elif key == b'\x03': # CTRL-C manual handle
                self.signal_handler(None, None)

    def run(self):
        if not self.args.notui and not self.args.batch:
            self.refresh_screen()
            threading.Thread(target=self._kb_handler, daemon=True).start()
        
        self.log("Bridge is starting...", UiColors._UI_COL_INFO_)
        
        use_named_pipe = getattr(self.args, 'namedpipe', None) is not None
        port_name = self.args.namedpipe if use_named_pipe else self.args.comport
        
        self.pipe_path = None
        self.pipe_thread = None
        
        try:
            if use_named_pipe:
                if sys.platform != "win32":
                    self.log("Named pipe only supported on Windows", UiColors._UI_COL_ERR_)
                    self.cleanup(); return
                if not WIN32_AVAILABLE:
                    self.log("Named pipe requires pywin32 module. Run: pip install pywin32", UiColors._UI_COL_ERR_)
                    self.cleanup(); return
                pipe_path = f"\\\\.\\pipe\\{port_name}"
                self.pipe_path = pipe_path
                self.log(f"Creating named pipe {pipe_path}...", UiColors._UI_COL_INFO_)
                self.ser_obj = win32pipe.CreateNamedPipe(
                    pipe_path,
                    win32pipe.PIPE_ACCESS_DUPLEX | win32file.FILE_FLAG_OVERLAPPED,
                    win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE,
                    1, 65536, 65536, 0, None
                )
                # Create overlapped structures for async I/O
                self.pipe_overlapped_read = pywintypes.OVERLAPPED()
                self.pipe_overlapped_read.hEvent = win32event.CreateEvent(None, 1, 0, None)
                self.pipe_overlapped_write = pywintypes.OVERLAPPED()
                self.pipe_overlapped_write.hEvent = win32event.CreateEvent(None, 1, 0, None)
                self.pipe_overlapped_connect = pywintypes.OVERLAPPED()
                self.pipe_overlapped_connect.hEvent = win32event.CreateEvent(None, 1, 0, None)
                self.log(f"Named pipe {pipe_path} created. Waiting for connection...", UiColors._UI_COL_INFO_)
                self.pipe_connected = False
                self.pipe_read_pending = False
                self.pipe_connect_pending = False
            else:
                p = serial.PARITY_NONE
                if self.args.line[1] == 'O': p = serial.PARITY_ODD
                elif self.args.line[1] == 'E': p = serial.PARITY_EVEN
                self.ser_obj = serial.Serial(self.args.comport, self.args.baud, bytesize=int(self.args.line[0]), parity=p, stopbits=int(self.args.line[2]), timeout=0.01)
                self.log(f"Serial {self.args.comport} opened.", UiColors._UI_COL_OK_)
        except KeyboardInterrupt:
            self.keep_running = False
            self.cleanup(); return
        except Exception as e: self.log(f"Port Error: {e}", UiColors._UI_COL_ERR_); self.cleanup(); return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.settimeout(5)
            sock.connect((self.args.host, self.args.port))
            self.local_ip, self.local_port = sock.getsockname()
            
            if self.args.secauto or self.args.sec:
                ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
                if self.args.sec:
                    try:
                        cp, kp = self.args.sec.split(',')
                        ctx.load_cert_chain(certfile=cp.strip(), keyfile=kp.strip())
                        self.sec_mode_str = "SSL (C)"
                    except Exception as e:
                        self.log(f"SSL Cert Error: {e}", UiColors._UI_COL_ERR_); self.cleanup(); return
                else: self.sec_mode_str = "SSL (A)"
                sock = ctx.wrap_socket(sock, server_hostname=self.args.host); self.is_sec = True
                sock.settimeout(5)
            
            self.net_conn = sock; self.session_start = time.time()
            if not self.args.notui and not self.args.batch:
                self.update_top_header()
            self.log(f"Connected to {self.args.host}.", UiColors._UI_COL_OK_)
        except Exception as e: self.log(f"Net Error: {e}", UiColors._UI_COL_ERR_); self.cleanup(); return

        id_msg = f"__#BR_VER_{__CODE_VERSION__}#__"
        self.net_conn.sendall(id_msg.encode())
        
        if self.is_sec and self.args.pwd:
            pwd_msg = f"__#PWD_{self.args.pwd}#__"
            self.net_conn.sendall(pwd_msg.encode())

        self.net_conn.sendall(GETVER_CMD)
        self.net_conn.sendall(GET_KA_TIMEOUT_CMD)
        self.awaiting_params = True
        self.net_conn.sendall(ASK_CMD); self.net_conn.setblocking(False)
        
        if self.args.keepalive > 0:
            threading.Thread(target=self._keepalive_loop, daemon=True).start()

        try:
            while self.keep_running:
                if platform.system() == "Windows" and not self.args.notui and not self.args.batch:
                    curr_c, curr_r = self._get_term_size()
                    if curr_c != self.cols or curr_r != self.rows: self.refresh_screen()
                try:
                    # Check exit flag before select to exit faster on CTRL-C
                    if not self.keep_running: break
                    r, _, _ = select.select([self.net_conn], [], [], 0.01)
                    # Check exit flag immediately after select returns
                    if not self.keep_running: break
                    if self.net_conn in r:
                        data = self.net_conn.recv(16384)
                        # Detect server disconnect: empty data means connection closed
                        if not data:
                            self.log("Server disconnected.", UiColors._UI_COL_INFO_)
                            self.keep_running = False
                            break

                        # Check for disconnect command immediately - this is critical and must be first
                        if DISCONNECT_CMD in data:
                            self.log("SRV-->BR: Disconnect signal received.", UiColors._UI_COL_ERR_)
                            self.keep_running = False
                            break

                        if b"__#" in data:
                            decoded_cmd = data.decode(errors='replace').strip()
                            if DISCONNECT_CMD in data:
                                self.log("SRV-->BR: Disconnect signal received.", UiColors._UI_COL_ERR_)
                                self.keep_running = False; break
                            if BAD_PWD_MSG in data:
                                self.log("Error: Server rejected authorization password.", UiColors._UI_COL_ERR_); break
                            if b"SRV_VER_" in data:
                                try:
                                    self.__SRV_VER__ = data.decode(errors='replace').split("SRV_VER_")[1].split("#")[0]
                                    self.log(f"Server version identified: {self.__SRV_VER__}", UiColors._UI_COL_OK_)
                                    is_named_pipe = getattr(self.args, 'namedpipe', None) is not None
                                    port_name = f"PIPE:{self.args.namedpipe}" if is_named_pipe else self.args.comport
                                    self.net_conn.sendall(f"__#COM_PARAMS_{port_name} {self.args.baud} {self.args.line}#__".encode())
                                    if not self.args.notui and not self.args.batch: self.update_status_line()
                                except: pass
                            if MY_KA_TIMEOUT_CMD in data:
                                try:
                                    srv_ka = int(data.decode(errors='replace').split(MY_KA_TIMEOUT_CMD.decode())[1].split("#")[0])
                                    if srv_ka > self.args.keepalive: self.log(f"SRV-->BR: KeepAlive {srv_ka}s - OK", UiColors._UI_COL_OK_)
                                    else: self.log(f"SRV-->BR: KeepAlive {srv_ka}s - RISK", UiColors._UI_COL_ERR_)
                                except: pass
                            
                            # DEBUG: Log Protocol Messages
                            if self.args.debug:
                                if KEEPALIVE_CMD in data: self.log("DEBUG: RX KEEPALIVE", is_debug=True)
                                if GETVER_CMD in data: self.log("DEBUG: RX GETVER", is_debug=True)
                                if GET_KA_TIMEOUT_CMD in data: self.log("DEBUG: RX GET_KA_TIMEOUT", is_debug=True)
                                if ASK_CMD in data: self.log("DEBUG: RX ASK_CMD", is_debug=True)
                                if b"__#COM_PARAMS_" in data: self.log(f"DEBUG: RX COM_PARAMS: {decoded_cmd}", is_debug=True)

                            if b"__#COM_PARAMS_" in data:
                                try:
                                    self.remote_params = decoded_cmd.split("__#COM_PARAMS_")[1].split("#__")[0].strip()
                                    self.log(f"SRV-->BR: Remote Params: {self.remote_params}", UiColors._UI_COL_OK_)
                                    self.serial_ready = True; self.awaiting_params = False
                                    if not self.args.notui and not self.args.batch: self.update_status_line()
                                except: pass
                            if GETVER_CMD in data: self.net_conn.sendall(id_msg.encode())
                            elif ASK_CMD in data:
                                is_named_pipe = getattr(self.args, 'namedpipe', None) is not None
                                port_name = f"PIPE:{self.args.namedpipe}" if is_named_pipe else self.args.comport
                                self.net_conn.sendall(f"__#COM_PARAMS_{port_name} {self.args.baud} {self.args.line}#__".encode())
                            # Remove protocol commands but preserve ANSI escape sequences
                            data = re.sub(b"__#[^#]*#__", b"", data)
                            if not data: continue

                        if self.serial_ready and data:
                            use_named_pipe = getattr(self.args, 'namedpipe', None) is not None
                            if use_named_pipe and self.pipe_connected:
                                try:
                                    win32file.WriteFile(self.ser_obj, data)
                                except pywintypes.error as e:
                                    if e.winerror == winerror.ERROR_NO_DATA or e.winerror == winerror.ERROR_BROKEN_PIPE:
                                        self.pipe_connected = False
                                        self.pipe_connect_pending = False
                                        self.log("Client disconnected.", UiColors._UI_COL_INFO_)
                                        win32pipe.DisconnectNamedPipe(self.ser_obj)
                            elif not use_named_pipe:
                                self.ser_obj.write(data)
                            
                            if self.pipe_connected or not use_named_pipe:
                                self.count_data("OUT", len(data))
                                self.log_transfer("OUT", data)
                                if self.logdata_file_path: self._write_to_file(self.logdata_file_path, data, True, self.args.logdatasizemax, self.args.logdatamax, strip_ansi=True)
                 
                    # Check for physical terminal connection (DSR/CD/CTS changes)
                    use_named_pipe = getattr(self.args, 'namedpipe', None) is not None
                    if not use_named_pipe and self.ser_obj and self.ser_obj.is_open:
                        try:
                            curr_signals = {'DSR': self.ser_obj.dsr, 'CD': self.ser_obj.cd, 'CTS': self.ser_obj.cts}
                            if self.prev_modem_signals and self.prev_modem_signals != curr_signals:
                                changes = []
                                for k, v in curr_signals.items():
                                    if self.prev_modem_signals.get(k) != v:
                                        changes.append(f"{k} {'HIGH' if v else 'LOW'}")
                                if changes:
                                    # Heuristic: if DSR goes HIGH, it likely means a terminal connected
                                    self.log(f"DEBUG: Serial Port Status Changed: {', '.join(changes)}", UiColors._UI_COL_INFO_, is_debug=True)
                            self.prev_modem_signals = curr_signals
                        except: pass
                
                except ssl.SSLWantReadError:
                    pass  # SSL waiting for data, this is normal
                except ssl.SSLWantWriteError:
                    pass  # SSL waiting for write capability, this is normal
                except Exception as e:
                    if self.args.debug and "did not complete" not in str(e):
                        self.log(f"DEBUG: Network/Pipe write error: {e}", UiColors._UI_COL_ERR_, is_debug=True)
                
                try:
                    use_named_pipe = getattr(self.args, 'namedpipe', None) is not None
                    if use_named_pipe:
                        # Handle ConnectNamedPipe overlapped
                        if not self.pipe_connected and not self.pipe_connect_pending:
                            try:
                                win32pipe.ConnectNamedPipe(self.ser_obj, self.pipe_overlapped_connect)
                                self.pipe_connect_pending = True
                            except pywintypes.error as e:
                                if e.winerror == winerror.ERROR_IO_PENDING:
                                    self.pipe_connect_pending = True
                                elif e.winerror == winerror.ERROR_PIPE_CONNECTED:
                                    self.pipe_connected = True
                                    self.pipe_connect_pending = False
                                    self.log(f"Client connected to {self.pipe_path}", UiColors._UI_COL_OK_)
                                else:
                                    self.log(f"DEBUG: ConnectNamedPipe error winerror={e.winerror}", UiColors._UI_COL_ERR_, is_debug=True)
                        
                        # Check if connection completed
                        if self.pipe_connect_pending:
                            wait_result = win32event.WaitForSingleObject(self.pipe_overlapped_connect.hEvent, 0)
                            if wait_result == win32event.WAIT_OBJECT_0:
                                self.pipe_connected = True
                                self.pipe_connect_pending = False
                                self.log(f"Client connected to {self.pipe_path}", UiColors._UI_COL_OK_)
                        
                        if self.pipe_connected:
                            try:
                                # Try to get result of pending read
                                if hasattr(self, 'pipe_read_pending') and self.pipe_read_pending:
                                    wait_result = win32event.WaitForSingleObject(self.pipe_overlapped_read.hEvent, 0)
                                    if wait_result == win32event.WAIT_OBJECT_0:
                                        try:
                                            # Using GetOverlappedResult (Wait=False) to get bytes
                                            n_bytes = win32file.GetOverlappedResult(self.ser_obj, self.pipe_overlapped_read, False)
                                            if n_bytes > 0:
                                                s_data = bytes(self.pipe_read_buffer[:n_bytes])
                                                self.net_conn.sendall(s_data)
                                                self.count_data("IN", len(s_data))
                                                self.log_transfer("IN", s_data)
                                                if self.logdata_file_path: 
                                                    self._write_to_file(self.logdata_file_path, s_data, True, self.args.logdatasizemax, self.args.logdatamax, strip_ansi=True)
                                            self.pipe_read_pending = False
                                        except pywintypes.error as e:
                                            if e.winerror == winerror.ERROR_BROKEN_PIPE:
                                                self.pipe_connected = False
                                                self.pipe_read_pending = False
                                                self.pipe_connect_pending = False
                                                self.log("Client disconnected.", UiColors._UI_COL_INFO_)
                                                win32pipe.DisconnectNamedPipe(self.ser_obj)
                                
                                # Start new read if not pending
                                if not hasattr(self, 'pipe_read_pending') or not self.pipe_read_pending:
                                    self.pipe_read_buffer = win32file.AllocateReadBuffer(4096)
                                    try:
                                        hr, _ = win32file.ReadFile(self.ser_obj, self.pipe_read_buffer, self.pipe_overlapped_read)
                                        
                                        if hr == 0:
                                            # Synchronous completion
                                            n_bytes = win32file.GetOverlappedResult(self.ser_obj, self.pipe_overlapped_read, False)
                                            if n_bytes > 0:
                                                s_data = bytes(self.pipe_read_buffer[:n_bytes])
                                                self.net_conn.sendall(s_data)
                                                self.count_data("IN", len(s_data))
                                                self.log_transfer("IN", s_data)
                                                if self.logdata_file_path: 
                                                    self._write_to_file(self.logdata_file_path, s_data, True, self.args.logdatasizemax, self.args.logdatamax, strip_ansi=True)
                                            self.pipe_read_pending = False
                                        else:
                                            self.pipe_read_pending = True
                                    except pywintypes.error as e:
                                        if e.winerror == winerror.ERROR_IO_PENDING:
                                            self.pipe_read_pending = True
                                        elif e.winerror == winerror.ERROR_BROKEN_PIPE:
                                            self.pipe_connected = False
                                            self.pipe_read_pending = False
                                            self.pipe_connect_pending = False
                                            self.log("Client disconnected.", UiColors._UI_COL_INFO_)
                                            win32pipe.DisconnectNamedPipe(self.ser_obj)
                                        else:
                                            self.log(f"DEBUG: ReadFile start error winerror={e.winerror} msg={e}", UiColors._UI_COL_ERR_, is_debug=True)
                            except Exception as e:
                                if self.args.debug:
                                    self.log(f"DEBUG: Pipe read error: {e}", UiColors._UI_COL_ERR_, is_debug=True)
                    elif not use_named_pipe:
                        if self.ser_obj and self.ser_obj.in_waiting > 0:
                            s_data = self.ser_obj.read(self.ser_obj.in_waiting)
                            if s_data:
                                self.net_conn.sendall(s_data)
                                self.count_data("IN", len(s_data)); self.log_transfer("IN", s_data)
                                if self.logdata_file_path: self._write_to_file(self.logdata_file_path, s_data, True, self.args.logdatasizemax, self.args.logdatamax, strip_ansi=True)
                except Exception as e:
                    if self.args.debug:
                        self.log(f"DEBUG: Serial read error: {e}", UiColors._UI_COL_ERR_, is_debug=True)
        except KeyboardInterrupt:
            self.keep_running = False
        finally: self.cleanup()

    def _keepalive_loop(self):
        while self.keep_running:
            time.sleep(self.args.keepalive)
            try: 
                if self.net_conn: self.net_conn.sendall(KEEPALIVE_CMD)
            except: break

    def cleanup(self):
        if not self.args.notui and not self.args.batch:
            sys.stdout.write(Colors.RESET)
            sys.stdout.write(Colors.CLEAR_SCR)
            sys.stdout.write("\033[0m")
        use_named_pipe = getattr(self.args, 'namedpipe', None) is not None
        try:
            if use_named_pipe and hasattr(self, 'pipe_overlapped_connect') and self.pipe_overlapped_connect:
                try:
                    if hasattr(self.pipe_overlapped_connect, 'hEvent') and self.pipe_overlapped_connect.hEvent:
                        win32file.CloseHandle(self.pipe_overlapped_connect.hEvent)
                except: pass
            if use_named_pipe and hasattr(self, 'pipe_overlapped_read') and self.pipe_overlapped_read:
                try:
                    if hasattr(self.pipe_overlapped_read, 'hEvent') and self.pipe_overlapped_read.hEvent:
                        win32file.CloseHandle(self.pipe_overlapped_read.hEvent)
                except: pass
            if use_named_pipe and hasattr(self, 'pipe_overlapped_write') and self.pipe_overlapped_write:
                try:
                    if hasattr(self.pipe_overlapped_write, 'hEvent') and self.pipe_overlapped_write.hEvent:
                        win32file.CloseHandle(self.pipe_overlapped_write.hEvent)
                except: pass
            if use_named_pipe and hasattr(self, 'pipe_read_event'):
                try:
                    win32event.SetEvent(self.pipe_read_event)
                    win32file.CloseHandle(self.pipe_read_event)
                except: pass
            if use_named_pipe and hasattr(self, 'pipe_event'):
                try:
                    win32event.SetEvent(self.pipe_event)
                    win32file.CloseHandle(self.pipe_event)
                except: pass
            if self.ser_obj:
                if use_named_pipe:
                    win32file.CloseHandle(self.ser_obj)
                else:
                    self.ser_obj.close()
            if self.net_conn: self.net_conn.close()
        except: pass
        if not self.args.batch:
            if not self.args.notui: sys.stdout.write("\n")
            sys.stdout.flush()
            dur = f"{int(time.time() - self.session_start)}s" if self.session_start else "N/A"
            summary = (f"\n---=== Summary ===---\n{__APP_NAME__}\nBR -> SRV ended.\nL: {self.local_ip}:{self.local_port} -> R: {self.args.host}:{self.args.port}\n"
                       f"Data Transmitted IN:{self.in_count}, OUT:{self.out_count}\nDuration: {dur}\n")
            sys.stdout.write(summary); sys.stdout.flush()

def validate_args(args):
    is_ask = getattr(args, 'ask', False)
    is_namedpipe = getattr(args, 'namedpipe', None) is not None
    has_comport = getattr(args, 'comport', None) is not None
    has_serial = has_comport or is_namedpipe
    
    if not all([args.host, args.port, has_serial]) and not is_ask:
        if not args.batch: print("[ERROR] Missing mandatory parameters: -H, -p, --comport or --namedpipe")
        else: sys.stderr.write("[ERROR] Missing mandatory parameters: -H, -p, --comport or --namedpipe\n")
        return False
    if is_ask and not all([args.host, args.port]):
        if not args.batch: print("[ERROR] --ask requires: -H and -p")
        else: sys.stderr.write("[ERROR] --ask requires: -H and -p\n")
        return False
    if (args.secauto or args.sec) and not args.pwd:
        if not args.batch: print("[ERROR] Security mode requires a password (--pwd).")
        else: sys.stderr.write("[ERROR] Security mode requires a password (--pwd)\n")
        return False
    if is_namedpipe and sys.platform != "win32":
        if not args.batch: print("[ERROR] --namedpipe only supported on Windows")
        else: sys.stderr.write("[ERROR] --namedpipe only supported on Windows\n")
        return False
    if is_namedpipe and sys.platform == "win32" and not WIN32_AVAILABLE:
        if not args.batch: print("[ERROR] --namedpipe requires pywin32. Run: pip install pywin32")
        else: sys.stderr.write("[ERROR] --namedpipe requires pywin32. Run: pip install pywin32\n")
        return False
    return True

def load_hierarchical_config():
    config = DEFAULT_CONFIG.copy()
    config_paths = ["/etc/soe/soebridge.conf", "soebridge.conf"]
    temp_parser = argparse.ArgumentParser(add_help=False)
    temp_parser.add_argument("--cfgfile")
    temp_args, _ = temp_parser.parse_known_args()
    if temp_args.cfgfile: config_paths.append(temp_args.cfgfile)
    
    for path in config_paths:
        if os.path.exists(path):
            cp = configparser.ConfigParser()
            try:
                # Try reading normally first (expects sections)
                with open(path, 'r') as f: file_content = f.read()
                try:
                    cp.read_string(file_content)
                except configparser.MissingSectionHeaderError:
                    # Fallback for old/simple configs without [DEFAULT]
                    cp.read_string('[DEFAULT]\n' + file_content)

                # 1. Parse Standard Options
                int_keys = ['port', 'baud', 'keepalive', 'logmax', 'logsizemax', 'logdatamax', 'logdatasizemax', 'logbufferlines', 'transferbufferlines']
                
                # Consolidate all relevant sections to scan
                # We always want to scan DEFAULT (which captures global keys or keys under [DEFAULT])
                # and any other user-defined sections (like [Connection], [Settings])
                # Note: cp.sections() does NOT include DEFAULT, so we add it manually.
                
                # Create a list of section proxies to iterate over
                sections_proxies = []
                if 'DEFAULT' in cp:
                    sections_proxies.append(cp['DEFAULT'])
                
                for sec_name in cp.sections():
                    if sec_name == 'COLORS': continue
                    sections_proxies.append(cp[sec_name])

                # Iterate through all sections and update config
                # Later sections overwrite earlier ones (if keys are duplicated)
                for section_data in sections_proxies:
                    for key in config:
                        # Check case-insensitive match in the section
                        for k in section_data:
                            if k.lower() == key.lower():
                                val = section_data[k]
                                # Remove inline comments if present (simple hash handling if getint fails)
                                # ConfigParser doesn't support inline comments by default for values
                                
                                if key in int_keys: 
                                    try: 
                                        config[key] = int(val.split('#')[0].strip())
                                    except: 
                                        try: config[key] = section_data.getint(k)
                                        except: pass
                                elif isinstance(DEFAULT_CONFIG[key], bool): 
                                    try: 
                                        # Handle basic bool strings manually or use getboolean
                                        v_lower = val.split('#')[0].strip().lower()
                                        if v_lower in ['true', '1', 'yes', 'on']: config[key] = True
                                        elif v_lower in ['false', '0', 'no', 'off']: config[key] = False
                                        else: config[key] = section_data.getboolean(k)
                                    except: pass
                                elif isinstance(DEFAULT_CONFIG[key], int): 
                                    try: config[key] = int(val.split('#')[0].strip())
                                    except: pass
                                else: 
                                    # String values
                                    config[key] = str(val.split('#')[0].strip())
                                break
                
                # 2. Parse Custom Colors (from [COLORS] section)
                if 'COLORS' in cp:
                    for key in cp['COLORS']:
                        col_val_name = cp['COLORS'][key]
                        attr_name = f"_UI_COL_{key.upper()}_"
                        col_code = Colors.get_by_name(col_val_name)
                        if hasattr(UiColors, attr_name):
                            setattr(UiColors, attr_name, col_code)
            
            except Exception as e:
                # If explicit config file fails, warn user
                if path == temp_args.cfgfile:
                    print(f"[WARNING] Failed to parse config file '{path}': {e}")
                pass

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-H", "--host"); parser.add_argument("-p", "--port", type=int)
    parser.add_argument("--comport"); parser.add_argument("--namedpipe"); parser.add_argument("--baud", type=int); parser.add_argument("--line")
    parser.add_argument("--keepalive", type=int); parser.add_argument("--secauto", action="store_true", default=False)
    parser.add_argument("--sec"); parser.add_argument("--pwd"); parser.add_argument("--log")
    parser.add_argument("--logmax", type=int); parser.add_argument("--logsizemax", type=int); parser.add_argument("--logdata")
    parser.add_argument("--logdatamax", type=int); parser.add_argument("--logdatasizemax", type=int)
    parser.add_argument("--logbufferlines", type=int); parser.add_argument("--transferbufferlines", type=int)
    parser.add_argument("--color", action="store_true", default=False); parser.add_argument("--count", action="store_true", default=False)
    parser.add_argument("--debug", action="store_true", default=False); 
    parser.add_argument("--showtransfer", nargs='?', const="ascii,all", default=None)
    parser.add_argument("--version", action="store_true"); parser.add_argument("-h", action="store_true")
    parser.add_argument("--help", action="store_true"); parser.add_argument("--ask", action="store_true", default=False)
    parser.add_argument("--cfgfile"); parser.add_argument("--notui", action="store_true", default=False)
    parser.add_argument("-b", "--batch", action="store_true", default=False)
    cli_args, _ = parser.parse_known_args()
    
    # FIXED: Only override config with CLI values if they were EXPLICITLY provided
    # For boolean flags: default=False means not provided, True means provided
    # For nargs='?' with default=None: None means not provided, any value means provided
    for key, value in vars(cli_args).items():
        if value is not None and value is not False:  # CLI arg was explicitly set
            config[key] = value
        elif isinstance(value, bool) and value is True:  # Boolean flag was set to True
            config[key] = True
    
    return argparse.Namespace(**config)

if __name__ == "__main__":
    args = load_hierarchical_config()
    if not args.batch and platform.system() == "Windows": os.system('') 
    
    if args.h:
        print(f"{__APP_NAME__} v{__CODE_VERSION__} ({__CODE_DATE__}) by {__CODE_AUTHOR__}")
        print("Options: -H -p --comport --namedpipe --baud --line --keepalive --secauto --sec --pwd --log --logmax --logsizemax --logdata --logdatamax --logdatasizemax --logbufferlines --transferbufferlines --color --count --debug --showtransfer --cfgfile --version --ask --notui -b|--batch")
        sys.exit(0)
        
    if args.help:
        print(f"{__APP_NAME__} v{__CODE_VERSION__} ({__CODE_DATE__}) by {__CODE_AUTHOR__}")
        print("\nCONFIGURATION SOURCES: CLI > --cfgfile > soebridge.conf > /etc/soe/soebridge.conf > Internal")
        print("\nCONNECTION PARAMETERS:")
        print(f"  -H, --host               Remote server IP address or hostname")
        print(f"  -p, --port               Remote server TCP port")
        print(f"  --keepalive SEC          Heartbeat interval (default: 30)")
        print(f"  --pwd PASSWORD           Authorization password (Mandatory for SSL/SEC modes)")
        print(f"  --secauto                Enable SSL/TLS auto-negotiation (Requires --pwd)")
        print(f"  --sec CERT,KEY           Enable SSL/TLS with cert/key files (Requires --pwd)")
        print(f"  --cfgfile FILE           Path to a custom configuration file")
        print("\nSERIAL PORT PARAMETERS:")
        print(f"  --comport NAME           Local serial port name (e.g., COM1)")
        print(f"  --namedpipe NAME         Windows named pipe name (e.g., MySerialPipe)")
        print(f"  --baud SPEED             Serial port speed (default: 9600)")
        print(f"  --line PARAMS            4-char params: [Data][Parity][Stop][Flow] (default: 8N1N)")
        print("\nLOGGING PARAMETERS:")
        print(f"  --log FILE[,new]         System log path. Add ',new' for unique file per run")
        print(f"  --logmax N               Max rotated system log files (default: 10)")
        print(f"  --logsizemax KB          Max size per system log file (default: 4096)")
        print(f"  --logdata FILE           Binary data log path for all traffic")
        print(f"  --logdatamax N           Max rotated data log files (default: 10)")
        print(f"  --logdatasizemax KB      Max size per data log file (default: 8192)")
        print("\nINTERFACE & DEBUG:")
        print(f"  --color                  Enable ANSI color output")
        print(f"  --count                  Display byte counters")
        print(f"  --debug                  Show debug info")
        print(f"  --showtransfer [F,D]     Enable monitor (default: ascii,all). FMT: ascii|hex, DIR: in|out|all")
        print(f"  --logbufferlines M       Max lines in system log buffer (default: 2000)")
        print(f"  --transferbufferlines N  Max lines in data monitor buffer (default: 2000)")
        print(f"  --notui                  Disable TUI windows, use standard line output")
        print(f"  -b, --batch              Batch mode: silent on stdout, errors to stderr")
        print("\nSYSTEM COMMANDS:")
        print(f"  --version                Show version")
        print(f"  --ask                    Query remote server version and serial parameters")
        sys.exit(0)
        
    if args.version:
        print(__CODE_VERSION__)
        sys.exit(0)
    
    if not validate_args(args):
        sys.exit(1)

    node = SerialBridgeNode(args)
    node.run()
