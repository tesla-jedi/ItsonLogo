# SPDX-FileCopyrightText: © 2026 ITSON - TeslaJedi
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge


ITSON_SEGS = [
    0x86,  # 0: 'I' + DP
    0x78,  # 1: 't'
    0x6D,  # 2: 'S'
    0x3F,  # 3: 'O'
    0x54,  # 4: 'n'
    0x00,  # 5: blank
]

BCD_SEGS = [
    0xBF,  # 0: '0' + DP
    0x06,  # 1: '1'
    0x5B,  # 2: '2'
    0x4F,  # 3: '3'
    0x66,  # 4: '4'
    0x6D,  # 5: '5'
    0x7D,  # 6: '6'
    0x07,  # 7: '7'
    0x7F,  # 8: '8'
    0x6F,  # 9: '9'
]


async def reset_dut(dut, ui_in=0x00, uio_in=0x00, cycles=5):
    """Apply active-low reset and settle on a falling clock edge."""
    dut.ena.value = 1
    dut.ui_in.value = ui_in
    dut.uio_in.value = uio_in
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, cycles)
    await FallingEdge(dut.clk)


async def step_clocks(dut, cycles):
    """Advance `cycles` rising clock edges and settle on the following falling edge."""
    await ClockCycles(dut.clk, cycles)
    await FallingEdge(dut.clk)


def check_outputs(dut, expected_uo, expected_bcd, expected_step=None):
    """Verify 7-segment output and bidirectional telemetry pins."""
    uo = int(dut.uo_out.value)
    uio = int(dut.uio_out.value)
    oe = int(dut.uio_oe.value)

    assert oe == 0xFF, f"Expected uio_oe=0xFF, got 0x{oe:02X}"
    assert uo == expected_uo, f"Expected uo_out=0x{expected_uo:02X}, got 0x{uo:02X}"
    assert (uio & 0x0F) == expected_bcd, (
        f"Expected uio_out[3:0]={expected_bcd}, got {uio & 0x0F}"
    )
    assert ((uio >> 5) & 0x07) == (expected_bcd & 0x07), (
        f"Expected uio_out[7:5]={expected_bcd & 0x07}, got {(uio >> 5) & 0x07}"
    )
    if expected_step is not None:
        step = (uio >> 4) & 0x01
        assert step == expected_step, f"Expected step_pulse={expected_step}, got {step}"


@cocotb.test()
async def test_itson_7seg_and_bcd(dut):
    dut._log.info("Start ITSON 7-Seg BCD & Silicon Art test")

    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())

    # 1. Reset state check
    await reset_dut(dut, ui_in=0x00, uio_in=0x00)
    check_outputs(dut, expected_uo=0x86, expected_bcd=0, expected_step=0)

    # 2. Turbo sequential ITSON mode (ui_in = 0x80, 4 clocks per step)
    dut.ui_in.value = 0x80
    dut.rst_n.value = 1

    # div_cnt: 0 -> 1 ('I'), then 1 -> 3 (step_pulse=1), then 3 -> 4 ('t')
    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=ITSON_SEGS[0], expected_bcd=0, expected_step=0)

    await step_clocks(dut, 2)
    check_outputs(dut, expected_uo=ITSON_SEGS[0], expected_bcd=0, expected_step=1)

    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=ITSON_SEGS[1], expected_bcd=1, expected_step=0)

    for idx in (2, 3, 4, 5, 0):
        await step_clocks(dut, 4)
        check_outputs(dut, expected_uo=ITSON_SEGS[idx], expected_bcd=idx, expected_step=0)

    # 3. Pause test (ui_in = 0xC0) holding non-zero state ('S' = idx 2)
    await step_clocks(dut, 8)
    check_outputs(dut, expected_uo=ITSON_SEGS[2], expected_bcd=2, expected_step=0)

    dut.ui_in.value = 0xC0
    await step_clocks(dut, 12)
    check_outputs(dut, expected_uo=ITSON_SEGS[2], expected_bcd=2, expected_step=0)

    # Resume from pause -> advances to 'O' (idx 3) on next step
    dut.ui_in.value = 0x80
    await step_clocks(dut, 4)
    check_outputs(dut, expected_uo=ITSON_SEGS[3], expected_bcd=3, expected_step=0)

    # 4. Numeric BCD mode (ui_in = 0x81) stepping 0..9 and wrapping to 0
    await reset_dut(dut, ui_in=0x81, uio_in=0x00)
    dut.rst_n.value = 1

    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=BCD_SEGS[0], expected_bcd=0, expected_step=0)

    await step_clocks(dut, 3)
    check_outputs(dut, expected_uo=BCD_SEGS[1], expected_bcd=1, expected_step=0)

    for digit in (2, 3, 4, 5, 6, 7, 8, 9, 0):
        await step_clocks(dut, 4)
        check_outputs(dut, expected_uo=BCD_SEGS[digit], expected_bcd=digit, expected_step=0)

    # Verify clean wrap from numeric >= 5 back to 0 when switching to ITSON mode
    await step_clocks(dut, 7 * 4)
    check_outputs(dut, expected_uo=BCD_SEGS[7], expected_bcd=7, expected_step=0)

    dut.ui_in.value = 0x80
    await step_clocks(dut, 4)
    check_outputs(dut, expected_uo=ITSON_SEGS[0], expected_bcd=0, expected_step=0)

    # 5. Manual BCD override mode (ui_in[3] = 1)
    dut.uio_in.value = 0x00

    # Manual switch bits [6:4] in ITSON mode (ui_in[0] = 0)
    dut.ui_in.value = 0x88 | (2 << 4)
    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=ITSON_SEGS[2], expected_bcd=2)

    dut.ui_in.value = 0x88 | (4 << 4)
    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=ITSON_SEGS[4], expected_bcd=4)

    dut.ui_in.value = 0x88 | (0 << 4)
    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=ITSON_SEGS[0], expected_bcd=0)

    # Manual switch bits [6:4] in numeric BCD mode (ui_in[0] = 1)
    dut.ui_in.value = 0x89 | (2 << 4)
    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=BCD_SEGS[2], expected_bcd=2)

    dut.ui_in.value = 0x89 | (5 << 4)
    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=BCD_SEGS[5], expected_bcd=5)

    dut.ui_in.value = 0x89 | (0 << 4)
    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=BCD_SEGS[0], expected_bcd=0)

    # Optional uio_in[3:0] manual override (takes precedence when non-zero)
    dut.ui_in.value = 0x89 | (2 << 4)
    dut.uio_in.value = 9
    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=BCD_SEGS[9], expected_bcd=9)
    dut.uio_in.value = 0x00

    # 6. Non-turbo divider tap 2'b00 (2^13 = 8192 clocks)
    await reset_dut(dut, ui_in=0x00, uio_in=0x00)
    dut.rst_n.value = 1

    await step_clocks(dut, 8191)
    check_outputs(dut, expected_uo=ITSON_SEGS[0], expected_bcd=0, expected_step=1)

    await step_clocks(dut, 1)
    check_outputs(dut, expected_uo=ITSON_SEGS[1], expected_bcd=1, expected_step=0)

    dut._log.info("ITSON 7-Seg BCD & Silicon Art test passed!")
