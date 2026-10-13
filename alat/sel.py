"""Tampilkan sel-sel per baris tabel atas + kotak bagian kepala satu file (berisi data pribadi: hanya untuk
pemeriksaan di layar). Pakai: python alat/sel.py <folder> <kode> [halaman]"""
import json
import re
import sys
from pathlib import Path
from statistics import median

import ocr_kk.urai as U
from ocr_kk.tata import luruskan

d = json.loads((Path(sys.argv[1]) / f'{sys.argv[2]}.json').read_text())
ks = luruskan(d['halaman'][int(sys.argv[3]) if len(sys.argv) > 3 else 0]['kotak'])
tinggi = median(k['h'] for k in ks)
nik = [k for k in ks if U.jenis_sel_t1(k['t'])[0] == 'nik' and not re.match(r'(?i)\s*no', k['t'])]
print('--- kepala')
for k in sorted(ks, key=lambda k: k['cy']):
    if nik and k['cy'] < min(n['cy'] for n in nik) - 2 * tinggi:
        print(f"  {int(k['x0'])}-{int(k['x1'])} y{int(k['cy'])} s{k['s']:.2f} {k['t']}")
print('--- tabel atas')
lain = [k for k in ks if k not in nik and min(n['cy'] for n in nik) - 2 * tinggi < k['cy'] < max(n['cy'] for n in nik) + tinggi]
b, _ = U.kelompokkan(nik, lain, U.jarak_antar([k['cy'] for k in nik], 2.2 * tinggi))
for r in b:
    print('  ' + ' | '.join(f"{k['t']}[{U.jenis_sel_t1(k['t'])[0]} {k['s']:.2f}]" for k in r))
