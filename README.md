# iCE40 Asynchronous Adder (Chisel)

8-bit adder on a Lattice iCE40 FPGA with a UART interface. Send two bytes (A, B) over serial; receive one byte back ((A+B) mod 256). Built with **Chisel 3** (Scala FIRRTL compiler) and the **OSS CAD Suite** (Yosys, nextpnr-ice40, icepack, iceprog). Target board: **iCEBreaker** (iCE40UP5K-SG48, 12 MHz).

## How it works

The design has three layers:

1. **UART TX/RX** ([UART.scala](src/main/scala/tool/UART.scala)) — serializer/deserializer at 115200 baud (divisor = clock/baud = 104). RX uses a 2-stage synchronizer and mid-bit sampling. TX shifts out start + 8 data + stop bits.

2. **Async adder** ([ADD.scala](src/main/scala/add/ADD.scala), [ACG.scala](src/main/scala/tool/ACG.scala)) — handshake-based asynchronous adder using request/acknowledge signaling (2-phase style via ACG). The ACG module joins two input handshakes into one output: when both inputs assert Req, ACG acknowledges them, asserts Out.Req, waits for Out.Ack, then pulses `fire_o` to capture the sum.

3. **Top state machine** ([Top.scala](src/main/scala/add/Top.scala)) — a 4-state FSM (`s_idle` / `s_add` / `s_ack` / `s_tx`) with a `gotFirst` flag:
   - **s_idle**: RX ready is asserted. On the first received byte, store it in `byte0` and set `gotFirst`. On the second byte, store it in `byte1` and transition to `s_add`.
   - **s_add**: Assert Req on both ADD inputs with data. Wait for `Out.Req` from the ADD module (handshake join complete).
   - **s_ack**: Acknowledge the ADD output (`Out.Ack = true`). Wait for `!Out.Req` — this signals that ACG has fired and `outDataReg` has captured the sum.
   - **s_tx**: Transmit `add.io.Out.Data` (the sum) via UART TX. When TX accepts, return to `s_idle`.

### Pin mapping (iCEBreaker)

| Signal | Pin | Function |
|--------|-----|----------|
| `clock` | 35 | 12 MHz oscillator |
| `io_reset_n` | 10 | Active-low reset (BTN_N) |
| `io_uart_rx` | 6 | FPGA receives from PC (FTDI TX) |
| `io_uart_tx` | 9 | FPGA transmits to PC (FTDI RX) |

### UART frame format

```
PC  -->  FPGA:  [byte A]  [byte B]      (8N1, 115200 baud)
FPGA -->  PC:   [(A+B) & 0xFF]
```

## Prerequisites

- **Java JDK 11+** and **sbt** — for Chisel RTL generation
- **OSS CAD Suite** — provides `yosys`, `nextpnr-ice40`, `icepack`, `iceprog`, `iverilog`, `vvp`
- **Python 3 + pyserial** — for UART tests (`pip install pyserial`)

**WSL users:** Install Java and sbt **inside WSL** (not Windows):

```bash
# Java
sudo apt update && sudo apt install -y openjdk-11-jdk

# sbt (not in default Ubuntu repos)
echo "deb https://repo.scala-sbt.org/scalasbt/debian all main" | sudo tee /etc/apt/sources.list.d/sbt.list
curl -sL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x2EE0EA64E40A89B84B2DF73499E82A75642AC823" | sudo gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/sbt.gpg > /dev/null
sudo apt update && sudo apt install -y sbt

which java   # expect /usr/bin/java
which sbt    # expect /usr/bin/sbt
```

## Quick start

```bash
make build          # Chisel → Verilog → Yosys → nextpnr → icepack
make prog           # Program iCEBreaker via iceprog
make test-fpga      # Run automated UART adder tests (7 test vectors)
```

## Project layout

```
├── src/main/scala/add/     # ADD (async adder), Top (UART bridge)
├── src/main/scala/tool/    # HS_Data, ACG, AsyncClock, UART TX/RX
├── src/rtl/chisel-verilog/ # Generated Verilog (after make rtl)
├── constraints/            # icebreaker.pcf (pin constraints)
├── build/                  # Synthesis output and .bin bitstream
├── scripts/                # UART test scripts
├── tests/                  # ADD_tb.v (Verilog testbench)
└── Makefile
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make rtl` | Generate Verilog: `sbt runMain add.Top` → `src/rtl/chisel-verilog/Top.v` |
| `make build` | Full pipeline: RTL + Yosys + nextpnr + icepack → `build/Top.bin` |
| `make prog` | Program FPGA with `iceprog build/Top.bin` |
| `make sim` | Run ADD testbench (iverilog + vvp) |
| `make test-fpga` | Automated UART adder tests (send A, B; expect A+B) |
| `make test-fpga-interactive` | Interactive mode: type `A B`, get A+B |
| `make build-echo` | Build minimal UART echo design (TopEcho) |
| `make prog-echo` | Program echo design |
| `make test-echo` | Test echo design (send byte, expect same byte back) |
| `make clean` | Remove `build/` and sim artifacts |

## UART testing

Run from **WSL** if the board is attached via USB passthrough (Windows COM ports are not visible in WSL).

```bash
pip install pyserial
make test-fpga                              # auto-detects /dev/ttyUSB1
python3 scripts/uart_adder_test.py -i       # interactive mode
python3 scripts/uart_adder_test.py -d -v    # debug + verbose output
```

**Troubleshooting:**

1. **No response** — Rebuild and reprogram: `make build && make prog`
2. **Wrong port** — iCEBreaker exposes two USB serial ports (FTDI FT2232H). Try both `/dev/ttyUSB0` and `/dev/ttyUSB1`; one is for programming, the other for UART.
3. **Reset held** — Ensure BTN_N (pin 10) is released. The button is active-low reset; when pressed, the design stays in reset.
4. **WSL clock skew** — If `make` says "Nothing to be done" after editing sources, use `touch <file> && make build`.

## Design notes

The Top module uses a **4-state FSM** (`Enum(4)` = 2-bit register, all 4 values used) to avoid iCE40 trap states. On iCE40, Chisel `Enum(N)` where N is not a power of 2 produces a register with unused bit patterns — if the register ever reaches an unhandled value (e.g. due to unreliable power-on reset), the design locks up permanently. `Enum(4)` uses a 2-bit register where all values (0–3) are handled. The `gotFirst` Bool flag tracks whether the first byte has been received while staying in `s_idle`, keeping the state count minimal.

The addition goes through the full ADD/ACG request-acknowledge handshake (4 clock cycles at 12 MHz ≈ 333 ns), not a combinational bypass.

### Bugs fixed in UART modules

- **UARTTx bitCount**: originally a free-running `Counter` that incremented even when not transmitting, causing truncated frames. Replaced with a manual register gated by `busy`.
- **UARTTx divCount**: originally a free-running `Counter` not reset on byte load, causing the start bit to be as short as 1 clock cycle (83 ns). The FTDI receiver needs ~half a bit period (~4.3 us) to confirm a start bit. Replaced with a manual register that resets to 0 when loading a new byte.
- **UARTRx bitCount threshold**: `bitCount === 8.U` stopped reception after 9 shifts (start + 8 data bits), missing the stop bit. Changed to `bitCount === 9.U` to shift all 10 bits, so `shreg[8:1]` correctly holds data bits d7..d0.
