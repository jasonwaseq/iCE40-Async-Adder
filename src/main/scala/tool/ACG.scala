package tool

import chisel3._
import chisel3.util._

/**
 * Arbiter/Control Join (ACG): joins multiple handshake channels into one.
 * When all InNum inputs have Req high, the module asserts Ack on all inputs
 * and raises Req on Out(0). When the consumer asserts Out(0).Ack, fire_o pulses.
 * Configurable via params: "InNum" -> N, "OutNum" -> 1.
 */
class ACG(params: Map[String, Int]) extends Module {
  val inNum  = params.getOrElse("InNum", 2)
  val outNum = params.getOrElse("OutNum", 1)

  val In  = IO(Vec(inNum, Flipped(new HS)))
  val Out = IO(Vec(outNum, new HS))

  val fire_o = IO(Output(Bool()))

  // All inputs requested
  val allInReq = In.map(_.Req).reduce(_ && _)
  // Output handshake: we send Req, consumer sends Ack
  val outReq = Out(0).Req
  val outAck = Out(0).Ack

  // Simple 2-phase style: when all inputs have Req, we ack them and assert output Req;
  // when output Ack comes, we complete (fire) and deassert.
  val s_idle :: s_ack_inputs :: s_wait_ack :: s_fire :: Nil = Enum(4)
  val state = RegInit(s_idle)

  Out(0).Req := false.B
  fire_o := false.B
  In.foreach(_.Ack := false.B)

  switch(state) {
    is(s_idle) {
      when(allInReq) {
        state := s_ack_inputs
      }
    }
    is(s_ack_inputs) {
      In.foreach(_.Ack := true.B)
      Out(0).Req := true.B
      state := s_wait_ack
    }
    is(s_wait_ack) {
      In.foreach(_.Ack := true.B)
      Out(0).Req := true.B
      when(outAck) {
        state := s_fire
      }
    }
    is(s_fire) {
      fire_o := true.B
      state := s_idle
    }
  }
}
