#!/usr/bin/env python3
"""
UART test for the iCE40 async adder.

Protocol: send byte A, then byte B over UART; receive one byte (A+B) mod 256.
Wiring: FPGA RX = Pin 6 (FTDI TX), FPGA TX = Pin 9 (FTDI RX). 115200 8N1.

Usage:
  python3 uart_adder_test.py                     # automated tests (auto-detect port)
  python3 uart_adder_test.py -i                  # interactive mode
  python3 uart_adder_test.py -r                  # randomized stress test
  python3 uart_adder_test.py -v                  # verbose output
  python3 uart_adder_test.py -l                  # list serial ports
  python3 uart_adder_test.py /dev/ttyUSB1        # specify port

Requires: pyserial (pip install pyserial)
"""

import sys
import time
import random
import argparse

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Install pyserial: pip install pyserial")
    sys.exit(1)


DEFAULT_BAUD = 115200
TIMEOUT = 3.0
SETTLE_AFTER_OPEN_S = 0.3
PAUSE_AFTER_SEND = 0.12
INTER_BYTE_MS = 3.0 / 1000.0
READ_RETRIES = 3
READ_RETRY_DELAY = 0.05


def find_icebreaker():
    """Find iCEBreaker or FTDI serial port."""
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


def send_and_receive(ser, a, b, verbose=False, debug=False):
    """Send A and B, return (received_byte, elapsed_ms) or (None, elapsed_ms)."""
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    t0 = time.perf_counter()

    if debug:
        n = ser.in_waiting or 0
        if n:
            drain = ser.read(n)
            print(f"  [debug] drained {n} byte(s): {drain.hex()}")

    ser.write(bytes([a & 0xFF]))
    ser.flush()
    if debug:
        print(f"  [debug] sent A=0x{a:02X} @ +{(time.perf_counter()-t0)*1000:.1f}ms")
    time.sleep(INTER_BYTE_MS)
    ser.write(bytes([b & 0xFF]))
    ser.flush()
    if debug:
        print(f"  [debug] sent B=0x{b:02X} @ +{(time.perf_counter()-t0)*1000:.1f}ms")
    time.sleep(PAUSE_AFTER_SEND)

    out = None
    for attempt in range(READ_RETRIES):
        out = ser.read(1)
        if out:
            elapsed = (time.perf_counter() - t0) * 1000
            if debug:
                print(f"  [debug] recv 0x{out[0]:02X} @ +{elapsed:.1f}ms (attempt {attempt+1})")
            return out[0], elapsed
        time.sleep(READ_RETRY_DELAY)

    elapsed = (time.perf_counter() - t0) * 1000
    return None, elapsed


def test_one(ser, a, b, verbose=False, debug=False):
    """Run one test, print result, return True if passed."""
    expected = (a + b) & 0xFF
    got, elapsed = send_and_receive(ser, a, b, verbose=verbose, debug=debug)

    if got is None:
        print(f"  TIMEOUT  {a:>3} + {b:>3}  (no response after {elapsed:.0f}ms)")
        return False

    ok = got == expected
    if verbose:
        status = "OK" if ok else "FAIL"
        print(f"  {status:>4}  {a:>3} + {b:>3} = {got:>3}  "
              f"(expected {expected:>3}, 0x{a:02X}+0x{b:02X}=0x{got:02X}, {elapsed:.0f}ms)")
    elif ok:
        print(f"  OK    {a:>3} + {b:>3} = {got}")
    else:
        print(f"  FAIL  {a:>3} + {b:>3} = {got}  (expected {expected})")
    return ok


def run_automated_tests(ser, verbose=False, debug=False):
    """Run comprehensive test suite."""
    print("=== iCE40 Async Adder — Automated Tests ===\n")

    all_tests = []
    total_passed = 0
    total_run = 0

    def run_section(name, tests):
        nonlocal total_passed, total_run
        print(f"--- {name} ---")
        passed = 0
        for a, b in tests:
            if test_one(ser, a, b, verbose=verbose, debug=debug):
                passed += 1
            time.sleep(0.02)
        total_passed += passed
        total_run += len(tests)
        print(f"  [{passed}/{len(tests)}]\n")
        return passed == len(tests)

    # Basic operations
    run_section("Basic", [
        (0, 0),
        (1, 0),
        (0, 1),
        (10, 20),
        (100, 57),
    ])

    # Boundary values
    run_section("Boundaries", [
        (255, 0),
        (0, 255),
        (128, 127),
        (127, 128),
        (1, 254),
    ])

    # Overflow / wrapping
    run_section("Overflow", [
        (255, 1),
        (1, 255),
        (255, 255),
        (128, 128),
        (200, 100),
        (200, 200),
    ])

    # Powers of two
    run_section("Powers of two", [
        (1, 1),
        (2, 2),
        (4, 4),
        (8, 8),
        (16, 16),
        (32, 32),
        (64, 64),
    ])

    # Commutativity (A+B should equal B+A)
    comm_tests = [(37, 198), (99, 156), (1, 254), (0, 128)]
    print("--- Commutativity ---")
    comm_passed = 0
    for a, b in comm_tests:
        r1, _ = send_and_receive(ser, a, b)
        time.sleep(0.02)
        r2, _ = send_and_receive(ser, b, a)
        time.sleep(0.02)
        expected = (a + b) & 0xFF
        ok = r1 == expected and r2 == expected and r1 == r2
        if ok:
            print(f"  OK    {a} + {b} = {b} + {a} = {r1}")
            comm_passed += 1
        else:
            print(f"  FAIL  {a}+{b}={r1}, {b}+{a}={r2} (expected {expected})")
    total_passed += comm_passed
    total_run += len(comm_tests)
    print(f"  [{comm_passed}/{len(comm_tests)}]\n")

    # Consecutive additions (tests state machine reset between operations)
    run_section("Consecutive (rapid)", [
        (1, 2),
        (3, 4),
        (5, 6),
        (7, 8),
        (9, 10),
        (11, 12),
        (13, 14),
        (15, 16),
    ])

    # Summary
    print(f"=== Results: {total_passed}/{total_run} passed ===")
    if total_passed == total_run:
        print("ALL TESTS PASSED.")
    else:
        print(f"FAILED: {total_run - total_passed} test(s).")
    return total_passed == total_run


