#!/usr/bin/env python3
"""Test independent Zapper wiring and held triggers with a generated NROM image.

Usage: python3 tests/zapper_input.py /path/to/fceumm_libretro.so
The same command accepts a .dylib or .dll on its native platform.
"""

import ctypes as C
from pathlib import Path
import sys
import tempfile


class Variable(C.Structure):
    _fields_ = [('key', C.c_char_p), ('value', C.c_char_p)]


class GameInfo(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p),
                ('size', C.c_size_t), ('meta', C.c_char_p)]


def make_rom():
    # Poll both input registers into RAM; no copyrighted game data.
    prg = bytearray(32768)
    code = bytes.fromhex('78 d8 a2 ff 9a a9 01 8d 16 40 a9 00 8d 16 40 8d 03 06 a2 08 ad 16 40 4a 6e 03 06 ca d0 f6 ad 03 06 8d 02 06 ad 16 40 8d 00 06 ad 17 40 8d 01 06 4c 05 80')
    prg[:len(code)] = code
    prg[-6:] = bytes.fromhex('00 80 00 80 00 80')
    return b'NES\x1a' + bytes([2, 0]) + bytes(10) + prg


def run(core_path):
    lib = C.CDLL(str(Path(core_path).resolve()))
    variables = {b'fceumm_ramstate': b'fill $00'}
    failures = []
    frame = 0
    held_port = 0
    menu_key = 3
    with tempfile.TemporaryDirectory(prefix='zapper-input-') as directory:
        encoded_directory = directory.encode()

        @C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
        def environment(command, data):
            if command in (9, 30, 31):  # system, assets, save directories
                C.cast(data, C.POINTER(C.c_char_p))[0] = encoded_directory
                return True
            if command == 3:  # GET_CAN_DUPE
                C.cast(data, C.POINTER(C.c_bool))[0] = True
                return True
            if command == 15:  # GET_VARIABLE
                var = C.cast(data, C.POINTER(Variable)).contents
                var.value = variables.get(var.key)
                return var.value is not None
            if command == 16:  # SET_VARIABLES (legacy options)
                entries = C.cast(data, C.POINTER(Variable))
                i = 0
                while entries[i].key:
                    default = entries[i].value.split(b'; ', 1)[-1].split(b'|')[0]
                    variables.setdefault(entries[i].key, default)
                    i += 1
                return True
            if command == 17:  # GET_VARIABLE_UPDATE
                C.cast(data, C.POINTER(C.c_bool))[0] = False
                return True
            if command == 52:  # GET_CORE_OPTIONS_VERSION
                C.cast(data, C.POINTER(C.c_uint))[0] = 0
                return True
            return command in (10, 11, 18, 32, 35, 36, 37, 44)

        callbacks = {
            'environment': environment,
            'video_refresh': C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint,
                                        C.c_size_t)(lambda *_: None),
            'audio_sample': C.CFUNCTYPE(None, C.c_int16, C.c_int16)(lambda *_: None),
            'audio_sample_batch': C.CFUNCTYPE(C.c_size_t, C.c_void_p,
                                            C.c_size_t)(lambda _, count: count),
            'input_poll': C.CFUNCTYPE(None)(lambda: None),
            'input_state': C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint,
                                      C.c_uint)(lambda port, device, index, key:
                        int(device == 4 and 10 <= frame < 40 and
                            ((key == 2 and port == held_port) or
                             (key == menu_key and port == held_port)))),
        }
        for name, callback in callbacks.items():
            setter = getattr(lib, 'retro_set_' + name)
            setter.argtypes = [type(callback)]
            setter(callback)
        lib.retro_load_game.argtypes = [C.POINTER(GameInfo)]
        lib.retro_load_game.restype = C.c_bool
        lib.retro_get_memory_data.argtypes = [C.c_uint]
        lib.retro_get_memory_data.restype = C.c_void_p
        lib.retro_get_memory_size.argtypes = [C.c_uint]
        lib.retro_get_memory_size.restype = C.c_size_t
        lib.retro_init()
        try:
            lib.retro_set_controller_port_device.argtypes = [C.c_uint, C.c_uint]
            for dual in (False, True):
                for hold in (False, True):
                    variables[b'fceumm_zapper_famicom_dual'] = b'enabled' if dual else b'disabled'
                    variables[b'fceumm_zapper_hold_trigger'] = b'enabled' if hold else b'disabled'
                    variables[b'fceumm_zapper_mode'] = b'clightgun'
                    for held_port in (0, 1):
                        menu_key = 3 if held_port == 0 else 6
                        rom = make_rom()
                        path = Path(directory) / 'test.nes'
                        path.write_bytes(rom)
                        buf = C.create_string_buffer(rom)
                        info = GameInfo(str(path).encode(), C.cast(buf, C.c_void_p), len(rom), None)
                        assert lib.retro_load_game(C.byref(info))
                        try:
                            for port in (0, 1):
                                lib.retro_set_controller_port_device(port, 258)
                            for frame in range(45):
                                lib.retro_run()
                                if frame not in (12, 30, 42):
                                    continue
                                ram = C.string_at(lib.retro_get_memory_data(2) + 0x600, 3)
                                active = frame == 12 or (hold and frame == 30)
                                expected = [0, 0]
                                if active:
                                    expected[held_port] = 0x10
                                    if dual and held_port == 0:
                                        expected[1] |= 0x04
                                actual = [ram[0] & 0x10, ram[1] & 0x14]
                                assert actual == expected, (dual, hold, held_port, frame, actual, expected)
                                expected_menu = (4 if menu_key == 3 else 8) if dual and frame < 40 else 0
                                assert ram[2] == expected_menu, (dual, frame, ram[2], expected_menu)
                            # With rendering disabled both sensors must report darkness.
                            assert ram[1] & 8
                            if dual:
                                assert ram[1] & 2
                            print(f'dual={dual} hold={hold} gun={held_port}: pulse, hold, release, sensor and menu serial bits passed')
                        finally:
                            lib.retro_unload_game()
        finally:
            lib.retro_deinit()
    if failures:
        raise SystemExit('\n'.join(failures))
    print('All Zapper input checks passed.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    run(sys.argv[1])
