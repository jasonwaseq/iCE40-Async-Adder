// Minimal testbench for ADD: drive handshakes and check sum
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
  always #5 clock = ~clock;

  integer errors;
  initial begin
    errors = 0;
    reset = 1;
    io_In0_HS_Req = 0;
    io_In1_HS_Req = 0;
    io_In0_Data   = 0;
    io_In1_Data   = 0;
    io_Out_HS_Ack = 0;
    #100;
    reset = 0;
    #20;

    // Test 1: 10 + 20 = 30
    io_In0_HS_Req = 1;
    io_In1_HS_Req = 1;
    io_In0_Data   = 10;
    io_In1_Data   = 20;

    wait (io_Out_HS_Req);
    #20;
    io_Out_HS_Ack = 1;
    #30;
    if (io_Out_Data !== 8'd30) begin
      $display("FAIL: expected 30, got %d", io_Out_Data);
      errors = errors + 1;
    end else
      $display("PASS: 10 + 20 = %d", io_Out_Data);
    io_Out_HS_Ack = 0;
    io_In0_HS_Req = 0;
    io_In1_HS_Req = 0;
    #50;

    // Test 2: 100 + 57 = 157
    io_In0_HS_Req = 1;
    io_In1_HS_Req = 1;
    io_In0_Data   = 100;
    io_In1_Data   = 57;
    wait (io_Out_HS_Req);
    #20;
    io_Out_HS_Ack = 1;
    #30;
    if (io_Out_Data !== 8'd157) begin
      $display("FAIL: expected 157, got %d", io_Out_Data);
      errors = errors + 1;
    end else
      $display("PASS: 100 + 57 = %d", io_Out_Data);
    io_Out_HS_Ack = 0;
    io_In0_HS_Req = 0;
    io_In1_HS_Req = 0;
    #50;

    if (errors == 0)
      $display("All tests PASSED.");
    else
      $display("TESTS FAILED: %0d error(s)", errors);
    $finish;
  end
endmodule
