// Testbench for ADD module: exercises handshake protocol with many test vectors.
// Dumps FST waveform to ADD_tb.fst for viewing in GTKWave.
`timescale 1ns/1ns

module ADD_tb;
  reg        clock;
  reg        reset;
  reg        io_In0_HS_Req;
  wire       io_In0_HS_Ack;
  reg  [7:0] io_In0_Data;
  reg        io_In1_HS_Req;
  wire       io_In1_HS_Ack;
  reg  [7:0] io_In1_Data;
  wire       io_Out_HS_Req;
  reg        io_Out_HS_Ack;
  wire [7:0] io_Out_Data;

  ADD dut (
    .clock         (clock),
    .reset         (reset),
    .io_In0_HS_Req (io_In0_HS_Req),
    .io_In0_HS_Ack (io_In0_HS_Ack),
    .io_In0_Data   (io_In0_Data),
    .io_In1_HS_Req (io_In1_HS_Req),
    .io_In1_HS_Ack (io_In1_HS_Ack),
    .io_In1_Data   (io_In1_Data),
    .io_Out_HS_Req (io_Out_HS_Req),
    .io_Out_HS_Ack (io_Out_HS_Ack),
    .io_Out_Data   (io_Out_Data)
  );

  initial clock = 0;
  always #5 clock = ~clock;  // 100 MHz (10 ns period)

  integer errors;
  integer passed;
  integer test_num;
  integer timeout_count;
  parameter TIMEOUT_CYCLES = 1000;

  // --- Handshake task: drive inputs, wait for output, check result ---
  task do_add;
    input [7:0] a;
    input [7:0] b;
    input [7:0] expected;
    begin
      test_num = test_num + 1;

      // Drive input handshake
      @(posedge clock);
      io_In0_Data   = a;
      io_In1_Data   = b;
      io_In0_HS_Req = 1;
      io_In1_HS_Req = 1;

      // Wait for output Req with timeout
      timeout_count = 0;
      while (!io_Out_HS_Req && timeout_count < TIMEOUT_CYCLES) begin
        @(posedge clock);
        timeout_count = timeout_count + 1;
      end

      if (timeout_count >= TIMEOUT_CYCLES) begin
        $display("FAIL [%0d]: %0d + %0d — output Req timeout after %0d cycles",
                 test_num, a, b, TIMEOUT_CYCLES);
        errors = errors + 1;
        // Release and reset for next test
        io_In0_HS_Req = 0;
        io_In1_HS_Req = 0;
        io_Out_HS_Ack = 0;
        #100;
      end else begin
        // Acknowledge output
        #20;
        io_Out_HS_Ack = 1;
        #30;

        if (io_Out_Data !== expected) begin
          $display("FAIL [%0d]: %0d + %0d = %0d (expected %0d)",
                   test_num, a, b, io_Out_Data, expected);
          errors = errors + 1;
        end else begin
          $display("PASS [%0d]: %0d + %0d = %0d", test_num, a, b, io_Out_Data);
          passed = passed + 1;
        end

        // Release handshake
        io_Out_HS_Ack = 0;
        io_In0_HS_Req = 0;
        io_In1_HS_Req = 0;
        #50;
      end
    end
  endtask

  initial begin
    // --- Waveform dump (FST for GTKWave) ---
    $dumpfile("ADD_tb.fst");
    $dumpvars(0, ADD_tb);

    errors   = 0;
    passed   = 0;
    test_num = 0;

    // Reset
    reset         = 1;
    io_In0_HS_Req = 0;
    io_In1_HS_Req = 0;
    io_In0_Data   = 0;
    io_In1_Data   = 0;
    io_Out_HS_Ack = 0;
    #100;
    reset = 0;
    #20;

    $display("");
    $display("=== ADD Module Testbench ===");
    $display("");

    // --- Basic operations ---
    $display("--- Basic ---");
    do_add(  0,   0,   0);   // zero + zero
    do_add(  1,   0,   1);   // identity
    do_add(  0,   1,   1);   // identity (swapped)
    do_add( 10,  20,  30);   // simple
    do_add(100,  57, 157);   // larger

    // --- Boundary values ---
    $display("--- Boundaries ---");
    do_add(255,   0, 255);   // max + zero
    do_add(  0, 255, 255);   // zero + max
    do_add(128, 127, 255);   // half + half-1 = max
    do_add(127, 128, 255);   // swapped

    // --- Overflow / wrap-around ---
    $display("--- Overflow ---");
    do_add(255,   1,   0);   // max + 1 wraps to 0
    do_add(  1, 255,   0);   // swapped
    do_add(255, 255, 254);   // max + max = 254
    do_add(128, 128,   0);   // 128 + 128 = 256 wraps to 0
    do_add(200, 100,  44);   // 300 mod 256 = 44
    do_add(200, 200, 144);   // 400 mod 256 = 144

    // --- Powers of two ---
    $display("--- Powers of two ---");
    do_add(  1,   1,   2);
    do_add(  2,   2,   4);
    do_add(  4,   4,   8);
    do_add(  8,   8,  16);
    do_add( 16,  16,  32);
    do_add( 32,  32,  64);
    do_add( 64,  64, 128);

    // --- Consecutive values ---
    $display("--- Consecutive ---");
    do_add(  1, 254, 255);
    do_add(  2, 253, 255);
    do_add( 50, 205, 255);
    do_add( 99, 156, 255);

    // --- Same operand ---
    $display("--- Same operand ---");
    do_add( 42,  42,  84);
    do_add(100, 100, 200);
    do_add(  0,   0,   0);

    // --- Summary ---
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
