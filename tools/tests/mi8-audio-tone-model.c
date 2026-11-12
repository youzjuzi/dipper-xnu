/* SPDX-License-Identifier: MIT */
/* Reuse the independent wire/word-latch peer, with power/clock observations. */
#define main tas_legacy_main
#include "mi8-tas2557.c"
#undef main
static uint8_t *firmware;
static size_t firmware_size;
static uint64_t *play_time, run_time, powered_at, stopped_at, write_at;
static unsigned scenario, startup_writes, shutdown_writes, gain_writes, health_reads, unmute_writes, mute_writes;
static uint64_t unmute_at,mute_at,mute_begin;
static bool muting;
static unsigned tone_lines;
static bool running, afe, power, nack_sent, shutting, software_shutdown;
static const struct expected startup[]={
 {0,1,0x4d,0x15},{0,1,0x3d,1},{0,1,0x3e,1},{0,0,5,0xa0},
 {0,0,5,0xa3},{0,0,4,0xf8},{0,0,0x2c,0x2b}};
static const struct expected shutdown[]={
 {0,0,0x2c,0},{100,0,7,1},{0,0,7,3},{0,0,4,0x60},
 {0,0,5,0},{0,0,4,0},{0,1,0x3d,0},{0,1,0x3e,0},{0,1,0x4d,0}};
