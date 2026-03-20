// Absolute minimal wire loopback: UART RX pin → TX pin (no logic, just a wire)
// If this doesn't echo bytes back, the pin assignments or serial port are wrong.
module WireEcho(
    input  clock,
    input  io_uart_rx,
    input  io_reset_n,
    output io_uart_tx
);
    assign io_uart_tx = io_uart_rx;
endmodule
