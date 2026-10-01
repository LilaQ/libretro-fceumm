#!/usr/bin/env python3
"""Optional USA precision-patch integration probe; no ROM is distributed.
Usage: python3 tests/mechanized_aim.py /path/to/diagnostic-core.dylib /path/to/patched.nes
For shot-coordinate logging, temporarily insert the following before b1 = RdMem(_PC)
in X6502_Run (include stdio.h), build the diagnostic core, then restore the source:
    if (_PC == 0xd568) fprintf(stderr, "MEASURE x=%u y=%u\\n", RAM[0x4e7], RAM[0x4e6]);
Compare each MEASURE with the most recent INPUT whose frame is divisible by 20.
Subtract the eight cropped top rows from measured Y. Each sweep fires 180 shots.
The probe holds player health/ammo constant to keep a long measurement run active.
"""
import ctypes as C, sys, json, zlib
from pathlib import Path
core_path,rom=sys.argv[1:3]
core='FCEUmm'
scan='disabled'
shoot=False;aim_x=1;aim_y=13000
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
variables={b'nestopia_zapper_device':b'lightgun',b'fceumm_zapper_mode':b'lightgun'}

variables.update({b'fceumm_zapper_mode':b'clightgun', b'fceumm_region':b'NTSC',
 b'fceumm_overscan_v_top':b'8', b'fceumm_overscan_v_bottom':b'8',
 b'fceumm_nospritelimit':b'disabled', b'fceumm_overclocking':b'disabled',
 b'fceumm_ramstate':b'fill $ff'})
variables[b'fceumm_zapper_scanline_mode']=scan.encode()
variables[b'fceumm_zapper_hold_trigger']=b'enabled'
variables[b'fceumm_zapper_tolerance']=b'0'
variables[b'fceumm_zapper_mechanized_latch']=b'enabled'
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
 if cmd in (1,11,18,32,35,36,37,44,53):return True
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
 for frame in range(4000):lib.retro_run()
 lib.retro_serialize_size.restype=C.c_size_t;lib.retro_serialize.argtypes=[C.c_void_p,C.c_size_t];lib.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t]
 size=lib.retro_serialize_size();state=C.create_string_buffer(size);lib.retro_serialize(state,size)
 for mode in ('stationary','moving'):
  lib.retro_unserialize(state,size);lib.FCEU_InitZapper(1)
  ptr=C.cast(lib.retro_get_memory_data(2),C.POINTER(C.c_uint8))
  for i in range(3600):
   # Prevent game-over in this measurement soak, without changing shot code.
   ptr[0x5f0]=9;ptr[0x5f1]=32;ptr[0x5f2]=9;ptr[0x5f3]=40
   x=128 if mode=='stationary' else 128+round(80*__import__('math').sin(i/20))
   y=130 if mode=='stationary' else 130+round(60*__import__('math').sin(i/33))
   aim_x=round(x*65534/256-32767);aim_y=round(y*65534/224-32767)
   print('INPUT',mode,i,x,y,ptr[0x508],flush=True)
   shoot=i%20<5;lib.retro_run()
 lib.retro_unload_game()
lib.retro_deinit()
print(json.dumps({'rom':Path(rom).name,'core':info.name.decode(),'version':info.version.decode(),'loaded':loaded,'frames':frames,'distinct_sampled_frames':len(hashes)}))
sys.exit(0 if loaded and frames>=300 else 1)
