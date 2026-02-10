#!/usr/bin/env python3
"""
UART test for the iCE40 async adder (Top design).

UART send/receive pattern follows fpga_sorting (misc/test_fpga_uart.py):
  - Settle after open (0.5 s), flush after writes, robust read timeout/retries.

Wiring (iCE40):
  FPGA RX = Pin 6  (connects to PC/FTDI TX - board receives from PC)
  FPGA TX = Pin 9  (connects to PC/FTDI RX - board sends to PC)

Protocol: send byte A, then byte B; receive one byte (A+B) mod 256.

Requires: pyserial (pip install pyserial)

Usage:
  python uart_adder_test.py [port] [baud]           # run automated tests
  python uart_adder_test.py --interactive [port]    # type pairs A B, get A+B
  python uart_adder_test.py --list-ports            # list available COM ports
  python uart_adder_test.py -v [port]               # verbose (timing + hex bytes)

Examples:
  # Board attached to WSL (run from WSL):
  python3 uart_adder_test.py /dev/ttyUSB0
  python3 uart_adder_test.py                          # auto-detect in WSL/Linux
  # Board attached to Windows:
  python uart_adder_test.py COM3
  python uart_adder_test.py COM3 115200 --interactive
"""

import sys
import time
import argparse

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Install pyserial: pip install pyserial")
    sys.exit(1)


DEFAULT_BAUD = 115200
# Serial read timeout (seconds). fpga_sorting uses 5.0 for robustness.
TIMEOUT = 3.0
# Let FPGA settle after port open (fpga_sorting: 0.5s; FPGA-RISC-V debug_test: 0.1s)
SETTLE_AFTER_OPEN_S = 0.2
# Pause after sending both bytes before reading (FPGA: RX byte0 -> RX byte1 -> ADD -> TX)
PAUSE_AFTER_SEND = 0.12
# Small delay between first and second byte so FPGA has time to leave s_idle
INTER_BYTE_MS = 3.0 / 1000.0
# Retries when no response (FPGA can be slow to start or under load)
READ_RETRIES = 3
READ_RETRY_DELAY = 0.05


def find_icebreaker():
    """Find iCEBreaker or FTDI serial port (same logic as test_fpga.py)."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = (port.description or "").upper()
        if "ICEBREAKER" in desc or "FTDI" in desc:
            return port.device
    for port in ports:
        dev = (port.device or "").lower()
        if "ttyusb" in dev or "ttyacm" in dev or dev.startswith("com"):
            return port.device
    return None


def list_ports():
    """Print available serial ports."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found.")
        return
    print("Available ports:")
    for p in ports:
        print(f"  {p.device}  {p.description}")


def test_one(ser, a: int, b: int, verbose: bool = False, debug: bool = False) -> bool:
    expected = (a + b) & 0xFF
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    def _in_waiting():
        return getattr(ser, "in_waiting", 0) or 0

    if debug:
        n = _in_waiting()
        drain = ser.read(n) if n else b''
        print(f"  [debug] in_waiting before drain: {n}")
        if drain:
            print(f"  [debug] drained RX: {len(drain)} byte(s) = {drain.hex()}")
        t0 = time.perf_counter()

    if verbose or debug:
        print(f"  [verbose] send A=0x{a:02X}({a}) B=0x{b:02X}({b})")
    # Send A then B with a short gap; flush after each so bytes are actually transmitted (fpga_sorting: ser.flush())
    ser.write(bytes([a & 0xFF]))
    ser.flush()
    if debug:
        print(f"  [debug] sent first byte 0x{a:02X}, flush done @ +{(time.perf_counter()-t0)*1000:.1f} ms")
    time.sleep(INTER_BYTE_MS)
    ser.write(bytes([b & 0xFF]))
    ser.flush()
    if debug:
        print(f"  [debug] sent second byte 0x{b:02X}, flush done @ +{(time.perf_counter()-t0)*1000:.1f} ms")
    if verbose or debug:
        print(f"  [verbose] waited {INTER_BYTE_MS*1000:.1f} ms inter-byte, then {PAUSE_AFTER_SEND*1000:.0f} ms before read")
    time.sleep(PAUSE_AFTER_SEND)
    out = None
    for attempt in range(READ_RETRIES):
        out = ser.read(1)
        if debug and attempt > 0:
            print(f"  [debug] read attempt {attempt+1}: got {len(out) if out else 0} byte(s)")
        if out:
            if verbose and attempt:
                print(f"  [verbose] got response on retry {attempt+1}")
            if debug:
                print(f"  [debug] received 0x{out[0]:02X} @ +{(time.perf_counter()-t0)*1000:.1f} ms")
            break
        time.sleep(READ_RETRY_DELAY)
    if not out:
        if debug:
            print(f"  [debug] no data after {READ_RETRIES} read attempts (timeout {TIMEOUT}s each)  in_waiting={_in_waiting()}")
        print(f"  No response for {a} + {b} (timeout)")
        return False
    got = out[0]
    if debug:
        print(f"  [debug] in_waiting after read: {_in_waiting()}")
    if verbose:
        print(f"  [verbose] received 1 byte: 0x{got:02X} ({got}), expected 0x{expected:02X} ({expected})")
    ok = got == expected
    if ok:
        print(f"  {a} + {b} = {got}  OK")
    else:
        print(f"  {a} + {b} = {got}  (expected {expected})  FAIL")
    return ok


