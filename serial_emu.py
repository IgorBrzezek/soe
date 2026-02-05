#!/usr/bin/env python3
# ==============================================================================
# Serial Device Emulator - Cisco-like Console Emulator
# Version: 0.0.7
# Date: 05.02.2026
# Author: Igor Brzezek
# ==============================================================================
# 
# A comprehensive serial port emulator that emulates a Cisco-like console
# supporting both Windows (serial port / named pipe) and Linux (serial port).
# Includes 50+ platform-specific commands with realistic output.
#
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
import subprocess
import json
import re
import configparser
import csv
import ctypes
import shutil
from pathlib import Path
from enum import Enum

if sys.platform == "win32":
    import msvcrt
    try:
        import win32pipe
        import win32file
        import win32event
        import win32api
        import winerror
        import pywintypes
        
        # Additional error codes that may not be in winerror
        if not hasattr(winerror, 'ERROR_PIPE_CONNECTED'):
            winerror.ERROR_PIPE_CONNECTED = 535
        if not hasattr(winerror, 'ERROR_NO_DATA'):
            winerror.ERROR_NO_DATA = 232
        if not hasattr(winerror, 'ERROR_MORE_DATA'):
            winerror.ERROR_MORE_DATA = 234
        if not hasattr(winerror, 'ERROR_PIPE_BUSY'):
            winerror.ERROR_PIPE_BUSY = 231
        if not hasattr(winerror, 'ERROR_PIPE_LISTENING'):
            winerror.ERROR_PIPE_LISTENING = 536
        if not hasattr(winerror, 'ERROR_CALL_NOT_IMPLEMENTED'):
            winerror.ERROR_CALL_NOT_IMPLEMENTED = 120
        if not hasattr(winerror, 'ERROR_PIPE_NOT_CONNECTED'):
            winerror.ERROR_PIPE_NOT_CONNECTED = 233
        
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
    sys.exit(1)

# --- Author ---
__APP_NAME__    = "Serial Device Emulator"
__CODE_AUTHOR__  = "Igor Brzezek"
__CODE_VERSION__ = "0.0.7"
__CODE_DATE__    = "05.02.2026"

# ==============================================================================
# TUI CLASS - Text User Interface for Status Line
# ==============================================================================

class TUI:
    def __init__(self, args):
        if sys.platform == "win32":
            self._enable_ansi_windows()
        self.enabled = args.tui
        self.mono = args.mono
        self.count_chars = args.count
        self.port_name = args.namedpipe if args.namedpipe else args.comport
        self.baud = args.baud
        self.line_format = args.line
        self.hostname = args.hostname
        self.serial_in_count = 0
        self.serial_out_count = 0
        self.running = False
        self.connection_status = "IN:x"
        self.is_connected = False
        self.peer_type = "" # "SRV" or empty
        self._lock = threading.Lock()
        
        # Terminal dimensions
        self.rows = 0
        self.cols = 0
        
        # ANSI color codes (disabled in mono mode)
        self.COLORS = {
            'reset': '\033[0m',
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
        }
    
    def set_connected(self, state, peer_type=""):
        """Set connection state (True/False) and peer type"""
        with self._lock:
            # Always update if state changes OR if peer_type changes while connected
            if self.is_connected != state or (state and self.peer_type != peer_type):
                self.is_connected = state
                if state:
                    self.peer_type = peer_type
                else:
                    self.peer_type = ""
                
                if self.enabled:
                    self._draw_status()

    def _enable_ansi_windows(self):
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            mode.value |= 0x0004
            kernel32.SetConsoleMode(handle, mode)
        except:
            pass
    
    def _c(self, text, color='white'):
        if self.mono:
            return text
        return f"{self.COLORS[color]}{text}{self.COLORS['reset']}"
    
    def _status_color(self):
        if 'OUT:y' in self.connection_status:
            return 'green'
        return 'red'
    
    def _get_status_line(self):
        """Generate status line"""
        # Removed red status section (IN:x) as requested
        
        if self.count_chars:
            count_text = f" | IN:{self.serial_in_count} OUT:{self.serial_out_count}"
        else:
            count_text = ""
            
        conn_color = 'green' if self.is_connected else 'red'
        
        if self.is_connected:
            conn_text = "CONNECTED"
            if self.peer_type == "SRV":
                conn_text += " SRV"
        else:
            conn_text = "DISCONNECTED"
            
        conn_display = self._c(conn_text, conn_color)
        
        port_info = self.port_name if self.port_name else 'COM1'
        
        return f"{self._c('SerialEmulator v' + __CODE_VERSION__, 'cyan')} | " \
               f"Port: {self._c(port_info, 'white')} | " \
               f"Baud: {self._c(str(self.baud), 'white')} | " \
               f"Line: {self._c(self.line_format, 'white')} | " \
               f"{self._c(self.hostname, 'white')} | " \
               f"{conn_display}" \
               f"{count_text}"
    
    def check_resize(self):
        """Check if terminal size changed and redraw if needed"""
        if not self.enabled:
            return
            
        try:
            cols, rows = shutil.get_terminal_size(fallback=(80, 24))
            with self._lock:
                if cols != self.cols or rows != self.rows:
                    # Dimensions changed
                    self.rows = rows
                    self.cols = cols
                    
                    # Full redraw sequence to fix artifacts
                    # 1. Reset scroll region and attributes
                    print('\033[0m\033[r', end='', flush=True)
                    # 2. Clear screen and move home
                    print('\033[2J\033[H', end='', flush=True)
                    # 3. Set scroll region
                    print(f'\033[1;{self.rows-1}r', end='', flush=True)
                    # 4. Draw status
                    self._draw_status()
        except:
            pass
    
    def _clear_line(self):
        """Clear the status line"""
        # No longer used in this implementation
        pass
    
    def _draw_status(self):
        """Draw the status line"""
        # Only draw if we have valid dimensions
        if self.rows == 0:
            return
            
        line = self._get_status_line()
        
        # Calculate text length stripping ANSI codes for padding check
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text_len = len(ansi_escape.sub('', line))
        
        # Apply Blue background (44) ONLY if not mono
        # Replace default reset (0) with Reset+BlueBG (0;44) to maintain background
        if not self.mono:
            styled_line = line.replace('\033[0m', '\033[0;44m')
            
            padding = self.cols - text_len
            if padding < 0:
                padding = 0
                
            final_line = f"\033[44m{styled_line}{' ' * padding}\033[0m"
        else:
            padding = self.cols - text_len
            if padding < 0:
                padding = 0
            # Use inverse video (7) for mono mode status line
            final_line = f"\033[7m{line}{' ' * padding}\033[0m"
        
        # Save Cursor (DEC), Move to Bottom Left, Print, Restore Cursor (DEC)
        print(f'\0337\033[{self.rows};1H{final_line}\0338', end='', flush=True)
    
    def update_connection(self, status):
        """Update connection status"""
        with self._lock:
            old_status = self.connection_status
            self.connection_status = status
            if old_status != status and self.enabled:
                self._draw_status()
    
    def increment_in(self):
        """Increment IN counter"""
        with self._lock:
            self.serial_in_count += 1
            if self.enabled:
                self._draw_status()
    
    def increment_out(self):
        """Increment OUT counter"""
        with self._lock:
            self.serial_out_count += 1
            if self.enabled:
                self._draw_status()
    
    def start(self):
        """Start TUI"""
        self.running = True
        self.connection_status = "IN:x"
        if self.enabled:
            # Clear screen and move to top-left
            print('\033[2J\033[H', end='', flush=True)
            print(f"\n{self._c('Serial Device Emulator v' + __CODE_VERSION__, 'cyan')} starting...")
            
            # Force initial setup of dimensions and draw immediately
            try:
                cols, rows = shutil.get_terminal_size(fallback=(80, 24))
                with self._lock:
                    self.rows = rows
                    self.cols = cols
                    # Set scrolling region to lines 1 to rows-1
                    print(f'\033[1;{self.rows-1}r', end='', flush=True)
                    # Draw status
                    self._draw_status()
            except Exception:
                pass
    
    def stop(self):
        """Stop TUI"""
        self.running = False
        if self.enabled:
            # Reset scrolling region
            print('\033[r', end='', flush=True)
            
            self.connection_status = "STOPPED"
            print()
            # Just print status one last time normally
            print(self._get_status_line())
            print()

