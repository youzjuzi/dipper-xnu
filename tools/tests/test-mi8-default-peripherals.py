#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native Bluetooth default dependency and loader peripheral admission checks."""
import argparse
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tree',type=Path,default=ROOT/'work');a=p.parse_args()
 body=runpy.run_path(str(ROOT/'tools/tests/test-mi8-audio-smmu.py'))['body']
 bt=(a.tree/'hackios/xnu-src/xnu-8796.121.2/bsd/dev/mi8_bt.c').read_text();loader=(a.tree/'hackios/xnuloader/loader.c').read_text()
 assert 'loader_peripheral_requested(pi.cmdline,"battery",PLAT==&platform_dipper,1)' in loader
 assert 'loader_peripheral_requested(pi.cmdline,"torch",PLAT==&platform_dipper,0)' in loader
 code=r'''#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef unsigned thread_t;
#define KERN_SUCCESS 0
static unsigned steps,radio,started,deallocated;
static bool from_default,mac;
static char message[128];
static bool PE_parse_boot_argn(const char *s,void *out,unsigned n){
 (void)n;if(!strcmp(s,"wifi_mac"))return mac;
 if(!strcmp(s,"bt")){if(out)*(unsigned*)out=steps;return true;}
 if(!strcmp(s,"mi8rp_mss")){if(out)*(unsigned*)out=radio;return true;}
 return false;
}
static bool PE_boot_arg_is_default(const char *s){assert(!strcmp(s,"bt"));return from_default;}
static void bt_thread(void *p){(void)p;assert(0);}
static int kernel_thread_start(void(*fn)(void*),void *arg,thread_t *t){assert(fn==bt_thread&&(uintptr_t)arg==steps);started++;*t=1;return 0;}
static void thread_deallocate(thread_t t){assert(t==1);deallocated++;}
static int capture(const char *s){snprintf(message,sizeof(message),"%s",s);return 0;}
#define printf capture
static int starts_with(const char *s,const char *p){return !strncmp(s,p,strlen(p));}
'''+body(bt,'void\nmi8_bt_init(')+'\n'+body(loader,'static int loader_peripheral_requested(')+r'''
#undef printf
int main(void){
 unsigned count=0;
 for(unsigned d=0;d<2;d++)for(unsigned r=0;r<2;r++)for(unsigned m=0;m<2;m++)for(unsigned n=0;n<=7;n++){
  from_default=d;radio=r?6:0;mac=m;steps=n;started=deallocated=0;message[0]=0;mi8_bt_init();
  bool launch=n && (!d || (r&&m));assert(started==launch&&deallocated==launch);
  if(n&&d&&(!r||!m))assert(!strcmp(message,"bt: default skipped: needs Wi-Fi side (wifi_mac/mi8rp_mss)\n"));else assert(!message[0]);count++;
 }
 for(unsigned def=0;def<2;def++){
  assert(loader_peripheral_requested("","battery",def,1)==(int)def);
  assert(loader_peripheral_requested("","torch",def,0)==(int)def);
  assert(!loader_peripheral_requested("battery=0 torch=0","battery",def,1));
  assert(!loader_peripheral_requested("battery=0 torch=0","torch",def,0));
  assert(loader_peripheral_requested("battery=1 torch=3","battery",def,1));
  assert(loader_peripheral_requested("battery=1 torch=3","torch",def,0));
  assert(!loader_peripheral_requested("battery=2","battery",def,1));
  assert(!loader_peripheral_requested("battery=10","battery",def,1));
  assert(loader_peripheral_requested("torch=7","torch",def,0));
  assert(loader_peripheral_requested("not_battery=0","battery",def,1)==(int)def);
 }
 printf("Default peripherals PASS: %u native Bluetooth cases, explicit bt=1..6 preserved; loader battery cache/torch identity defaults, explicit zero and non-dipper isolation\n",count);
}
'''
 with tempfile.TemporaryDirectory(prefix='mi8-default-peripherals-') as tmp:
  d=Path(tmp);(d/'test.c').write_text(code)
  subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-no-pie',str(d/'test.c'),'-o',str(d/'test')],check=True)
  subprocess.run([str(d/'test')],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1'})
if __name__=='__main__':main()
