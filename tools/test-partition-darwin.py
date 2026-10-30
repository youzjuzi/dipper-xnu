#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic GPT and sandboxed shell tests. No ADB or real block devices."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


m = module('partition', 'partition-darwin.py')
f = module('fixtures', 'test-restore-android-layout.py')
f.N = 30038016
NEW_GUID = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'


class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entries = {1:f.entry('persist',6,100,1),21:f.entry('userdata',393216,30038010,21)}
        self.c = dict(schema_version=1, device='dipper', disk='/dev/block/sda', sector_size=4096,
                      disk_bytes=123035713536, serial='TEST', twrp_version='3.7.0_9-0',
                      sgdisk_sha256='a'*64, darwin_size_gib=24, darwin_guid=NEW_GUID)
        self.write()

    def write(self):
        p,b = f.captures(self.entries)
        for key,data in [('before_primary',p),('before_backup',b)]:
            (self.root/key).write_bytes(data)
            self.c[key] = dict(path=key,sha256=m.gpt.sha(data))
        self.save()

    def save(self):
        self.path=self.root/'config.json'; self.path.write_text(json.dumps(self.c))

    def load(self): return m.load_plan(self.path)

    def test_valid(self):
        c,b,g,t,p=self.load()
        self.assertEqual((p['userdata_end'],p['darwin_start'],p['darwin_end']),(23746559,23746560,30038013))
        self.assertEqual(p['darwin_bytes'],25769795584)
        self.assertEqual(p['alignment_shortfall_bytes'],8192)
        self.assertEqual(t[:20*128],g['table'][:20*128])
        subprocess.run(['sh','-n'],input=m.render_script(c,b,p),text=True,check=True)

    def test_bad_hash(self):
        self.c['before_primary']['sha256']='0'*64;self.save()
        with self.assertRaisesRegex(ValueError,'SHA256'):self.load()

    def test_already_partitioned(self):
        self.entries[21]=f.entry('userdata',393216,23746559,21)
        self.entries[22]=f.entry('darwin',23746560,30038013,22);self.write()
        with self.assertRaisesRegex(ValueError,'already exists'):self.load()

    def test_userdata_not_last(self):
        self.entries[21]=f.entry('userdata',393216,23746559,21)
        self.entries[22]=f.entry('other',23746560,30038013,22);self.write()
        with self.assertRaisesRegex(ValueError,'last physical'):self.load()

    def test_large_gap(self):
        self.entries[21]=f.entry('userdata',393216,30037000,21);self.write()
        with self.assertRaisesRegex(ValueError,'free space'):self.load()

    def test_no_free_entry(self):
        self.entries[32]=self.entries.pop(21);self.write()
        with self.assertRaisesRegex(ValueError,'free GPT entry'):self.load()

    def test_oversized(self):
        self.c['darwin_size_gib']=112;self.save()
        with self.assertRaisesRegex(ValueError,'less than 8 GiB'):self.load()

    def test_invalid_sizes(self):
        for size in [0,-1,True,'24',24.5]:
            with self.subTest(size=size):
                self.c['darwin_size_gib']=size;self.save()
                with self.assertRaises(ValueError):self.load()

    def test_invalid_guid(self):
        for guid in ['; touch /tmp/never','00000000-0000-0000-0000-000000000000']:
            self.c['darwin_guid']=guid;self.save()
            with self.assertRaises(ValueError):self.load()

    def test_attributes(self):
        self.entries[21]=f.entry('userdata',393216,30038010,21,1);self.write()
        with self.assertRaisesRegex(ValueError,'attributes'):self.load()

    def test_changed_results_and_stale_sizes(self):
        c,b,g,t,p=self.load()
        entries={i+1:t[i*128:(i+1)*128] for i in range(32) if any(t[i*128:(i+1)*128])}
        primary,backup=f.captures(entries)
        self.assertIn('PASS',m.verify(c,g,t,p,primary,backup))
        self.assertIn('PASS',m.verify(c,g,t,p,primary,backup,p['userdata_bytes'],p['darwin_bytes']))
        with self.assertRaisesRegex(ValueError,'kernel sizes'):m.verify(c,g,t,p,primary,backup,121425080320,p['darwin_bytes'])
        entries[1]=f.entry('persist',6,101,1)
        with self.assertRaisesRegex(ValueError,'differ'):m.verify(c,g,t,p,*f.captures(entries))

    def test_cli_no_overwrite_and_rebased_config(self):
        args=[sys.executable,str(Path(m.__file__)),'--config',str(self.path)]
        out=self.root/'output'
        self.assertEqual(subprocess.run(args+['--output-dir',str(out)],capture_output=True).returncode,0)
        self.assertEqual(m.load_plan(out/'config.json')[-1],self.load()[-1])
        self.assertNotEqual(subprocess.run(args+['--output-dir',str(out)],capture_output=True).returncode,0)
        self.assertNotEqual(subprocess.run(args+['--kernel-userdata-bytes','1'],capture_output=True).returncode,0)

    def shell(self, fault=None):
        """Redirect every device/sysfs/proc path and command to this temporary fixture."""
        import os
        c,b,g,t,p=self.load(); box=self.root/'box';box.mkdir()
        for name in ['bin','dev/block','sys/class/block/sda21/holders','proc/self','tmp']:(box/name).mkdir(parents=True,exist_ok=True)
        (box/'sys/class/block/sda21/dev').write_text('259:5\n')
        (box/'proc/self/mountinfo').write_text('')
        (box/'proc/mounts').write_text('')
        (box/'proc/swaps').write_text('Filename Type Size Used Priority\n')
        def program(name, body):
            path=box/'bin'/name;path.write_text('#!/bin/sh\n'+body+'\n');path.chmod(0o700)
        program('id','echo '+('1000' if fault=='root' else '0'))
        program('getprop','case "$1" in ro.product.device) echo dipper;; ro.serialno) echo '+('OTHER' if fault=='identity' else 'TEST')+';; ro.twrp.version) echo 3.7.0_9-0;; esac')
        program('blockdev','case "$1" in --getss) echo 4096;; --getsize64) echo 123035713536;; esac')
        program('sync',':')
        program('umount','exit '+('1' if fault=='umount' else '0'))
        dd=box/'bin/dd';dd.write_text('#!'+sys.executable+'\nimport sys,shutil\na=dict(x.split("=",1) for x in sys.argv[1:])\nassert a["if"]=='+repr(str(box/'dev/block/sda'))+'\nsource='+repr(str(self.root))+'+("/before_primary" if a["skip"]=="0" else "/before_backup")\nshutil.copyfile(source,a["of"])\n');dd.chmod(0o700)
        tool=box/'tmp/sgdisk';log=box/'tool-log';tool.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> '+str(log)+'\n');tool.chmod(0o700)
        c['sgdisk_sha256']=m.gpt.sha(tool.read_bytes())
        if fault=='tool':c['sgdisk_sha256']='0'*64
        script=m.render_script(c,b,p)
        import re
        mapping={real:str(box/real.lstrip('/'))+('/' if real.endswith('/') else '')
                 for real in ['/dev/block','/sys/class/block','/proc/self/mountinfo','/proc/mounts','/proc/swaps','/tmp/']}
        script=re.sub('|'.join(re.escape(x) for x in mapping),lambda match:mapping[match.group()],script)
        if fault=='gpt':(self.root/'before_primary').write_bytes(b'changed')
        if fault=='holder':(box/'sys/class/block/sda21/holders/dm-0').touch()
        if fault in ('mounted','umount'):
            (box/'proc/self/mountinfo').write_text('1 0 259:5 / /data rw - ext4 /fake rw\n')
            (box/'proc/mounts').write_text('/fake /data ext4 rw 0 0\n')
        if fault=='swap':(box/'proc/swaps').write_text('Filename Type Size Used Priority\n/fake partition 1 0 -1\n')
        if fault=='existing':(box/'dev/block/sda22').touch()
        env=dict(os.environ,PATH=str(box/'bin')+':/usr/bin:/bin')
        args=['sh','-s','--']+([] if fault=='confirmation' else ['CREATE-DARWIN'])
        result=subprocess.run(args,input=script,text=True,capture_output=True,env=env)
        return result,log.read_text() if log.exists() else ''

    def test_shell_success_fake_device(self):
        result,log=self.shell();self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--delete=21',log);self.assertIn('--new=22:',log)
        self.assertNotIn('--delete=1 ',log)

    def test_shell_fail_closed(self):
        # A new sandbox for every fault; none may reach even mock sgdisk.
        for fault in ['root','identity','tool','gpt','holder','mounted','umount','swap','existing','confirmation']:
            with self.subTest(fault=fault):
                case=PartitionTests();case.setUp()
                try:
                    result,log=case.shell(fault)
                    self.assertNotEqual(result.returncode,0,result.stdout)
                    self.assertEqual(log,'')
                finally:case.doCleanups()


if __name__=='__main__':unittest.main()
