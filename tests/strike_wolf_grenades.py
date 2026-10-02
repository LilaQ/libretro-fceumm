#!/usr/bin/env python3
"""Optional Strike Wolf fresh grenade-aim integration test; supply your own ROM.
Usage: python3 tests/strike_wolf_aim.py CORE PATCHED_ROM disabled enabled [moving]
Checks forty raster measurements, including movement after the trigger, and a
controller-B grenade press. No diagnostic core instrumentation is required.
"""
import ctypes as C, sys
from pathlib import Path
core_path,rom=sys.argv[1:3]
scan='disabled'
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
variables={}

variables.update({b'fceumm_zapper_mode':b'clightgun', b'fceumm_region':b'NTSC',
 b'fceumm_overscan_v_top':b'8', b'fceumm_overscan_v_bottom':b'8',
 b'fceumm_nospritelimit':b'disabled', b'fceumm_overclocking':b'disabled',
 b'fceumm_ramstate':b'fill $ff'})
variables[b'fceumm_zapper_scanline_mode']=scan.encode()
variables[b'fceumm_zapper_hold_trigger']=b'enabled'
variables[b'fceumm_zapper_tolerance']=b'0'
variables[b'fceumm_zapper_mechanized_latch']=b'disabled'
variables[b'fceumm_zapper_strike_wolf_latch']=sys.argv[4].encode() if len(sys.argv)>4 else b'enabled'
import tempfile
test_directory=tempfile.TemporaryDirectory();directory=test_directory.name.encode()
variables[b'fceumm_nospritelimit']=sys.argv[3].encode()
frame=0;pixel=0
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
def video(data,w,h,pitch):pass
@AUDIO
def audio(a,b):pass
@BATCH
def batch(data,n):return n
@POLL
def poll():pass
aimx=0;aimy=0;fire=False;grenade=False
@INPUT
def inp(port,device,index,key):
 if device==1 and port==0 and key in (0,256) and grenade:return 1
 if device==1 and port==0 and key==3 and 500<=frame<505:return 1
 if device==4 and port==1:
  if key==13:return aimx
  if key==14:return aimy
  if key==2 and (1500<=frame<1505 or fire):return 1
 return 0
for name,callback in [('environment',env),('video_refresh',video),('audio_sample',audio),('audio_sample_batch',batch),('input_poll',poll),('input_state',inp)]:
 fn=getattr(lib,'retro_set_'+name);fn.argtypes=[type(callback)];fn(callback)
lib.retro_init()
info=SysInfo();lib.retro_get_system_info.argtypes=[C.POINTER(SysInfo)];lib.retro_get_system_info(C.byref(info))
data=Path(rom).read_bytes();buf=C.create_string_buffer(data)
game=GameInfo(str(Path(rom).resolve()).encode(),C.cast(buf,C.c_void_p),len(data),None)
lib.retro_load_game.argtypes=[C.POINTER(GameInfo)];lib.retro_load_game.restype=C.c_bool
loaded=lib.retro_load_game(C.byref(game));assert loaded
lib.retro_set_controller_port_device.argtypes=[C.c_uint,C.c_uint]
if loaded:
 lib.retro_set_controller_port_device(0,1)
 lib.retro_set_controller_port_device(1,258)
 lib.retro_get_memory_data.argtypes=[C.c_uint];lib.retro_get_memory_data.restype=C.c_void_p
 for frame in range(2600):lib.retro_run()
 lib.retro_serialize_size.restype=C.c_size_t;lib.retro_serialize.argtypes=[C.c_void_p,C.c_size_t];lib.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t]
 size=lib.retro_serialize_size();state=C.create_string_buffer(size);assert lib.retro_serialize(state,size)
 ptr=C.cast(lib.retro_get_memory_data(2),C.POINTER(C.c_uint8))
 for y in (35,65,95,125,155):
  for x in (16,48,80,112,144,176,208,240):
   assert lib.retro_unserialize(state,size)
   lib.FCEU_InitZapper(1)
   grenade=False
   aimx=round(x*65534/256-32767);aimy=round(y*65534/224-32767)
   got=False;before=ptr[0x669]
   for i in range(90):
    fire=False;grenade=i<5
    if len(sys.argv)>5 and sys.argv[5]=='moving' and i>0:
     aimx=round(min(250,x+i*32)*65534/256-32767);aimy=round(min(180,y+i*16)*65534/224-32767)
    lib.retro_run()
    if ptr[0x669]==before-1 and not ptr[0x4d] and any(ptr[0xb2+j]==0x70 for j in range(10)):
     j=next(j for j in range(10) if ptr[0xb2+j]==0x70)
     px=(ptr[0xe3+j]+16)&255;py=(ptr[0xed+j]+16)&255
     assert abs(px-x)<=8 and abs(py-(y+8))<=8, (x,y,px,py)
     assert not ptr[0x90], 'unexpected bullet flag'
     got=True;break
   assert got, ('NO SHOT',x,y)
 assert lib.retro_unserialize(state,size)
 lib.FCEU_InitZapper(1)
 before=ptr[0x669];aimx=0;aimy=0
 for i in range(70):
  grenade=i<60;fire=False;lib.retro_run()
 assert ptr[0x669]==before-1, 'held RMB repeated grenade'
 for i in range(70):
  grenade=i<60;lib.retro_run()
 assert ptr[0x669]==before-2, 'second press failed'
 # Controller-only aiming must keep its existing cell without a gun scan.
 assert lib.retro_unserialize(state,size)
 lib.FCEU_InitZapper(1)
 ptr[0xaa]=0;ptr[0x48]=12;ptr[0x4a]=10
 before=ptr[0x669]
 for i in range(70):
  grenade=i<5;lib.retro_run()
 assert ptr[0x669]==before-1 and ptr[0x48]==12 and ptr[0x4a]==10
 print('Forty fresh-aim grenades, held RMB, second press and controller mode passed.')
 lib.retro_unload_game()
lib.retro_deinit()
