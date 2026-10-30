#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic GPT regression tests; no ADB and no real block devices."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import uuid
import zlib

spec = importlib.util.spec_from_file_location('restore_layout', Path(__file__).with_name('restore-android-layout.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
S = 4096
N = 10000


def entry(name, start, end, ident, attrs=0):
    return uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le + uuid.UUID(int=ident).bytes_le + struct.pack('<QQQ', start, end, attrs) + name.encode('utf-16-le').ljust(72, b'\0')


def captures(entries):
    table = bytearray(S)
    for i, e in entries.items(): table[(i-1)*128:i*128] = e
    def header(backup):
        h = bytearray(S);h[:8] = b'EFI PART'
        struct.pack_into('<IIIIQQQQ', h, 8, 0x10000, 92, 0, 0, N-1 if backup else 1, 1 if backup else N-1, 6, N-3)
        h[56:72] = uuid.UUID(int=100).bytes_le
        struct.pack_into('<QIII', h, 72, N-2 if backup else 2, 32, 128, zlib.crc32(table))
        struct.pack_into('<I', h, 16, zlib.crc32(h[:92]));return h
    p = bytearray(S*6);p[S:2*S] = header(False);p[2*S:3*S] = table
    b = bytearray(S*5);b[3*S:4*S] = table;b[4*S:5*S] = header(True)
    return bytes(p),bytes(b)


class RestorationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.before={1:entry('persist',6,100,1),21:entry('userdata',2048,5999,21),22:entry('darwin',6000,9997,22)}
        self.target={1:self.before[1],21:entry('userdata',2048,9994,21)}
        self.config=dict(schema_version=1,device='dipper',disk='/dev/block/sda',sector_size=S,disk_bytes=N*S,serial='TEST',twrp_version='3.7.0_9-0',sgdisk_sha256='a'*64)
        self.write()

    def write(self):
        p,b=captures(self.before);o,_=captures(self.target)
        for key,data in [('before_primary',p),('before_backup',b),('original_primary',o)]:
            (self.base/key).write_bytes(data);self.config[key]={'path':key,'sha256':m.sha(data)}
        self.save()

    def save(self):
        self.path=self.base/'config.json';self.path.write_text(json.dumps(self.config))

    def load(self):return m.load_plan(self.path)

    def test_valid_plan_and_script(self):
        c,b,t,p=self.load();self.assertEqual(p['userdata_bytes'],(9994-2048+1)*S)
        script=m.render_script(c,b,p)
        self.assertIn('RESTORE-ANDROID-GPT',script)
        self.assertIn('/proc/self/mountinfo',script)
        self.assertIn('holders',script)
        self.assertNotIn('mkfs',script)
        self.assertNotIn('adb ',script)
        import subprocess
        subprocess.run(['sh','-n'],input=script,text=True,check=True)

    def test_bad_hash(self):
        self.config['before_primary']['sha256']='0'*64;self.save()
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):self.load()

    def test_header_corruption(self):
        p=bytearray(captures(self.before)[0]);p[S+24]^=1
        with self.assertRaisesRegex(ValueError,'header CRC'):m.parse_gpt(p,S,N)

    def test_table_corruption(self):
        p=bytearray(captures(self.before)[0]);p[2*S+56]^=1
        with self.assertRaisesRegex(ValueError,'table CRC'):m.parse_gpt(p,S,N)

    def test_truncated_capture(self):
        with self.assertRaises(ValueError):m.parse_gpt(captures(self.before)[0][:2*S],S,N)

    def test_mismatched_backup(self):
        with self.assertRaisesRegex(ValueError,'disagree'):m.pair(captures(self.before)[0],captures(self.target)[1],S,N)

    def test_overlap(self):
        self.before[22]=entry('darwin',5999,9997,22);self.write()
        with self.assertRaisesRegex(ValueError,'overlapping'):self.load()

    def test_unrelated_change(self):
        self.target[1]=entry('persist',6,101,1);self.write()
        with self.assertRaisesRegex(ValueError,'unrelated'):self.load()

    def test_darwin_absent(self):
        self.before=self.target;self.write()
        with self.assertRaisesRegex(ValueError,'one darwin'):self.load()

    def test_bad_geometry(self):
        self.config['disk_bytes']+=S;self.save()
        with self.assertRaisesRegex(ValueError,'geometry'):self.load()

    def test_wrong_device(self):
        self.config['device']='other';self.save()
        with self.assertRaises(ValueError):self.load()

    def test_gap(self):
        self.before[22]=entry('darwin',6001,9997,22);self.write()
        with self.assertRaisesRegex(ValueError,'adjacent'):self.load()

    def test_target_overrun(self):
        self.target[21]=entry('userdata',2048,9998,21);self.write()
        with self.assertRaisesRegex(ValueError,'outside'):self.load()

    def test_attributes(self):
        self.target[21]=entry('userdata',2048,9994,21,1);self.write()
        with self.assertRaisesRegex(ValueError,'attributes'):self.load()

    def test_injection(self):
        self.config['serial']='TEST; touch /tmp/never';self.save()
        with self.assertRaisesRegex(ValueError,'invalid serial'):self.load()

    def test_duplicate_guid(self):
        self.before[22]=entry('darwin',6000,9997,21);self.write()
        with self.assertRaisesRegex(ValueError,'duplicate'):self.load()

    def test_cli_verify_and_no_overwrite(self):
        import subprocess,sys
        command=[sys.executable,str(Path(m.__file__)),'--config',str(self.path)]
        out=self.base/'run'
        self.assertEqual(subprocess.run(command+['--output-dir',str(out)],capture_output=True).returncode,0)
        saved=(out/'restore-android-layout.sh').read_bytes()
        self.assertNotEqual(subprocess.run(command+['--output-dir',str(out)],capture_output=True).returncode,0)
        self.assertEqual(saved,(out/'restore-android-layout.sh').read_bytes())
        p,b=captures(self.target);(self.base/'after-p').write_bytes(p);(self.base/'after-b').write_bytes(b)
        args=command+['--verify-primary',str(self.base/'after-p'),'--verify-backup',str(self.base/'after-b'),'--kernel-userdata-bytes']
        self.assertEqual(subprocess.run(args+[str((9994-2048+1)*S)],capture_output=True).returncode,0)
        self.assertNotEqual(subprocess.run(args+['1'],capture_output=True).returncode,0)
        self.assertNotEqual(subprocess.run(command+['--verify-primary',str(self.base/'after-p')],capture_output=True).returncode,0)


if __name__=='__main__':unittest.main()
