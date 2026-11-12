/* SPDX-License-Identifier: MIT */
/* Independent I2C wire/word-latch peer; only the controller touches it. */
#define main tas_legacy_main
#include "mi8-tas2557.c"
#undef main
static uint8_t *firmware;
static size_t firmware_size;
static unsigned starts,mutings,checks_y,health,mode,stage,session_logs;
static uint64_t startup_at,soft_at;
static unsigned observed_zeros,observed_wake;
void session_model_submit(bool nz){
 struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);
 if(a.wakes!=observed_wake){observed_wake=a.wakes;__atomic_store_n(&observed_zeros,0,__ATOMIC_RELEASE);}
 if(!nz&&a.request==2)__atomic_fetch_add(&observed_zeros,1,__ATOMIC_RELEASE);
}
extern void session_test_reset(void);
static void session_write(struct model *p,unsigned r,uint8_t v) {
 CHECK((p->book==0 && p->page==0 && (r==4||r==5||r==7||r==44)) ||
     (p->book==0&&p->page==1&&(r==61||r==62||r==77)) || (p->book==100&&!p->page&&r==7));
 if(p->book==0 && p->page==1 && r==0x4d && v==0x15){starts++;startup_at=p->time;stage=1;}
 if(p->book==0 && p->page==0 && r==7 && v==0){CHECK(p->time-startup_at>=200000 && health);stage=2;}
 if(p->book==100 && p->page==0 && r==7 && v==1){struct mi8_amp_snapshot a;mi8_tas_session_snapshot(&a);
  if(a.request==2)CHECK(__atomic_load_n(&observed_zeros,__ATOMIC_ACQUIRE)>=8);
  soft_at=p->time;mutings++;stage=3;}
 if(p->book==0 && p->page==0 && r==7 && v==3 && stage==3)CHECK(p->time-soft_at>=10000);
 ram[p->book][p->page][r]=v;
}
static uint8_t session_read(struct model *p,unsigned r,uint8_t v) {
 if(p->book==100 && !p->page && r==7 && starts==1 && stage==1)return 7;
 if(!p->book && !p->page){
  if(r==0x68){health++;return mode==2 || (mode==3 && stage==2)?0x80:2;}
  if(r==0x6c)return 0;
  if(r==0x64)return 0xfc;
 }
 if(!p->book && p->page==53 && r==49){checks_y++;if(mode==1 && starts)return v^1;}
 return v;
}
static void session_log(void *ctx,const char *fmt,...) {
 char line[1024];va_list ap;va_start(ap,fmt);vsnprintf(line,sizeof(line),fmt,ap);va_end(ap);
 if(!strncmp(line,"audio:",6)){CHECK(++session_logs<=1000);return;}
 log_line(ctx,"%s",line);
}
void session_model_load(const char *raw,const char *reference) {
 firmware=file(raw,&firmware_size);FILE *f=fopen(reference,"r");CHECK(f);unsigned index,v;
 CHECK(fscanf(f,"%u %u %u %u",&expected_n,&prog_end,&v,&index)==4);expected_p=(uint8_t)v;
 for(unsigned i=0;i<expected_n;i++){unsigned b,p,r;CHECK(fscanf(f,"%u %u %u %u",&b,&p,&r,&v)==4);expected[i]=(struct expected){b,p,r,v};}fclose(f);
}
bool session_model_prepare(unsigned which) {
 session_test_reset();init();bitbang();mode=which;starts=mutings=checks_y=health=stage=session_logs=0;
 observed_zeros=observed_wake=0;m.which=99;m.corrupt_p=mode==4;m.extra_write=session_write;m.extra_read=session_read;
 const struct mi8_tas_io io={&m,read32,write32,clock_us,delay_us,session_log};
 bool ok=mi8_tas_session_prepare(&io,firmware,firmware_size,20000000);
 CHECK(ok==(mode!=4));return ok;
}
void session_model_advance(uint64_t until){if(until>m.time)m.time=until;}
uint64_t session_model_now(void){return m.time;}
unsigned session_model_mutes(void){return mutings;}
unsigned session_model_starts(void){return starts;}
void session_model_check_done(void){CHECK(!m.pin[76] && m.cfg[85]==m.saved_cfg[85] && m.cfg[86]==m.saved_cfg[86]);}
unsigned long session_model_checks(void){return checks;}

void session_model_prior_wakes(unsigned n){starts=n;ram[100][0][7]=1;}
