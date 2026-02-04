#!/usr/bin/env python3
# ==============================================================================
# Serial Device Simulator - Cisco-like Console Emulator
# Version: 0.0.1
# Date: 04.02.2026
# Author: Igor Brzezek
# ==============================================================================
# 
# A comprehensive serial port simulator that emulates a Cisco-like console
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
from pathlib import Path

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
    sys.exit(1)

__APP_NAME__    = "Serial Device Simulator"
__CODE_AUTHOR__  = "Igor Brzezek"
__CODE_VERSION__ = "0.0.1"
__CODE_DATE__    = "04.02.2026"

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
    'enable_password': 'cisco123',
    'login_banner': True,
    'login_message': 'Welcome to Serial Device Simulator',
    'enable_history': True,
    'cmdfile': None,
    'notui': False,
    'batch': False,
    'debug': False,
    'h': False,
    'help': False,
    'version': False,
}

# ==============================================================================
# WINDOWS COMMANDS (50+)
# ==============================================================================

WINDOWS_COMMANDS = {
    # System Information
    'show system': 'systeminfo | findstr /C:"OS Name" /C:"System Boot Time" /C:"Total Physical Memory"',
    'show uptime': 'systeminfo | findstr "System Boot Time"',
    'show memory': 'wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /format:list',
    'show processor': 'wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors /format:list',
    'show disk': 'wmic logicaldisk get Name,Size,FreeSpace /format:list',
    'show disks detail': 'diskpart <<< (list disk)',
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
    'show dns': 'ipconfig /displaydns',
    'show tcp-statistics': 'netstat -s -p tcp',
    'show ip-statistics': 'netstat -s',
    
    # Processes
    'show processes': 'tasklist',
    'show processes detail': 'tasklist /v',
    'show processes memory': 'tasklist /v | findstr /I memory',
    'show running-services': 'tasklist /svc',
    'show services': 'sc query | findstr "SERVICE_NAME"',
    'show services detail': 'sc query state=all',
    
    # Users & Accounts
    'show users': 'query user',
    'show accounts': 'net user',
    'show groups': 'net localgroup',
    'show logged-in': 'query user',
    'show whoami': 'whoami /all',
    
    # Logs & Events
    'show event-log': 'wevtutil qe System /c:20 /rd:true /f:text',
    'show errors': 'wevtutil qe System /c:10 /rd:true /f:text /q:"Level=2"',
    'show warnings': 'wevtutil qe System /c:10 /rd:true /f:text /q:"Level=3"',
    
    # Device Info
    'show hardware': 'wmic baseboard get Product,Manufacturer,SerialNumber',
    'show bios': 'wmic bios get Version,Manufacturer,ReleaseDate',
    'show network-adapters': 'wmic nic get Name,MACAddress,Speed',
    
    # Time & NTP
    'show time': 'time /t',
    'show date': 'date /t',
    'show ntp': 'w32tm /query /status',
    'show time-servers': 'w32tm /query /peers',
    
    # Diagnostic Commands
    'ping 8.8.8.8': 'ping -c 4 8.8.8.8',
    'tracert 8.8.8.8': 'tracert 8.8.8.8',
    'show dns-cache': 'ipconfig /displaydns',
    'clear-dns-cache': 'ipconfig /flushdns',
    
    # File System
    'show filesystem': 'fsutil fsinfo drives',
    'show volumes': 'vol',
    'show partition-info': 'wmic partition get Name,Size,BlockSize',
    'dir /': 'dir \\',
    'show environment': 'set',
}

