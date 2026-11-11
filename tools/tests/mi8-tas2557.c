/* SPDX-License-Identifier: MIT */
/* Synthetic SE5 FIFO and TAS2557 peer. The P-CRC register is a fixture latch
 * enabled only after the entire independently decoded program write stream
 * matches. This tests the read/compare contract, not the silicon polynomial. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "mi8_tas2557.h"
#define CHECK(x) do { checks++;if(!(x)){fprintf(stderr,"FAIL line %u: %s\n",__LINE__,#x);exit(1);} } while(0)
static unsigned long checks;
#define GCC 0x100000u
#define SE 0x894000u
#define PIN(n) (0x3500000u+0x1000u*(n))
#define VOTE 0x15200cu
#define VOTES ((1u<<6)|(1u<<7)|(1u<<15))
#define RCG 0x117624u
static uint8_t ram[256][256][128];
struct expected { uint8_t b,p,r,v; };
static struct expected expected[20000];
static unsigned expected_n,prog_end;
static uint8_t expected_p;
struct model {
	uint32_t gcc[0x60000/4],se[0x4000/4],cfg[100],pin[100];
	uint32_t saved_gcc[0x60000/4],saved_se[0x4000/4],saved_cfg[100];
	uint8_t tx[132],rx[132];unsigned tx_at,tx_n,rx_at,rx_n,book,page,reg,op;
	unsigned serial,fail_at,which,seen,lines,writes,flags[3],p_reads,p_resets,forbidden;
	uint64_t time,low_at,high_at,sw_at;
	bool low_set,high_set,corrupt_p,corrupt_y,stuck_clock,stuck_cancel,restore_fail,other_vote;
};
static struct model m;
static const uint8_t reset_regs[]={0,0,0,0xa0,0,0,0x7c,3,0,0x25,8,0x18,0,0x20,0x33,0x28};
static uint32_t *cell(struct model *p,uint32_t a) {
	if(a>=GCC && a<GCC+0x60000)return &p->gcc[(a-GCC)/4];
	if(a>=SE && a<SE+0x4000)return &p->se[(a-SE)/4];
	for(unsigned i=0;i<100;i++) { if(a==PIN(i))return &p->cfg[i];if(a==PIN(i)+4)return &p->pin[i]; }
	CHECK(0);return NULL;
}
static uint8_t tas_read(struct model *p,unsigned r) {
	if(!p->book && !p->page && r==32) {
		CHECK(p->p_resets==1 && p->seen==prog_end);p->p_reads++;return expected_p^(p->corrupt_p?1:0);
	}
	if(!p->book && !p->page) {
		if(r==0x68)p->flags[0]++;
		if(r==0x6c)p->flags[1]++;
		if(r==0x64)p->flags[2]++;
	}
	uint8_t v=ram[p->book][p->page][r];
	if(p->corrupt_y && p->book==140 && p->page==42 && r==88)v^=1;
	return v;
}
static void tas_write(struct model *p,unsigned r,uint8_t v) {
	CHECK(r<128);
	if(!r) { p->page=v;return; }
	if(!p->page && r==127) { p->book=v;return; }
	if(!p->book && !p->page && r==1) {
		CHECK(v==1 && p->high_set && p->time-p->high_at>=2000);memset(ram,0,sizeof(ram));memcpy(ram[0][0],reset_regs,16);
		if(p->which==4)ram[0][0][3]=0x80;
		if(p->which==5)ram[0][0][6]=0;
		p->sw_at=p->time;return;
	}
	CHECK(p->time-p->sw_at>=1000);
	if(!p->book && !p->page && r==33) { CHECK(v==1);p->p_resets++;return; }
	if((!p->book && !p->page && (r==4||r==5||r==7||r==44)) || (!p->book&&p->page==1&&(r==61||r==62||r==77)) || (p->book==100&&!p->page&&r==7))p->forbidden++;
	CHECK(p->seen<expected_n);
	const struct expected *e=&expected[p->seen++];
	CHECK(e->b==p->book && e->p==p->page && e->r==r && e->v==v);
	ram[p->book][p->page][r]=v;
}
static void complete_write(struct model *p) {
	CHECK(p->tx_at==p->tx_n && p->tx_n>0);unsigned reg=p->tx[0];
	p->time+=(p->tx_n+1)*90; p->reg=reg;
	for(unsigned i=1;i<p->tx_n;i++)tas_write(p,reg+i-1,p->tx[i]);
	p->se[0x610/4]|=1;p->se[0x40/4]=0;
}
static uint32_t read32(void *ctx,uint32_t a) {
	struct model *p=ctx;
	if(a==SE+0x804) {
		unsigned n=p->rx_n-p->rx_at;return n?0x80000000u|((n%4)<<28)|((n+3)/4):0;
	}
	if(a==SE+0x780) {
		uint32_t v=0;for(unsigned i=0;i<4 && p->rx_at<p->rx_n;i++)v|=(uint32_t)p->rx[p->rx_at++]<<(8*i);return v;
	}
	if(a==SE+0x800)return 0;
	return *cell(p,a);
}
static void write32(void *ctx,uint32_t a,uint32_t v) {
	struct model *p=ctx;p->writes++;
	CHECK(a!=PIN(87) && a!=PIN(87)+4);
	if(a==PIN(76)+4) {
		if(!v) { p->low_at=p->time;p->low_set=true; }
		else { CHECK(v==2 && p->low_set && p->time-p->low_at>=5000);p->high_at=p->time;p->high_set=true; }
		*cell(p,a)=v;return;
	}
	if(a==PIN(76))CHECK(p->low_set && !(p->pin[76]&2) && (v&0x200));
	if(p->restore_fail && a==PIN(85) && v==p->saved_cfg[85])return;
	if(a==VOTE) {
		*cell(p,a)=v;
		const unsigned off[]={0x17004,0x17008,0x17620},bit[]={6,7,15};
		for(unsigned i=0;i<3;i++)p->gcc[off[i]/4]=((v&(1u<<bit[i])) && !p->stuck_clock)?0:0x80000000u;
		return;
	}
	if(a==RCG) { *cell(p,a)=v&~1u;return; }
	if(a==SE+0x618) { p->se[0x610/4]&=~v;return; }
	if(a==SE+0x604) {
		if(!p->stuck_cancel) { p->se[0x610/4]|=(v==4?1u<<4:1u<<5);p->se[0x40/4]=0;p->rx_n=p->rx_at=0; }
		return;
	}
	if(a==SE+0x600) {
		CHECK(((v>>9)&127)==0x4c);p->serial++;p->op=v>>27;CHECK(p->op==1||p->op==2);
		if(p->other_vote)p->gcc[0x5200c/4]|=1u<<28;
		if(p->fail_at==p->serial) {
			p->se[0x40/4]=1;
			p->se[0x610/4]=p->which==1?1u<<10:p->which==2?1u<<13:0;return;
		}
		if(p->op==1) { p->tx_at=0;p->tx_n=p->se[0x26c/4];CHECK(p->tx_n<=129); }
		else {
			p->rx_at=0;p->rx_n=p->se[0x270/4];p->time+=(p->rx_n+1)*90;CHECK(p->rx_n<=128 && p->reg+p->rx_n<=128);
			for(unsigned i=0;i<p->rx_n;i++)p->rx[i]=tas_read(p,p->reg+i);
			p->se[0x610/4]=1;p->se[0x40/4]=0;
		}
		return;
	}
	if(a==SE+0x700) {
		if(p->fail_at==p->serial)return;
		for(unsigned i=0;i<4 && p->tx_at<p->tx_n;i++)p->tx[p->tx_at++]=(uint8_t)(v>>(8*i));
		if(p->tx_at==p->tx_n)complete_write(p);
		return;
	}
	*cell(p,a)=v;
}
static uint64_t clock_us(void *ctx) { return ((struct model *)ctx)->time; }
static void delay_us(void *ctx,unsigned n) { ((struct model *)ctx)->time+=n; }
static void log_line(void *ctx,const char *fmt,...) {
	struct model *p=ctx;char s[1024];va_list ap;va_start(ap,fmt);vsnprintf(s,sizeof(s),fmt,ap);va_end(ap);p->lines++;
	CHECK(p->lines<=30);if(!p->which && !p->corrupt_p && !p->corrupt_y)fputs(s,stdout);
}
static void init(void) {
	memset(&m,0,sizeof(m));memset(ram,0,sizeof(ram));
	m.se[0x68/4]=0x301;m.se[0xe24/4]=32u<<16;m.se[0xe28/4]=32u<<16;
	m.gcc[0x17628/4]=1;m.gcc[0x17004/4]=m.gcc[0x17008/4]=m.gcc[0x17620/4]=0x80000000;
	m.gcc[0x5200c/4]=1u<<28;m.cfg[76]=0x200;m.cfg[85]=0x123;m.cfg[86]=0x103;m.cfg[87]=0x341;
	memcpy(m.saved_gcc,m.gcc,sizeof(m.gcc));memcpy(m.saved_se,m.se,sizeof(m.se));memcpy(m.saved_cfg,m.cfg,sizeof(m.cfg));
}
static void preserved(const struct mi8_tas_result *r,bool se_ok,bool pins_ok) {
	CHECK(!m.forbidden && m.time<=10000000 && !m.pin[76]);
	CHECK(m.cfg[87]==m.saved_cfg[87]);
	CHECK((m.gcc[0x5200c/4]&VOTES)==(m.saved_gcc[0x5200c/4]&VOTES));
	CHECK(r->reset_low && r->clocks_restored && r->se_restored==se_ok && r->pins_restored==pins_ok);
	if(pins_ok)CHECK(m.cfg[85]==m.saved_cfg[85] && m.cfg[86]==m.saved_cfg[86]);
	if(se_ok) {
		const unsigned regs[]={0x24,0x28,0x48,0x7c,0x254,0x258,0x260,0x264,0x26c,0x270,0x278,0x284,0x288,0x614,0x80c,0x810,0x814,0xe18,0xe1c,0xe30};
		for(unsigned i=0;i<sizeof(regs)/sizeof(regs[0]);i++)CHECK(m.se[regs[i]/4]==m.saved_se[regs[i]/4]);
	}
}
static bool trace(void *ctx,const struct mi8_tas_block *b,uint32_t at,uint8_t book,uint8_t page,uint8_t reg,const uint8_t *v,unsigned n,unsigned ms) {
	uint32_t *prev=ctx;if(*prev!=b->offset){printf("B %u %u %u %u %u %u %u\n",b->offset,b->type,b->words,b->p_present,b->p_crc,b->y_present,b->y_crc);*prev=b->offset;}
	if(!n)printf("D %u %u\n",at,ms);
	for(unsigned i=0;i<n;i++)printf("W %u %u %u %u %u\n",at,book,page,reg+i,v[i]);
	return true;
}
static uint8_t *file(const char *name,size_t *n) {
	FILE *f=fopen(name,"rb");CHECK(f);CHECK(!fseek(f,0,SEEK_END));long s=ftell(f);CHECK(s>0);*n=(size_t)s;rewind(f);
	uint8_t *buf=malloc(*n);CHECK(buf);CHECK(fread(buf,1,*n,f)==*n);CHECK(!fclose(f));return buf;
}
int main(int argc,char **argv) {
	CHECK(argc>=3);size_t size;uint8_t *raw=file(argv[1],&size);struct mi8_tas_firmware fw;
	CHECK(mi8_tas2557_parse(raw,size,&fw,NULL,NULL));
	if(!strcmp(argv[2],"--dump")){uint32_t prev=~0u;CHECK(mi8_tas2557_parse(raw,size,&fw,trace,&prev));free(raw);return 0;}
	FILE *f=fopen(argv[2],"rb");CHECK(f);unsigned b,p,r,v,config_index;
	CHECK(fscanf(f,"%u %u %u %u",&expected_n,&prog_end,&v,&config_index)==4);expected_p=(uint8_t)v;CHECK(expected_n<20000);
	for(unsigned i=0;i<expected_n;i++){CHECK(fscanf(f,"%u %u %u %u",&b,&p,&r,&v)==4);expected[i]=(struct expected){b,p,r,v};}fclose(f);
	struct mi8_tas_io io={&m,read32,write32,clock_us,delay_us,log_line};struct mi8_tas_result result;
	init();CHECK(mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(m.seen==expected_n && result.blocks==4 && m.p_reads==1);
	CHECK(m.flags[0]==1 && m.flags[1]==1 && m.flags[2]==1);unsigned transfers=result.transfers;preserved(&result,true,true);
	for(unsigned kind=1;kind<=3;kind++)for(unsigned pos=1;pos<=transfers;pos+=97) {
		init();m.which=kind;m.fail_at=pos;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));
		CHECK(result.nacks==(kind==1) && result.arbitration==(kind==2) && result.timeouts==(kind==3));preserved(&result,true,true);
	}
	for(unsigned kind=4;kind<=5;kind++){init();m.which=kind;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(!m.seen);preserved(&result,true,true);}
	init();m.which=6;m.se[0x68/4]=0x201;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(!m.writes);preserved(&result,true,true);
	init();m.which=7;m.se[0x64/4]=1;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(!m.writes);preserved(&result,true,true);
	init();m.which=8;m.stuck_clock=true;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(!m.seen);preserved(&result,true,true);
	init();m.corrupt_p=true;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(!strcmp(result.error,"CRC MISMATCH"));preserved(&result,true,true);
	init();m.corrupt_y=true;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(!strcmp(result.error,"Y readback MISMATCH"));preserved(&result,true,true);
	init();m.which=9;m.gcc[0x17638/4]=1;m.gcc[(0x17624+0x1c)/4]=0x601;m.gcc[(0x17624+0x20)/4]=1;
	CHECK(mi8_tas2557_run(&io,raw,size,10000000,&result));preserved(&result,true,true);
	init();m.which=10;m.gcc[0x17628/4]=0x601;CHECK(mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(m.gcc[0x17628/4]==0x601);preserved(&result,true,true);
	init();m.which=3;m.fail_at=20;m.stuck_cancel=true;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));preserved(&result,false,true);
	init();m.which=11;m.restore_fail=true;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));preserved(&result,true,false);
	init();m.which=12;m.other_vote=true;m.gcc[0x5200c/4]=0;CHECK(mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(m.gcc[0x5200c/4]&(1u<<28));preserved(&result,true,true);
	init();m.which=13;CHECK(!mi8_tas2557_run(&io,raw,size,100000,&result));CHECK(!m.writes);preserved(&result,true,true);
	/* Every truncation is rejected; length/header/index/block mutation cases follow. */
	for(size_t i=0;i<size;i++)CHECK(!mi8_tas2557_parse(raw,i,&fw,NULL,NULL));
	const unsigned offsets[]={0,4,8,12,16,20,config_index,config_index+1,fw.program.offset,fw.program.offset+8,fw.pre.offset,fw.coeff.offset+8};
	for(unsigned i=0;i<sizeof(offsets)/sizeof(offsets[0]);i++){unsigned at=offsets[i];uint8_t old=raw[at];raw[at]^=0x80;CHECK(!mi8_tas2557_parse(raw,size,&fw,NULL,NULL));raw[at]=old;}
	unsigned bulk=fw.program.offset+12;
	while(raw[bulk+2]!=0x85)bulk+=4;
	uint8_t len0=raw[bulk],len1=raw[bulk+1],reg0=raw[bulk+6];
	raw[bulk]=raw[bulk+1]=0;CHECK(!mi8_tas2557_parse(raw,size,&fw,NULL,NULL));
	raw[bulk]=len0;raw[bulk+1]=len1;raw[bulk+6]=127;CHECK(!mi8_tas2557_parse(raw,size,&fw,NULL,NULL));raw[bulk+6]=reg0;
	/* A valid parser stream containing an unsafe register must stop before MMIO writes. */
	unsigned command=fw.program.offset+12+8+2;uint8_t saved=raw[command];raw[command]=4;
	init();m.which=14;CHECK(!mi8_tas2557_run(&io,raw,size,10000000,&result));CHECK(!m.writes);raw[command]=saved;
	/* Deadline during download still leaves reset low and restores configuration. */
	init();m.which=15;CHECK(!mi8_tas2557_run(&io,raw,size,250000,&result));preserved(&result,true,true);
	free(raw);printf("TAS2557 SELFTEST PASS %lu/%lu\n",checks,checks);return 0;
}
