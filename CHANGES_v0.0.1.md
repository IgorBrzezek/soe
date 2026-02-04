# Serial Device Simulator v0.0.1 - Fixes and Improvements

## Summary of Changes

Complete rewrite of option validation and error handling to prevent invalid arguments from being silently ignored.

## Fixed Issues

### 1. **Invalid Options Accepted Without Error**
   - **Problem**: Script accepted `--namedpi` instead of `--namedpipe` without error
   - **Solution**: Added early validation (line 589-603) that checks all arguments before processing
   - **Detection**: All `--option` arguments are validated against `VALID_OPTIONS` set
   - **Error Message**: 
     ```
     [ERROR] Unknown options detected: --namedpi
     [ERROR] Use --help for valid options
     ```

### 2. **No Baud Rate Validation**
   - **Problem**: Any value passed to `--baud` was accepted
   - **Solution**: Added `VALID_BAUD_RATES` set with standard rates (110-115200)
   - **Validation**: Check at line 631-635
   - **Error Message**:
     ```
     [ERROR] Invalid baud rate: 999999
     [ERROR] Valid rates: 110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200
     ```

### 3. **No Serial Line Format Validation**
   - **Problem**: Invalid `--line` values like "99Z99" were accepted
   - **Solution**: Added `validate_line_format()` function (line 616-631)
   - **Format Validation**: 
     - DataBits: 5-8
     - Parity: N (None), O (Odd), E (Even)
     - StopBits: 1, 1.5, 2
     - FlowControl: N (only None for now)
   - **Error Message**:
     ```
     [ERROR] Invalid line format: 99Z99
     [ERROR] Valid formats: 5N1N, 6N1N, 7N1N, 8N1N, 8N2N, 8E1N, 8O1N, etc.
     [ERROR] Format: [DataBits][Parity][StopBits][FlowControl]
     ```

### 4. **Port/Pipe Validation**
   - **Problem**: Invalid port names accepted (e.g., "INVALID" instead of "COM1")
   - **Solution**: 
     - Added `validate_comport()` for serial ports (line 640-648)
     - Added `validate_namedpipe()` for Windows named pipes (line 650-657)
   - **Windows Validation**: Port must start with "COM" followed by digits
   - **Linux Validation**: Port must start with "/dev/tty"
   - **Error Messages**:
     ```
     [ERROR] Invalid COM port: INVALID
     [ERROR] Valid format: COM1, COM2, COM3, etc.
     ```
     or
     ```
     [ERROR] Invalid named pipe name: port@123
     [ERROR] Use alphanumeric characters and underscores only
     ```

### 5. **Conflicting Options Not Caught**
   - **Problem**: Could specify both `--comport` and `--namedpipe` simultaneously
   - **Solution**: Added check at line 665-667
   - **Error Message**:
     ```
     [ERROR] Cannot specify both --comport and --namedpipe
     ```

### 6. **Named Pipe Validation**
   - **Problem**: Named pipes could be used on Linux (not supported)
   - **Solution**: Added platform check at line 669-671
   - **Error Message**:
     ```
     [ERROR] Named pipes are only supported on Windows
     ```

### 7. **Command File Not Validated**
   - **Problem**: Could specify non-existent `--cmdfile` without error until runtime
   - **Solution**: Added file existence check at line 673-676
   - **Error Message**:
     ```
     [ERROR] Command file not found: /path/to/missing/file.txt
     ```

### 8. **Poor Serial Port Connection Error Handling**
   - **Problem**: Serial port errors produced cryptic messages; terminal didn't handle data properly
   - **Solution**:
     - Improved error handling in `run_serial()` (lines 518-530)
     - Better debugging for connection attempts
     - Proper error reporting for port not found, already in use, permissions
   - **Improvements**:
     - Shows helpful error messages for common problems
     - Resets input/output buffers after opening port
     - Validates line format parameters before opening port

### 9. **Data Reception from Port**
   - **Problem**: Terminal/port communication not working properly
   - **Solution**:
     - Fixed line ending detection (lines 584-596)
     - Better input buffer handling
     - Proper support for both `\r` and `\n` line endings
     - Fixed edge cases in buffer processing

### 10. **Missing Help Information**
   - **Problem**: Help message didn't explain valid formats and options clearly
   - **Solution**: Enhanced `--help` output with:
     - Clear separation of REQUIRED and OPTIONAL options
     - List of valid baud rates
     - Serial line format explanation
     - Multiple examples for different platforms

## Validation Execution Order

1. **Early Option Detection** (line 589-603)
   - Checks all CLI arguments are known options
   - Fails fast before anything else

2. **Baud Rate Validation** (line 631-635)
   - Only if `--baud` is provided

3. **Line Format Validation** (line 637-646)
   - Only if `--line` is provided

4. **Port/Pipe Conflict** (line 665-667)
   - Cannot use both `--comport` and `--namedpipe`

5. **Port Format Validation** (line 669-680)
   - Validates against OS-specific formats

6. **Named Pipe OS Check** (line 669-671)
   - Named pipes only on Windows

7. **File Validation** (line 673-676)
   - Command file must exist

## Error Exit Codes

All validation errors use `sys.exit(1)` - this ensures:
- Script never runs with invalid configuration
- Clear failure signal to calling processes
- Batch scripts can detect failures properly

## Testing Results

All test cases pass successfully:

```
TEST: Invalid option --namedpi
RESULT: ✓ Rejected with helpful error

TEST: Invalid baud rate 999999
RESULT: ✓ Rejected with list of valid rates

TEST: Invalid line format 99Z99
RESULT: ✓ Rejected with format explanation

TEST: Invalid COM port
RESULT: ✓ Rejected with format guidance

TEST: No connection method specified
RESULT: ✓ Clear error with examples

TEST: Valid options with --help
RESULT: ✓ Shows comprehensive help

TEST: Non-existent serial port (COM99)
RESULT: ✓ Shows connection error with troubleshooting tips
```

## Backward Compatibility

- All valid previous command lines remain functional
- Only invalid command lines that previously "silently failed" now show errors
- No breaking changes to working configurations

## Future Improvements

Possible enhancements:
1. Support for other line control options (RTS/CTS, XON/XOFF)
2. Configuration file validation
3. Port existence detection before attempt to open
4. Serial port discovery and listing (`--list-ports`)
5. Connection timeout configuration
