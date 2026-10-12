"""Hitung kolom yang paling sering ragu/kosong (hanya angka)."""
import collections
import json
import sys
from pathlib import Path

from alat.ukur import WAJIB
from ocr_kk.hasil import susun
from ocr_kk.urai import urai_halaman

r, kos = collections.Counter(), collections.Counter()
for f in sorted(Path(sys.argv[1]).glob('*.json')):
    d = json.loads(f.read_text())
    h = max((susun(urai_halaman(x['kotak'])) for x in d['halaman']), key=lambda h: len(h['anggota']))
    for a in h['anggota']:
        r.update(a['_ragu'])
        kos.update(k for k in WAJIB if not a.get(k))
print('ragu', r.most_common())
print('kosong', kos.most_common())
