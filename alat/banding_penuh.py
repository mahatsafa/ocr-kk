"""Seperti banding.py, tetapi menjalankan alur lengkap baca_file (termasuk bacaan kedua) pada file asli.

Pakai: python alat/banding_penuh.py <daftar file (path per baris)> <kunci.json>   (hanya mencetak angka)"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

from alat.banding import KOLOM, nilai
from ocr_kk.baca import baca_file

daftar = Path(sys.argv[1]).read_text().splitlines()
kunci = json.loads(Path(sys.argv[2]).read_text())
nik_kk = Counter(b['kartuKeluargaId'] for b in kunci.values())
hasil = Counter()
t0 = time.time()
for p in daftar:
    h = baca_file(Path(p).read_bytes())['hasil']
    nilai(h['anggota'], kunci, hasil, 'penuh')
    kk = Counter(kunci[a['nik']]['kartuKeluargaId'] for a in h['anggota'] if a['nik'] in kunci)
    for k, n in kk.items():
        b = next(x for x in kunci.values() if x['kartuKeluargaId'] == k)['kartuKeluarga']['noKK']
        # KK yang hanya berbagi 1 anggota dengan kunci (orang pindah KK) dihitung terpisah: foto itu KK lain
        jenis = 'kk' if n >= 2 or nik_kk[k] == 1 else 'kk-1anggota'
        hasil[jenis] += 1
        hasil[jenis, 'benar'] += h['noKK'] == b
        hasil[jenis, 'kosong'] += not h['noKK']
n = hasil['anggota', 'penuh']
print(f'{len(daftar)} file, {n} anggota cocok NIK, {time.time() - t0:.0f} dtk')
for j in ('kk', 'kk-1anggota'):
    print(f"No. KK ({j}): benar {hasil[j, 'benar']}/{hasil[j]}, kosong {hasil[j, 'kosong']}")
print(f"{'kolom':20s} {'benar':>6s} {'salah':>6s} {'kosong':>7s} {'salah ditandai':>15s}")
for k in KOLOM:
    b, s, ks, sd = (hasil[k, 'penuh', x] for x in ('benar', 'salah', 'kosong', 'salah-ditandai'))
    print(f'{k:20s} {b/max(n,1):6.0%} {s/max(n,1):6.0%} {ks/max(n,1):7.0%} {sd:>15d}')
