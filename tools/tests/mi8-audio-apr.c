/* SPDX-License-Identifier: MIT */
/* Synthetic remote endpoint. Protocol fixtures use literal on-wire values. */
#include "mi8_glink.h"
#include "mi8_audio.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

static unsigned checks;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr, "FAIL line %u: %s\n", __LINE__, #x); exit(1); } } while (0)
#define DESC 64u
#define TX 256u
#define RX 16640u
#define FIFO 16384u
struct peer {
    unsigned char mem[33024];
    uint64_t now;
    uint16_t local_cid, remote_cid;
    unsigned received, bytes, closes, requests, opens, qrtr_hello;
    unsigned local_ids[64], local_sizes[64], intents;
    unsigned logs;
    bool running, offer_remote, grant, reply, legacy, bad_version, state_zero;
    bool hold_close, fragment_reply, silent_open, malformed_first, no_reuse;
    unsigned char packet[16384];
    unsigned packet_size, taken, packet_intent, reused_unnegotiated;
    unsigned char pending[20];
    bool have_pending;
};
static uint32_t rd(const void *v) { const unsigned char *p=v; return p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24; }
static void wr(void *v,uint32_t n) { unsigned char *p=v; p[0]=n; p[1]=n>>8; p[2]=n>>16; p[3]=n>>24; }
static void hdr(unsigned char *p,unsigned cmd,unsigned cid,uint32_t arg) { p[0]=cmd;p[1]=0;p[2]=cid;p[3]=cid>>8;wr(p+4,arg); }
static void peer_push(struct peer *p,const unsigned char *data,unsigned size) {
    unsigned head=rd(p->mem+DESC+12), n=(size+7)&~7u;
    CHECK(n < FIFO);
    for(unsigned i=0;i<n;i++)p->mem[RX+(head+i)%FIFO]=i<size?data[i]:0;
    wr(p->mem+DESC+12,(head+n)%FIFO);
}
static void control(struct peer *p,unsigned cmd,unsigned cid,uint32_t arg) {
    unsigned char b[8];hdr(b,cmd,cid,arg);peer_push(p,b,8);
}
static void intent(struct peer *p,unsigned id,unsigned size) {
    unsigned char b[16];hdr(b,5,p->remote_cid,1);wr(b+8,size);wr(b+12,id);peer_push(p,b,16);
}
static void open_peer(struct peer *p,const char *name) {
    unsigned char b[48]={0};unsigned n=(unsigned)strlen(name)+1;
    hdr(b,2,p->remote_cid,n);memcpy(b+8,name,n);peer_push(p,b,n+8);
}
static void respond(struct peer *p,const unsigned char *req) {
    unsigned char b[4096]={0}, frame[4200];unsigned n=24;uint32_t op=rd(req+16);
    b[0]=0x50;b[1]=1;b[4]=3;b[5]=4;b[8]=3;b[9]=5;memcpy(b+12,req+12,4);
    if(op==0x1290c) {wr(b+16,0x1290d);wr(b+20,p->state_zero?0:1);}
    else if(op==0x1292c && p->legacy) {n=28;wr(b+16,0x110e8);wr(b+20,0x1292c);wr(b+24,3);}
    else {
        unsigned count=40, base=p->legacy?28:40, width=p->legacy?8:12;
        n=base+width*count;wr(b+16,p->legacy?0x12906:0x1292d);
        wr(b+base-4,p->bad_version?count+1:count);
        for(unsigned i=0;i<count;i++){wr(b+base+width*i,i+1);wr(b+base+width*i+4,0x100+i+1);if(width==12)wr(b+base+width*i+8,0x200+i+1);}
    }
    b[2]=n;b[3]=n>>8;
    unsigned slot=p->intents;
    for(unsigned i=0;i<p->intents;i++)if(p->local_sizes[i]>=n){slot=i;break;}
    if(slot==p->intents){memcpy(p->pending,req,20);p->have_pending=true;control(p,7,p->remote_cid,n);return;}
    p->have_pending=false;
    if(p->malformed_first) {
        hdr(frame,9,p->remote_cid,p->local_ids[slot]);wr(frame+8,n);wr(frame+12,0);memcpy(frame+16,b,n);
        frame[16+12]^=0x40;peer_push(p,frame,n+16);p->malformed_first=false;
    }
    if(p->fragment_reply){
        unsigned first=20;hdr(frame,9,p->remote_cid,p->local_ids[slot]);wr(frame+8,first);wr(frame+12,n-first);memcpy(frame+16,b,first);peer_push(p,frame,first+16);
        hdr(frame,12,p->remote_cid,p->local_ids[slot]);wr(frame+8,n-first);wr(frame+12,0);memcpy(frame+16,b+first,n-first);peer_push(p,frame,n-first+16);
    } else {hdr(frame,9,p->remote_cid,p->local_ids[slot]);wr(frame+8,n);wr(frame+12,0);memcpy(frame+16,b,n);peer_push(p,frame,n+16);}
}
static void turn(struct peer *p) {
    if(p->running)return;
    p->running=true;
    unsigned tail=rd(p->mem+DESC), head=rd(p->mem+DESC+4);
    while(tail!=head){
        unsigned char b[8400]={0};for(unsigned i=0;i<16;i++)b[i]=p->mem[TX+(tail+i)%FIFO];
        unsigned cmd=b[0]|b[1]<<8,cid=b[2]|b[3]<<8,arg=rd(b+4),size=8;
        if(cmd==2)size+=arg&0xffff;
        if(cmd==5)size+=arg*8;
        if(cmd==9||cmd==12)size=16+rd(b+8);
        CHECK(size<=sizeof(b));for(unsigned i=16;i<size;i++)b[i]=p->mem[TX+(tail+i)%FIFO];
        size=(size+7)&~7u;tail=(tail+size)%FIFO;wr(p->mem+DESC,tail);
        switch(cmd){
        case 0:control(p,0,1,p->no_reuse?0:1);control(p,1,1,p->no_reuse?0:1);if(!p->silent_open)open_peer(p,p->local_cid==1?"IPCRTR":"apr_audio_svc");break;
        case 2:p->opens++;CHECK(cid==p->local_cid);control(p,4,cid,0);if(p->offer_remote)intent(p,0,16384);break;
        case 5:
            for(unsigned i=0;i<arg;i++){CHECK(p->intents<64);p->local_sizes[p->intents]=rd(b+8+8*i);p->local_ids[p->intents]=rd(b+12+8*i);p->intents++;}
            if(p->have_pending)respond(p,p->pending);
            break;
        case 7:p->requests++;control(p,8,p->remote_cid,p->grant);if(p->grant)intent(p,17,arg);break;
        case 9:case 12:
            CHECK(cid==p->local_cid);CHECK(p->taken+rd(b+8)<=sizeof(p->packet));
            if(cmd==9){CHECK(!p->taken);p->packet_intent=arg;}else CHECK(p->taken&&p->packet_intent==arg);
            memcpy(p->packet+p->taken,b+16,rd(b+8));p->taken+=rd(b+8);p->bytes+=rd(b+8);
            if(!rd(b+12)){
                p->received++;p->packet_size=p->taken;control(p,14,p->remote_cid,arg);
                if(p->local_cid==1 && p->taken>=32){if(rd(p->packet+4)==2)p->qrtr_hello++;}
                else if(p->reply && p->taken==20)respond(p,p->packet);
                p->taken=0;
            }break;
        case 3:p->closes++;if(!p->hold_close)control(p,11,cid,0);break;
        case 14:if(p->no_reuse)p->reused_unnegotiated++;break;
        default:break;
        }
        head=rd(p->mem+DESC+4);
    }p->running=false;
}
static bool item(void *v,uint32_t id,uint32_t *base,uint32_t *size) {
    (void)v;if(id==478){*base=DESC;*size=32;}else if(id==479){*base=TX;*size=FIFO;}else if(id==480){*base=RX;*size=FIFO;}else return false;return true;
}
static void read_mem(void *v,uint32_t at,void *b,uint32_t n){struct peer*p=v;CHECK(at+n<=sizeof(p->mem));memcpy(b,p->mem+at,n);}
static void write_mem(void *v,uint32_t at,uint32_t n){struct peer*p=v;CHECK(at+4<=sizeof(p->mem));wr(p->mem+at,n);}
static void ring(void*v){turn(v);}
static void sleep_us(void*v,uint32_t us){struct peer*p=v;p->now+=us;turn(p);}
static uint64_t now_us(void*v){return ((struct peer*)v)->now;}
static void log_line(void*v,const char*fmt,...){(void)fmt;((struct peer*)v)->logs++;}
static bool alive(void*v){(void)v;return true;}
static struct mi8_glink_cfg cfg(struct peer *p) {
    struct mi8_glink_cfg c={0};c.name="synthetic";c.remote_pid=2;c.smem_item=item;c.smem_read=read_mem;c.smem_write32=write_mem;c.ring=ring;c.sleep_us=sleep_us;c.now_us=now_us;c.log=log_line;c.ctx=p;return c;
}
static void received(void*v,const void*data,size_t n){struct peer*p=v;p->received++;p->bytes+=(unsigned)n;CHECK(n && data);}
static void init(struct peer*p){memset(p,0,sizeof(*p));p->local_cid=2;p->remote_cid=43;p->offer_remote=true;p->grant=true;}
static struct mi8_glink *raw(struct peer *p) {
    static const uint32_t sizes[20]={512,512,512,512,512,512,512,512,512,512,512,512,512,512,512,512,512,512,512,512};
    struct mi8_glink_cfg c=cfg(p);c.raw.name="apr_audio_svc";c.raw.local_cid=2;c.raw.intent_sizes=sizes;c.raw.intent_count=20;c.raw.receive=received;c.raw.ctx=p;
    struct mi8_glink*g=mi8_glink_create(&c);CHECK(g);CHECK(mi8_glink_start(g)==0);
    for(unsigned i=0;i<20;i++)mi8_glink_poll_once(g);
    return g;
}
static void test_raw(void) {
    struct peer p;init(&p);struct mi8_glink*g=raw(&p);struct mi8_glink_channel_status s;
    CHECK(mi8_glink_raw_status(g,&s)==0);CHECK(s.open&&s.negotiated&&s.local_cid==2&&s.remote_cid==43);CHECK(p.intents==20);
    unsigned char packet[12000];memset(packet,0x5a,sizeof(packet));
    CHECK(mi8_glink_raw_send(g,packet,sizeof(packet),200)==0);CHECK(p.packet_size==12000);CHECK(!memcmp(p.packet,packet,12000));CHECK(!p.qrtr_hello);
    CHECK(mi8_glink_raw_close(g,100)==0);CHECK(p.closes==1);mi8_glink_destroy(g);
    init(&p);p.offer_remote=false;p.grant=true;g=raw(&p);CHECK(mi8_glink_raw_send(g,packet,700,200)==0);CHECK(p.requests==1);mi8_glink_destroy(g);
    init(&p);p.offer_remote=false;p.grant=false;g=raw(&p);CHECK(mi8_glink_raw_send(g,packet,700,200)==ENOBUFS);mi8_glink_destroy(g);
    init(&p);p.hold_close=true;g=raw(&p);CHECK(mi8_glink_raw_close(g,50)==ETIMEDOUT);CHECK(p.now<=51000);mi8_glink_destroy(g);
}
static void reply_header(unsigned char*b,unsigned n,unsigned token,unsigned opcode) {
    memset(b,0,n);b[0]=0x50;b[1]=1;b[2]=n;b[3]=n>>8;b[4]=3;b[5]=4;b[8]=3;b[9]=5;wr(b+12,token);wr(b+16,opcode);
}
static void test_codec(void) {
    unsigned char b[1024];struct mi8_apr_reply r;
    static const unsigned char want[20]={0x50,2,20,0,3,5,0,0,3,4,0,0,0x78,0x56,0x34,0x12,0x0c,0x29,1,0};
    CHECK(mi8_apr_encode_request(b,0x12345678,0x1290c)==0);CHECK(!memcmp(b,want,20));
    mi8_apr_begin(&r,0x1290c,7);reply_header(b,24,7,0x1290d);wr(b+20,1);
    CHECK(mi8_apr_receive(&r,b,23)!=0&&!r.done);CHECK(mi8_apr_receive(&r,b,24)==0&&r.done&&r.state==1);
    for(unsigned kind=0;kind<7;kind++){
        mi8_apr_begin(&r,0x1290c,7);reply_header(b,24,7,0x1290d);wr(b+20,1);
        if(kind==0)b[12]=8;
        if(kind==1)b[16]=1;
        if(kind==2)b[5]=5;
        if(kind==3)b[0]=0x60;
        if(kind==4)b[2]=25;
        if(kind==5)b[1]=2;
        if(kind==6)b[4]=4;
        CHECK(mi8_apr_receive(&r,b,24)!=0&&!r.done);
    }
    mi8_apr_begin(&r,0x1292c,9);reply_header(b,520,9,0x1292d);wr(b+36,40);
    for(unsigned i=0;i<40;i++){wr(b+40+12*i,i+1);wr(b+44+12*i,0xabc000+i);wr(b+48+12*i,0xdef000+i);}
    CHECK(mi8_apr_receive(&r,b,520)==0&&r.done&&r.num_services==40);CHECK(r.services[39].id==40&&r.services[39].version==0xabc027&&r.services[39].branch==0xdef027);
    mi8_apr_begin(&r,0x1292c,9);wr(b+36,41);CHECK(mi8_apr_receive(&r,b,520)!=0&&!r.done);
    mi8_apr_begin(&r,0x1292c,9);wr(b+36,0xffffffff);CHECK(mi8_apr_receive(&r,b,520)!=0&&!r.done);
    mi8_apr_begin(&r,0x1292c,9);reply_header(b,28,9,0x110e8);wr(b+20,0x1292c);wr(b+24,3);CHECK(mi8_apr_receive(&r,b,28)==0&&r.done&&r.error==ENOTSUP);
    mi8_apr_begin(&r,0x1290c,9);CHECK(mi8_apr_receive(&r,b,28)!=0&&!r.done);
    mi8_apr_begin(&r,0x12905,11);reply_header(b,348,11,0x12906);wr(b+24,40);
    for(unsigned i=0;i<40;i++){wr(b+28+8*i,i+1);wr(b+32+8*i,500+i);}
    CHECK(mi8_apr_receive(&r,b,348)==0&&r.num_services==40&&r.services[39].version==539);
}
static void test_flow(void) {
    struct peer p;struct mi8_glink_cfg c;
    init(&p);p.reply=true;p.fragment_reply=true;p.malformed_first=true;c=cfg(&p);CHECK(mi8_audio_run(&c,alive,&p));CHECK(p.closes==1&&p.requests<=2&&p.logs<60&&p.now<18000000);
    init(&p);p.reply=true;p.legacy=true;c=cfg(&p);CHECK(mi8_audio_run(&c,alive,&p));CHECK(p.closes==1);
    init(&p);p.reply=true;p.bad_version=true;c=cfg(&p);CHECK(!mi8_audio_run(&c,alive,&p));CHECK(p.closes==1&&p.logs<60&&p.now<18000000);
    init(&p);p.reply=false;c=cfg(&p);CHECK(!mi8_audio_run(&c,alive,&p));CHECK(p.closes==1&&p.now<18000000);
    init(&p);p.silent_open=true;c=cfg(&p);CHECK(!mi8_audio_run(&c,alive,&p));CHECK(p.now<18000000&&p.logs<60);
    init(&p);p.reply=true;p.state_zero=true;c=cfg(&p);CHECK(!mi8_audio_run(&c,alive,&p));CHECK(p.closes==1&&p.now<18000000);
    init(&p);p.no_reuse=true;p.reply=true;c=cfg(&p);(void)mi8_audio_run(&c,alive,&p);CHECK(!p.reused_unnegotiated);
}
static void qrtr_receive(void*v,uint32_t node,uint32_t port,const void*b,size_t n) {
    struct peer*p=v;CHECK(node==2&&port==4103&&n==4);CHECK(!memcmp(b,"PING",4));p->received++;
}
static void test_qrtr_default(void) {
    struct peer p;init(&p);p.local_cid=1;struct mi8_glink_cfg c=cfg(&p);struct mi8_glink*g=mi8_glink_create(&c);
    CHECK(g&&mi8_glink_start(g)==0);for(unsigned i=0;i<20;i++)mi8_glink_poll_once(g);
    static const unsigned sizes[10]={2048,2048,2048,2048,2048,8192,8192,8192,17408,17408};
    CHECK(p.intents==10);for(unsigned i=0;i<10;i++)CHECK(p.local_sizes[i]==sizes[i]);
    const struct redwood_qrtr_ops*ops=mi8_glink_qrtr_ops(g);CHECK(ops);
    struct redwood_qrtr_port*port=ops->open(qrtr_receive,NULL,&p);CHECK(port);
    unsigned char packet[52]={0},frame[80];wr(packet,1);wr(packet+4,2);wr(packet+8,2);wr(packet+12,0xfffffffe);wr(packet+20,20);wr(packet+24,1);wr(packet+28,0xfffffffe);wr(packet+32,2);
    hdr(frame,9,43,p.local_ids[0]);wr(frame+8,52);wr(frame+12,0);memcpy(frame+16,packet,52);peer_push(&p,frame,68);
    for(unsigned i=0;i<10;i++)mi8_glink_poll_once(g);
    CHECK(p.qrtr_hello==1);
    CHECK(ops->send(port,2,4103,"PING",4)==0);CHECK(p.packet_size==36&&rd(p.packet)==1&&rd(p.packet+4)==1&&rd(p.packet+8)==1&&rd(p.packet+12)==16384&&rd(p.packet+20)==4&&rd(p.packet+24)==2&&rd(p.packet+28)==4103&&!memcmp(p.packet+32,"PING",4));
    unsigned before=p.received;wr(packet,1);wr(packet+4,1);wr(packet+8,2);wr(packet+12,4103);wr(packet+20,4);wr(packet+24,1);wr(packet+28,16384);memcpy(packet+32,"PING",4);
    hdr(frame,9,43,p.local_ids[0]);wr(frame+8,36);wr(frame+12,0);memcpy(frame+16,packet,36);peer_push(&p,frame,52);
    mi8_glink_poll_once(g);CHECK(p.received==before+1);ops->close(port);mi8_glink_destroy(g);
}
int main(void){test_raw();test_codec();test_flow();test_qrtr_default();printf("SELFTEST PASS %u/%u\n",checks,checks);return 0;}
