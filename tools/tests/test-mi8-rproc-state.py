#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute the actual per-remote SMP2P helpers with synthetic SMEM callbacks."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import runpy

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tree', type=Path, default=ROOT / 'work')
    source = (ap.parse_args().tree / 'hackios/xnu-src/xnu-8796.121.2/bsd/dev/mi8_rproc.c').read_text()
    if 'struct mi8_remote {' not in source:
        raise SystemExit('SELFTEST FAIL: independent ADSP/modem state is missing')
    smp = source[source.index('struct smp2p {'):source.index('};', source.index('struct smp2p {')) + 2]
    helpers = source[source.index('struct mi8_remote {'):source.index('static uint64_t\nnow_us(void)')]
    code = r'''
#include <pthread.h>
#include <stdatomic.h>
#include <sched.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#define SMEM_US 0
#define SMEM_ADSP 2
#define SMEM_MODEM 1
#define ITEM_SMP2P_THEIRS 443
#define ITEM_SMP2P_THEIRS_ALT 435
#define IPC_SMP2P_ADSP (1u<<10)
#define IPC_SMP2P_MODEM (1u<<14)
#define SMP2P_MAGIC 0x504d5324u
#define SMP2P_RESTART_ACKS 1u
#define SMP2P_AT_VERSION 4
static unsigned checks, bells, pending_logs, completed_logs;
static uint8_t mem[16384];
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"FAIL %u: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint32_t smem_partition(unsigned us,unsigned remote,uint32_t*c,uint32_t*s){CHECK(us==0);*c=32;*s=4096;return remote*4096;}
static uint32_t item_find(uint32_t base,uint32_t line,uint32_t item,uint32_t*size){CHECK(line==32);CHECK((base==8192&&item==443)||(base==4096&&item==435));*size=344;return base+512;}
static bool smem_peek(uint64_t at,void*dst,uint32_t n){CHECK(at+n<=sizeof(mem));memcpy(dst,mem+at,n);return true;}
static void smem_poke(uint32_t at,uint32_t value){CHECK(at+4<=sizeof(mem));memcpy(mem+at,&value,4);}
static int say(const char*fmt,...){if(strstr(fmt,"Pending"))pending_logs++;if(strstr(fmt,"step 10 completed"))completed_logs++;return 0;}
static void settle(void){}
static void ring(unsigned mask){bells|=mask;}
'''+smp+'\n'+helpers+r'''
int main(void){
 struct smp2p adsp={0},modem={0},ours={0},got;
 adsp.magic=modem.magic=ours.magic=SMP2P_MAGIC;
 adsp.version=modem.version=0x101;ours.version=0x301;
 adsp.valid=modem.valid=1;strcpy(adsp.entry[0].name,"slave-kernel");strcpy(modem.entry[0].name,"slave-kernel");
 adsp.entry[0].value=2;modem.entry[0].value=1;
 memcpy(mem+8192+512,&adsp,sizeof(adsp));memcpy(mem+4096+512,&modem,sizeof(modem));
 memcpy(mem+8192,&ours,sizeof(ours));memcpy(mem+4096,&ours,sizeof(ours));
 adsp_remote.our_item=8192;modem_remote.our_item=4096;
 CHECK(remote_words(&adsp_remote,&got)&&dsp_state(&got)==2);
 CHECK(dsp_words(&got)&&dsp_state(&got)==1);
 remote_listen(&adsp_remote,&adsp);
 CHECK(adsp_remote.agreed&&!modem_remote.agreed);
 CHECK(*(uint32_t*)(mem+8192+4)==0x101&&*(uint32_t*)(mem+4096+4)==0x301);
 dsp_listen(&modem);CHECK(modem_remote.agreed);
 adsp.flags=1;remote_listen(&adsp_remote,&adsp);
 CHECK(adsp_remote.restart_acked&&!modem_remote.restart_acked);CHECK(bells==(1u<<10));
 modem.flags=1;dsp_listen(&modem);CHECK(modem_remote.restart_acked&&bells==((1u<<10)|(1u<<14)));
 CHECK(remote_words(&adsp_remote,&got)&&dsp_state(&got)==2);
 printf("SELFTEST PASS %u/%u\n",checks,checks);return 0;
}
'''
    # Exercise the real lookup and step dispatcher too: nested lookups must not
    # share scratch state, and every new step9 exit must release its AOP vote.
    lookup = source[source.index('static uint32_t\nitem_find('):source.index("/* Linux's qcom_smem_alloc_private()", source.index('static uint32_t\nitem_find('))]
    body = runpy.run_path(str(ROOT / 'tools/tests/test-mi8-audio-smmu.py'))['body']
    dispatcher = body(source, 'static void\nsteps_from_five(')
    code = code.replace("item_find(", "helper_item_find(")
    code += r'''
#define MAX_ITEMS 192
struct smem_item { uint32_t item, offset, size; };
static struct smem_item found[MAX_ITEMS];
static unsigned smem_items(uint32_t, uint32_t, struct smem_item *, unsigned);
static uint32_t item_find(uint32_t, uint32_t, uint32_t, uint32_t *);
static const struct smem_item *find_item(unsigned n,uint32_t id){for(unsigned i=0;i<n;i++)if(found[i].item==id)return &found[i];return NULL;}
'''+lookup+r'''
static unsigned smem_items(uint32_t partition,uint32_t line,struct smem_item *out,unsigned max){
 (void)line;(void)max;out[0]=(struct smem_item){43,partition+128,344};
 if(partition==8192){uint32_t size=0;CHECK(item_find(4096,32,43,&size)==4224);}
 return 1;
}
#define __unused __attribute__((unused))
#define NSEC_PER_MSEC 1
#define KERN_SUCCESS 0
#define NULL_THREAD 0
typedef int wait_result_t;
static bool adsp_started, prep_ok, start_ok, starts_dsp, down_ok, ack_ok, aop_ok, handshake_ok;
static bool adsp_last_stop_acked, adsp_last_aop_off;
static bool audio_ring_stream;
static void audio_ring_report(bool completed,const char *cleanup){(void)completed;(void)cleanup;CHECK(false);}
static unsigned shutdowns,offs,handshakes,terminations;
static int redwood_ufs_read_named(const char*n,unsigned off,void*p,unsigned sz){(void)n;(void)off;(void)p;(void)sz;return 0;}
static void delay_for_interval(unsigned a,unsigned b){(void)a;(void)b;}
static void step_firmware(void){}
static void step_aop(void){}
static bool step_header(void){return true;}
static bool step_image(void){return true;}
static bool mi8_audio_play_proven(void){return false;}
static const char *mi8_audio_play_cleanup(void){return "complete";}
static bool mi8_audio_play_completed(void){return true;}
static bool mi8_audio_finish_play(bool down){return down;}
static pthread_mutex_t wsmmu_lock;static bool audio_play_locked;
static void lck_mtx_unlock(pthread_mutex_t *lock);
static int audio_play_thread;static bool audio_play_brief;static uint64_t audio_play_until;static char audio_play_note[400];
static uint64_t now_us(void){return 0;}
static const int audio_amp_ops=0;
static void mi8_tas2557_prepare_tone(uint64_t end){(void)end;CHECK(false);}
static void mi8_tas2557_prepare(uint64_t end){(void)end;CHECK(false);}
static void mi8_tas2557_stop(void){CHECK(false);}
static void mi8_tas2557_report(const char *s){(void)s;CHECK(false);}
static void mi8_audio_set_amp(const void *p){(void)p;CHECK(false);}
static bool adsp_glink_prepare(void){return prep_ok;}
static bool step_start(void){adsp_started=starts_dsp;return start_ok;}
static bool adsp_audio_handshake(uint32_t last){CHECK(last==9||last==10);handshakes++;return handshake_ok;}
static bool dsp_shutdown(const char*s){(void)s;shutdowns++;adsp_last_stop_acked=ack_ok;adsp_last_aop_off=aop_ok;if(down_ok)offs++;return down_ok;}
static bool qmp_send(const char*s){CHECK(strstr(s,"val: off")!=NULL);offs++;return true;}
static int current_thread(void){return 0;}
static void thread_terminate(int t){(void)t;terminations++;}
'''+dispatcher.replace('audio_play_thread=NULL', 'audio_play_thread=0')+r'''
static void lifecycle_tests(void){
 uint32_t size=0;CHECK(item_find(8192,32,43,&size)==8320&&size==344);
 for(unsigned scenario=0;scenario<10;scenario++){
  prep_ok=scenario!=0;start_ok=scenario!=1;starts_dsp=scenario>=2;down_ok=scenario!=3&&scenario!=9;ack_ok=scenario!=7;aop_ok=scenario!=8;handshake_ok=scenario!=6;
  adsp_started=false;pending_logs=completed_logs=0;shutdowns=offs=handshakes=terminations=0;
  steps_from_five((void*)(uintptr_t)(scenario>=5?10:scenario==4?8:9),0);
  CHECK(terminations==1);CHECK(offs==1);CHECK(shutdowns==(scenario>=2));
  CHECK(handshakes==(scenario>=2&&scenario!=4));
  if(scenario>=7)CHECK(pending_logs>0&&!completed_logs);
  if(scenario==5)CHECK(!pending_logs&&completed_logs==1);
  if(scenario==6)CHECK(!completed_logs);
 }
}
'''
    gate_parts = []
    for signature, end in [('static bool\nlock_take(void)', 'static void\nlock_give'),
                           ('static void\nlock_give(void)', 'static void\nstep_lock_try'),
                           ('static bool\nqmp_send(const char *text)', '/* ---- RPMh:'),
                           ('static bool\nrpmh_write(const char *what', 'static bool\nrpmh_level(')]:
        start = source.index(signature)
        gate_parts.append(source[start:source.index(end, start + len(signature))])
    gate = '\n'.join(gate_parts)
    for name in ('lock_take', 'lock_give', 'qmp_send', 'rpmh_write'):
        gate = gate.replace(name + '(', 'gate_' + name + '(')
    code += r'''
#include <pthread.h>
#include <stdatomic.h>
#include <sched.h>
static pthread_mutex_t remote_shared_lock=PTHREAD_MUTEX_INITIALIZER;
static bool adsp_shared_serial, take_ok=true;
static atomic_uint active,overlaps,entries;
static unsigned gate_locks,gate_unlocks;
static void lck_mtx_lock(pthread_mutex_t*p){pthread_mutex_lock(p);gate_locks++;}
static void lck_mtx_unlock(pthread_mutex_t*p){gate_unlocks++;pthread_mutex_unlock(p);}
static bool gate_enter(void){if(atomic_fetch_add(&active,1))atomic_fetch_add(&overlaps,1);sched_yield();atomic_fetch_sub(&active,1);atomic_fetch_add(&entries,1);return true;}
static bool lock_take_unserialized(void){return take_ok;}
static bool qmp_send_unserialized(const char*s){(void)s;return gate_enter();}
static bool rpmh_write_unserialized(const char*s,uint32_t a,uint32_t d){(void)s;(void)a;(void)d;return gate_enter();}
#define MUTEX_SMEM 3
#define MUTEX_STRIDE 4096
static unsigned mutex_map(void){return 0;}
static void wr(unsigned addr,unsigned value){(void)addr;(void)value;}
'''+gate+r'''
static void *gate_worker(void*arg){for(unsigned i=0;i<1000;i++){if(arg)gate_qmp_send("test");else gate_rpmh_write("test",1,2);}return NULL;}
static void gate_tests(void){
 pthread_t a,b;
 adsp_shared_serial=false;gate_locks=gate_unlocks=0;
 CHECK(gate_lock_take());gate_lock_give();CHECK(gate_qmp_send("test"));CHECK(gate_rpmh_write("test",1,2));
 CHECK(gate_locks==0&&gate_unlocks==0);
 adsp_shared_serial=true;take_ok=false;CHECK(!gate_lock_take());CHECK(gate_locks==1&&gate_unlocks==1);
 take_ok=true;CHECK(gate_lock_take());gate_lock_give();CHECK(gate_locks==2&&gate_unlocks==2);
 atomic_store(&entries,0);CHECK(!pthread_create(&a,NULL,gate_worker,(void*)1));CHECK(!pthread_create(&b,NULL,gate_worker,NULL));
 CHECK(!pthread_join(a,NULL));CHECK(!pthread_join(b,NULL));CHECK(!atomic_load(&overlaps)&&atomic_load(&entries)==2000);
 CHECK(gate_locks==2002&&gate_unlocks==2002);
}
'''
    code = code.replace('int main(void){', 'static void gate_tests(void);\nint main(void){\n gate_tests();', 1)
    code = code.replace('int main(void){', 'static void lifecycle_tests(void);\nint main(void){\n lifecycle_tests();', 1)
    with tempfile.TemporaryDirectory(prefix='mi8-smp2p-test-') as tmp:
        c, exe = Path(tmp) / 'test.c', Path(tmp) / 'test'
        c.write_text(code)
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-pthread',
                        str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
