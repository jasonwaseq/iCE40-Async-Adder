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
    val add    = Module(new ADD)

    io.uart_tx   := uartTx.io.tx
    uartRx.io.rx := io.uart_rx

    val s_idle :: s_rx0 :: s_rx1 :: s_do_add :: s_wait_out :: s_ack_out :: s_tx :: Nil = Enum(7)
    val state = RegInit(s_idle)
    val byte0 = Reg(UInt(8.W))
    val byte1 = Reg(UInt(8.W))

    add.io.In0.HS.Req := false.B
    add.io.In1.HS.Req := false.B
    add.io.In0.Data   := byte0
    add.io.In1.Data   := byte1
    add.io.Out.HS.Ack := false.B

    uartTx.io.valid := false.B
    uartTx.io.data  := add.io.Out.Data
    uartRx.io.ready := false.B

    switch(state) {
      is(s_idle) {
        uartRx.io.ready := true.B
        when(uartRx.io.valid) {
          byte0  := uartRx.io.data
          state  := s_rx0
        }
      }
      is(s_rx0) {
        uartRx.io.ready := true.B
        when(uartRx.io.valid) {
          byte1  := uartRx.io.data
          state  := s_rx1
        }
      }
      is(s_rx1) {
        add.io.In0.HS.Req := true.B
        add.io.In1.HS.Req := true.B
        state := s_do_add
      }
      is(s_do_add) {
        add.io.In0.HS.Req := true.B
        add.io.In1.HS.Req := true.B
        when(add.io.Out.HS.Req) {
          state := s_wait_out
        }
      }
      is(s_wait_out) {
        add.io.Out.HS.Ack := true.B
        state := s_ack_out
      }
      is(s_ack_out) {
        add.io.Out.HS.Ack := false.B
        add.io.In0.HS.Req := false.B
        add.io.In1.HS.Req := false.B
        state := s_tx
      }
      is(s_tx) {
        uartTx.io.valid := true.B
        uartTx.io.data  := add.io.Out.Data
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
