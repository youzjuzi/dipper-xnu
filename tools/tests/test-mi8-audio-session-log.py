#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native audio=5 log chain, including upstream PCM budget and init flags."""
import argparse
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--tree',type=Path,default=ROOT/'work')
 ap.add_argument('--sanitize',action='store_true')
 a=ap.parse_args();x=a.tree.resolve()/'hackios/xnu-src/xnu-8796.121.2';d=x/'bsd/dev'
 body=runpy.run_path(str(ROOT/'tools/tests/test-mi8-audio-smmu.py'))['body']
 rp=(d/'mi8_rproc.c').read_text();au=(d/'mi8_audio.c').read_text();pc=(d/'mi8_audio_pcm.c').read_text();ld=(x/'osfmk/arm64/loader_return.c').read_text()
 assert 'cfg.log = svc_log;' in body(rp,'static bool __attribute__((noinline))\nadsp_audio_handshake(')
 assert 'pcm_poll,pcm_tell,' in au
 assert 'audio_play_thread=current_thread();' in body(rp,'static void\nsteps_audio_session(')
 code=r'''#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include "mi8_audio_pcm.h"
#define __unused __attribute__((unused))
#define NSEC_PER_SEC 1000000000ull
#define NSEC_PER_MSEC 1000000ull
#define KERN_SUCCESS 0
#define LOADER_LOG_SIZE (1536*1024)
typedef unsigned thread_t;
static thread_t audio_play_thread;
static bool audio_play_brief,audio_ring_stream,audio_clip_stream,audio_session_stream,audio_tail_on;
static unsigned audio_tail_len,audio_session_seconds=300,wake_lines;
static char audio_tail[16384],audio_play_note[400],loader_log[LOADER_LOG_SIZE];
static uint32_t loader_log_len;
static thread_t current_thread(void){return 1;}
static uint64_t mach_absolute_time(void){return 0;}
static void absolutetime_to_nanoseconds(uint64_t n,uint64_t *out){*out=n;}
static size_t strlcpy(char *d,const char *s,size_t n){size_t z=strlen(s);if(n)snprintf(d,n,"%s",s);return z;}
static void loader_log_putc(char c){(void)c;} /* desktop noise overwrites live log below */
static int quiet_printf(const char *fmt,...){(void)fmt;return 0;}
#define printf quiet_printf
'''
 for sig in ['static void audio_tail_append(', 'const char *\nmi8_rproc_audio_tail(', 'static bool audio_play_worker(', 'static bool\nsays_dsp_state(', 'static int\nsay(', 'static void\nsvc_log(']:code+=body(rp,sig)+'\n'
 code+='struct audio_session {const struct mi8_glink_cfg *io;};\n'
 code+='#define TELL(s, ...) do { if ((s).io->log) (s).io->log((s).io->ctx, __VA_ARGS__); } while (0)\n'
 code+=body(au,'static void pcm_tell(')+'\n/* @pcm_log */\n'
 code+='''static unsigned mi8_audio_sink_summary(char *out,unsigned size){return (unsigned)snprintf(out,size,"audio: final count-only snapshot=stable\\n");}
'''
 for sig in ['static void\nloader_audio_append(', 'static void\nloader_audio_summary(']:code+=body(ld,sig)+'\n'
 code+=r'''
static void steps_audio_session(void *p,int wr){
 (void)p;(void)wr;audio_play_thread=current_thread();
 struct mi8_glink_cfg cfg={.log=svc_log};struct audio_session ctx={.io=&cfg};
 struct mi8_pcm_ops io={.ctx=&ctx,.log=pcm_tell};struct mi8_pcm_state s={.io=&io,.session=(const void*)1};
 /* Actual startup has seven PCM messages before its 15-second progress. */
 for(unsigned i=0;i<7;i++)pcm_log(&s,"setup %u",i);
 for(unsigned i=0;i<wake_lines;i++)pcm_log(&s,"wake #%u flushed=123456 waveform and ring statistics padding for tail rollover",i+1);
 for(unsigned i=1;i<=20;i++)pcm_log(&s,"zero: %u s, submitted=%u done=%u ring counts",i*15,i*750,i*750);
 pcm_log(&s,"play: 15000 periods submitted, done=15000 errors=0");
 pcm_log(&s,"asm stream close status=0");pcm_log(&s,"asm unmap regions status=0");pcm_log(&s,"adm device close status=0");
 say("mi8rp: audio=5: cleanup=complete conservation=ok\n");
 audio_play_thread=0;
}
static void steps_audio_clip(void *p,int wr){(void)p;(void)wr;assert(0);}
static void steps_from_five(void *p,int wr){(void)p;(void)wr;assert(0);}
static void audio_session_report(bool okay,const char *s){(void)okay;(void)s;assert(0);}
static void audio_clip_report(bool okay,const char *s){(void)okay;(void)s;assert(0);}
static void audio_ring_report(bool okay,const char *s){(void)okay;(void)s;assert(0);}
static bool mi8_audio_ring_requested(void){return true;}
void mi8_audio_set_ring(bool on){assert(on);}
static int kernel_thread_start(void(*fn)(void*,int),void *p,thread_t *out){*out=1;fn(p,0);return 0;}
static void thread_deallocate(thread_t t){assert(t==1);}
static void dispatch(void){uint32_t audio=5,shared_step=0;
'''
 code+=body(rp,'if(audio==5)')+'\n'+body(rp,'if (audio == 2 && (shared_step == 17 || audio_session_stream))')+'\nassert(0);}\n'
 code+=r'''
#undef printf
int main(void){
 for(unsigned stress=0;stress<2;stress++){
  audio_tail_len=0;audio_play_thread=0;audio_session_stream=audio_ring_stream=audio_tail_on=false;wake_lines=stress?200:0;
  dispatch();assert(audio_session_stream&&audio_ring_stream&&audio_tail_on&&!audio_play_thread);
  memset(loader_log,'x',sizeof(loader_log));loader_log_len=sizeof(loader_log);
  loader_audio_summary();char tail[32769];memcpy(tail,loader_log+loader_log_len-32768,32768);tail[32768]=0;
  assert(strstr(tail,"cleanup=complete")&&strstr(tail,"audio: final count-only"));
#ifdef LEGACY
  assert(!strstr(tail,"play: 15000")&&!strstr(tail,"asm stream close"));
  if(!stress)assert(strstr(tail,"zero: 195 s")&&!strstr(tail,"zero: 210 s"));
#else
  assert(strstr(tail,"zero: 300 s")&&strstr(tail,"play: 15000")&&strstr(tail,"asm stream close"));
  if(stress){assert(audio_tail_len==sizeof(audio_tail)-1);assert(strstr(tail,"wake #200 flushed="));}
#endif
 }
#ifdef LEGACY
 puts("Native log chain regression reproduced: PCM budget ends at 195s; tail rolls but play/close never arrive");
#else
 puts("Native log chain PASS: real audio=5 dispatch flags, PCM->pcm_tell->svc_log->say->tail getter->loader final32KiB; 300s + 200 wakes; play/close/summary retained");
#endif
}
'''
 flags=['-DMI8_GLINK_HOST_TEST','-std=c11','-Wall','-Wextra','-Werror','-Wno-format','-I'+str(d)];env=dict(os.environ)
 if a.sanitize:flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-sanitize-recover=all','-no-pie'];env['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1'
 pcm=body(pc,'static void\npcm_log(')
 assert '(s->session?256u:20u)' in pcm
 with tempfile.TemporaryDirectory(prefix='mi8-log-chain-') as tmp:
  t=Path(tmp)
  for legacy in [True,False]:
   fn=pcm.replace('(s->session?256u:20u)','20') if legacy else pcm
   (t/'test.c').write_text(code.replace('/* @pcm_log */',fn))
   subprocess.run(['cc',*flags,*(['-DLEGACY'] if legacy else []),str(t/'test.c'),'-o',str(t/'test')],check=True)
   subprocess.run([str(t/'test')],env=env,check=True)
if __name__=='__main__':main()
