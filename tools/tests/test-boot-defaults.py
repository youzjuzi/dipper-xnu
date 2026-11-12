#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the actual ARM boot-default code and XNU parser against host DT stubs."""
import argparse
import ctypes
import json
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--tree', type=Path, default=ROOT / 'work/hackios/xnu-src/xnu-8796.121.2')
p.add_argument('--old-cmdline', type=Path)
p.add_argument('--package-cmdline', type=Path, help='verify a private package uses all seven platform defaults; never print its MAC')
a = p.parse_args()
x = a.tree.resolve()
source = (x / 'pexpert/arm/pe_bootargs.c').read_text()
entries = re.findall(r'\{ "([^"]+)", "([^"]+)" \}', source)
assert len(entries) == 34
measure = 'taskload touch_lat mi8_cpuclk perfprof fprof loader_return_after'.split()
retained = 'bootcpu=7 cpus=7 ufs=2 root_apfs=ufs_darwin epoch=1793436756 wifi_mac=00:00:00:00:00:00'
# Independent complete reference profile: do not derive expected values from the table.
reference = (retained + ' '
    'fts=1 fts_steps=6 fts_raw=0 buttons=1 buttons_steps=5 '
    'gpu=1 mi8gpu_gmuclk=1 mi8gpu_zap_keep=1 caenv=FD_MESA_DEBUG=sysmem '
    'fb_partial=0 fb_flip=1 fb_native=1 sb_fps_clamp=1 '
    'mi8rp_mss=6 mi8rp_hold=90 mi8rp_svc=1 mi8rp_servreg=1 mi8rp_wlfw=1 '
    'mi8rp_bdf=1 mi8rp_wsmmu=3 mi8rp_lx=1 mi8rp_lxirq=1 '
    'wifi_lx=2 wifi_station=1 wifi_quiet=1 thermgov=66 ffix=1 '
    'bt=7 audio=5 audio_level_db=0 audio_seconds=0 battery=1 torch=3 haptic=3 '
    'taskload=500 touch_lat=1 mi8_cpuclk=10 perfprof=1 fprof=1000 loader_return_after=360')
old = a.old_cmdline.read_text().strip() if a.old_cmdline else reference
old = re.sub(r'wifi_mac=[^\s]+', 'wifi_mac=00:00:00:00:00:00', old)
keys = [t.split('=',1)[0] for t in old.split()]
bench = ' '.join(t for t in old.split() if t.split('=',1)[0] not in dict(entries))
daily = ' '.join(t for t in bench.split() if t.split('=',1)[0] not in measure)
# Include a separating byte in addition to the specified worst loader prefix.
assert len(bench.encode()) + 80 < 600
checks = 0

def check(value):
    global checks
    assert value
    checks += 1

