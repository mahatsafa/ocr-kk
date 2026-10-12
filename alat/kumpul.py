"""Simpan kotak OCR mentah (sudah ditegakkan) + pratinjau, untuk mengembangkan & mengukur parser.

Pakai: daftar path file per baris di stdin; KELUAR=<folder privat> SUMBER=<akar folder KK>."""
import json, sys, time, hashlib, os
from pathlib import Path
from PIL import Image
from ocr_kk.gambar import muat
from ocr_kk.baca import baca_halaman
out = Path(os.path.expanduser(os.environ.get('KELUAR','~/data-kk/ocr-kk-uji/tegak'))); out.mkdir(exist_ok=True)
for p in sys.stdin.read().splitlines():
    data = Path(p).read_bytes(); kode = hashlib.sha1(data).hexdigest()[:10]
    if (out / f'{kode}.json').exists(): continue
    try: hal = muat(data)
    except Exception as e: print(kode, 'gagal', e); continue
    t = time.time(); semua = []
    for i, img in enumerate(hal):
        kotak, d, img2 = baca_halaman(img)
        semua.append({'w': img2.shape[1], 'h': img2.shape[0], 'derajat': d, 'kotak': kotak})
        pv = Image.fromarray(img2); pv.thumbnail((1800, 1800)); pv.save(out / f'{kode}-{i}.jpg', quality=80)
    rel = os.path.relpath(p, os.path.expanduser(os.environ.get('SUMBER', '~/data-kk/Sisir_KK')))
    json.dump({'file': rel, 'halaman': semua}, open(out / f'{kode}.json', 'w'))
    print(kode, f'{time.time()-t:.1f}s', [h['derajat'] for h in semua], flush=True)
