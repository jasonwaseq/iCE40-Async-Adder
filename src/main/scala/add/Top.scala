package add

import chisel3._
import chisel3.util._
import tool._

/**
 * Top module: UART bridge to the async ADD (handshake-based adder).
 * Protocol: send byte A, then byte B over UART; receive one byte (A+B) mod 256.
 * Addition goes through the ADD/ACG request-acknowledge handshake.
 * Assumes 12 MHz system clock; 115200 baud (divisor = 104).
 * reset_n: active-low reset (BTN_N on iCEBreaker).
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

    // 4-state FSM (2-bit register, all values used → no iCE40 trap states)
    //   s_idle: receive two UART bytes (gotFirst flag tracks first vs second)
    //   s_add:  assert Req on both ADD inputs, wait for ADD Out.Req
    //   s_ack:  acknowledge ADD output, wait for handshake completion (!Out.Req)
    //   s_tx:   transmit result byte via UART
    val s_idle :: s_add :: s_ack :: s_tx :: Nil = Enum(4)
    val state = RegInit(s_idle)
    val byte0 = Reg(UInt(8.W))
    val byte1 = Reg(UInt(8.W))
    val gotFirst = RegInit(false.B)

    // UART defaults
    uartTx.io.valid := false.B
    uartTx.io.data  := add.io.Out.Data
    uartRx.io.ready := false.B

    // ADD handshake defaults
    add.io.In0.HS.Req := false.B
    add.io.In1.HS.Req := false.B
    add.io.In0.Data   := byte0
    add.io.In1.Data   := byte1
    add.io.Out.HS.Ack := false.B

    switch(state) {
      is(s_idle) {
        uartRx.io.ready := true.B
        when(uartRx.io.valid) {
          when(gotFirst) {
            byte1    := uartRx.io.data
            state    := s_add
            gotFirst := false.B
          }.otherwise {
            byte0    := uartRx.io.data
            gotFirst := true.B
          }
        }
      }
      is(s_add) {
        // Request addition: drive data and assert Req on both inputs
        add.io.In0.HS.Req := true.B
        add.io.In1.HS.Req := true.B
        when(add.io.Out.HS.Req) {
          state := s_ack
        }
      }
      is(s_ack) {
        // Keep input Reqs high (data must be stable); acknowledge the result
        add.io.In0.HS.Req := true.B
        add.io.In1.HS.Req := true.B
        add.io.Out.HS.Ack := true.B
        when(!add.io.Out.HS.Req) {
          // ACG has fired: outDataReg captures the sum on this clock edge
          state := s_tx
        }
      }
      is(s_tx) {
        // Transmit the sum via UART
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