with tempfile.TemporaryDirectory(prefix='boot-defaults-') as tmp:
    d = Path(tmp)
    (d/'pexpert').mkdir()
    (d/'pexpert/pexpert.h').write_text('''#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
#undef __x86_64__
#define int64_t long long
#define strlcpy test_strlcpy
#define strlcat test_strlcat
typedef int boolean_t;
#define TRUE 1
#define FALSE 0
#define PE_BOOT_ARGS_MAX 2048
#define BOOT_LINE_LENGTH 608
struct { void *bootArgs; } PE_state;
char *PE_boot_args(void);
boolean_t PE_parse_boot_argn(const char *, void *, int);
boolean_t PE_parse_boot_arg_str(const char *, char *, int);
static size_t strlcpy(char *d, const char *s, size_t n) { size_t z=strlen(s); if(n) { size_t k=z<n-1?z:n-1; memcpy(d,s,k); d[k]=0; } return z; }
static size_t strlcat(char *d, const char *s, size_t n) { size_t z=strlen(d); return z+strlcpy(d+z,s,n-z); }
#define panic(...) abort()
static char captured[4096];
static int capture_printf(const char *fmt, ...) { va_list a; va_start(a,fmt); int n=vsnprintf(captured,sizeof(captured),fmt,a); va_end(a); return n; }
#define printf capture_printf
''')
    (d/'pexpert/boot.h').write_text('typedef struct { char CommandLine[608]; } boot_args;\n')
    (d/'pexpert/device_tree.h').write_text('''#pragma once
typedef void *DTEntry;
#define kSuccess 0
static const char *platform;
static unsigned type_size;
static int SecureDTLookupEntry(DTEntry unused, const char *path, DTEntry *out) { (void)unused; *out=(void*)1; return strcmp(path,"/arm-io")==0 && platform ? 0 : -1; }
static int SecureDTGetProperty(DTEntry entry, const char *name, const void **out, unsigned *size) { (void)entry; if(strcmp(name,"device_type")) return -1; *out=platform; *size=type_size; return 0; }
static int IODTGetDefault(const char *k, void *p, unsigned n) { (void)k; (void)p; (void)n; return -1; }
''')
    c = '#include '+json.dumps(str(x/'pexpert/arm/pe_bootargs.c'))+'\n#include '+json.dumps(str(x/'pexpert/gen/bootargs.c'))+'\n'
    c += '''static boot_args input;
void reset(const char *raw, const char *plat, unsigned size, int init) {
 assert(strlen(raw)<sizeof(input.CommandLine));
 strlcpy(input.CommandLine,raw,sizeof(input.CommandLine));
 PE_state.bootArgs=&input; platform=plat; type_size=size;
 dipper_args_ready=0; memset(default_used,0,sizeof(default_used));
 memset(effective_args,0,sizeof(effective_args)); captured[0]=0;
 if(init) PE_init_boot_defaults();
}
const char *log_line(void) { PE_log_boot_defaults(); return captured; }
const char *raw_input(void) { return input.CommandLine; }
'''
    (d/'test.c').write_text(c)
    subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(d),str(d/'test.c'),'-o',str(d/'test.so')],check=True)
    lib=ctypes.CDLL(str(d/'test.so'))
    lib.reset.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint,ctypes.c_int]
    for name in ['PE_boot_args','log_line','raw_input']:
        getattr(lib,name).restype=ctypes.c_char_p
    lib.PE_boot_arg_is_default.argtypes=[ctypes.c_char_p]
    lib.PE_parse_boot_argn.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_int]
    lib.PE_parse_boot_arg_str.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_int]
    def reset(raw, plat=b'dipper', init=1, size=None):
        lib.reset(raw.encode(),plat,len(plat)+1 if size is None and plat else (size or 0),init)
    def snapshot(names):
        out={}
        for name in names:
            # Compare parser return value and all output bytes, not a Python reimplementation.
            for n in [0,1,2,3,4,8,128]:
                for func in ['PE_parse_boot_argn','PE_parse_boot_arg_str']:
                    b=ctypes.create_string_buffer(b'Z'*128,129)
                    found=getattr(lib,func)(name.encode(),b,n)
                    out[(name,n,func)]=(found,b.raw)
        return out
    prefix = 'debug=0x8 rd=md0 vtimer_intid=19 hv_wdt_pet=1 ufs_shared_pa=0x' + 'f'*16 + ' '
    check(len(prefix) <= 80)
    added={'bt','audio','audio_level_db','audio_seconds','battery','torch','haptic'}
    prefix_old=' '.join(t for t in old.split() if t.split('=',1)[0] not in added)
    prefix_keys=[k for k in keys if k not in added]+['debug','rd','vtimer_intid','hv_wdt_pet','ufs_shared_pa']
    reset(prefix+prefix_old,init=0); prefixed_before=snapshot(prefix_keys)
    reset(prefix+bench);check(snapshot(prefix_keys)==prefixed_before)
    reset(daily)
    for key in measure: check(not lib.PE_parse_boot_argn(key.encode(),None,0))
    reset(old,init=0); before=snapshot(keys)
    reset(bench); check(snapshot(keys)==before)
    check(lib.raw_input()==bench.encode())
    check(len(lib.PE_boot_args())<1023) # existing userland consumer buffers
    line=lib.log_line(); check(b'wifi_mac=set(arg)' in line and b'00:00:00:00:00:00' not in line)
    for k,v in entries: check((k+'='+v+'(def)').encode() in line);check(lib.PE_boot_arg_is_default(k.encode()))
    reset(old); check(snapshot(keys)==before)
    line=lib.log_line()
    for k,v in entries:
        check((k+'='+v+('(arg)' if k in keys else '(def)')).encode() in line)
        check(bool(lib.PE_boot_arg_is_default(k.encode()))==(k not in keys))
    for platform in [b'redwood',b'qemu-virt',None,b'dipper-extra',b'Dipper']:
        for raw in ['',old,'fb_native=0\tfts=0  unknown=9']:
            reset(raw,platform,init=0); before=snapshot(keys+['unknown'])
            reset(raw,platform); check(snapshot(keys+['unknown'])==before)
            check(lib.PE_boot_args()==raw.encode());check(lib.log_line()==b'')
    for size in [0,3,6,8]:
        reset('',size=size);check(lib.PE_boot_args()==b'')
    for k,v in entries:
        for override in ['0','2','0x1'] if k!='caenv' else ['0','FD_MESA_DEBUG=other']:
            raw=k+'='+override
            reset(raw,init=0);before=snapshot([k])
            reset(raw);check(snapshot([k])==before)
            check((k+'='+override+'(arg)').encode() in lib.log_line())
    for raw in ['audio_level_db=-30','bt=0 audio=0 battery=0 torch=0 haptic=0','fb_native=1 fb_native=0','fb_native=0 fb_native=1','\tfts=0\tfts_steps=0','caenv=A=1 caenv=B=2']:
        reset(raw,init=0);before=snapshot([t.split('=')[0] for t in raw.split()])
        reset(raw);check(snapshot([t.split('=')[0] for t in raw.split()])==before)
    reset('x='+'a'*605);check(len(lib.PE_boot_args())<2048);check(lib.raw_input()==('x='+'a'*605).encode())
    saved=lib.PE_boot_args();lib.PE_init_boot_defaults();check(lib.PE_boot_args()==saved)
    spec=importlib.util.spec_from_file_location('packager', ROOT/'tools/build/build-payload.py')
    packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
    for wifi in [None,'00:00:00:00:00:00']:
        for no_audio in [False,True]:
            raw=packager.build_cmdline(300,1793436756,wifi,no_audio=no_audio)
            check(('audio=0' in raw)==no_audio)
            check(('bt=' in raw)==(wifi is None))
            check('audio_seconds' not in raw and 'audio_level_db' not in raw)
            check(len(raw)+116<600)
            reset(raw)
            check(lib.PE_parse_boot_argn(b'wifi_mac',None,0)==(wifi is not None))
            for key,expected in [('mi8rp_mss',6),('wifi_lx',2),('wifi_station',1)]:
                v=ctypes.c_uint32(99)
                lib.PE_parse_boot_argn(key.encode(),ctypes.byref(v),4)
                check(v.value==(expected if wifi is not None else 0))
            for key,expected in [('bt',7 if wifi else 0),('audio',0 if no_audio else 5),('audio_level_db',0),('audio_seconds',0),('battery',1),('torch',3),('haptic',3)]:
                v=ctypes.c_int32(99);check(lib.PE_parse_boot_argn(key.encode(),ctypes.byref(v),4));check(v.value==expected)
                if wifi and not no_audio:check((key+'='+str(expected)+'(def)').encode() in lib.log_line())
            check(raw==packager.build_cmdline(300,1793436756,wifi,True,bluetooth=True,no_audio=no_audio))
    if a.package_cmdline:
        raw=a.package_cmdline.read_text().strip()
        check(len(raw.encode())+80<600 and len(raw.encode())+116<608)
        check(not any(t.split('=',1)[0] in {'bt','audio','audio_level_db','audio_seconds','battery','torch','haptic'} for t in raw.split()))
        reset(raw)
        for key,expected in [('bt',7),('audio',5),('audio_level_db',0),('audio_seconds',0),('battery',1),('torch',3),('haptic',3)]:
            v=ctypes.c_int32(99);check(lib.PE_parse_boot_argn(key.encode(),ctypes.byref(v),4));check(v.value==expected)
            check((key+'='+str(expected)+'(def)').encode() in lib.log_line())
    for wifi in [None,'00:00:00:00:00:00']:
        plain=packager.build_cmdline(300,1793436756,wifi,True)
        raw=packager.build_cmdline(300,1793436756,wifi,True,True)
        check(raw.startswith(plain)and raw[len(plain):]==' ufs_write=1 var_store=1 var_save_ms=120000')
        check(len(raw)+116<600)
        check('ufs_write' not in plain and 'var_store' not in plain)
        reset(raw)
        for key in ['ufs_write','var_store']:
            v=ctypes.c_uint32(99);lib.PE_parse_boot_argn(key.encode(),ctypes.byref(v),4);check(v.value==1)
        v=ctypes.c_uint32(0);lib.PE_parse_boot_argn(b'var_save_ms',ctypes.byref(v),4);check(v.value==120000)

print(json.dumps({'status':'PASS_HOST_ONLY','assertions':checks,'defaults':len(entries),'daily_bytes':len(daily),'bench_bytes':len(bench),'prefix_budget_including_separator':80,'bench_total':len(bench)+80,'strict_limit_additional_bytes':599-len(bench)-80},indent=2))
