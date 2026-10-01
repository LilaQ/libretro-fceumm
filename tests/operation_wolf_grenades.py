#!/usr/bin/env python3
"""RMB-only grenade integration test with a legally obtained USA ROM patch.
Usage: python3 tests/operation_wolf_grenades.py CORE PATCHED_ROM
Port 1 receives NES B only; the Zapper trigger stays released in the level.
"""
import ctypes as C, sys, json, zlib
from pathlib import Path
core_path,rom=sys.argv[1:3]
core='Nestopia' if 'nestopia' in core_path else 'FCEUmm'
scan='disabled'
grenade=False;shoot=False;aim_x=1;aim_y=13000
lib=C.CDLL(str(Path(core_path).resolve()))
class Variable(C.Structure):_fields_=[('key',C.c_char_p),('value',C.c_char_p)]
class GameInfo(C.Structure):_fields_=[('path',C.c_char_p),('data',C.c_void_p),('size',C.c_size_t),('meta',C.c_char_p)]
class SysInfo(C.Structure):_fields_=[('name',C.c_char_p),('version',C.c_char_p),('ext',C.c_char_p),('fullpath',C.c_bool),('block_extract',C.c_bool)]
ENV=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
VIDEO=C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t)
AUDIO=C.CFUNCTYPE(None,C.c_int16,C.c_int16)
BATCH=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)
POLL=C.CFUNCTYPE(None)
INPUT=C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
variables={b'nestopia_zapper_device':b'lightgun', b'nestopia_overscan_v_top':b'8', b'nestopia_overscan_v_bottom':b'8',b'fceumm_zapper_mode':b'lightgun'}

variables.update({b'fceumm_zapper_mode':b'clightgun', b'fceumm_region':b'NTSC',
 b'fceumm_overscan_v_top':b'8', b'fceumm_overscan_v_bottom':b'8',
 b'fceumm_nospritelimit':b'disabled', b'fceumm_overclocking':b'disabled',
 b'fceumm_ramstate':b'fill $ff'})
variables[b'fceumm_zapper_scanline_mode']=scan.encode()
variables[b'fceumm_zapper_hold_trigger']=b'enabled'
variables[b'fceumm_zapper_tolerance']=b'0'
variables[b'fceumm_zapper_operation_wolf_latch']=sys.argv[3].encode() if len(sys.argv)>3 else b'enabled'
import tempfile
test_directory=tempfile.TemporaryDirectory();directory=test_directory.name.encode()
frames=0;hashes=set();frame=0;pixel=0
@ENV
def env(cmd,data):
 global pixel
 if cmd in (9,30,31):C.cast(data,C.POINTER(C.c_char_p))[0]=directory;return True
 if cmd==10:pixel=C.cast(data,C.POINTER(C.c_int))[0];return True
 if cmd==15:
  var=C.cast(data,C.POINTER(Variable)).contents
  var.value=variables.get(var.key)
  return var.value is not None
 if cmd==16:
  vs=C.cast(data,C.POINTER(Variable));i=0
  while vs[i].key:
   variables.setdefault(vs[i].key,vs[i].value.split(b'; ',1)[-1].split(b'|')[0]);i+=1
  return True
 if cmd in (17,39):C.cast(data,C.POINTER(C.c_bool))[0]=False;return True
 if cmd==52:C.cast(data,C.POINTER(C.c_uint))[0]=0;return True
 if cmd==3:C.cast(data,C.POINTER(C.c_bool))[0]=True;return True
 if cmd in (1,11,18,32,35,36,44,53):return True
 return False
@VIDEO
def video(data,w,h,pitch):
 global frames
 frames+=1
 if data and frames%30==0:hashes.add(zlib.crc32(C.string_at(data,pitch*h)))
@AUDIO
def audio(a,b):pass
@BATCH
def batch(data,n):return n
@POLL
def poll():pass
@INPUT
def inp(port,device,index,key):
 if device==1 and port==0 and grenade and key in (0,256):return 1
 # Press/release START to pass an ordinary title screen; no file or OS input.
 if device==4 and port==1 and key==13:return aim_x
 if device==4 and port==1 and key==14:return aim_y
 if device==4 and port==1 and key==2 and (any(a<=frame<a+5 for a in (500,1500,2500)) or shoot):return 1
 return 0
for name,callback in [('environment',env),('video_refresh',video),('audio_sample',audio),('audio_sample_batch',batch),('input_poll',poll),('input_state',inp)]:
 fn=getattr(lib,'retro_set_'+name);fn.argtypes=[type(callback)];fn(callback)
lib.retro_init()
info=SysInfo();lib.retro_get_system_info.argtypes=[C.POINTER(SysInfo)];lib.retro_get_system_info(C.byref(info))
data=Path(rom).read_bytes();buf=C.create_string_buffer(data)
game=GameInfo(str(Path(rom).resolve()).encode(),C.cast(buf,C.c_void_p),len(data),None)
lib.retro_load_game.argtypes=[C.POINTER(GameInfo)];lib.retro_load_game.restype=C.c_bool
loaded=lib.retro_load_game(C.byref(game))
lib.retro_set_controller_port_device.argtypes=[C.c_uint,C.c_uint]
if loaded:
 lib.retro_set_controller_port_device(0,1)
 if 'Space Shadow' in rom:
  lib.retro_set_controller_port_device(1,1);lib.retro_set_controller_port_device(4,1282)
 else:lib.retro_set_controller_port_device(1,262 if core=='Nestopia' else 258)
 lib.retro_get_memory_data.argtypes=[C.c_uint];lib.retro_get_memory_data.restype=C.c_void_p
 for frame in range(2500):lib.retro_run()
 lib.retro_serialize_size.restype=C.c_size_t;lib.retro_serialize.argtypes=[C.c_void_p,C.c_size_t];lib.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t]
 size=lib.retro_serialize_size();state=C.create_string_buffer(size);lib.retro_serialize(state,size)
 ptr=C.cast(lib.retro_get_memory_data(2),C.POINTER(C.c_uint8))
 assert ptr[0x18]==3, 'Probe must run in the active level, not the continue screen'
 assert ptr[0x53]==5
 for i in range(150):
  grenade=60<=i<100 or 120<=i<130;shoot=False
  lib.retro_run()
  if i in (99,130):assert ptr[0x53]==(4 if i==99 else 3), (i,ptr[0x53])
 print('RMB-only grenades: held press, release and second press passed (5 -> 4 -> 3).')
 lib.retro_unload_game()
lib.retro_deinit()
