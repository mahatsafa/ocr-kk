"""Daftar file yang hasilnya jauh berbeda dari kunci jawaban (baris tertukar), untuk diperiksa.

Pakai: python alat/jauh.py <folder> <kunci.json> [--rinci]  (--rinci mencetak nilai: data pribadi, jangan disimpan)"""
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

from alat.banding import norm
from ocr_kk.hasil import susun
from ocr_kk.urai import urai_halaman

folder, file_kunci = sys.argv[1:3]
rinci = '--rinci' in sys.argv
kunci = json.loads(Path(file_kunci).read_text())
for f in sorted(Path(folder).glob('*.json')):
    d = json.loads(f.read_text())
    h = max((susun(urai_halaman(x['kotak'])) for x in d['halaman']), key=lambda h: len(h['anggota']))
    for i, a in enumerate(h['anggota']):
        b = kunci.get(a['nik'])
        if not b:
            continue
        for c in ('namaLengkap', 'namaAyah', 'namaIbu', 'statusHubungan', 'statusPerkawinan'):
            x, y = norm(c, a[c]), norm(c, b[c])
            if x and SequenceMatcher(None, x, y).ratio() < 0.6:
                print(f.stem[:10], 'anggota', i + 1, c, (a[c], '|', b[c]) if rinci else '')
