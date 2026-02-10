#!/usr/bin/env python3
"""
Debug script for iCE40 async adder UART. Use when make test-fpga fails with "No response".

- --listen N: listen only for N seconds, print any bytes (hex + timestamp).
- Default: drain RX, send A then B, read one byte; print in_waiting at each step.

Usage (from WSL when board is attached):
  python3 scripts/uart_adder_debug.py /dev/ttyUSB1
  python3 scripts/uart_adder_debug.py /dev/ttyUSB1 --listen 5
  python3 scripts/uart_adder_debug.py /dev/ttyUSB1 --slow
  python3 scripts/uart_adder_debug.py /dev/ttyUSB1 --a 0 --b 0
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
# Match FPGA-RISC-V: 0.1s settle after open, then reset buffers (debug_test.py)
SETTLE_S = 0.1


def in_waiting(ser):
    return getattr(ser, "in_waiting", 0) or 0


def find_port():
    for p in serial.tools.list_ports.comports():
        if "ICEBREAKER" in (p.description or "").upper() or "FTDI" in (p.description or "").upper():
            return p.device
    for p in serial.tools.list_ports.comports():
        d = (p.device or "").lower()
        if "ttyusb" in d or "ttyacm" in d or d.startswith("com"):
            return p.device
    return None


def run_listen(ser, duration_s):
    """Listen for any bytes and print with timestamp."""
    print(f"[listen] Listening for {duration_s} s. Send bytes from FPGA (e.g. run test in another terminal)...")
    ser.reset_input_buffer()
    ser.timeout = 0.1
    t0 = time.perf_counter()
    all_bytes = bytearray()
    last_print = 0.0
    while (time.perf_counter() - t0) < duration_s:
        n = in_waiting(ser)
        if n:
            chunk = ser.read(n)
            all_bytes.extend(chunk)
            now = time.perf_counter() - t0
            for b in chunk:
                print(f"  +{now*1000:.0f} ms  RX 0x{b:02X} ({b})")
        else:
            time.sleep(0.02)
    elapsed = time.perf_counter() - t0
    print(f"[listen] Done. Total: {len(all_bytes)} byte(s) in {elapsed:.2f} s")
    if all_bytes:
        print(f"  raw hex: {bytes(all_bytes).hex()}")
    else:
        print("  (no data received — FPGA may not be sending, or wrong port)")


def main():
    ap = argparse.ArgumentParser(description="UART adder debug: drain, send A B, read with timestamps.")
    ap.add_argument("port", nargs="?", default=None, help="Serial port (e.g. /dev/ttyUSB1)")
    ap.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    ap.add_argument("--a", type=int, default=10, help="First byte A")
    ap.add_argument("--b", type=int, default=20, help="Second byte B")
    ap.add_argument("--slow", action="store_true", help="50ms between bytes, 2s read timeout")
    ap.add_argument("--listen", type=float, metavar="SEC", default=0, help="Listen only for SEC seconds, print any RX bytes")
    ap.add_argument("--settle", type=float, default=SETTLE_S, help=f"Seconds to wait after open (default {SETTLE_S})")
    args = ap.parse_args()

    port = args.port or find_port()
    if not port:
        print("No port. Use: python3 uart_adder_debug.py /dev/ttyUSB1")
        sys.exit(1)

    try:
        ser = serial.Serial(port, baudrate=args.baud, timeout=2.0)
        time.sleep(args.settle)
    except serial.SerialException as e:
        print(f"Open failed: {e}")
        sys.exit(1)

    try:
        if args.listen > 0:
            run_listen(ser, args.listen)
            return
    finally:
        if args.listen > 0:
            ser.close()
            return

    # Normal send-A-B-then-read path
    a, b = args.a & 0xFF, args.b & 0xFF
    expected = (a + b) & 0xFF
    inter_ms = 50.0 if args.slow else 2.0
    pause_s = 0.25 if args.slow else 0.12
    read_timeout = 2.0 if args.slow else 1.0

    print(f"Port: {port} @ {args.baud} baud (settle={args.settle}s)")
    print(f"Test: A={a} (0x{a:02X}) B={b} (0x{b:02X}) -> expect sum {expected} (0x{expected:02X})")
    print(f"Timing: inter_byte={inter_ms}ms, pause_after_send={pause_s}s, read_timeout={read_timeout}s")
    print()

    try:
        n0 = in_waiting(ser)
        drained = ser.read(n0) if n0 else b""
        print(f"[1] in_waiting before drain: {n0}")
        if drained:
            print(f"    Drained RX: {len(drained)} byte(s) = {drained.hex()}")
        else:
            print("    Drained RX: 0 bytes")
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        t0 = time.perf_counter()

        ser.write(bytes([a]))
        ser.flush()
        print(f"[2] Sent A=0x{a:02X} @ +{(time.perf_counter()-t0)*1000:.0f} ms  in_waiting={in_waiting(ser)}")

        time.sleep(inter_ms / 1000.0)

        ser.write(bytes([b]))
        ser.flush()
        print(f"[3] Sent B=0x{b:02X} @ +{(time.perf_counter()-t0)*1000:.0f} ms  in_waiting={in_waiting(ser)}")

        time.sleep(pause_s)
        print(f"[4] Reading (timeout={read_timeout}s) @ +{(time.perf_counter()-t0)*1000:.0f} ms  in_waiting={in_waiting(ser)} ...")

        ser.timeout = read_timeout
        out = ser.read(1)
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000

        if out:
            got = out[0]
            ok = got == expected
            print(f"[5] Received 1 byte: 0x{got:02X} ({got}) @ +{elapsed_ms:.0f} ms  in_waiting={in_waiting(ser)}")
            print(f"    Expected: 0x{expected:02X} ({expected}) -> {'PASS' if ok else 'FAIL'}")
        else:
            print(f"[5] No byte received (timeout after {elapsed_ms:.0f} ms)  in_waiting={in_waiting(ser)}")

        ser.timeout = 0.05
        extra = b""
        while True:
            chunk = ser.read(128)
            if not chunk:
                break
            extra += chunk
        if extra:
            print(f"[6] Extra bytes in RX: {len(extra)} = {extra.hex()}")
    finally:
        ser.close()

    print("\nIf no byte received: try --listen 5 and run test in another terminal; check port (ttyUSB0 vs ttyUSB1); ensure reset released (BTN_N); rebuild/prog after PCF/RTL changes.")


if __name__ == "__main__":
    main()
