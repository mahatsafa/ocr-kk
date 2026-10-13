"""Tampilkan baris tabel bawah (status, hubungan, orang tua) satu file, beserta jenis tiap sel (data pribadi:
hanya untuk pemeriksaan di layar). Pakai: python alat/sel2.py <folder> <kode> [halaman]"""
import json
import sys
from pathlib import Path

import ocr_kk.urai as U

d = json.loads((Path(sys.argv[1]) / f'{sys.argv[2]}.json').read_text())
asli = U.urai_baris_t2


def cetak(b, pisah=None, kolom=None):
    print('  ' + ' | '.join(f"{k['t']}[{U.jenis_sel_t2(k['t'])[0]} {k['s']:.2f}]" for k in b))
    return asli(b, pisah, kolom)


U.urai_baris_t2 = cetak
r = U.urai_halaman(d['halaman'][int(sys.argv[3]) if len(sys.argv) > 3 else 0]['kotak'])
for a in r['anggota']:
    print('->', a.get('statusPerkawinan', ''), '/', a.get('statusHubungan', ''), '/', a.get('namaAyah', ''), '/', a.get('namaIbu', ''))
