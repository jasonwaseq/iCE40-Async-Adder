package tool

import chisel3._

/** Handshake bundle: Req (request) and Ack (acknowledge) for 2-phase or 4-phase protocols. */
class HS extends Bundle {
  val Req = Output(Bool())
  val Ack = Input(Bool())
}

/** Handshake + Data bundle: HS handshake signals plus a data channel of given width. */
class HS_Data(width: Int) extends Bundle {
  val HS  = new HS
  val Data = Output(UInt(width.W))
}

object HS_Data {
  def apply(width: Int): HS_Data = new HS_Data(width)
}
