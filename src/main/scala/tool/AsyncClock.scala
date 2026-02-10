package tool

import chisel3._

/**
 * AsyncClock(cond)(body): runs `body` only when `cond` is true.
 * Used to update registers only when the async handshake fires (e.g. fire_o).
 * Implemented as a when(cond) block so that any assignments in body
 * only take effect when cond is high.
 */
object AsyncClock {
  def apply(cond: Bool)(body: => Unit): Unit = {
    when(cond) {
      body
    }
  }
}
