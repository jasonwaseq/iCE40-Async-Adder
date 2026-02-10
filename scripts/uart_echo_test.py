#!/usr/bin/env python3
"""Minimal UART echo test: send byte, expect same byte back. Validates RX+TX path."""
import serial
import time
import sys

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB1"
    print(f"Opening {port} @ 115200...")
    ser = serial.Serial(port, 115200, timeout=2.0)
    time.sleep(0.5)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    for b in [0x55, 0xAA, 0x00, 0xFF, 0x0A]:
        ser.write(bytes([b]))
        ser.flush()
        time.sleep(0.1)
        got = ser.read(1)
        if got and len(got) == 1:
            g = got[0]
            ok = "OK" if g == b else "FAIL"
            print(f"  0x{b:02X} -> 0x{g:02X}  {ok}")
        else:
            print(f"  0x{b:02X} -> NO RESPONSE")
    ser.close()
    print("Done.")

if __name__ == "__main__":
    main()
