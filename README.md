# iCE40 Asynchronous Adder (Chisel)

Asynchronous adder in Chisel with handshake interfaces (HS_Data, ACG), for Lattice iCE40 FPGAs. Uses **Chisel 3** and the **Scala FIRRTL compiler**. Build and program with **OSS CAD Suite** (Yosys, nextpnr-ice40, icepack, iceprog), driven by a **Makefile** (see [FPGA-RISC-V-5-Stage-Pipelined-Processor](https://github.com/jasonwaseq/FPGA-RISC-V-5-Stage-Pipelined-Processor) for a similar setup).

## This shit does not work, will synthesize but UART cannot transmit efficiently

## Prerequisites

- **Java JDK 11+** and **sbt** – for Chisel RTL generation
- **OSS CAD Suite** – provides `yosys`, `nextpnr-ice40`, `icepack`, `iceprog`, `iverilog`, `vvp`. Put its `bin/` on `PATH` (e.g. source `environment.sh` from the OSS CAD Suite install).

**WSL:** Use **Java and sbt installed inside WSL** (not Windows), or you get `java: command not found` when `make` runs Windows sbt. sbt is not in default Ubuntu/Debian repos; add the official repo and install:

```bash
# 1) Java
sudo apt update && sudo apt install -y openjdk-11-jdk

# 2) sbt (add official repo; not in default Ubuntu repos)
echo "deb https://repo.scala-sbt.org/scalasbt/debian all main" | sudo tee /etc/apt/sources.list.d/sbt.list
curl -sL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x2EE0EA64E40A89B84B2DF73499E82A75642AC823" | sudo gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/sbt.gpg > /dev/null
sudo apt update && sudo apt install -y sbt

# 3) Confirm WSL tools are used (not Windows)
which java   # expect /usr/bin/java
which sbt    # expect /usr/bin/sbt
```

Then run `make build` from the same WSL shell.

## Project layout

```
├── src/main/scala/add/     # ADD (async adder), Top (UART + ADD)
├── src/main/scala/tool/    # HS_Data, ACG, AsyncClock, UART
├── src/rtl/chisel-verilog/ # Generated Verilog (after make rtl / make build)
├── constraints/            # icebreaker.pcf (iCE40UP5K-SG48)
├── build/                  # Yosys/nextpnr output and .bin
├── scripts/                # uart_adder_test.py, uart_adder_debug.py, requirements-uart.txt
├── tests/                  # ADD_tb.v
└── Makefile
```

## Quick start (OSS CAD Suite)

From the project root (WSL or Linux; OSS CAD Suite on `PATH`):

```bash
# Build bitstream for iCEBreaker (generates RTL, then synth + P&R + pack)
make build

# Program FPGA
make prog
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make rtl` | Generate Verilog: `sbt runMain add.Top` → `src/rtl/chisel-verilog/Top.v` |
| `make build` | RTL (if needed) + Yosys + nextpnr + icepack → `build/Top.bin` |
| `make prog` | Program FPGA with `iceprog build/Top.bin` |
| `make sim` | Run ADD testbench (iverilog + vvp) |
| `make test-fpga` | UART adder tests (`python3 scripts/uart_adder_test.py`) |
| `make test-fpga-interactive` | Interactive A+B over UART |
| `make clean` | Remove `build/` and sim artifacts |
| `make help` | List targets |

## FPGA settings (Makefile)

Target is **iCEBreaker** (iCE40UP5K-SG48), 12 MHz, constraints in `constraints/icebreaker.pcf`. To change device/package, edit `DEVICE`, `PACKAGE`, and `PCF_FILE` in the Makefile.

## Design summary

- **ADD**: 8-bit async adder; handshake inputs In0/In1, handshake output Out; uses ACG (2-in, 1-out) and AsyncClock.
- **Top**: Wraps ADD with UART; send byte A, byte B → receive byte (A+B). 115200 baud.

## UART testing

**If the board is attached via WSL**, run the UART test **from inside WSL** so the script sees the serial device (Windows COM ports are not visible in WSL).

**IMPORTANT:** Ensure **BTN_N (pin 10) is released** (not pressed). The button is active-low reset; when pressed, the design stays in reset.

```bash
# From WSL (with OSS CAD Suite and Python/pyserial available):
pip install -r scripts/requirements-uart.txt
make test-fpga                    # automated tests (auto-detects /dev/ttyUSB0 etc.)
make test-fpga-interactive        # interactive: type "A B" to get A+B
# Or specify port explicitly:
python3 scripts/uart_adder_test.py /dev/ttyUSB0
python3 scripts/uart_adder_test.py /dev/ttyUSB0 -v   # verbose
```

From Windows (board not attached to Windows): use `wsl` to run the test, e.g.  
`wsl -e bash -c "cd /mnt/c/Users/.../iCE40-Async-Adder && make test-fpga"`  
or open a WSL terminal in the project and run `make test-fpga` there.

**Debug (UART tests failing / no response):**

1. **Rebuild and reprogram** after any RTL or PCF change: `make build && make prog`.  
   (The PCF file had a corrupted first line fixed so constraints apply correctly.)

2. **Run with debug prints** (shows `in_waiting`, timestamps, drained bytes):  
   `python3 scripts/uart_adder_test.py /dev/ttyUSB1 -d`

3. **Standalone debug script** (one add, `in_waiting` at each step):  
   `python3 scripts/uart_adder_debug.py /dev/ttyUSB1`  
   `python3 scripts/uart_adder_debug.py /dev/ttyUSB1 --slow`  # longer delays  
   **Listen only** (see if FPGA sends anything):  
   `python3 scripts/uart_adder_debug.py /dev/ttyUSB1 --listen 5`  
   Then in another terminal run `make test-fpga` or send bytes; first terminal prints any RX with timestamps.

4. **Port**: iCEBreaker often has two USB serial ports; try both `/dev/ttyUSB0` and `/dev/ttyUSB1` (one may be programming, one UART).

5. **Reset**: Ensure BTN_N is not pressed (reset released).
