package add

import chisel3._
import chisel3.util._
import tool._

/** Minimal UART echo: receive byte, send it back. Same pins as Top. */
class TopEcho(clockFreqHz: Int = 12000000, baudRate: Int = 115200) extends Module {
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

    io.uart_tx := uartTx.io.tx
    uartRx.io.rx := io.uart_rx

    uartRx.io.ready := uartTx.io.ready
    uartTx.io.valid := uartRx.io.valid
    uartTx.io.data := uartRx.io.data
  }
}

object TopEcho extends App {
  (new chisel3.stage.ChiselStage).emitVerilog(
    new TopEcho,
    Array("--target-dir", "src/rtl/chisel-verilog")
  )
}
