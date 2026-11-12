#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract the native panic hook/configuration and test its MMIO and one-shot gates."""
import argparse
from pathlib import Path
import runpy
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tree',type=Path,default=ROOT/'work')
    a=ap.parse_args();x=a.tree/'hackios/xnu-src/xnu-8796.121.2'
    body=runpy.run_path(str(ROOT/'tools/tests/test-mi8-audio-smmu.py'))['body']
    source=(x/'bsd/dev/mi8_tas2557.c').read_text()
    pieces='\n'.join(body(source,sig) for sig in ['static bool amp_panic_reset(', 'static void amp_panic_callout(', 'static void amp_panic_bind(', 'static void session_panic_configure(', 'static void native_write(', 'void mi8_tas_session_panic_tick('])
    primitive=body(source,'static bool amp_panic_reset(')
    callback=body(source,'static void amp_panic_callout(')
    assert primitive.count('*panic_reset=0;')==1
    for forbidden in ['printf(', 'native_log(', 'alloc(', 'delay_', 'sleep', 'ml_io_map(', 'lock(', 'transfer(', 'read_regs(']:
        assert forbidden not in primitive+callback,forbidden
    assert 'amp_panic_bind(' not in body(source,'void mi8_tas2557_probe(')
    for fn in ['mi8_tas2557_prepare','mi8_tas2557_prepare_tone','mi8_tas2557_prepare_clip','mi8_tas_session_start']:
        assert 'amp_panic_bind(' in body(source,'void '+fn+'(')
    kdp=(x/'osfmk/kdp/kdp_callout.h').read_text();debug=(x/'osfmk/kern/debug.c').read_text()
    assert 'processors other than the callout processor quiesced' in kdp
    assert 'kdp_callouts(KDP_EVENT_PANICLOG);' in debug
    assert 'DebuggerHaltOtherCores' in debug
    debug_putc=body(debug,'void\ndebug_putc(')
    assert '*debug_buf_ptr = c;' in debug_putc and 'lock' not in debug_putc
    # Only the architecture barrier changes in the host translation unit.
    assert pieces.count('__asm__ volatile("dsb sy":::"memory");')==2
    pieces=pieces.replace('__asm__ volatile("dsb sy":::"memory");','__sync_synchronize();')
    code=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <setjmp.h>
#include "mi8_tas2557.h"
#define SA(p) __atomic_load_n(&(p),__ATOMIC_ACQUIRE)
#define SP(p,v) __atomic_store_n(&(p),(v),__ATOMIC_RELEASE)
#define PIN(n) (0x03500000u+0x1000u*(n))
typedef enum {KDP_EVENT_ENTER,KDP_EVENT_EXIT,KDP_EVENT_PANICLOG} kdp_event_t;
static volatile uint32_t reset_cell,other_cell;
static volatile uint32_t *panic_reset;
static unsigned panic_amp_state,panic_test_enabled,registrations,panic_calls,log_calls;
static bool panic_registered;
static struct{unsigned expired;}session;
static struct mi8_amp_snapshot snapshot;
static unsigned audio_arg,request_arg;static bool have_audio,have_request;
static char panic_buffer[128];static unsigned panic_len;
static jmp_buf escape;
static void (*registered)(void *,kdp_event_t);
static uintptr_t address(uint32_t a){return (uintptr_t)(a==PIN(76)+4?&reset_cell:&other_cell);}
static bool PE_parse_boot_argn(const char *name,void *out,unsigned size){assert(size==4);bool found=!strcmp(name,"audio")?have_audio:have_request;if(found)*(uint32_t*)out=!strcmp(name,"audio")?audio_arg:request_arg;return found;}
static void kdp_register_callout(void(*f)(void*,kdp_event_t),void *arg){assert(!arg);registrations++;registered=f;}
void debug_putc(char c){assert(panic_len<sizeof(panic_buffer)-1);panic_buffer[panic_len++]=c;}
void mi8_tas_session_snapshot(struct mi8_amp_snapshot *out){*out=snapshot;}
static void native_log(void *ctx,const char *fmt){assert(!ctx&&!strcmp(fmt,"audio: panic hook armed\n"));log_calls++;}
static void panic(const char *fmt){assert(!strcmp(fmt,"audio panic test"));panic_calls++;registered(NULL,KDP_EVENT_PANICLOG);longjmp(escape,1);}
''' +pieces+r'''
int main(void){
 amp_panic_bind();amp_panic_bind();assert(registrations==1&&panic_registered);
 reset_cell=7;registered(NULL,KDP_EVENT_PANICLOG);assert(reset_cell==7&&!panic_len);
 native_write(NULL,PIN(76)+4,2);assert(reset_cell==2&&panic_amp_state==1);
 registered(NULL,KDP_EVENT_ENTER);registered(NULL,KDP_EVENT_EXIT);assert(reset_cell==2&&!panic_len);
 registered(NULL,KDP_EVENT_PANICLOG);assert(!reset_cell&&panic_amp_state==2&&!strcmp(panic_buffer,"audio: amp reset low (panic)\n"));
 unsigned saved_len=panic_len;reset_cell=7;registered(NULL,KDP_EVENT_PANICLOG);assert(reset_cell==7&&panic_len==saved_len);
 native_write(NULL,PIN(76)+4,2);assert(reset_cell==7); /* latched, no reset-high */
 panic_amp_state=0;panic_len=0;memset(panic_buffer,0,sizeof(panic_buffer));
 native_write(NULL,PIN(76)+4,2);native_write(NULL,PIN(76)+4,0);assert(!panic_amp_state);
 reset_cell=7;registered(NULL,KDP_EVENT_PANICLOG);assert(reset_cell==7&&!panic_len);
 session.expired=1;native_write(NULL,PIN(76)+4,2);assert(reset_cell==7);session.expired=0;
 for(unsigned present=0;present<4;present++)for(unsigned audio=0;audio<=6;audio++)for(unsigned value=0;value<=2;value++){
  have_audio=present&1;have_request=present&2;audio_arg=audio;request_arg=value;
  session_panic_configure();assert(panic_test_enabled==(have_audio&&have_request&&audio==5&&value==1));
 }
 have_audio=have_request=true;audio_arg=5;request_arg=1;session_panic_configure();native_write(NULL,PIN(76)+4,2);
 snapshot=(struct mi8_amp_snapshot){.state=MI8_AMP_LIVE,.wakes=1,.live_start=1000};
 mi8_tas_session_panic_tick(1000999);assert(!panic_calls&&!log_calls);
 snapshot.wakes=2;mi8_tas_session_panic_tick(2000000);assert(!panic_calls);snapshot.wakes=1;
 snapshot.state=MI8_AMP_WARMING;mi8_tas_session_panic_tick(2000000);assert(!panic_calls);snapshot.state=MI8_AMP_LIVE;
 if(!setjmp(escape)){mi8_tas_session_panic_tick(1001000);assert(false);}
 assert(panic_calls==1&&log_calls==1&&!reset_cell&&!panic_test_enabled);
 mi8_tas_session_panic_tick(2000000);assert(panic_calls==1);
 puts("Panic hook PASS: one MMIO write, held-only, repeat latch, 84 bootarg cases, first LIVE +1s, panic RAM marker");
}
'''
    with tempfile.TemporaryDirectory(prefix='mi8-panic-') as tmp:
        p=Path(tmp);(p/'test.c').write_text(code)
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(x/'bsd/dev'),str(p/'test.c'),'-o',str(p/'test')],check=True)
        subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':main()