def run_random_stress(ser, count=50, verbose=False, debug=False):
    """Run randomized stress test with `count` random pairs."""
    print(f"=== Randomized Stress Test ({count} pairs) ===\n")
    passed = 0
    failed_cases = []

    for i in range(count):
        a = random.randint(0, 255)
        b = random.randint(0, 255)
        expected = (a + b) & 0xFF
        got, elapsed = send_and_receive(ser, a, b, debug=debug)
        time.sleep(0.02)

        if got == expected:
            passed += 1
            if verbose:
                print(f"  [{i+1:>3}/{count}] OK    {a:>3} + {b:>3} = {got:>3}")
        else:
            got_str = str(got) if got is not None else "TIMEOUT"
            print(f"  [{i+1:>3}/{count}] FAIL  {a:>3} + {b:>3} = {got_str}  (expected {expected})")
            failed_cases.append((a, b, got, expected))

    print(f"\n=== Results: {passed}/{count} passed ===")
    if failed_cases:
        print("Failed cases:")
        for a, b, got, exp in failed_cases:
            got_str = str(got) if got is not None else "TIMEOUT"
            print(f"  {a} + {b} = {got_str} (expected {exp})")
    else:
        print("ALL TESTS PASSED.")
    return passed == count


def run_interactive(ser, verbose=False):
    """Interactive mode: user enters A B, FPGA returns A+B."""
    print("=== Interactive Adder ===")
    print("Enter two numbers (0-255) separated by space.")
    print("Commands: 'q' quit, 'r' random pair, 'sweep' test all 256 values\n")

    while True:
        try:
            line = input("A B > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line or line.lower() == "q":
            break

        if line.lower() == "r":
            a, b = random.randint(0, 255), random.randint(0, 255)
            print(f"  (random: {a} {b})")
        elif line.lower() == "sweep":
            print("  Sweeping A=0..255 with B=1...")
            passed = 0
            for a in range(256):
                expected = (a + 1) & 0xFF
                got, _ = send_and_receive(ser, a, 1)
                time.sleep(0.01)
                if got == expected:
                    passed += 1
                else:
                    got_str = str(got) if got is not None else "TIMEOUT"
                    print(f"  FAIL  {a} + 1 = {got_str} (expected {expected})")
            print(f"  Sweep: {passed}/256 passed")
            continue
        else:
            parts = line.split()
            if len(parts) != 2:
                print("  Enter two numbers (e.g. 10 20), 'r' for random, 'sweep', or 'q' to quit")
                continue
            try:
                a, b = int(parts[0]), int(parts[1])
            except ValueError:
                print("  Invalid numbers")
                continue
            if not (0 <= a <= 255 and 0 <= b <= 255):
                print("  Values must be 0-255")
                continue

        expected = (a + b) & 0xFF
        got, elapsed = send_and_receive(ser, a, b, verbose=verbose)
        if got is None:
            print(f"  No response from FPGA ({elapsed:.0f}ms)")
        else:
            status = "OK" if got == expected else f"FAIL (expected {expected})"
            print(f"  {a} + {b} = {got}  {status}  [{elapsed:.0f}ms]")


def main():
    parser = argparse.ArgumentParser(
        description="UART test for iCE40 async adder (send A, B; receive (A+B) mod 256)."
    )
    parser.add_argument(
        "port", nargs="?", default=None,
        help="Serial port (auto-detect iCEBreaker/FTDI if omitted)",
    )
    parser.add_argument(
        "baud", nargs="?", type=int, default=DEFAULT_BAUD,
        help=f"Baud rate (default: {DEFAULT_BAUD})",
    )
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Interactive mode: type A B to get A+B")
    parser.add_argument("-r", "--random", nargs="?", type=int, const=50, default=None,
                        metavar="N", help="Randomized stress test with N pairs (default 50)")
    parser.add_argument("-l", "--list-ports", action="store_true",
                        help="List available serial ports and exit")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose: hex values, timing for each test")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Debug: raw byte dumps and timestamps")
    args = parser.parse_args()

    if args.list_ports:
        list_ports()
        sys.exit(0)

    port = args.port or find_icebreaker()
    if not port:
        print("Error: no serial port found. Use -l to list ports.")
        list_ports()
        sys.exit(1)

    baud = args.baud
    if not args.port:
        print(f"Auto-detected port: {port}")
    print(f"Opening {port} at {baud} baud...")
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=TIMEOUT)
        time.sleep(SETTLE_AFTER_OPEN_S)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except serial.SerialException as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        if args.interactive:
            run_interactive(ser, verbose=args.verbose)
        elif args.random is not None:
            ok = run_random_stress(ser, count=args.random, verbose=args.verbose, debug=args.debug)
            sys.exit(0 if ok else 1)
        else:
            ok = run_automated_tests(ser, verbose=args.verbose, debug=args.debug)
            sys.exit(0 if ok else 1)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