# ==============================================================================
# ENUMS FOR MODES
# ==============================================================================

class ExecMode(Enum):
    USER_EXEC = 1
    PRIVILEGED_EXEC = 2
    CONFIG_MODE = 3

# ==============================================================================
# DEFAULT CONFIGURATION
# ==============================================================================

DEFAULT_CONFIG = {
    'comport': None,
    'namedpipe': None,
    'baud': 9600,
    'line': "8N1N",
    'device_name': 'DEVICE-SIM',
    'device_model': 'IOS XE',
    'device_version': '16.12.01',
    'hostname': 'device-sim',
    'enable_password': 'cisco',
    'login_banner': True,
    'login_message': 'Welcome to Serial Device Emulator',
    'enable_history': True,
    'cmdfile': None,
    'tui': True,
    'mono': False,
    'count': False,
    'notui': False,
    'batch': False,
    'debug': False,
    'h': False,
    'help': False,
    'version': False,
}

# ==============================================================================
# WINDOWS COMMANDS (FIXED - NO TIMEOUTS)
# ==============================================================================

WINDOWS_COMMANDS = {
    # System Information
    'show system': 'systeminfo',
    'show uptime': 'systeminfo | findstr "System Boot Time"',
    'show memory': 'wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /format:list',
    'show processor': 'wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors /format:list',
    'show disk': 'wmic logicaldisk get Name,Size,FreeSpace /format:list',
    'show drives': 'wmic logicaldisk get Name,VolumeName,Size /format:list',
    
    # Network Commands
    'show interfaces': 'ipconfig',
    'show interfaces detail': 'ipconfig /all',
    'show arp': 'arp -a',
    'show routes': 'route print',
    'show routing-table': 'route print',
    'show tcp': 'netstat -an | findstr TCP',
    'show udp': 'netstat -an | findstr UDP',
    'show connections': 'netstat -ano',
    'show tcp-statistics': 'netstat -s -p tcp',
    'show ip-statistics': 'netstat -s',
    
    # Processes
    'show processes': 'tasklist',
    'show processes detail': 'tasklist /v',
    'show running-services': 'tasklist /svc',
    'show services': 'sc query',
    'show services detail': 'sc query state=all',
    
    # Users & Accounts
    'show users': 'query user',
    'show accounts': 'net user',
    'show groups': 'net localgroup',
    'show logged-in': 'query user',
    'show whoami': 'whoami /all',
    
    # Device Info
    'show hardware': 'wmic baseboard get Product,Manufacturer,SerialNumber',
    'show bios': 'wmic bios get Version,Manufacturer,ReleaseDate',
    'show network-adapters': 'wmic nic get Name,MACAddress,Speed',
    
    # Time & NTP
    'show time': 'time /t',
    'show date': 'date /t',
    'show ntp': 'w32tm /query /status',
    'show time-servers': 'w32tm /query /peers',
    
    # File System
    'show filesystem': 'fsutil fsinfo drives',
    'show volumes': 'vol',
    'show partition-info': 'wmic partition get Name,Size,BlockSize',
    'dir /': 'dir \\',
    'show environment': 'set',
}

# ==============================================================================
# LINUX COMMANDS (FIXED - NO TIMEOUTS)
# ==============================================================================

LINUX_COMMANDS = {
    # System Information
    'show system': 'uname -a',
    'show uptime': 'uptime',
    'show memory': 'free -h',
    'show processor': 'lscpu',
    'show disk': 'df -h',
    'show disks detail': 'lsblk',
    'show drives': 'fdisk -l | grep Disk',
    'show loadavg': 'cat /proc/loadavg',
    
    # Network Commands
    'show interfaces': 'ip addr show',
    'show interfaces detail': 'ip -d link show',
    'show arp': 'arp -a',
    'show routes': 'ip route show',
    'show routing-table': 'route -n',
    'show tcp': 'ss -tan',
    'show udp': 'ss -uan',
    'show connections': 'ss -ano',
    'show dns': 'cat /etc/resolv.conf',
    'show tcp-statistics': 'ss -s',
    'show ip-statistics': 'netstat -s',
    
    # Processes
    'show processes': 'ps aux',
    'show processes detail': 'ps auxww',
    'show processes memory': 'ps aux --sort=-%mem | head -20',
    'show running-services': 'systemctl list-units --type=service --state=running',
    'show services': 'service --status-all',
    'show services detail': 'systemctl status',
    
    # Users & Accounts
    'show users': 'who',
    'show accounts': 'cut -d: -f1 /etc/passwd',
    'show groups': 'cut -d: -f1 /etc/group',
    'show logged-in': 'w',
    'show whoami': 'whoami && id',
    
    # Device Info
    'show hardware': 'cat /sys/class/dmi/id/product_name',
    'show bios': 'cat /sys/class/dmi/id/bios_version',
    'show pci': 'lspci',
    'show usb': 'lsusb',
    
    # Time & NTP
    'show time': 'date',
    'show date': 'date +%Y-%m-%d',
    'show ntp': 'timedatectl show',
    
    # File System
    'show filesystem': 'mount | grep -E "^/dev"',
    'show volumes': 'lsblk -o NAME,SIZE,TYPE',
    'show partition-info': 'parted -l',
    'dir /': 'ls -la /',
    'show environment': 'env',
    
    # System Performance
    'show cpu-usage': 'top -b -n 1 | head -15',
    'show netstat': 'netstat -i',
}

# ==============================================================================
# CISCO-LIKE DEVICE CLASS
# ==============================================================================

