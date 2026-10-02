/* Standalone tests of the real Zapper update code. No game ROM is needed.
 * cc -std=c99 -Isrc/drivers/libretro/libretro-common/include tests/zapper_measurement.c -o /tmp/zapper_measurement && /tmp/zapper_measurement
 */
#include <assert.h>
#include <stdio.h>
#include "../src/input/zapper.c"

uint8_t RAM[0x800];
uint8_t PAL;
int scanline;
uint32_t timestamp;
uint64_t timestampbase;
FCEUGI *GameInfo;
pal *palo;
void FCEUPPU_LineUpdate(void) {}
void FCEU_DrawGunSight(uint8_t *buf, int x, int y) { (void)buf; (void)x; (void)y; }

int main(void) {
    uint32_t input[4] = {40, 80, 1, 0};
    zapper_hold_trigger = 1;
    zapper_mechanized_latch = 1;
    memset(ZD, 0, sizeof(ZD));
    UpdateZapper(1, input, 0); /* capture trigger position */
    input[0] = 90;
    UpdateZapper(1, input, 0); /* game hasn't started the measurement yet */
    RAM[0x508] = 1;
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 40 && ZD[1].mzy == 80);
    RAM[0x508] = 255;
    input[0] = 230; input[1] = 200; input[2] = 2; /* move offscreen, release */
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 40 && ZD[1].mzy == 80);
    assert(!(ZD[1].mzb & 2) && !ZD[1].bogo);
    RAM[0x508] = 0;
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 230 && ZD[1].mzy == 200 && (ZD[1].mzb & 2));

    /* Secondary weapons can start a measurement without a gun trigger. */
    RAM[0x508] = 1; input[0] = 75; input[1] = 100; input[2] = 0;
    UpdateZapper(1, input, 0);
    input[0] = 200; UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 75);
    FCEU_ZapperResetMeasurement();
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 200); /* no stale latch after a restored state */

    /* Neither the other gun nor a disabled option may freeze input. */
    input[0] = 15; UpdateZapper(0, input, 0);
    input[0] = 215; UpdateZapper(0, input, 0);
    assert(ZD[0].mzx == 215);
    zapper_mechanized_latch = 0;
    input[0] = 25; UpdateZapper(1, input, 0);
    input[0] = 225; UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 225);

    /* A trigger ignored by the game must expire instead of latching later. */
    memset(ZD, 0, sizeof(ZD));
    zapper_mechanized_latch = 1; RAM[0x508] = 0;
    input[0] = 45; input[2] = 1; UpdateZapper(1, input, 0);
    input[0] = 145; input[2] = 0;
    for (int i = 0; i < 10; i++) UpdateZapper(1, input, 0);
    RAM[0x508] = 1; UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 145);
    /* Operation Wolf uses A3=1/0x40, and ends at A3=0x80. */
    memset(ZD, 0, sizeof(ZD));
    zapper_mechanized_latch = 0;
    zapper_operation_wolf_latch = 1;
    RAM[0x508] = 255; RAM[0xa3] = 0;
    input[0] = 48; input[1] = 72; input[2] = 1;
    UpdateZapper(1, input, 0);
    RAM[0xa3] = 1; input[0] = 148;
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 48);
    RAM[0xa3] = 0x40; input[0] = 228; input[2] = 2;
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 48 && !(ZD[1].mzb & 2) && !ZD[1].bogo);
    input[0] = 17; UpdateZapper(0, input, 0);
    input[0] = 217; UpdateZapper(0, input, 0);
    assert(ZD[0].mzx == 217);
    input[0] = 228;
    RAM[0xa3] = 0x80;
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 228 && (ZD[1].mzb & 2));
    RAM[0xa3] = 0x40; input[2] = 0;
    UpdateZapper(1, input, 0);
    input[0] = 88; FCEU_ZapperResetMeasurement();
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 88);
    zapper_operation_wolf_latch = 0;
    input[0] = 188; UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 188);
    /* Strike Wolf uses 4D; release must not change the captured aim. */
    memset(ZD, 0, sizeof(ZD));
    zapper_strike_wolf_latch = 1; RAM[0x4d] = 0;
    input[0] = 64; input[1] = 96; input[2] = 1;
    UpdateZapper(1, input, 0);
    RAM[0x4d] = 1; input[0] = 224; input[2] = 0;
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 64 && ZD[1].mzy == 96 && !ZD[1].bogo);
    input[0] = 12; UpdateZapper(0, input, 0);
    input[0] = 212; UpdateZapper(0, input, 0);
    assert(ZD[0].mzx == 212);
    RAM[0x4d] = 0; UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 212);
    RAM[0x4d] = 1; input[0] = 32; UpdateZapper(1, input, 0);
    input[0] = 132; FCEU_ZapperResetMeasurement();
    UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 132);
    zapper_strike_wolf_latch = 0;
    input[0] = 232; UpdateZapper(1, input, 0);
    assert(ZD[1].mzx == 232);
    puts("Measurement latch: trigger, movement, release, offscreen, secondary weapon, state reset, expiry, other gun and disabled option passed.");
    return 0;
}
