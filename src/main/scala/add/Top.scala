package add

import chisel3._
import chisel3.util._
import tool._

/**
 * Top module: UART bridge to the async ADD.
 * Protocol: send byte A, then byte B over UART; receive one byte (A+B).
 * Assumes 12 MHz system clock; 115200 baud (divisor = 104).
 * reset_n: active-low reset (e.g. CRESET_B on iCEstick).
 */
class Top(clockFreqHz: Int = 12000000, baudRate: Int = 115200) extends Module {
  val io = IO(new Bundle {
    val uart_tx = Output(Bool())
    val uart_rx = Input(Bool())
    val reset_n = Input(Bool())
  })

  val sysReset = !io.reset_n
  val divisor = clockFreqHz / baudRate

  withReset(sysReset) {
    val uartTx = Module(new UARTTx(divisor))
    val uartRx = Module(new UARTRx(divisor))

    io.uart_tx   := uartTx.io.tx
    uartRx.io.rx := io.uart_rx

    // 2-byte adder bypass: receive A, B, send (A+B) mod 256
    val s_idle :: s_tx :: Nil = Enum(2)
    val state = RegInit(s_idle)
    val byte0 = Reg(UInt(8.W))
    val byte1 = Reg(UInt(8.W))
    val gotFirst = RegInit(false.B)

    uartTx.io.valid := false.B
    uartTx.io.data  := (byte0 +& byte1)(7, 0)
    uartRx.io.ready := false.B

    switch(state) {
      is(s_idle) {
        uartRx.io.ready := true.B
        when(uartRx.io.valid) {
          when(gotFirst) {
            byte1    := uartRx.io.data
            state    := s_tx
            gotFirst := false.B
          }.otherwise {
            byte0    := uartRx.io.data
            gotFirst := true.B
          }
        }
      }
      is(s_tx) {
        uartTx.io.valid := true.B
        when(uartTx.io.ready) {
          state := s_idle
        }
      }
    }
  }
}

object Top extends App {
  (new chisel3.stage.ChiselStage).emitVerilog(
    new Top,
    Array("--target-dir", "src/rtl/chisel-verilog")
  )
}