class CiscoLikeDevice:
    def __init__(self, args):
        self.args = args
        self.keep_running = True
        self.hostname = args.hostname
        self.mode = ExecMode.USER_EXEC
        self.config_history = []
        self.command_history = [] if args.enable_history else None
        self.history_index = -1
        self.ser_obj = None
        self.pipe_connected = False
        self.custom_commands = {}
        self.worker_thread = None
        self.shutdown_event = threading.Event()
        self.password_input_mode = False
        self.disconnect_requested = False
        self.line_buffer = ""
        self.start_time = time.time()
        
        # PTY support for Linux COMx emulation
        self._pty_master_fd = None
        self._pty_connected = False
        self._pty_empty_reads = 0
        
        # Initialize TUI if enabled
        self.tui = TUI(args) if args.tui else None
        if self.tui:
            self.tui.start()
        
        # Platform-specific commands
        self.platform_commands = WINDOWS_COMMANDS if sys.platform == "win32" else LINUX_COMMANDS
        
        # Load custom commands if provided
        if args.cmdfile:
            self._load_cmdfile(args.cmdfile)
        
        # Get all available commands for tab completion
        self.all_commands = self._get_all_commands()
    
    def _get_all_commands(self):
        """Get list of all available commands for tab completion"""
        commands = set()
        
        # Built-in commands
        commands.update(self.builtin_commands.keys())
        
        # Platform commands
        commands.update(self.platform_commands.keys())
        
        # Custom commands
        commands.update(self.custom_commands.keys())
        
        return sorted(commands)
    
    def _load_cmdfile(self, filepath):
        """Load custom commands from file in CSV format: console_command,linux_command,windows_command"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or len(row) < 3:
                        continue
                    if row[0].startswith('#'):
                        continue
                    
                    console_cmd = row[0].strip().strip('"')
                    linux_cmd = row[1].strip().strip('"')
                    windows_cmd = row[2].strip().strip('"')
                    
                    if not console_cmd:
                        continue
                    
                    # Select appropriate command based on platform
                    if sys.platform == "win32" and windows_cmd:
                        self.custom_commands[console_cmd.lower()] = windows_cmd
                    elif linux_cmd:
                        self.custom_commands[console_cmd.lower()] = linux_cmd
        except Exception as e:
            self._send_output(f"ERROR: Failed to load command file: {e}\n")
    
    def _signal_handler(self, sig, frame):
        if self.args.debug:
            print(f"[DEBUG] Signal {sig} received, initiating shutdown")
        print("\n[INFO] Shutdown signal received, stopping device...")
        self.keep_running = False
        self.shutdown_event.set()
        if self.tui:
            self.tui.stop()
    
    def _normalize_line_endings(self, text):
        """Normalize line endings to \r\n for serial port output"""
        if not text:
            return text
        # Replace \r\n or just \n with \r\n, and \r followed by non-\n with \r\n
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        text = text.replace('\n', '\r\n')
        return text
    
    def _send_output(self, data, flush=False):
        """Send output to serial/pipe with proper line endings"""
        if isinstance(data, str):
            data = self._normalize_line_endings(data)
            data = data.encode()
        if self.args.debug:
            print(f"[DEBUG] _send_output called with {len(data)} bytes, pipe_connected={self.pipe_connected}")
        
        # Calculate output size for TUI count
        output_size = len(data) if isinstance(data, bytes) else len(data.encode())
        
        try:
            # PTY mode - write to master_fd
            if hasattr(self, '_pty_master_fd') and self._pty_master_fd is not None:
                try:
                    os.write(self._pty_master_fd, data)
                    if self.tui:
                        self.tui.increment_out()
                except OSError as e:
                    if self.args.debug:
                        print(f"[DEBUG] PTY write error: {e}")
            elif self.ser_obj:
                if sys.platform == "win32" and self.pipe_connected:
                    try:
                        if self.args.debug:
                            print(f"[DEBUG] Writing to named pipe")
                        win32file.WriteFile(self.ser_obj, data)
                        if self.args.debug:
                            print(f"[DEBUG] WriteFile completed successfully")
                        # Increment OUT counter for TUI
                        if self.tui:
                            self.tui.increment_out()
                    except pywintypes.error as e:
                        if self.args.debug:
                            print(f"[DEBUG] WriteFile pywintypes.error: {e.winerror}: {e}")
                    except Exception as e:
                        if self.args.debug:
                            print(f"[DEBUG] Write error: {e}")
                else:
                    if self.args.debug:
                        print(f"[DEBUG] Writing to serial port")
                    self.ser_obj.write(data)
                    if flush or hasattr(self.ser_obj, 'flush'):
                        try:
                            self.ser_obj.flush()
                        except:
                            pass
                    # Increment OUT counter for TUI
                    if self.tui:
                        self.tui.increment_out()
        except Exception as e:
            if self.args.debug:
                print(f"[DEBUG] Send output error: {e}")
    
    def _get_prompt(self):
        """Generate prompt like Cisco device based on mode"""
        if self.mode == ExecMode.CONFIG_MODE:
            return f"{self.hostname}(config)# "
        elif self.mode == ExecMode.PRIVILEGED_EXEC:
            return f"{self.hostname}# "
        else:
            return f"{self.hostname}> "
    
    def _execute_system_command(self, cmd):
        """Execute system command and return output"""
        try:
            # Use different timeouts for different command types
            timeout = 10  # Default 10 seconds
            if sys.platform == "win32":
                # Some Windows commands are slower
                if 'systeminfo' in cmd.lower():
                    timeout = 15
                elif 'sc query state=all' in cmd.lower():
                    timeout = 15
                elif 'tasklist /v' in cmd.lower():
                    timeout = 15
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            else:
                # Some Linux commands are slower
                if 'systemctl status' in cmd.lower():
                    timeout = 15
                elif 'lscpu' in cmd.lower():
                    timeout = 10
                elif 'lsblk' in cmd.lower():
                    timeout = 10
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            
            output = result.stdout if result.stdout else result.stderr
            return output if output else "(no output)\n"
        except subprocess.TimeoutExpired:
            return "ERROR: Command timeout (command took too long to execute)\n"
        except Exception as e:
            return f"ERROR: {str(e)}\n"
    
    # ==============================================================================
    # COMMAND HANDLERS
    # ==============================================================================
    
    def _cmd_exit(self, args_str):
        """exit command - exit current mode or device"""
        if self.mode == ExecMode.CONFIG_MODE:
            self.mode = ExecMode.PRIVILEGED_EXEC
            return ""
        elif self.mode == ExecMode.PRIVILEGED_EXEC:
            self.mode = ExecMode.USER_EXEC
            return ""
        else:
            # self._send_output("Device disconnecting...\n")
            # self.disconnect_requested = True
            return ""
    
    def _cmd_quit(self, args_str):
        """quit command - alias for exit"""
        return self._cmd_exit(args_str)
    
    def _cmd_end(self, args_str):
        """end command - exit config mode to privileged exec"""
        if self.mode == ExecMode.CONFIG_MODE:
            self.mode = ExecMode.PRIVILEGED_EXEC
            return ""
        return ""
    
    def _cmd_enable(self, args_str):
        """enable command - enter privileged mode"""
        if self.mode == ExecMode.PRIVILEGED_EXEC:
            return ""
        self.password_input_mode = True
        return "Password: "
    
    def _cmd_disable(self, args_str):
        """disable command - exit privileged mode"""
        self.mode = ExecMode.USER_EXEC
        return ""
    
    def _cmd_config(self, args_str):
        """configure terminal - enter configuration mode"""
        if self.mode == ExecMode.USER_EXEC:
            return "No permission\n"
        self.mode = ExecMode.CONFIG_MODE
        return "Enter configuration commands, one per line. End with CNTL/Z.\n"
    
    def _cmd_hostname(self, args_str):
        """hostname command - set device hostname"""
        if args_str.strip():
            self.hostname = args_str.strip()
            return f"Hostname set to {self.hostname}\n"
        return f"Current hostname: {self.hostname}\n"
    
    def _cmd_show_version(self, args_str):
        """show version"""
        output = f"""
{self.args.device_name} {self.args.device_model}
{self.args.device_version}

 uptime is 45 days, 3 hours, 22 minutes
 System uptime: {datetime.datetime.now().isoformat()}
 Model: {self.args.device_model}
 Serial Number: SN{int(time.time()) % 1000000}

"""
        return output
    
    def _cmd_show_clock(self, args_str):
        """show clock"""
        now = datetime.datetime.now()
        return f"{now.strftime('%a %b %d %H:%M:%S %Z %Y')}\n"
    
    def _cmd_show_running_config(self, args_str):
        """show running-config"""
        output = f"""
Building configuration...

Current configuration : 1423 bytes
!
version {self.args.device_version}
hostname {self.hostname}
!
enable password {self.args.enable_password}
!
interface GigabitEthernet0/0
 ip address dhcp
