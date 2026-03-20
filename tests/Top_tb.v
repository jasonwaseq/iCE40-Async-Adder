// Testbench for full Top module: simulates UART TX/RX at bit level.
// Sends two bytes (A, B), expects one byte back ((A+B) mod 256).
// Dumps FST waveform to Top_tb.fst for viewing in GTKWave.
`timescale 1ns/1ns

module Top_tb;
  reg        clock;
  reg        io_uart_rx;
  wire       io_uart_tx;
  reg        io_reset_n;

  Top dut (
    .clock(clock),
    .reset(1'b0),          // Chisel default reset — unused, tied low
    .io_uart_tx(io_uart_tx),
    .io_uart_rx(io_uart_rx),
    .io_reset_n(io_reset_n)
  );

  // 12 MHz clock: period = 83.33 ns
  initial clock = 0;
  always #41.67 clock = ~clock;

  // UART parameters (115200 baud @ 12 MHz → divisor = 104)
  localparam BAUD_NS   = 8681;     // 1 / 115200 * 1e9
  localparam HALF_BAUD = BAUD_NS / 2;

  // ------- UART send (drive io_uart_rx) -------
  task send_byte;
    input [7:0] data;
    integer i;
    begin
      io_uart_rx = 0;              // start bit
      #BAUD_NS;
      for (i = 0; i < 8; i = i + 1) begin
        io_uart_rx = data[i];      // data LSB first
        #BAUD_NS;
      end
      io_uart_rx = 1;              // stop bit
      #BAUD_NS;
    end
  endtask

  // ------- UART receive (sample io_uart_tx) -------
  task receive_byte;
    output [7:0] data;
    integer i;
    integer timeout;
    begin
      data = 8'hXX;
      timeout = 0;
      // wait for start bit (TX goes low)
      while (io_uart_tx !== 1'b0 && timeout < 1000000) begin
        @(posedge clock);
        timeout = timeout + 1;
      end
      if (timeout >= 1000000) begin
        $display("  TIMEOUT waiting for TX start bit");
        data = 8'hFF;
      end else begin
        #HALF_BAUD;                // move to centre of start bit
        // sample 8 data bits
        for (i = 0; i < 8; i = i + 1) begin
          #BAUD_NS;
          data[i] = io_uart_tx;
        end
        #BAUD_NS;                  // stop bit
      end
    end
  endtask

  // ------- Test helper -------
  integer errors;
  integer passed;
  integer test_num;

  task do_test;
    input [7:0] a;
    input [7:0] b;
    input [7:0] expected;
    reg   [7:0] result;
    begin
      test_num = test_num + 1;
      send_byte(a);
      #20000;                      // gap > 1 bit period for idleSeen
      send_byte(b);
      receive_byte(result);
      if (result === expected) begin
        $display("  PASS [%0d]: %0d + %0d = %0d", test_num, a, b, result);
        passed = passed + 1;
      end else begin
        $display("  FAIL [%0d]: %0d + %0d = %0d (expected %0d)",
                 test_num, a, b, result, expected);
        errors = errors + 1;
      end
      #20000;                      // inter-test gap
    end
  endtask

  // ------- Main -------
  initial begin
    $dumpfile("Top_tb.fst");
    $dumpvars(0, Top_tb);

    errors   = 0;
    passed   = 0;
    test_num = 0;

    io_uart_rx = 1;                // UART idle = high
    io_reset_n = 0;                // assert reset
    #2000;
    io_reset_n = 1;                // release reset
    #10000;

    $display("");
    $display("=== Top Module — Full UART Testbench ===");
    $display("");

    // Basic
    $display("--- Basic ---");
    do_test(  0,   0,   0);
    do_test(  1,   0,   1);
    do_test(  0,   1,   1);
    do_test( 10,  20,  30);
    do_test(100,  57, 157);

    // Boundaries
    $display("--- Boundaries ---");
    do_test(255,   0, 255);
    do_test(  0, 255, 255);
    do_test(128, 127, 255);

    // Overflow
    $display("--- Overflow ---");
    do_test(255,   1,   0);
    do_test(255, 255, 254);
    do_test(128, 128,   0);
    do_test(200, 100,  44);

    // Summary
    $display("");
    $display("=== Results: %0d/%0d passed, %0d failed ===",
             passed, test_num, errors);
    if (errors == 0)
      $display("ALL TESTS PASSED.");
    else
      $display("TESTS FAILED.");
    $display("");
    $finish;
  end
endmodule