# ==============================================================================
# LINUX COMMANDS (50+)
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
    
    # Logs & Events
    'show syslog': 'tail -n 30 /var/log/syslog',
    'show kernel-log': 'dmesg | tail -n 30',
    'show auth-log': 'tail -n 20 /var/log/auth.log',
    'show errors': 'grep -i error /var/log/syslog | tail -n 10',
    'show warnings': 'grep -i warning /var/log/syslog | tail -n 10',
    
    # Device Info
    'show hardware': 'dmidecode -s system-product-name',
    'show bios': 'dmidecode -s bios-version',
    'show network-adapters': 'ethtool -i eth0',
    'show pci': 'lspci',
    'show usb': 'lsusb',
    
    # Time & NTP
    'show time': 'date',
    'show date': 'date +%Y-%m-%d',
    'show ntp': 'timedatectl show',
    'show time-servers': 'grep -i "^server" /etc/ntp.conf',
    
    # Diagnostic Commands
    'ping 8.8.8.8': 'ping -c 4 8.8.8.8',
    'tracert 8.8.8.8': 'traceroute 8.8.8.8',
    'show dns-cache': 'systemd-resolve --statistics',
    
    # File System
    'show filesystem': 'mount | grep -E "^/dev"',
    'show volumes': 'lsblk -o NAME,SIZE,TYPE',
    'show partition-info': 'parted -l',
    'dir /': 'ls -la /',
    'show environment': 'env',
    
    # System Performance
    'show cpu-usage': 'top -b -n 1 | head -15',
    'show io-stats': 'iostat -x 1 2',
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
        self.enable_mode = False
        self.command_history = [] if args.enable_history else None
        self.ser_obj = None
        self.pipe_connected = False
        self.custom_commands = {}
        
        # Platform-specific commands
        self.platform_commands = WINDOWS_COMMANDS if sys.platform == "win32" else LINUX_COMMANDS
        
        # Load custom commands if provided
        if args.cmdfile:
            self._load_cmdfile(args.cmdfile)
        
        # Built-in commands
        self.builtin_commands = {
            'exit': self._cmd_exit,
            'quit': self._cmd_exit,
            'enable': self._cmd_enable,
            'disable': self._cmd_disable,
            'configure terminal': self._cmd_config,
            'config t': self._cmd_config,
            'exit-config': self._cmd_exit_config,
            'end': self._cmd_exit_config,
            'hostname': self._cmd_hostname,
            'show version': self._cmd_show_version,
            'show clock': self._cmd_show_clock,
            'clear history': self._cmd_clear_history,
            'history': self._cmd_history,
            '?': self._cmd_help,
            'help': self._cmd_help,
            'h': self._cmd_help,  # Short alias for help
        }
        
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _load_cmdfile(self, filepath):
        """Load custom commands from file"""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('|')
                    if len(parts) == 2:
                        cmd, shell_cmd = parts[0].strip(), parts[1].strip()
                        self.custom_commands[cmd.lower()] = shell_cmd
        except Exception as e:
            self._send_output(f"ERROR: Failed to load command file: {e}\n")
    
    def _signal_handler(self, sig, frame):
        self.keep_running = False
    
    def _send_output(self, data):
        """Send output to serial/pipe with proper line endings"""
        if isinstance(data, str):
            data = data.encode()
        try:
            if self.ser_obj:
                if sys.platform == "win32" and self.pipe_connected:
                    try:
                        win32file.WriteFile(self.ser_obj, data)
                    except Exception as e:
                        if self.args.debug:
                            print(f"[DEBUG] Write error: {e}")
                elif sys.platform != "win32":
                    self.ser_obj.write(data)
        except Exception as e:
            if self.args.debug:
                print(f"[DEBUG] Send output error: {e}")
    
    def _get_prompt(self):
        """Generate prompt like Cisco device"""
        suffix = "#" if self.enable_mode else ">"
        return f"{self.hostname}{suffix} "
    
    def _execute_system_command(self, cmd):
        """Execute system command and return output"""
        try:
            if sys.platform == "win32":
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            else:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            output = result.stdout if result.stdout else result.stderr
            return output if output else "(no output)\n"
        except subprocess.TimeoutExpired:
            return "ERROR: Command timeout\n"
        except Exception as e:
            return f"ERROR: {str(e)}\n"
    
    def _cmd_exit(self, args_str):
        """exit command"""
        self._send_output("Device disconnecting...\n")
        self.keep_running = False
        return ""
    
    def _cmd_enable(self, args_str):
        """enable command"""
        self._send_output(f"Password: ")
        # Simplified - just prompt and wait
        return "Entered enable mode\n"
    
    def _cmd_disable(self, args_str):
        """disable command"""
        self.enable_mode = False
        return "Exited enable mode\n"
    
    def _cmd_config(self, args_str):
        """configure terminal"""
        # Simplified - just acknowledge
        return "Entering configuration mode\n"
    
    def _cmd_exit_config(self, args_str):
        """exit configuration mode"""
        return "Exited configuration mode\n"
    
    def _cmd_hostname(self, args_str):
        """hostname command"""
        if args_str.strip():
            self.hostname = args_str.strip()
            return f"Hostname set to {self.hostname}\n"
        return f"Current hostname: {self.hostname}\n"
    
    def _cmd_show_version(self, args_str):
        """show version"""
        output = f"""
Cisco IOS Software, C9300 Software, Version 16.12.01
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
    
    def _cmd_clear_history(self, args_str):
        """clear history"""
        if self.command_history is not None:
            self.command_history.clear()
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
        """help command"""
        output = f"""