!
interface GigabitEthernet0/1
 no ip address
 shutdown
!
line vty 0 4
!
end
"""
        return output
    
    def _cmd_show_startup_config(self, args_str):
        """show startup-config"""
        return self._cmd_show_running_config(args_str)
    
    def _cmd_write_memory(self, args_str):
        """write memory - save configuration"""
        return "Building configuration...[OK]\n"
    
    def _cmd_copy_run_start(self, args_str):
        """copy running-config startup-config"""
        return self._cmd_write_memory(args_str)
    
    def _cmd_clear_history(self, args_str):
        """clear history"""
        if self.command_history is not None:
            self.command_history.clear()
            self.history_index = -1
            return "History cleared\n"
        return "History disabled\n"
    
    def _cmd_history(self, args_str):
        """show history"""
        if not self.command_history:
            return "No history\n"
        output = "Command history:\n"
        for i, cmd in enumerate(self.command_history[-20:], 1):
            output += f"  {i}: {cmd}\n"
        return output
    
    def _cmd_help(self, args_str):
        """help command - display available commands"""
        output = f"""
Available Commands:

System:
  show version               - Display device version
  show clock                 - Display system time
  show running-config        - Display running configuration
  show startup-config        - Display startup configuration
  show system                - Display system information
  show memory                - Display memory usage
  show processes             - Display running processes

Network:
  show interfaces            - Display network interfaces
  show ip                    - Display IP configuration
  show routes                - Display routing table
  show arp                   - Display ARP table

Device Management:
  configure terminal         - Enter configuration mode
  exit / quit / end          - Exit current mode
  enable                     - Enter privileged mode
  disable                    - Exit privileged mode
  hostname <name>            - Set device hostname
  write memory               - Save configuration
  copy running-config startup-config - Save configuration

History:
  history                    - Show command history
  clear history              - Clear command history

Help:
  help / ?                  - Display this help

Custom Commands:
  (loaded from cmdfile if provided)