static void power_write_model(struct model *p,unsigned r,uint8_t v) {
 CHECK(r!=0 && !(p->book==0 && p->page==0 && r==6));CHECK(running && afe);
 if(r==7&&!p->page&&!v&&(p->book==0||p->book==100)) {
  CHECK(health_reads==1 && p->time>=run_time+600000 && p->time<run_time+1000000);
  CHECK(unmute_writes<2 && p->book==(unmute_writes?100u:0u));
  if(!unmute_writes)unmute_at=p->time;
  unmute_writes++;ram[p->book][p->page][r]=v;return;
 }
 if(unmute_writes && !shutting) {
  if(!mute_writes){CHECK(p->book==100&&!p->page&&r==7&&v==1);muting=true;mute_begin=p->time;}
  else CHECK(mute_writes==1&&!p->book&&!p->page&&r==7&&v==3&&p->time-write_at>=10000);
  mute_writes++;write_at=p->time;ram[p->book][p->page][r]=v;
  if(mute_writes==2){mute_at=p->time;shutting=true;}return;
 }
 CHECK(ram[0][0][7]==3);
 if(!p->book&&!p->page&&r==0x2c&&!v)shutting=true;
 const struct expected *e;
 if(shutting){
  if(unmute_writes && shutdown_writes==1)shutdown_writes=3;
  CHECK(shutdown_writes<9);e=&shutdown[shutdown_writes++];
 } else {CHECK(startup_writes<7);e=&startup[startup_writes++];}
 CHECK(p->book==e->b && p->page==e->p && r==e->r && v==e->v);
 CHECK(p->time>=run_time+300000);
 if(!shutting && startup_writes==7)CHECK(p->time-write_at>=2000);
 if(shutting && !unmute_writes && shutdown_writes==3)CHECK(p->time-write_at>=10000);
 if(shutting && shutdown_writes==5)CHECK(p->time-write_at>=2000);
 if(!p->book&&!p->page&&r==5&&v==0xa0){power=true;powered_at=p->time;}
 if(shutting && shutdown_writes==9)software_shutdown=true;
 ram[p->book][p->page][r]=v;write_at=p->time;
}
static uint8_t power_read_model(struct model *p,unsigned r,uint8_t v) {
 if(power&&!p->page) {
  if(p->book==100 && r==7) {
   if(!unmute_writes)return scenario==14?0:7;
   if(muting)return v; /* After soft mute, read the written 01, not power-on 07. */
   if(scenario==3)return 7;
   return v;
  }
  if(!p->book) {
   if(r==0x68){health_reads++;CHECK(p->time-powered_at>=200000);return scenario==1 || (scenario==2&&unmute_writes)?0x80:2;}
   if(r==0x6c)return 0;
   if(r==0x64)return 0xfc;
  }
 }
 return v;
}
static bool power_nack(void) {
 if(scenario==4 && unmute_writes==1 && !muting && !nack_sent){nack_sent=true;return true;}
 if(scenario==15 && unmute_writes==2 && !muting && m.time>=unmute_at+250000 && !nack_sent){nack_sent=true;return true;}
 if(scenario==5 && mute_writes==1){nack_sent=true;return true;}
 return false;
}
static uint32_t power_read32(void *ctx,uint32_t a) {
 m.time=*play_time;uint32_t v=read32(ctx,a);*play_time=m.time;
 if(a==PIN(76)+4)v=(v&2)|((v>>1)&1);
 return v;
}
static void power_write32(void *ctx,uint32_t a,uint32_t v) {
 CHECK(a!=PIN(30) && a!=PIN(30)+4);m.time=*play_time;write32(ctx,a,v);*play_time=m.time;
 if(a==PIN(76)+4&&!v){power=false;stopped_at=m.time;}
 if(scenario==12 && unmute_writes==2)m.scl_ready=UINT64_MAX;
}
static uint64_t power_now(void *ctx){(void)ctx;return *play_time;}
static void power_delay(void *ctx,unsigned n){
 m.time=*play_time;
 if(scenario==16 && muting && n==10000)n+=30000; /* Slow normal shutdown, not a timeout. */
 delay_us(ctx,n);*play_time=m.time;
}
static void power_log(void *ctx,const char *fmt,...) {
 char line[1024];va_list ap;va_start(ap,fmt);vsnprintf(line,sizeof(line),fmt,ap);va_end(ap);
 if(strstr(line,"mi8rp: 16:")||strstr(line,"mi8rp: step 16:"))tone_lines++;
 log_line(ctx,"%s",line);if(scenario==0)fputs(line,stdout);
}
void amp_model_load(const char *raw,const char *reference) {
 firmware=file(raw,&firmware_size);FILE*f=fopen(reference,"r");CHECK(f);unsigned v,index;
 CHECK(fscanf(f,"%u %u %u %u",&expected_n,&prog_end,&v,&index)==4);expected_p=(uint8_t)v;
 for(unsigned i=0;i<expected_n;i++){unsigned b,p,r;CHECK(fscanf(f,"%u %u %u %u",&b,&p,&r,&v)==4);expected[i]=(struct expected){b,p,r,v};if(!b&&!p&&r==6){CHECK(v==0x7c);gain_writes++;}}
 CHECK(gain_writes==1);fclose(f);
}
bool amp_model_begin(uint64_t *clock,unsigned mode,bool gpio) {
 play_time=clock;scenario=mode;tone_lines=0;startup_writes=shutdown_writes=health_reads=0;
 running=afe=power=nack_sent=shutting=software_shutdown=muting=false;unmute_writes=mute_writes=0;unmute_at=mute_at=mute_begin=0;run_time=powered_at=stopped_at=write_at=0;
 init();if(gpio)bitbang();m.time=*clock;m.which=99;m.extra_write=power_write_model;m.extra_read=power_read_model;m.extra_nack=power_nack;
 m.corrupt_p=mode==11;
 struct mi8_tas_io io={&m,power_read32,power_write32,power_now,power_delay,power_log};
 bool ok=mi8_tas2557_hold_tone(&io,firmware,firmware_size,*clock+20000000);
 CHECK(ok==(mode!=11));
 return ok;
}
void amp_model_event(uint32_t op) {
 if(op==0x100e5)afe=true;
 if(op==0x10daa){CHECK(afe);running=true;run_time=*play_time;}
 if(op==0x10bcd || op==0x100e6){CHECK(!power && !m.pin[76]);CHECK(m.cfg[85]==m.saved_cfg[85]&&m.cfg[86]==m.saved_cfg[86]);}
 if(op==0x100e6)afe=false;
}
bool tone_model_unmuted(void){return unmute_writes==2 && !muting && power;}
void amp_model_check(unsigned mode) {
 fprintf(stderr,"tone scenario %u: startup=%u unmute=%u mute=%u stop_at=%llu run_at=%llu\n",mode,startup_writes,unmute_writes,mute_writes,(unsigned long long)stopped_at,(unsigned long long)run_time);
 CHECK(!power && !m.pin[76] && m.cfg[85]==m.saved_cfg[85] && m.cfg[86]==m.saved_cfg[86]);
 CHECK(m.lines<=28 && tone_lines<=11); /* plus the one PCM description line */
 if(mode==0||mode==16){CHECK(startup_writes==7&&shutdown_writes==9&&health_reads>=6&&software_shutdown);CHECK(mute_at>=run_time+2050000&&stopped_at<=run_time+2500000);CHECK(unmute_writes==2&&mute_writes==2);}
 if(mode==16)CHECK(stopped_at-mute_begin>=40000);
 if(mode==17)CHECK(unmute_writes==2 && mute_writes==2 && software_shutdown);
 if(mode==1){CHECK(!unmute_writes&&health_reads==1);CHECK(stopped_at<run_time+600000);}
 if(mode==2){CHECK(health_reads==2&&mute_writes==2&&stopped_at<run_time+1000000);}
 if(mode==3||mode==4){CHECK(mute_writes==2&&stopped_at<run_time+800000);}
 if(mode==4||mode==5)CHECK(nack_sent);
 if(mode==5||mode==12)CHECK(!software_shutdown);
 if(mode==5||mode==6||mode==7||mode==8||mode==13)CHECK(unmute_writes==2);
 if(mode==6||mode==7||mode==8||mode==13)CHECK(mute_writes==2 && software_shutdown);
 if(mode==14)CHECK(!unmute_writes && health_reads==1);
 if(mode==15)CHECK(nack_sent && unmute_writes==2 && mute_writes==2 && software_shutdown);
 if(mode==11 || mode>=20)CHECK(!startup_writes&&!unmute_writes);
}
unsigned long amp_model_checks(void){return checks;}