def run_automated_tests(ser, verbose: bool = False, debug: bool = False):
    print("Testing async adder (send A, send B, receive A+B):\n")
    tests = [
        (0, 0),
        (10, 20),
        (100, 57),
        (128, 127),
        (255, 1),
        (255, 255),
        (1, 254),
    ]
    passed = 0
    for a, b in tests:
        if test_one(ser, a, b, verbose=verbose, debug=debug):
            passed += 1
        time.sleep(0.02)
    print(f"\n{passed}/{len(tests)} tests passed.")
    return passed == len(tests)


def add_once(ser, a: int, b: int, verbose: bool = False):
    """Send two bytes, return received sum or None on failure."""
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    if verbose:
        print(f"  [verbose] send A=0x{a:02X} B=0x{b:02X}")
    ser.write(bytes([a & 0xFF]))
    ser.flush()
    time.sleep(INTER_BYTE_MS)
    ser.write(bytes([b & 0xFF]))
    ser.flush()
    time.sleep(PAUSE_AFTER_SEND)
    for _ in range(READ_RETRIES):
        out = ser.read(1)
        if out:
            if verbose:
                print(f"  [verbose] received 0x{out[0]:02X} (expected 0x{(a+b)&0xFF:02X})")
            return out[0]
        time.sleep(READ_RETRY_DELAY)
    return None


def run_interactive(ser, verbose: bool = False):
    print("Interactive mode. Enter two numbers A B (0-255), get A+B.")
    print("Examples: 10 20   or  255 1   (empty line or Ctrl+C to quit)\n")
    while True:
        try:
            line = input("A B > ").strip()
        except EOFError:
            break
        if not line:
            break
        parts = line.split()
        if len(parts) != 2:
            print("  Enter two numbers, e.g. 10 20")
            continue
        try:
            a, b = int(parts[0]), int(parts[1])
        except ValueError:
            print("  Invalid numbers")
            continue
        if not (0 <= a <= 255 and 0 <= b <= 255):
            print("  Values must be 0-255")
            continue
        result = add_once(ser, a, b, verbose=verbose)
        if result is None:
            print(f"  No response from FPGA (check wiring and baud)")
        else:
            expected = (a + b) & 0xFF
            ok = "OK" if result == expected else f"expected {expected}"
            print(f"  {a} + {b} = {result}  {ok}")


def main():
    parser = argparse.ArgumentParser(
        description="UART test for iCE40 async adder (send A, B; receive A+B)."
    )
    parser.add_argument(
        "port", nargs="?", default=None,
        help="Serial port (auto-detect iCEBreaker/FTDI if not given)",
    )
    parser.add_argument(
        "baud", nargs="?", type=int, default=DEFAULT_BAUD,
        help=f"Baud rate (default: {DEFAULT_BAUD})",
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="Interactive mode: type A B to get A+B",
    )
    parser.add_argument(
        "-l", "--list-ports", action="store_true",
        help="List available serial ports and exit",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print timing and byte values (hex/decimal) for each test",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true",
        help="Debug: drain RX, print timestamps and raw bytes for each send/read",
    )
    args = parser.parse_args()

    if args.list_ports:
        list_ports()
        sys.exit(0)

    port = args.port or find_icebreaker()
    if not port:
        print("Error: No serial port specified and could not auto-detect.")
        print("List ports: python uart_adder_test.py --list-ports")
        print("\nAvailable ports:")
        list_ports()
        sys.exit(1)

    baud = args.baud
    if not args.port:
        print(f"Auto-detected port: {port}")
    print(f"Opening {port} at {baud} baud...")
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=TIMEOUT)
        time.sleep(SETTLE_AFTER_OPEN_S)  # Let FPGA settle (fpga_sorting: 0.5 s)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except serial.SerialException as e:
        print(f"Error: {e}")
        print("List ports: python uart_adder_test.py --list-ports")
        sys.exit(1)

    try:
        if args.interactive:
            run_interactive(ser, verbose=args.verbose)
        else:
            ok = run_automated_tests(ser, verbose=args.verbose, debug=args.debug)
            sys.exit(0 if ok else 1)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
