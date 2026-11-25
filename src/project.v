/*
 * Copyright (c) 2026 ITSON - TeslaJedi
 * SPDX-License-Identifier: Apache-2.0
 *
 * ITSON 7-Seg BCD & Silicon Art
 * Target: Tiny Tapeout gf180mcuD (1x1 tile = 346.64 x 160.72 um)
 *
 * Features:
 *   1. Physical Silicon Art macro ("itson_logo") on Metal2 & Metal3.
 *   2. Sequential I-T-S-O-N wordmark & 0-9 numeric BCD 7-segment driver
 *      with configurable clock divider, turbo sim mode, pause, and manual override.
 */

`default_nettype none

(* blackbox *) (* keep *)
module itson_logo ();
endmodule

module tt_um_8bitadder (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs: {DP, g, f, e, d, c, b, a}
    input  wire [7:0] uio_in,   // IOs: Input path (uio_in[3:0] optional manual BCD)
    output wire [7:0] uio_out,  // IOs: Output path ({active_bcd[2:0], step_pulse, active_bcd})
    output wire [7:0] uio_oe,   // IOs: Enable path (8'hFF)
    input  wire       ena,      // Always 1 when design is powered
    input  wire       clk,      // Clock
    input  wire       rst_n     // Active-low reset
);

  // =========================================================================
  // 1. Silicon Art Macro Instance (Metal2 Shield + Metal3 ITSON Letters)
  // =========================================================================
  (* keep *)
  itson_logo logo ();

  // =========================================================================
  // 2. Control Inputs
  // =========================================================================
  wire       mode_bcd  = ui_in[0];   // 0: I-T-S-O-N mode, 1: Numeric BCD 0..9 mode
  wire [1:0] speed_sel = ui_in[2:1]; // Divider tap when turbo == 0
  wire       manual_en = ui_in[3];   // 1: Override counter with manual BCD
  wire       pause     = ui_in[6];   // 1: Freeze counter & divider
  wire       turbo     = ui_in[7];   // 1: Turbo / simulation mode (step every 4 clocks)

  // =========================================================================
  // 3. Programmable Clock Divider & Step Pulse
  // =========================================================================
  reg [22:0] div_cnt;
  reg        div_hit;

  always @(*) begin
    if (turbo) begin
      div_hit = (div_cnt[1:0] == 2'b11);
    end else begin
      case (speed_sel)
        2'b00:   div_hit = (div_cnt[12:0] == 13'h1FFF); // 2^13 clocks
        2'b01:   div_hit = (div_cnt[15:0] == 16'hFFFF); // 2^16 clocks
        2'b10:   div_hit = (div_cnt[19:0] == 20'hFFFFF); // 2^20 clocks
        default: div_hit = (div_cnt[22:0] == 23'h7FFFFF); // 2^23 clocks
      endcase
    end
  end

  wire step_pulse = div_hit & ~pause;

  // =========================================================================
  // 4. Sequential BCD / Character Index Counter
  // =========================================================================
  reg [3:0] bcd_cnt;

  always @(posedge clk) begin
    if (!rst_n) begin
      div_cnt <= 23'd0;
      bcd_cnt <= 4'd0;
    end else if (!pause) begin
      div_cnt <= div_cnt + 23'd1;
      if (step_pulse) begin
        if (mode_bcd) begin
          bcd_cnt <= (bcd_cnt >= 4'd9) ? 4'd0 : (bcd_cnt + 4'd1);
        end else begin
          bcd_cnt <= (bcd_cnt >= 4'd5) ? 4'd0 : (bcd_cnt + 4'd1);
        end
      end
    end
  end

  // =========================================================================
  // 5. Manual Override & 7-Segment Common-Cathode Decoder
  // =========================================================================
  wire [3:0] manual_bcd = (uio_in[3:0] != 4'd0) ? uio_in[3:0] : {1'b0, ui_in[6:4]};
  wire [3:0] active_bcd = manual_en ? manual_bcd : bcd_cnt;

  reg [6:0] seg;
  always @(*) begin
    if (!mode_bcd) begin
      // ITSON mode: 0='I', 1='t', 2='S', 3='O', 4='n', 5=' '
      case (active_bcd)
        4'd0:    seg = 7'b000_0110; // 0x06 'I'
        4'd1:    seg = 7'b111_1000; // 0x78 't'
        4'd2:    seg = 7'b110_1101; // 0x6D 'S'
        4'd3:    seg = 7'b011_1111; // 0x3F 'O'
        4'd4:    seg = 7'b101_0100; // 0x54 'n'
        4'd5:    seg = 7'b000_0000; // 0x00 blank
        default: seg = 7'b000_0000;
      endcase
    end else begin
      // Numeric BCD 0..9 mode
      case (active_bcd)
        4'd0:    seg = 7'b011_1111; // 0x3F '0'
        4'd1:    seg = 7'b000_0110; // 0x06 '1'
        4'd2:    seg = 7'b101_1011; // 0x5B '2'
        4'd3:    seg = 7'b100_1111; // 0x4F '3'
        4'd4:    seg = 7'b110_0110; // 0x66 '4'
        4'd5:    seg = 7'b110_1101; // 0x6D '5'
        4'd6:    seg = 7'b111_1101; // 0x7D '6'
        4'd7:    seg = 7'b000_0111; // 0x07 '7'
        4'd8:    seg = 7'b111_1111; // 0x7F '8'
        4'd9:    seg = 7'b110_1111; // 0x6F '9'
        default: seg = 7'b000_0000;
      endcase
    end
  end

  wire dp = (active_bcd == 4'd0) ? 1'b1 : 1'b0;

  assign uo_out  = {dp, seg};
  assign uio_oe  = 8'hFF;
  assign uio_out = {active_bcd[2:0], step_pulse, active_bcd};

  // =========================================================================
  // 6. Tie Off Unused Inputs for Clean Linting
  // =========================================================================
  wire _unused = &{ena, uio_in[7:4], 1'b0};

endmodule
