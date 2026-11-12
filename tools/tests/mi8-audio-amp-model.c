/* SPDX-License-Identifier: MIT */
/* Reuse the independent wire/word-latch peer, with power/clock observations. */
#define main tas_legacy_main
#include "mi8-tas2557.c"
#undef main
static uint8_t *firmware;
static size_t firmware_size;
static uint64_t *play_time, run_time, powered_at, stopped_at, write_at;
static unsigned scenario, startup_writes, shutdown_writes, gain_writes, health_reads;
static bool running, afe, power, nack_sent, shutting, software_shutdown;
static const struct expected startup[]={
 {0,1,0x4d,0x15},{0,1,0x3d,1},{0,1,0x3e,1},{0,0,5,0xa0},
 {0,0,5,0xa3},{0,0,4,0xf8},{0,0,0x2c,0x2b}};
static const struct expected shutdown[]={
 {0,0,0x2c,0},{100,0,7,1},{0,0,7,3},{0,0,4,0x60},
 {0,0,5,0},{0,0,4,0},{0,1,0x3d,0},{0,1,0x3e,0},{0,1,0x4d,0}};
static void power_write_model(struct model *p,unsigned r,uint8_t v) {
 CHECK(r!=0 && !(p->book==0 && p->page==0 && r==6));
 CHECK(ram[0][0][7]==3 && running && afe);
 if(!p->book&&!p->page&&r==0x2c&&!v)shutting=true;
 const struct expected *e;
 if(shutting){CHECK(shutdown_writes<9);e=&shutdown[shutdown_writes++];}
 else {CHECK(startup_writes<7);e=&startup[startup_writes++];}
 CHECK(p->book==e->b && p->page==e->p && r==e->r && v==e->v);
 CHECK(p->time>=run_time+300000);
 if(!shutting && startup_writes==7)CHECK(p->time-write_at>=2000);
 if(shutting && shutdown_writes==3)CHECK(p->time-write_at>=10000);
 if(shutting && shutdown_writes==5)CHECK(p->time-write_at>=2000);
 if(!p->book&&!p->page&&r==5&&v==0xa0){power=true;powered_at=p->time;}
 if(shutting && shutdown_writes==9)software_shutdown=true;
 ram[p->book][p->page][r]=v;write_at=p->time;
}
static uint8_t power_read_model(struct model *p,unsigned r,uint8_t v) {
 if(!p->book&&!p->page&&r==6 && p->seen==expected_n && (scenario==6 || (scenario==14 && running)))return 0;
 if(power&&!p->book&&!p->page){
  if(r==0x68){health_reads++;CHECK(p->time-powered_at>=200000);return scenario==2?0x80:2;}
  if(r==0x6c)return 0;
  if(r==0x64)return 0xfc;
  if(r==7&&scenario==7)return 0;
 }
 return v;
}
static bool power_nack(void) {
 if(scenario==1&&startup_writes>=4&&!nack_sent){nack_sent=true;return true;}
 if(scenario==19&&power&&m.time-powered_at>=200000&&!nack_sent){nack_sent=true;return true;}
 if(scenario==9&&shutting){nack_sent=true;return true;}
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
 if(scenario==17 && startup_writes>=4)m.scl_ready=UINT64_MAX;
}
static uint64_t power_now(void *ctx){(void)ctx;return *play_time;}
static void power_delay(void *ctx,unsigned n){m.time=*play_time;delay_us(ctx,n);*play_time=m.time;}
static void power_log(void *ctx,const char *fmt,...) {
 char line[1024];va_list ap;va_start(ap,fmt);vsnprintf(line,sizeof(line),fmt,ap);va_end(ap);
 log_line(ctx,"%s",line);if(scenario==0)fputs(line,stdout);
}
void amp_model_load(const char *raw,const char *reference) {
 firmware=file(raw,&firmware_size);FILE*f=fopen(reference,"r");CHECK(f);unsigned v,index;
 CHECK(fscanf(f,"%u %u %u %u",&expected_n,&prog_end,&v,&index)==4);expected_p=(uint8_t)v;
 for(unsigned i=0;i<expected_n;i++){unsigned b,p,r;CHECK(fscanf(f,"%u %u %u %u",&b,&p,&r,&v)==4);expected[i]=(struct expected){b,p,r,v};if(!b&&!p&&r==6){CHECK(v==0x7c);gain_writes++;}}
 CHECK(gain_writes==1);fclose(f);
}
bool amp_model_begin(uint64_t *clock,unsigned mode,bool gpio) {
 play_time=clock;scenario=mode;startup_writes=shutdown_writes=health_reads=0;
 running=afe=power=nack_sent=shutting=software_shutdown=false;run_time=powered_at=stopped_at=write_at=0;
 init();if(gpio)bitbang();m.time=*clock;m.which=99;m.extra_write=power_write_model;m.extra_read=power_read_model;m.extra_nack=power_nack;
 m.corrupt_p=mode==5;
 struct mi8_tas_io io={&m,power_read32,power_write32,power_now,power_delay,power_log};
 unsigned mutation=mode==18?0x32ae:0x30b9;
 if(mode==16||mode==18)firmware[mutation]^=1;
 bool ok=mi8_tas2557_hold(&io,firmware,firmware_size,*clock+20000000);
 if(mode==16||mode==18){firmware[mutation]^=1;if(mode==16)CHECK(!m.writes);}
 CHECK(ok==(mode!=5 && mode!=6 && mode!=16));
 return ok;
}
void amp_model_event(uint32_t op) {
 if(op==0x100e5)afe=true;
 if(op==0x10daa){CHECK(afe);running=true;run_time=*play_time;}
 if(op==0x10bcd || op==0x100e6){CHECK(!power && !m.pin[76]);CHECK(m.cfg[85]==m.saved_cfg[85]&&m.cfg[86]==m.saved_cfg[86]);}
 if(op==0x100e6)afe=false;
}
void amp_model_check(unsigned mode) {
 CHECK(!power && !m.pin[76] && m.cfg[85]==m.saved_cfg[85] && m.cfg[86]==m.saved_cfg[86]);
 CHECK(m.lines<=20);
 if(mode==0){CHECK(startup_writes==7&&shutdown_writes==9&&health_reads==2&&software_shutdown);CHECK(stopped_at<=run_time+2500000);}
 if(mode==5||mode==6||mode==11||mode==12||mode==13||mode==14||mode==15||mode==16||mode>=20)CHECK(!startup_writes&&!health_reads);
 if(mode==1||mode==9||mode==19)CHECK(nack_sent);
 if(mode==2||mode==7)CHECK(health_reads==1 && stopped_at<run_time+1000000);
 if(mode==9||mode==17)CHECK(!software_shutdown);
}
unsigned long amp_model_checks(void){return checks;}
