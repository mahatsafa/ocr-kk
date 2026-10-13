"""File yang tidak menghasilkan anggota: bukan KK, atau KK yang gagal terbaca? Hanya mencetak kode & ciri.

Pakai: python alat/kosong.py <folder kotak OCR>"""
import json
import sys
from pathlib import Path

from ocr_kk.tata import kunci
from ocr_kk.urai import urai_halaman

CIRI = ('KARTUKELUARGA', 'NAMALENGKAP', 'JENISKELAMIN', 'KEWARGANEGARAAN', 'NAMAORANGTUA', 'STATUSHUBUNGAN')
JENIS = {'KTP': ('NIK', 'BERLAKUHINGGA', 'GOLDARAH'), 'AKTA': ('AKTAKELAHIRAN', 'KUTIPAN'),
         'IJAZAH': ('IJAZAH',), 'SURAT': ('SURATKETERANGAN', 'NOMOR'), 'BPJS': ('BPJS', 'JKN', 'KIS')}

for f in sorted(Path(sys.argv[1]).glob('*.json')):
    d = json.loads(f.read_text())
    rs = [urai_halaman(h['kotak']) or {'anggota': []} for h in d['halaman']]
    if any(r['anggota'] for r in rs):
        continue
    semua = ' '.join(kunci(k['t']) for h in d['halaman'] for k in h['kotak'])
    ciri = [c for c in CIRI if c in semua]
    tebak = [j for j, cs in JENIS.items() if any(c in semua for c in cs)]
    print(f.stem, Path(d['file']).suffix.lower(), 'kotak', sum(len(h['kotak']) for h in d['halaman']),
          'ciri-KK', len(ciri), 'judul-KK' if 'KARTUKELUARGA' in semua else '-', 'mirip', ','.join(tebak) or '-')
