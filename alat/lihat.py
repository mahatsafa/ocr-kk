"""Tampilkan hasil urai satu file dari kotak OCR tersimpan (berisi data pribadi: hanya untuk pemeriksaan
langsung di layar, jangan disimpan). Pakai: python alat/lihat.py <folder> <kode>"""
import json
import sys
from pathlib import Path

from ocr_kk.hasil import susun
from ocr_kk.urai import urai_halaman

d = json.loads((Path(sys.argv[1]) / f'{sys.argv[2]}.json').read_text())
for i, hal in enumerate(d['halaman']):
    r = urai_halaman(hal['kotak'])
    if not r or not r['anggota']:
        continue
    h = susun(r)
    print(f"hal {i} derajat {hal['derajat']} | noKK {h['noKK']} | kepala {h['kepalaKeluarga']} | alamat {h['alamat']} "
          f"RT {h['rt']} RW {h['rw']} | ragu {h['_ragu']}")
    for a in h['anggota']:
        print(' ', ' | '.join(str(a[k]) for k in ('namaLengkap', 'nik', 'jenisKelamin', 'tempatLahir', 'tanggalLahir',
                                                   'agama', 'pendidikanTerakhir', 'pekerjaan', 'statusPerkawinan',
                                                   'tanggalPerkawinan', 'statusHubungan', 'namaAyah', 'namaIbu')),
              '| RAGU', a['_ragu'])
