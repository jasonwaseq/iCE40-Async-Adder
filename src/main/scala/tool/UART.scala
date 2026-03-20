package tool

import chisel3._
import chisel3.util._

/** UART TX: serializes bytes at the given baud divisor (clock cycles per bit). */
class UARTTx(divisor: Int) extends Module {
  val io = IO(new Bundle {
    val tx    = Output(Bool())
    val valid = Input(Bool())
    val data  = Input(UInt(8.W))
    val ready = Output(Bool())
  })

  // Manual divCount so it can be reset to 0 when a byte starts, guaranteeing
  // the start bit is exactly `divisor` cycles long (a free-running Counter can
  // produce a start bit as short as 1 cycle, which the PC UART will miss).
  val divCount = RegInit(0.U(log2Ceil(divisor).W))
  val divWrap  = divCount === (divisor - 1).U
  val bitCount = RegInit(0.U(4.W))
  val shreg    = Reg(UInt(10.W))  // {stop(1), data[7:0], start(0)}
  val busy     = RegInit(false.B)

  io.ready := !busy
  io.tx    := Mux(busy, shreg(0), true.B)  // idle = high

  when(busy) {
    when(divWrap) {
      divCount := 0.U
      shreg    := 1.U(1.W) ## shreg(9, 1)
      when(bitCount === 9.U) {
        busy     := false.B
        bitCount := 0.U
      }.otherwise {
        bitCount := bitCount + 1.U
      }
    }.otherwise {
      divCount := divCount + 1.U
    }
  }
  // Loading a new byte resets divCount so the start bit is always a full period.
  when(io.valid && !busy) {
    busy     := true.B
    divCount := 0.U
    shreg    := 1.U(1.W) ## io.data ## 0.U(1.W)
    bitCount := 0.U
  }
}

/** UART RX: receives bytes, outputs valid + data when a byte is done.
  * Sampling is synchronized to the start-bit edge (per FPGA-RISC-V uart_rx.v style):
  * detect start -> wait half bit to center sample -> sample every full bit period.
  */
class UARTRx(divisor: Int) extends Module {
  val io = IO(new Bundle {
    val rx     = Input(Bool())
    val valid  = Output(Bool())
    val data   = Output(UInt(8.W))
    val ready  = Input(Bool())  // flow control: clear valid when accepted
  })

  val halfDiv = divisor / 2
  val fullDiv = divisor

  val receiving = RegInit(false.B)
  val bitCount = RegInit(0.U(4.W))  // 0..9: start + 8 data + stop
  val prescaleReg = Reg(UInt(16.W))
  val shreg = Reg(UInt(10.W))
  val rxSync = RegNext(RegNext(io.rx))  // 2-stage sync for metastability

  val startBit = !rxSync && !receiving
  val (idleCount, idleWrap) = Counter(!receiving && rxSync, divisor)
  val idleSeen = RegInit(true.B)  // allow first byte without prior idle (line typically high at boot)
  when(idleWrap) { idleSeen := true.B }
  when(startBit && idleSeen) {
    receiving := true.B
    idleSeen := false.B
    bitCount := 0.U
    prescaleReg := (halfDiv + fullDiv - 2).U  // wait 1.5 bit to center on first data bit
  }

  val doneReceiving = WireDefault(false.B)
  when(receiving) {
    when(prescaleReg === 0.U) {
      // Shift 10 times: start + 8 data + stop (FPGAwars style), then raw_data[8:1] = data
      shreg := rxSync ## shreg(9, 1)
      prescaleReg := (fullDiv - 1).U
      when(bitCount === 9.U) {  // 10th shift (stop bit) done; shreg[8:1]=d7..d0
        receiving := false.B
        doneReceiving := true.B
      }
      bitCount := bitCount + 1.U
    }.otherwise {
      prescaleReg := prescaleReg - 1.U
    }
  }

  val hasByte = RegInit(false.B)
  val outData = Reg(UInt(8.W))
  when(doneReceiving) {
    hasByte := true.B
    outData := shreg(8, 1)  // after 10 shifts: shreg[9]=stop, shreg[8:1]=d7..d0, shreg[0]=start
  }
  when(io.ready && hasByte) {
    hasByte := false.B
  }

  io.valid := hasByte
  io.data  := outData
}
