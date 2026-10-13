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
hasil = Counter()
t0 = time.time()
for p in daftar:
    h = baca_file(Path(p).read_bytes())['hasil']
    nilai(h['anggota'], kunci, hasil, 'penuh')
n = hasil['anggota', 'penuh']
print(f'{len(daftar)} file, {n} anggota cocok NIK, {time.time() - t0:.0f} dtk')
print(f"{'kolom':20s} {'benar':>6s} {'salah':>6s} {'kosong':>7s} {'salah ditandai':>15s}")
for k in KOLOM:
    b, s, ks, sd = (hasil[k, 'penuh', x] for x in ('benar', 'salah', 'kosong', 'salah-ditandai'))
    print(f'{k:20s} {b/max(n,1):6.0%} {s/max(n,1):6.0%} {ks/max(n,1):7.0%} {sd:>15d}')
