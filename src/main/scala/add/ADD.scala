package add

import chisel3._
import tool._

// Chisel 3 stage: uses Scala FIRRTL compiler (no firtool; works on Windows)
import chisel3.stage.ChiselStage

class ADD extends Module {
  val io = IO(new Bundle {
    val In0 = Flipped(new HS_Data(8))  // we consume: Req/Data in, Ack out
    val In1 = Flipped(new HS_Data(8))
    val Out = new HS_Data(8)           // we produce: Req/Data out, Ack in
  })

  private val ACG = Module(new ACG(Map(
    "InNum"  -> 2,
    "OutNum" -> 1
  )))

  // ACG receives Req from ports and drives Ack to ports
  ACG.In(0).Req := io.In0.HS.Req
  io.In0.HS.Ack := ACG.In(0).Ack
  ACG.In(1).Req := io.In1.HS.Req
  io.In1.HS.Ack := ACG.In(1).Ack
  ACG.Out(0) <> io.Out.HS

  // Output data: only update when handshake fires (async clock semantics)
  val outDataReg = Reg(UInt(8.W))
  AsyncClock(ACG.fire_o) {
    outDataReg := io.In0.Data + io.In1.Data
  }
  io.Out.Data := outDataReg
}

object ADD extends App {
  (new ChiselStage).emitVerilog(
    new ADD,
    Array("--target-dir", "src/rtl/chisel-verilog")
  )
}
