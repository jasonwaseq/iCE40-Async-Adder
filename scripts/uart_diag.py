#!/usr/bin/env python3
"""Minimal UART diagnostic: send 2 bytes, read everything back with long timeout."""
import sys, time, serial, serial.tools.list_ports

def find_port():
    for p in serial.tools.list_ports.comports():
        dev = (p.device or "").lower()
        if "ttyusb" in dev or "ttyacm" in dev:
            return p.device
    return None

port = sys.argv[1] if len(sys.argv) > 1 else find_port()
if not port:
    print("No port found"); sys.exit(1)

print(f"Opening {port} at 115200...")
ser = serial.Serial(port=port, baudrate=115200, timeout=5.0)
time.sleep(0.5)  # settle

# Drain anything pending
n = ser.in_waiting
if n:
    print(f"Drained {n} bytes: {ser.read(n).hex()}")

# Test 1: Send single byte, see if echo comes back
# (If bypass Top is loaded, this should NOT echo -- it waits for 2nd byte)
print("\n--- Test 1: Send 1 byte (0x41='A'), wait 2s ---")
ser.reset_input_buffer()
ser.write(b'\x41')
ser.flush()
time.sleep(2.0)
n = ser.in_waiting
print(f"  in_waiting={n}")
if n:
    data = ser.read(n)
    print(f"  received: {data.hex()} = {list(data)}")
else:
    print("  no response (expected for 2-byte design)")

# Test 2: Send 2 bytes with gap, long wait
print("\n--- Test 2: Send 0x01 then 0x02 (expect 0x03), wait 5s ---")
ser.reset_input_buffer()
ser.write(bytes([0x01]))
ser.flush()
time.sleep(0.003)
ser.write(bytes([0x02]))
ser.flush()
print("  sent both bytes, waiting...")
time.sleep(5.0)
n = ser.in_waiting
print(f"  in_waiting={n}")
if n:
    data = ser.read(n)
    print(f"  received: {data.hex()} = {list(data)}")
else:
    print("  NO RESPONSE")

# Test 3: Send 2 bytes back-to-back (no gap)
print("\n--- Test 3: Send 0x0A 0x14 back-to-back (expect 0x1E=30), wait 5s ---")
ser.reset_input_buffer()
ser.write(bytes([0x0A, 0x14]))
ser.flush()
print("  sent both bytes at once, waiting...")
time.sleep(5.0)
n = ser.in_waiting
print(f"  in_waiting={n}")
if n:
    data = ser.read(n)
    print(f"  received: {data.hex()} = {list(data)}")
else:
    print("  NO RESPONSE")

# Test 4: Send many bytes, see if anything comes back
print("\n--- Test 4: Send 10 bytes, wait 5s ---")
ser.reset_input_buffer()
ser.write(bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A]))
ser.flush()
time.sleep(5.0)
n = ser.in_waiting
print(f"  in_waiting={n}")
if n:
    data = ser.read(n)
    print(f"  received: {data.hex()} = {list(data)}")
else:
    print("  NO RESPONSE")

ser.close()
print("\nDone.")
