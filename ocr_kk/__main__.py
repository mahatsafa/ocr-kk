"""Pemakaian:
  python -m ocr_kk FILE...      -> satu JSON per file (baris per baris) ke stdout
  python -m ocr_kk --layan      -> baca path file per baris dari stdin, balas satu baris JSON per file
                                   (model dimuat sekali; dipakai pekerja-kantor.mjs)
"""
import json
import sys
import time
import traceback

from .baca import baca_file


def _satu(path):
    t = time.time()
    try:
        with open(path, 'rb') as f:
            hasil = baca_file(f.read())
        hasil['detik'] = round(time.time() - t, 1)
        return hasil
    except Exception as e:  # noqa: BLE001 - galat dikirim ke pemanggil sebagai JSON
        return {'galat': str(e) or e.__class__.__name__, 'jejak': traceback.format_exc(limit=3)}


def main():
    if '--layan' in sys.argv:
        for baris in sys.stdin:
            path = baris.strip()
            if path:
                print(json.dumps(_satu(path), ensure_ascii=False), flush=True)
        return
    for path in sys.argv[1:]:
        print(json.dumps(_satu(path), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