Available Commands:

System:
  show version              - Display device version
  show clock                - Display system time
  show system               - Display system information
  show memory               - Display memory usage
  show processes            - Display running processes

Network:
  show interfaces           - Display network interfaces
  show ip                   - Display IP configuration
  show routes               - Display routing table
  show arp                  - Display ARP table

Device Management:
  configure terminal        - Enter configuration mode
  exit / quit               - Exit current mode
  enable / disable          - Enter / exit privileged mode
  hostname <name>           - Set device hostname

History:
  history                   - Show command history
  clear history             - Clear command history

Help:
  help / ?                  - Display this help

Custom Commands:
  (loaded from cmdfile if provided)

"""
        return output
    
    def process_command(self, cmd_line):
        """Process user command and return output"""
        cmd_lower = cmd_line.lower().strip()
        
        if not cmd_lower:
            return ""
        
        # Add to history
        if self.command_history is not None:
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
    
    def run_serial(self):
        """Run device on serial port/pipe"""
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
                    win32pipe.ConnectNamedPipe(self.ser_obj, None)
                    self.pipe_connected = True
                    print(f"[INFO] Client connected to named pipe")
                except Exception as e:
                    print(f"[ERROR] Failed to create/connect named pipe: {e}")
                    return
            else:
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
                    
                    # Flush any existing data and configure port
                    time.sleep(0.1)
                    try:
                        self.ser_obj.reset_input_buffer()
                        self.ser_obj.reset_output_buffer()
                    except:
                        pass  # Some ports don't support this
                    
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
            
            print(f"[INFO] Device simulator is running. Type 'exit' to quit.")
            print(f"[INFO] Hostname: {self.hostname}")
            print(f"[INFO] Press CTRL-C to shutdown gracefully.\n")
            
            # Send initial prompt
            self._send_output(self._get_prompt())
            
            # Main loop
            input_buffer = ""
            last_activity = time.time()
            
            while self.keep_running:
                try:
                    data = b""
                    
                    # Read from serial/pipe with timeout to allow CTRL-C handling
                    if use_named_pipe and self.pipe_connected:
                        try:
                            # Use PeekNamedPipe to check for data without blocking
                            # This allows the loop to run and process signals (CTRL-C)
                            _, _, total_bytes_avail, _ = win32pipe.PeekNamedPipe(self.ser_obj, 0)
                            
                            if total_bytes_avail > 0:
                                err, data = win32file.ReadFile(self.ser_obj, total_bytes_avail)
                            else:
                                data = b""
                        except Exception as e:
                            # Check for broken pipe (client disconnected)
                            if isinstance(e, pywintypes.error) and e.winerror == 109: # ERROR_BROKEN_PIPE
                                print("[INFO] Client disconnected from pipe")
                                # Wait for new connection or exit?
                                # For simple sim, just reconnect logic or clear pipe
                                win32pipe.DisconnectNamedPipe(self.ser_obj)
                                win32pipe.ConnectNamedPipe(self.ser_obj, None)
                                print("[INFO] Client reconnected")
                                continue
                            
                            if self.args.debug:
                                print(f"[DEBUG] Pipe read error: {e}")
                            data = b""
                    elif self.ser_obj and hasattr(self.ser_obj, 'in_waiting'):
                        # Serial port
                        bytes_waiting = self.ser_obj.in_waiting
                        if bytes_waiting > 0:
                            data = self.ser_obj.read(bytes_waiting)
                    
                    if data:
                        last_activity = time.time()
                        try:
                            input_buffer += data.decode(errors='replace')
                        except AttributeError:
                            # If data is already string
                            input_buffer += str(data)
                        
                        # Process complete lines
                        while '\n' in input_buffer or '\r' in input_buffer:
                            # Find line ending
                            idx_n = input_buffer.find('\n')
                            idx_r = input_buffer.find('\r')
                            idx = -1
                            
                            if idx_n >= 0 and idx_r >= 0:
                                idx = min(idx_n, idx_r)
                            elif idx_n >= 0:
                                idx = idx_n
                            elif idx_r >= 0:
                                idx = idx_r
                            
                            if idx >= 0:
                                cmd_line = input_buffer[:idx].strip()
                                input_buffer = input_buffer[idx+1:].lstrip('\r\n')
                                
                                if cmd_line:
                                    if self.args.debug:
                                        print(f"[DEBUG] Command received: {cmd_line}")
                                    
                                    # Echo command with proper line ending
                                    self._send_output(cmd_line + "\r\n")
                                    
                                    # Flush after echo
                                    if hasattr(self.ser_obj, 'flush'):
                                        try:
                                            self.ser_obj.flush()
                                        except:
                                            pass
                                    
                                    # Process and send output
                                    output = self.process_command(cmd_line)
                                    if output:
                                        # Ensure output ends with proper line ending
                                        if not output.endswith(('\n', '\r\n', '\r')):
                                            output += "\r\n"
                                        self._send_output(output)
                                    
                                    # Flush after output
                                    if hasattr(self.ser_obj, 'flush'):
                                        try:
                                            self.ser_obj.flush()
                                        except:
                                            pass
                                
                                # Send prompt with proper line ending
                                self._send_output(self._get_prompt())
                                
                                # Final flush
                                if hasattr(self.ser_obj, 'flush'):
                                    try:
                                        self.ser_obj.flush()
                                    except:
                                        pass
                            else:
                                break
                    
                    # Allow CTRL-C to be processed more responsively
                    # Use smaller sleep intervals for better signal handling
                    time.sleep(0.1)
                
                except KeyboardInterrupt:
                    raise  # Re-raise to outer exception handler
                except Exception as e:
                    if self.args.debug:
                        print(f"[DEBUG] Error in main loop: {e}")
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")
            self.keep_running = False
        except Exception as e:
            print(f"[ERROR] Fatal error: {e}")
        finally:
            # Cleanup
            if self.ser_obj:
                try:
                    if use_named_pipe:
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
                        print(f"[DEBUG] Cleanup error: {e}")
            
            print(f"[INFO] Device simulator stopped")

# ==============================================================================
# CONFIGURATION LOADER AND VALIDATOR
# ==============================================================================

VALID_OPTIONS = {
    'comport', 'namedpipe', 'baud', 'line', 'device-name', 'device-model',
    'device-version', 'hostname', 'enable-password', 'cmdfile', 'notui',
    'batch', 'debug', 'h', 'help', 'version', 'login-banner', 'login-message',
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
    
    # Format: DataBits + Parity + StopBits + FlowControl
    # Example: 8N1N (8 data bits, No parity, 1 stop bit, No flow control)
    
    try:
        data_bits = int(line_param[0])
        parity = line_param[1].upper()
        stop_bits_str = line_param[2:].replace('N', '')  # Get stop bits
        
        if data_bits not in [5, 6, 7, 8]:
            return False
        if parity not in ['N', 'O', 'E']:  # None, Odd, Even
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
        # Windows: COM1, COM2, etc.
        return port.upper().startswith('COM') and port[3:].isdigit()
    else:
        # Linux: /dev/ttyUSB0, /dev/ttyS0, etc.
        return port.startswith('/dev/tty')

def validate_namedpipe(pipe_name):
    """Validate named pipe name"""
    if not pipe_name or not isinstance(pipe_name, str):
        return False
    if sys.platform != "win32":
        return False
    # Simple validation - alphanumeric and underscore
    return all(c.isalnum() or c == '_' for c in pipe_name)

def load_config():
    """Load configuration from device.conf and CLI args"""
    config = DEFAULT_CONFIG.copy()
    
    # Detect invalid options early
    invalid_options = []
    for arg in sys.argv[1:]:
        if arg.startswith('--'):
            option = arg[2:].split('=')[0]
            if option not in VALID_OPTIONS:
                invalid_options.append(f"--{option}")
        elif arg.startswith('-') and len(arg) == 2:
            option = arg[1]
            if option not in {'h', 'b'}:  # -h for help, -b for batch
                invalid_options.append(arg)
    
    if invalid_options:
        print(f"\n[ERROR] Unknown options detected: {', '.join(invalid_options)}")
        print("[ERROR] Use --help for valid options")
        sys.exit(1)
    
    # Load from device.conf if exists
    if os.path.exists('device.conf'):
        try:
            parser = configparser.ConfigParser()
            parser.read('device.conf')
            
            if 'DEFAULT' in parser:
                for key, value in parser['DEFAULT'].items():
                    if key in config:
                        if isinstance(config[key], bool):
                            config[key] = value.lower() in ['true', '1', 'yes', 'on']
                        elif isinstance(config[key], int):
                            config[key] = int(value)
                        else:
                            config[key] = value
        except Exception as e:
            print(f"[WARNING] Failed to load device.conf: {e}")
    
    # Parse CLI arguments
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--comport")
    parser.add_argument("--namedpipe")
    parser.add_argument("--baud", type=int)
    parser.add_argument("--line")
    parser.add_argument("--device-name")
    parser.add_argument("--device-model")
    parser.add_argument("--device-version")
    parser.add_argument("--hostname")
    parser.add_argument("--enable-password")
    parser.add_argument("--cmdfile")
    parser.add_argument("--notui", action="store_true", default=False)
    parser.add_argument("--batch", action="store_true", default=False)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("-h", action="store_true", default=False)
    parser.add_argument("--help", action="store_true", default=False)
    parser.add_argument("--version", action="store_true", default=False)
    
    cli_args, unknown = parser.parse_known_args()
    
    # Check for unknown args (shouldn't happen after early validation)
    if unknown:
        print(f"\n[ERROR] Unknown arguments: {' '.join(unknown)}")
        sys.exit(1)
    
    # Override config with CLI args
    for key, value in vars(cli_args).items():
        if value is not None and value is not False:
            config[key] = value
        elif isinstance(value, bool) and value is True:
            config[key] = True
    
    # ===== VALIDATION =====
    
    # Validate baud rate if provided
    if config['baud'] is not None:
        if config['baud'] not in VALID_BAUD_RATES:
            print(f"\n[ERROR] Invalid baud rate: {config['baud']}")
            print(f"[ERROR] Valid rates: {', '.join(map(str, sorted(VALID_BAUD_RATES)))}")
            sys.exit(1)
    
    # Validate line format
    if config['line']:
        if not validate_line_format(config['line']):
            print(f"\n[ERROR] Invalid line format: {config['line']}")
            print("[ERROR] Valid formats: 5N1N, 6N1N, 7N1N, 8N1N, 8N2N, 8E1N, 8O1N, etc.")
            print("[ERROR] Format: [DataBits][Parity][StopBits][FlowControl]")
            print("[ERROR] DataBits: 5-8, Parity: N/O/E, StopBits: 1/1.5/2, FlowControl: N")
            sys.exit(1)
    
    # Validate serial port and named pipe
    if config['comport'] and config['namedpipe']:
        print("\n[ERROR] Cannot specify both --comport and --namedpipe")
        sys.exit(1)
    
    if config['comport']:
        if not validate_comport(config['comport']):
            if sys.platform == "win32":
                print(f"\n[ERROR] Invalid COM port: {config['comport']}")
                print("[ERROR] Valid format: COM1, COM2, COM3, etc.")
            else:
                print(f"\n[ERROR] Invalid serial port: {config['comport']}")
                print("[ERROR] Valid format: /dev/ttyUSB0, /dev/ttyS0, etc.")
            sys.exit(1)
    
    if config['namedpipe']:
        if not validate_namedpipe(config['namedpipe']):
            print(f"\n[ERROR] Invalid named pipe name: {config['namedpipe']}")
            print("[ERROR] Use alphanumeric characters and underscores only")
            sys.exit(1)
        if sys.platform != "win32":
            print("\n[ERROR] Named pipes are only supported on Windows")
            sys.exit(1)
    
    # Validate cmdfile exists if provided
    if config['cmdfile']:
        if not os.path.exists(config['cmdfile']):
            print(f"\n[ERROR] Command file not found: {config['cmdfile']}")
            sys.exit(1)
    
    return argparse.Namespace(**config)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    args = load_config()
    
    if args.version:
        print(f"{__APP_NAME__} v{__CODE_VERSION__}")
        sys.exit(0)
    
    if args.help or args.h:
        print(f"\n{__APP_NAME__} v{__CODE_VERSION__} by {__CODE_AUTHOR__}")
        print("\nUsage: python3 serial_device_0.0.1.py [OPTIONS]")
        print("\nREQUIRED OPTIONS:")
        print("  --comport PORT              Serial port (e.g., COM1, COM2 on Windows; /dev/ttyUSB0 on Linux)")
        print("  --namedpipe NAME            Windows named pipe name (Windows only)")
        print("                              Use ONE of: --comport OR --namedpipe")
        print("\nOPTIONAL OPTIONS:")
        print("  --baud SPEED                Baud rate (default: 9600)")
        print("                              Valid: 110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200")
        print("  --line PARAMS               Serial line format (default: 8N1N)")
        print("                              Format: [DataBits][Parity][StopBits][FlowControl]")
        print("                              DataBits: 5-8, Parity: N/O/E, StopBits: 1/1.5/2, FlowControl: N")
        print("                              Examples: 8N1N, 8N2N, 8E1N, 8O1N")
        print("  --hostname NAME             Device hostname (default: device-sim)")
        print("  --device-name NAME          Device name (default: DEVICE-SIM)")
        print("  --device-model MODEL        Device model (default: IOS XE)")
        print("  --device-version VERSION    Device version (default: 16.12.01)")
        print("  --enable-password PASSWORD  Enable password (default: cisco123)")
        print("  --login-message MESSAGE     Login banner message")
        print("  --cmdfile FILE              Load custom commands from file")
        print("  --debug                     Enable debug output")
        print("  --version                   Show version")
        print("  --help, -h                  Show this help message")
        print("\nEXAMPLES:")
        print("  # Serial port on Windows:")
        print("  python3 serial_device_0.0.1.py --comport COM1 --hostname router1 --baud 9600")
        print("\n  # Serial port on Linux:")
        print("  python3 serial_device_0.0.1.py --comport /dev/ttyUSB0 --hostname router1")
        print("\n  # Named pipe on Windows:")
        print("  python3 serial_device_0.0.1.py --namedpipe mydevice --hostname router1")
        print("\n  # With custom settings:")
        print("  python3 serial_device_0.0.1.py --comport COM1 --baud 115200 --line 8N2N --hostname device1")
        sys.exit(0)
    
    # FINAL VALIDATION
    if not args.comport and not args.namedpipe:
        print("\n" + "="*70)
        print("[ERROR] No connection method specified!")
        print("="*70)
        print("\nYou must specify ONE of the following:")
        print("  --comport <PORT>    - For serial port connection")
        print("  --namedpipe <NAME>  - For Windows named pipe connection")
        print("\nExamples:")
        print("  python3 serial_device_0.0.1.py --comport COM1")
        print("  python3 serial_device_0.0.1.py --comport /dev/ttyUSB0")
        print("  python3 serial_device_0.0.1.py --namedpipe mydevice")
        print("\nFor complete help, use: --help")
        print("="*70 + "\n")
        sys.exit(1)
    
    # Create and run device
    print(f"\n[INFO] {__APP_NAME__} v{__CODE_VERSION__}")
    print("[INFO] Starting device simulator...")
    print(f"[INFO] Hostname: {args.hostname}")
    print()
    
    device = CiscoLikeDevice(args)
    device.run_serial()
