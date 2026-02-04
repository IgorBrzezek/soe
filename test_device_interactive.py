#!/usr/bin/env python3
"""
Simple test for serial_device_0.0.1.py using socat or named pipes
This helps test the terminal functionality
"""

import sys
import subprocess
import time
import os

def test_with_namedpipe():
    """Test using Windows named pipe"""
    if sys.platform != "win32":
        print("[INFO] Named pipe test only on Windows")
        return False
    
    try:
        import win32pipe
        import win32file
    except ImportError:
        print("[ERROR] pywin32 not installed")
        return False
    
    print("[INFO] Starting device simulator with named pipe...")
    proc = subprocess.Popen(
        [sys.executable, "serial_device_0.0.1.py", "--namedpipe", "test_device"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(1)
    
    try:
        pipe_path = "\\.\pipe\test_device"
        print(f"[INFO] Connecting to pipe: {pipe_path}")
        
        pipe = win32file.CreateFile(
            pipe_path,
            0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
            0,
            None,
            3,  # OPEN_EXISTING
            0,
            None
        )
        
        # Send test commands
        test_commands = [
            b"?\r\n",
            b"help\r\n",
            b"show version\r\n",
            b"exit\r\n"
        ]
        
        for cmd in test_commands:
            print(f"[TEST] Sending: {cmd.decode().strip()}")
            win32file.WriteFile(pipe, cmd)
            time.sleep(0.5)
            
            # Try to read response
            try:
                err, data = win32file.ReadFile(pipe, 1024)
                if data:
                    print(f"[RESPONSE] {data.decode(errors='replace')}")
            except:
                pass
        
        win32file.CloseHandle(pipe)
        print("[INFO] Test completed")
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        proc.terminate()
        return False
    finally:
        proc.terminate()
        proc.wait(timeout=2)

def show_help():
    print("""
Manual Testing Guide for serial_device_0.0.1.py
================================================

1. Test with real serial port (if available):
   python serial_device_0.0.1.py --comport COM1
   
   Then use terminal emulator (Putty, Serial Monitor, etc.) to connect

2. Test help command:
   Type: ?
   or:   help
   or:   h
   
3. Test CTRL-C shutdown:
   While running, press CTRL-C
   Expected: Clean shutdown message

4. Test output formatting:
   Type: show version
   Type: show clock
   Check that output has proper line endings (no overlapping text)

5. Test with debug output:
   python serial_device_0.0.1.py --comport COM1 --debug
    """)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "pipe":
        test_with_namedpipe()
    else:
        show_help()