"""
        return output
    
    # ==============================================================================
    # BUILTIN COMMANDS MAP
    # ==============================================================================
    
    @property
    def builtin_commands(self):
        return {
            'exit': self._cmd_exit,
            'quit': self._cmd_quit,
            'end': self._cmd_end,
            'enable': self._cmd_enable,
            'disable': self._cmd_disable,
            'configure terminal': self._cmd_config,
            'config t': self._cmd_config,
            'conf t': self._cmd_config,
            'hostname': self._cmd_hostname,
            'show version': self._cmd_show_version,
            'show clock': self._cmd_show_clock,
            'show running-config': self._cmd_show_running_config,
            'show running-config ': self._cmd_show_running_config,
            'show startup-config': self._cmd_show_startup_config,
            'show startup-config ': self._cmd_show_startup_config,
            'write memory': self._cmd_write_memory,
            'write': self._cmd_write_memory,
            'copy running-config startup-config': self._cmd_copy_run_start,
            'clear history': self._cmd_clear_history,
            'history': self._cmd_history,
            '?': self._cmd_help,
            'help': self._cmd_help,
            'h': self._cmd_help,
        }
    
    def _tab_complete(self, partial_cmd):
        """Perform tab completion for partial command"""
        partial_lower = partial_cmd.lower()
        matches = [cmd for cmd in self.all_commands if cmd.startswith(partial_lower)]
        
        if not matches:
            return None
        elif len(matches) == 1:
            # Single match - complete the command
            return matches[0][len(partial_lower):]
        else:
            # Multiple matches - show them
            output = "\r\n" + "  ".join(matches) + "\r\n"
            self._send_output(output)
            return None
    
    def _handle_special_key(self, key_byte):
        """Handle special keys (backspace, arrows, tab, etc.)"""
        # key_byte is already an int when iterating over bytes in Python 3
        key_code = key_byte if isinstance(key_byte, int) else ord(key_byte)
        
        # Tab key for completion
        if key_code == 9:  # Tab
            completion = self._tab_complete(self.line_buffer)
            if completion:
                self._send_output(completion)
                self.line_buffer += completion
            return True
        
        # Backspace
        if key_code == 8 or key_code == 127:  # Backspace or DEL
            if self.line_buffer:
                self.line_buffer = self.line_buffer[:-1]
                self._send_output(b"\b \b")
            return True
        
        # Arrow keys (escape sequences)
        if key_code == 27:  # ESC - start of escape sequence
            return False  # Let the main loop handle escape sequences
        
        # Enter/Ctrl+M
        if key_code == 13 or key_code == 10:
            return False  # Let the main loop handle line endings
        
        # Ctrl+C - interrupt
        if key_code == 3:
            self._send_output("^C\r\n")
            self.line_buffer = ""
            return True
        
        return False
    
    def _process_escape_sequence(self, data):
        """Process escape sequences for arrow keys"""
        # Check for arrow key escape sequences: ESC [ A/B/C/D
        if len(data) >= 3 and data[0] == 27 and data[1] == 91:
            arrow = data[2]
            
            # Up arrow (Ctrl+P) - previous history
            if arrow == 65 and self.command_history:
                if self.history_index < len(self.command_history) - 1:
                    # Clear current line
                    self._send_output(b"\r" + b" " * len(self.line_buffer) + b"\r")
                    self.history_index += 1
                    self.line_buffer = self.command_history[-(self.history_index + 1)]
                    self._send_output(self.line_buffer)
                return 3
            
            # Down arrow (Ctrl+N) - next history
            if arrow == 66 and self.command_history:
                if self.history_index > 0:
                    # Clear current line
                    self._send_output(b"\r" + b" " * len(self.line_buffer) + b"\r")
                    self.history_index -= 1
                    self.line_buffer = self.command_history[-(self.history_index + 1)]
                    self._send_output(self.line_buffer)
                elif self.history_index == 0:
                    self.history_index = -1
                    self._send_output(b"\r" + b" " * len(self.line_buffer) + b"\r")
                    self.line_buffer = ""
                return 3
        
        return 0
    
    def process_command(self, cmd_line):
        """Process user command and return output"""
        cmd_lower = cmd_line.lower().strip()
        
        if not cmd_lower:
            return ""
        
        # Reset history index when a new command is entered
        self.history_index = -1
        
        # Add to history (but not passwords)
        if self.command_history is not None and not self.password_input_mode:
            self.command_history.append(cmd_lower)
            if len(self.command_history) > 100:
                self.command_history.pop(0)
        
        # Check built-in commands
        for cmd_name, cmd_func in self.builtin_commands.items():
            if cmd_lower.startswith(cmd_name):
                args = cmd_lower[len(cmd_name):].strip()
                return cmd_func(args)
        
        # Check custom commands
        if cmd_lower in self.custom_commands:
            shell_cmd = self.custom_commands[cmd_lower]
            return self._execute_system_command(shell_cmd)
        
        # Check platform commands
        for cmd_name, shell_cmd in self.platform_commands.items():
            if cmd_lower == cmd_name:
                return self._execute_system_command(shell_cmd)
        
        # Unknown command
        return f"Unknown command: {cmd_lower}\n"
    
    def _detect_client_type(self):
        """Detect the type of connected client process on Windows Named Pipe"""
        if sys.platform != "win32" or not self.ser_obj:
            return ""
        
        try:
            # Get the client PID using GetNamedPipeClientProcessId
            client_pid = win32pipe.GetNamedPipeClientProcessId(self.ser_obj)
            if not client_pid:
                return ""
            
            # Query the command line for this PID using wmic (standard on Windows)
            # wmic process where processid=<PID> get commandline
            cmd = f"wmic process where processid={client_pid} get commandline"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            output = result.stdout.lower()
            
            if "serial_server" in output:
                return "SRV"
            else:
                return "CL" # Generic Client
        except Exception:
            return ""
    
    def _worker_thread_main(self):
        """Main worker thread method"""
        port_name = self.args.namedpipe if self.args.namedpipe else self.args.comport
        use_named_pipe = self.args.namedpipe is not None
        
        try:
            if use_named_pipe:
                if sys.platform != "win32":
                    print("[ERROR] Named pipes only supported on Windows")
                    return
                if not WIN32_AVAILABLE:
                    print("[ERROR] Named pipes require pywin32 library")
                    print("[ERROR] Install with: pip install pywin32")
                    return
                
                pipe_path = f"\\\\.\\pipe\\{port_name}"
                print(f"[INFO] Creating named pipe: {pipe_path}")
                
                try:
                    self.ser_obj = win32pipe.CreateNamedPipe(
                        pipe_path,
                        win32pipe.PIPE_ACCESS_DUPLEX,
                        win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE,
                        1, 65536, 65536, 0, None
                    )
                    print(f"[INFO] Named pipe created successfully")
                    print(f"[INFO] Waiting for client connection to {pipe_path}...")
                    print(f"[INFO] Press CTRL-C to cancel waiting.")
                    if self.args.debug:
                        print(f"[DEBUG] Pipe handle: {self.ser_obj}")
                        print(f"[DEBUG] keep_running initial: {self.keep_running}")
                    
                    # Asynchronous connection waiting to allow CTRL-C
                    overlapped_connect = pywintypes.OVERLAPPED()
                    overlapped_connect.hEvent = win32event.CreateEvent(None, 1, 0, None)
                    if self.args.debug:
                        print(f"[DEBUG] Event created: {overlapped_connect.hEvent}")
                    
                    pending_connection = False
                    self.pipe_connected = False
                    if self.args.debug:
                        print(f"[DEBUG] pipe_connected set to False initially")
                    
                    try:
                        win32pipe.ConnectNamedPipe(self.ser_obj, overlapped_connect)
                        if self.args.debug:
                            print(f"[DEBUG] ConnectNamedPipe returned without error - treating as pending")
                        pending_connection = True
                    except pywintypes.error as e:
                        if self.args.debug:
                            print(f"[DEBUG] ConnectNamedPipe raised error: {e.winerror} - {e}")
                        if e.winerror == winerror.ERROR_IO_PENDING:
                            pending_connection = True
                            if self.args.debug:
                                print(f"[DEBUG] Connection pending, will wait")
                        elif e.winerror == winerror.ERROR_PIPE_CONNECTED:
                            self.pipe_connected = True
                            peer = self._detect_client_type()
                            if self.tui:
                                self.tui.set_connected(True, peer)
                            if self.args.debug:
                                print(f"[DEBUG] Client already connected!")
                        else:
                            if self.args.debug:
                                print(f"[DEBUG] Unexpected error, will raise")
                            raise
                    
                    # Wait loop if connection is pending
                    if pending_connection:
                        if self.args.debug:
                            print(f"[DEBUG] Entering wait loop for connection")
                        wait_counter = 0
                        while self.keep_running and not self.shutdown_event.is_set():
                            try:
                                # Wait 100ms for connection
                                rc = win32event.WaitForSingleObject(overlapped_connect.hEvent, 100)
                                if self.args.debug and wait_counter % 10 == 0:
                                    print(f"[DEBUG] WaitForSingleObject returned: {rc}")
                                if rc == win32event.WAIT_OBJECT_0:
                                    self.pipe_connected = True
                                    peer = self._detect_client_type()
                                    if self.tui:
                                        self.tui.set_connected(True, peer)
                                    if self.args.debug:
                                        print(f"[DEBUG] Event signaled, pipe_connected set to True")
                                    break
                                wait_counter += 1
                                if self.shutdown_event.is_set():
                                    print("[INFO] Shutdown requested during connection wait")
                                    break
                            except KeyboardInterrupt:
                                print("\n[INFO] Connection cancelled.")
                                self.keep_running = False
                                return
                    
                    if self.args.debug:
                        print(f"[DEBUG] After wait loop: pipe_connected={self.pipe_connected}, keep_running={self.keep_running}")
                    
                    if self.pipe_connected:
                        print(f"[INFO] Client connected to named pipe")
                        if self.args.debug:
                            print("[DEBUG] Starting main communication loop")
                    else:
                        if self.args.debug:
                            print(f"[DEBUG] pipe_connected is False, returning from run_serial")
                        return
                        
                except Exception as e:
                    print(f"[ERROR] Failed to create/connect named pipe: {e}")
                    import traceback
                    if self.args.debug:
                        traceback.print_exc()
                    return
            else:
                # Serial port mode - not using named pipe
                self.pipe_connected = False
                
                # Validate comport
                if not self.args.comport:
                    print("[ERROR] No serial port specified. Use --comport option.")
                    return
                
                # Parse line format
                try:
                    data_bits = int(self.args.line[0])
                    parity_char = self.args.line[1].upper()
                    stop_bits = float(self.args.line[2:3])
                    
                    parity_map = {'N': serial.PARITY_NONE, 'O': serial.PARITY_ODD, 'E': serial.PARITY_EVEN}
                    parity = parity_map.get(parity_char, serial.PARITY_NONE)
                    
                except (ValueError, IndexError) as e:
                    print(f"[ERROR] Invalid line format: {self.args.line}")
                    print(f"[ERROR] Error: {e}")
                    return
                
                try:
                    # Linux: Create PTY for COMx style ports in local directory
                    if sys.platform != "win32" and self.args.comport.upper().startswith("COM"):
                        import pty
                        import os
                        import select as select_module
                        import tty
                        import termios
                        
                        # Create pseudo-terminal
                        self._pty_master_fd, slave_fd = pty.openpty()
                        slave_name = os.ttyname(slave_fd)
                        
                        # Configure slave to disable echo and raw mode
                        # This prevents echo of transmitted data back to master
                        try:
                            tty.setraw(slave_fd, termios.TCSANOW)
                        except:
                            pass
                        
                        # Create symlink in current directory
                        local_port = f"./{self.args.comport}"
                        if os.path.exists(local_port):
                            os.remove(local_port)
                        os.symlink(slave_name, local_port)
                        
                        print(f"[INFO] Created pseudo-terminal: {local_port} -> {slave_name}")
                        print(f"[INFO] Emulator using master side, clients connect to: {local_port}")
                        
                        # Create a fake serial object for PTY master
                        self.ser_obj = None  # No serial object, we use master_fd directly
                        self._pty_slave_name = slave_name
                        print(f"[INFO] PTY ready - waiting for client connection...")
                    else:
                        print(f"[INFO] Opening serial port: {self.args.comport} at {self.args.baud} baud")
                        self.ser_obj = serial.Serial(
                            self.args.comport,
                            self.args.baud,
                            bytesize=data_bits,
                            parity=parity,
                            stopbits=stop_bits,
                            timeout=0.1,
                            write_timeout=0.1
                        )
                        print(f"[INFO] Serial port opened successfully ({self.args.line} format)")
                    
                    if self.tui:
                        self.tui.set_connected(True)
                    
                    time.sleep(0.1)
                    if self.ser_obj is not None:
                        try:
                            self.ser_obj.reset_input_buffer()
                            self.ser_obj.reset_output_buffer()
                        except:
                            pass
                    
                except serial.SerialException as e:
                    print(f"[ERROR] Failed to open serial port {self.args.comport}: {e}")
                    print(f"[ERROR] Possible causes:")
                    print(f"[ERROR]   - Port does not exist")
                    print(f"[ERROR]   - Port is already in use")
                    print(f"[ERROR]   - Insufficient permissions (try running as administrator/root)")
                    return
                except Exception as e:
                    print(f"[ERROR] Unexpected error opening serial port: {e}")
                    return
            
            # Send login banner with proper line endings
            if self.args.login_banner:
                self._send_output(f"\r\n{self.args.login_message}\r\n\r\n")
            
            # Send initial prompt
            self._send_output(self._get_prompt())
            
            if self.args.debug:
                print("[DEBUG] Initial prompt sent, entering main loop")
            
            # Main loop
            self.line_buffer = ""
            last_activity = time.time()
            loop_iteration = 0
            escape_buffer = b""
            
            if self.args.debug:
                print(f"[DEBUG] About to enter main loop, keep_running={self.keep_running}")
            
            while self.keep_running and not self.shutdown_event.is_set():
                loop_iteration += 1
                
                if self.disconnect_requested:
                    self.disconnect_requested = False
                    if use_named_pipe and self.pipe_connected:
                        try:
                            win32pipe.DisconnectNamedPipe(self.ser_obj)
                        except:
                            pass
                    elif not use_named_pipe:
                        self._send_output("\r\n\r\n[Device Disconnected]\r\nPress ENTER to connect...\r\n")
                
                try:
                    data = b""
                    
                    # Read from serial/pipe/PTY with timeout to allow CTRL-C handling
                    if use_named_pipe and self.pipe_connected:
                        try:
                            try:
                                read_buffer = win32file.AllocateReadBuffer(1024)
                                err, data = win32file.ReadFile(self.ser_obj, read_buffer, None)
                                if err != 0:
                                    data = b""
                            except pywintypes.error as read_err:
                                # Re-raise disconnect errors to be handled by outer except
                                if sys.platform == "win32" and (read_err.winerror == 109 or read_err.winerror == 233):
                                    raise
                                elif sys.platform == "win32" and read_err.winerror == 232: # No data
                                    data = b""
                                else:
                                    data = b""
                        except pywintypes.error as e:
                            if sys.platform == "win32" and (e.winerror == 109 or e.winerror == 233):
                                print("[INFO] Client disconnected from pipe")
                                self.pipe_connected = False
                                if self.tui:
                                    self.tui.set_connected(False)
                                try:
                                    win32pipe.DisconnectNamedPipe(self.ser_obj)
                                except:
                                    pass
                                print("[INFO] Waiting for new connection...")
                                pending_reconnect = False
                                overlapped_reconnect = pywintypes.OVERLAPPED()
                                overlapped_reconnect.hEvent = win32event.CreateEvent(None, 1, 0, None)
                                try:
                                    win32pipe.ConnectNamedPipe(self.ser_obj, overlapped_reconnect)
                                    # If no exception, connection might be active or pending without exception (rare for overlapped)
                                    # Treat as pending to be safe
                                    pending_reconnect = True
                                except pywintypes.error as e:
                                    if e.winerror == winerror.ERROR_IO_PENDING:
                                        pending_reconnect = True
                                    elif e.winerror == winerror.ERROR_PIPE_CONNECTED:
                                        print("[INFO] Client reconnected")
                                        self.pipe_connected = True
                                        peer = self._detect_client_type()
                                        if self.tui:
                                            self.tui.set_connected(True, peer)
                                    else:
                                        raise
                                
                                if pending_reconnect:
                                    reconnect_counter = 0
                                    while self.keep_running and not self.shutdown_event.is_set():
                                        try:
                                            rc = win32event.WaitForSingleObject(overlapped_reconnect.hEvent, 100)
                                            if self.args.debug and reconnect_counter % 10 == 0:
                                                print(f"[DEBUG] Reconnect wait iteration {reconnect_counter}, rc={rc}")
                                            if rc == win32event.WAIT_OBJECT_0:
                                                print("[INFO] Client reconnected")
                                                self.pipe_connected = True
                                                peer = self._detect_client_type()
                                                if self.tui:
                                                    self.tui.set_connected(True, peer)
                                                self._send_output(self._get_prompt())
                                                break
                                            reconnect_counter += 1
                                            if self.shutdown_event.is_set():
                                                print("[INFO] Shutdown requested during reconnection wait")
                                                break
                                        except KeyboardInterrupt:
                                            print("\n[INFO] Interrupted by user")
                                            self.keep_running = False
                                            self.shutdown_event.set()
                                            break
                                try:
                                    win32api.CloseHandle(overlapped_reconnect.hEvent)
                                except:
                                    pass
                                if not self.keep_running:
                                    return
                                continue
                            else:
                                if self.args.debug:
                                    print(f"[DEBUG] Pipe read error: {e}")
                                data = b""
                    elif hasattr(self, '_pty_master_fd') and self._pty_master_fd is not None:
                        # PTY mode - read from master_fd
                        import select
                        try:
                            ready, _, _ = select.select([self._pty_master_fd], [], [], 0.01)
                            if ready:
                                data = os.read(self._pty_master_fd, 1024)
                                if data:
                                    # Client sent data - mark as connected
                                    if not self._pty_connected:
                                        self._pty_connected = True
                                        if self.tui:
                                            self.tui.set_connected(True)
                                        print(f"[INFO] Client connected to PTY")
                                    # Reset disconnect detection counter
                                    self._pty_empty_reads = 0
                                else:
                                    # EOF - client closed connection (0 bytes read)
                                    if self._pty_connected:
                                        self._pty_connected = False
                                        if self.tui:
                                            self.tui.set_connected(False)
                                        print(f"[INFO] Client disconnected from PTY")
                                    data = b""
                            else:
                                data = b""
                                # Increment empty read counter for disconnect detection
                                if self._pty_connected:
                                    self._pty_empty_reads = getattr(self, '_pty_empty_reads', 0) + 1
                                    # After ~5 seconds of no data (500 * 0.01s), assume disconnected
                                    if self._pty_empty_reads > 500:
                                        self._pty_connected = False
                                        if self.tui:
                                            self.tui.set_connected(False)
                                        print(f"[INFO] Client connection timeout (no data)")
                        except OSError as e:
                            # Client disconnected or error
                            if self._pty_connected:
                                self._pty_connected = False
                                if self.tui:
                                    self.tui.set_connected(False)
                                print(f"[INFO] Client disconnected from PTY")
                            if self.args.debug:
                                print(f"[DEBUG] PTY read error: {e}")
                            data = b""
                    elif self.ser_obj and hasattr(self.ser_obj, 'in_waiting'):
                        bytes_waiting = self.ser_obj.in_waiting
                        if bytes_waiting > 0:
                            data = self.ser_obj.read(bytes_waiting)
                    
                    if data:
                        if self.args.debug:
                            print(f"[DEBUG] Got data: {data} (length: {len(data)})")
                        last_activity = time.time()
                        
                        # Increment IN counter for TUI
                        if self.tui:
                            for byte in data:
                                self.tui.increment_in()
                        
                        # Handle escape sequences for arrow keys
                        escape_buffer += data
                        if len(escape_buffer) >= 3:
                            consumed = self._process_escape_sequence(escape_buffer)
                            if consumed > 0:
                                escape_buffer = escape_buffer[consumed:]
                                continue
                        
                        # Process each byte for special keys
                        for byte in data:
                            # byte is already an int when iterating over bytes in Python 3
                            key_code = byte if isinstance(byte, int) else ord(byte)
                            key_handled = self._handle_special_key(byte)
                            if not key_handled:
                                # Regular character - add to line buffer
                                if 32 <= key_code <= 126:  # Printable ASCII
                                    self.line_buffer += chr(key_code)
                                    if not self.password_input_mode:
                                        self._send_output(bytes([key_code]))
                        
                        # Check for line endings in the data
                        for i, byte in enumerate(data):
                            # byte is already an int when iterating over bytes in Python 3
                            key_code = byte if isinstance(byte, int) else ord(byte)
                            if key_code in (10, 13):  # LF or CR
                                # Line ending found - process the command
                                cmd_line = self.line_buffer
                                self.line_buffer = ""
                                escape_buffer = b""
                                
                                if self.args.debug:
                                    print(f"[DEBUG] Command received: {cmd_line}")
                                
                                # Handle password input mode
                                if self.password_input_mode:
                                    self.password_input_mode = False
                                    # Validate password
                                    if cmd_line == self.args.enable_password:
                                        self.mode = ExecMode.PRIVILEGED_EXEC
                                        output = "\r\n"
                                    else:
                                        output = "\r\nPassword: \r\n% Access denied\r\n"
                                    self._send_output(output)
                                else:
                                    # Echo command
                                    self._send_output("\r\n")
                                    
                                    # Process and send output
                                    output = self.process_command(cmd_line)
                                    if output:
                                        self._send_output(output)
                                
                                # Send prompt
                                self._send_output(self._get_prompt())
                                break
                    
                    if not self.keep_running or self.shutdown_event.is_set():
                        break
                    time.sleep(0.01)
                
                except KeyboardInterrupt:
                    if self.args.debug:
                        print("[DEBUG] KeyboardInterrupt in main loop")
                    raise
                except Exception as e:
                    if self.args.debug:
                        print(f"[DEBUG] Exception in main loop iteration {loop_iteration}: {e}")
                        import traceback
                        traceback.print_exc()
                    time.sleep(0.01)
            
            if self.args.debug:
                print(f"[DEBUG] Main loop exited, iterations: {loop_iteration}")
                
        except Exception as e:
            if self.args.debug:
                print(f"[ERROR] Worker thread exception: {e}")
                import traceback
                traceback.print_exc()
        finally:
            if self.args.debug:
                print("[DEBUG] Worker thread cleanup")
            # Cleanup PTY if used (only for virtual COMx ports, not physical)
            if hasattr(self, '_pty_master_fd') and self._pty_master_fd is not None:
                try:
                    os.close(self._pty_master_fd)
                    if self.args.debug:
                        print("[DEBUG] PTY master fd closed")
                except Exception as e:
                    if self.args.debug:
                        print(f"[DEBUG] PTY close error: {e}")
                finally:
                    self._pty_master_fd = None
                    # Remove symlink only for virtual COMx ports
                    if self.args.comport.upper().startswith("COM"):
                        local_port = f"./{self.args.comport}"
                        try:
                            if os.path.exists(local_port):
                                os.remove(local_port)
                                print(f"[INFO] Removed virtual port: {local_port}")
                        except Exception as e:
                            if self.args.debug:
                                print(f"[DEBUG] Symlink removal error: {e}")
            if self.ser_obj:
                try:
                    if use_named_pipe and sys.platform == "win32":
                        try:
                            win32pipe.DisconnectNamedPipe(self.ser_obj)
                        except:
                            pass
                        try:
                            win32file.CloseHandle(self.ser_obj)
                        except:
                            pass
                    else:
                        if hasattr(self.ser_obj, 'close'):
                            self.ser_obj.close()
                except Exception as e:
                    if self.args.debug:
                        print(f"[DEBUG] Worker cleanup error: {e}")
    
    def run_serial(self):
        """Run device on serial port/pipe using separate thread"""
        if sys.platform != "win32":
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        else:
            signal.signal(signal.SIGINT, self._signal_handler)
        
        # Start TUI if enabled
        if self.tui:
            self.tui.start()
        
        try:
            self.worker_thread = threading.Thread(target=self._worker_thread_main, name="SerialDeviceWorker")
            self.worker_thread.daemon = True
            self.worker_thread.start()
            
            if self.args.debug:
                print("[DEBUG] Worker thread started, waiting for completion or interrupt")
            
            while self.worker_thread.is_alive() and not self.shutdown_event.is_set():
                try:
                    self.worker_thread.join(timeout=0.1)
                    if self.tui:
                        self.tui.check_resize()
                except KeyboardInterrupt:
                    if self.args.debug:
                        print("[DEBUG] KeyboardInterrupt in main thread")
                    print("\n[INFO] Keyboard interrupt received, shutting down...")
                    self.keep_running = False
                    self.shutdown_event.set()
                    self.worker_thread.join(timeout=1.0)
                    break
                
                if self.shutdown_event.is_set():
                    if self.args.debug:
                        print("[DEBUG] Shutdown event detected in main thread")
                    break
            
            if self.args.debug:
                print("[DEBUG] Main thread exiting")
                
        except Exception as e:
            print(f"[ERROR] Fatal error in main thread: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.tui:
                self.tui.stop()
            self.keep_running = False
            self.shutdown_event.set()
            
            if self.worker_thread and self.worker_thread.is_alive():
                if self.args.debug:
                    print("[DEBUG] Waiting for worker thread to finish...")
                self.worker_thread.join(timeout=2.0)
            
            # Cleanup PTY symlink in main thread (backup cleanup)
            if hasattr(self, '_pty_master_fd') and self._pty_master_fd is not None:
                try:
                    os.close(self._pty_master_fd)
                    self._pty_master_fd = None
                except:
                    pass
                # Remove virtual port symlink
                if self.args.comport.upper().startswith("COM"):
                    local_port = f"./{self.args.comport}"
                    try:
                        if os.path.exists(local_port):
                            os.remove(local_port)
                            print(f"[INFO] Cleaned up virtual port: {local_port}")
                    except:
                        pass
            
            # Print summary and clear screen
            duration = time.time() - self.start_time
            print('\033[2J\033[H', end='', flush=True)
            print(f"\n{__APP_NAME__} Session Summary")
            print("=" * 30)
            print(f"Duration: {datetime.timedelta(seconds=int(duration))}")
            if self.tui:
                 print(f"Bytes IN:  {self.tui.serial_in_count}")
                 print(f"Bytes OUT: {self.tui.serial_out_count}")
            print("=" * 30)
            print("Session closed.")

# ==============================================================================
# CONFIGURATION LOADER AND VALIDATOR
# ==============================================================================

VALID_OPTIONS = {
    'comport', 'namedpipe', 'baud', 'line', 'device-name', 'device-model',
    'device-version', 'hostname', 'enable-password', 'cmdfile', 'tui', 'mono', 'count',
    'notui', 'batch', 'debug', 'h', 'help', 'version', 'login-banner', 'login-message',
    'enable-history'
}

VALID_BAUD_RATES = {110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200}
VALID_LINE_FORMATS = {'5N1N', '5N1.5N', '5N2N', '6N1N', '6N1.5N', '6N2N', 
                      '7N1N', '7N1.5N', '7N2N', '8N1N', '8N1.5N', '8N2N',
                      '5O1N', '5O1.5N', '5O2N', '6O1N', '6O1.5N', '6O2N',
                      '7O1N', '7O1.5N', '7O2N', '8O1N', '8O1.5N', '8O2N',
                      '5E1N', '5E1.5N', '5E2N', '6E1N', '6E1.5N', '6E2N',
                      '7E1N', '7E1.5N', '7E2N', '8E1N', '8E1.5N', '8E2N'}

def validate_line_format(line_param):
    """Validate serial line format"""
    if not isinstance(line_param, str) or len(line_param) < 4:
        return False
    
    try:
        data_bits = int(line_param[0])
        parity = line_param[1].upper()
        stop_bits_str = line_param[2:].replace('N', '')
        
        if data_bits not in [5, 6, 7, 8]:
            return False
        if parity not in ['N', 'O', 'E']:
            return False
        if not stop_bits_str or float(stop_bits_str) not in [1.0, 1.5, 2.0]:
            return False
        
        return True
    except (ValueError, IndexError):
        return False

def validate_comport(port):
    """Validate serial port name"""
    if not port or not isinstance(port, str):
        return False
    
    if sys.platform == "win32":
        return port.upper().startswith('COM') and port[3:].isdigit()
    else:
        return port.startswith('/dev/tty')

def load_config():
    """Load configuration from arguments and/or config file"""
    # 1. Default config
    config = DEFAULT_CONFIG.copy()
    
    # 1.5 Pre-parse CLI to get --cfgfile
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--cfgfile")
    pre_args, _ = pre_parser.parse_known_args()
    
    # 2. Config File - Determine file to load
    config_file = pre_args.cfgfile if pre_args.cfgfile else 'serial_emu.conf'
    
    # 3. Load from file if exists
    if os.path.exists(config_file):
        try:
            config_parser = configparser.ConfigParser()
            config_parser.read(config_file)
            if 'DEFAULT' in config_parser:
                defaults = config_parser['DEFAULT']
                for key in defaults:
                    # Normalize key: replace - with _ (e.g., enable-history -> enable_history)
                    norm_key = key.replace('-', '_')
                    if norm_key in config:
                        # Convert types based on DEFAULT_CONFIG
                        default_val = config[norm_key]
                        val = defaults[key]
                        
                        # Remove inline comments
                        if '#' in val:
                            val = val.split('#')[0].strip()
                        
                        if isinstance(default_val, bool):
                            config[norm_key] = val.lower() in ('true', 'yes', '1', 'on')
                        elif isinstance(default_val, int):
                            try:
                                config[norm_key] = int(val)
                            except:
                                pass
                        elif default_val is None: 
                             # Try to infer type or just store as string
                             if val.lower() in ('true', 'yes', 'on'):
                                 config[norm_key] = True
                             elif val.lower() in ('false', 'no', 'off'):
                                 config[norm_key] = False
                             elif val.isdigit():
                                 config[norm_key] = int(val)
                             else:
                                 config[norm_key] = val
                        else:
                            config[norm_key] = val
        except Exception as e:
            print(f"[WARNING] Error reading {config_file}: {e}")
    elif pre_args.cfgfile:
        print(f"[WARNING] Config file not found: {pre_args.cfgfile}")

    # 4. Parse command line arguments
    parser = argparse.ArgumentParser(description=f"{__APP_NAME__} v{__CODE_VERSION__}", add_help=False)
    
    # Connection args
    parser.add_argument("--comport", help="Serial port name (e.g. COM1, /dev/ttyUSB0)")
    parser.add_argument("--namedpipe", help="Windows named pipe name (e.g. device-sim)")
    parser.add_argument("--baud", type=int, help="Baud rate (default: 9600)")
    parser.add_argument("--line", help="Line format (data/parity/stop, e.g. 8N1N)")
    
    # Device args
    parser.add_argument("--device-name", dest="device_name", help="Device name for show version")
    parser.add_argument("--device-model", dest="device_model", help="Device model")
    parser.add_argument("--device-version", dest="device_version", help="Device OS version")
    parser.add_argument("--hostname", help="Device hostname")
    parser.add_argument("--enable-password", dest="enable_password", help="Enable mode password")
    
    # Feature args
    parser.add_argument("--cmdfile", help="Path to CSV file with custom commands")
    parser.add_argument("--cfgfile", help="Path to configuration file")
    # For booleans, use default=None to detect if user specified the flag
    parser.add_argument("--tui", action="store_true", default=None, help="Enable Text User Interface (default)")
    parser.add_argument("--notui", action="store_true", default=None, help="Disable Text User Interface")
    parser.add_argument("--mono", action="store_true", default=None, help="Monochrome mode (no colors)")
    parser.add_argument("--count", action="store_true", default=None, help="Show char counters in TUI")
    parser.add_argument("--login-banner", dest="login_banner", type=lambda x: (str(x).lower() == 'true'), help="Show login banner (true/false)")
    parser.add_argument("--login-message", dest="login_message", help="Custom login message")
    parser.add_argument("--enable-history", dest="enable_history", type=lambda x: (str(x).lower() == 'true'), help="Enable command history (true/false)")
    
    # Meta args
    parser.add_argument("-b", "--batch", action="store_true", default=None, help="Batch mode (no interaction)")
    parser.add_argument("--debug", action="store_true", default=None, help="Enable debug output")
    parser.add_argument("-h", "--help", action="store_true", default=None, help="Show help message")
    parser.add_argument("--version", action="store_true", default=None, help="Show version")
    
    args, unknown = parser.parse_known_args()
    
    # 5. Handle help/version
    if args.help:
        print(f"{__APP_NAME__} v{__CODE_VERSION__}")
        print("\nUsage: python serial_device.py [options]")
        print("\nOptions:")
        print("  --comport PORT       Serial port to use (COMx or /dev/ttyX)")
        print("  --namedpipe NAME     Windows named pipe to use")
        print("  --baud RATE          Baud rate (default: 9600)")
        print("  --line FORMAT        Line format (default: 8N1N)")
        print("  --hostname NAME      Device hostname")
        print("  --notui              Disable TUI status line")
        print("  --mono               Disable colors")
        print("  --count              Show byte counters in TUI")
        print("  --cmdfile FILE       Load custom commands from CSV")
        print("  --cfgfile FILE       Load configuration from specific file")
        print("  --debug              Enable debug logging")
        sys.exit(0)
        
    if args.version:
        print(f"{__APP_NAME__} v{__CODE_VERSION__}")
        sys.exit(0)
    
    # 6. Merge args into config (Only if not None)
    for key, value in vars(args).items():
        if value is not None:
            # Handle special TUI logic
            if key == 'notui' and value:
                config['tui'] = False
            elif key == 'tui' and value:
                config['tui'] = True
            else:
                config[key] = value
                
    # 6. Validation
    if not config['comport'] and not config['namedpipe']:
        # Default to named pipe 'device-sim' on Windows if nothing specified
        if sys.platform == "win32":
            config['namedpipe'] = 'device-sim'
        else:
            print("[ERROR] You must specify --comport or --namedpipe")
            sys.exit(1)
            
    if config['baud'] not in VALID_BAUD_RATES:
        print(f"[WARNING] Non-standard baud rate: {config['baud']}")
        
    if not validate_line_format(config['line']):
        print(f"[ERROR] Invalid line format: {config['line']}. Expected format like 8N1N.")
        sys.exit(1)
        
    return argparse.Namespace(**config)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    if sys.platform == "win32":
        os.system('color')
        
    args = load_config()
    
    if args.debug:
        print(f"[DEBUG] Starting {__APP_NAME__} v{__CODE_VERSION__}")
        print(f"[DEBUG] Configuration: {vars(args)}")
    
    device = CiscoLikeDevice(args)
    try:
        device.run_serial()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[ERROR] Unhandled exception: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
