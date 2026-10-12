"""Bandingkan hasil OCR dengan data yang sudah diverifikasi manusia (kunci jawaban privat).

Pakai: python alat/banding.py <folder kotak OCR> <kunci.json> [draf-lama.json]
  kunci.json     : {nik: {namaLengkap, tanggalLahir, ...}} dari database (jangan masuk repo)
  draf-lama.json : {nama file relatif: hasil Tesseract lama}, opsional, untuk pembanding
Hanya mencetak angka per kolom: benar / salah / kosong (tanpa data pribadi)."""
import hashlib
import json
import re
from difflib import SequenceMatcher
import sys
from collections import Counter
from pathlib import Path

from ocr_kk.hasil import susun
from ocr_kk.urai import urai_halaman

KOLOM = ['namaLengkap', 'jenisKelamin', 'tempatLahir', 'tanggalLahir', 'agama', 'pendidikanTerakhir', 'pekerjaan',
         'statusPerkawinan', 'statusHubungan', 'namaAyah', 'namaIbu']


def norm(k, v):
    v = str(v or '').strip()
    if k in ('tanggalLahir',):
        return v[:10]
    v = v.upper()
    if k == 'statusPerkawinan':
        v = v.replace(' TERCATAT', '').replace(' BELUM', '')  # Kawin Tercatat ~ Kawin di data lama
    return re.sub(r'[^A-Z0-9]', '', v)


def nilai(anggota, kunci, hasil, label):
    for a in anggota:
        b = kunci.get(a.get('nik', ''))
        if not b:
            continue
        hasil['anggota', label] += 1
        for k in KOLOM:
            v = norm(k, a.get(k))
            if not v:
                hasil[k, label, 'kosong'] += 1
            elif v == norm(k, b.get(k)):
                hasil[k, label, 'benar'] += 1
            else:
                hasil[k, label, 'salah'] += 1
                if SequenceMatcher(None, v, norm(k, b.get(k))).ratio() < 0.6:
                    hasil[k, label, 'jauh'] += 1
            if k in (a.get('_ragu') or []) and v and v != norm(k, b.get(k)):
                hasil[k, label, 'salah-ditandai'] += 1


def main(folder, file_kunci, file_lama=None):
    kunci = json.loads(Path(file_kunci).read_text())
    lama = json.loads(Path(file_lama).read_text()) if file_lama else {}
    hasil = Counter()
    nik_kunci_kk = {}
    for nik, b in kunci.items():
        nik_kunci_kk.setdefault(b['kartuKeluargaId'], set()).add(nik)
    for f in sorted(Path(folder).glob('*.json')):
        d = json.loads(f.read_text())
        h = max((susun(urai_halaman(x['kotak'])) for x in d['halaman']), key=lambda h: len(h['anggota']))
        nilai(h['anggota'], kunci, hasil, 'baru')
        # anggota KK yang terlewat (KK dikenali dari NIK mana pun yang cocok)
        kk = {kunci[a['nik']]['kartuKeluargaId'] for a in h['anggota'] if a['nik'] in kunci}
        for k in kk:
            hasil['anggota-kk', 'baru'] += len(nik_kunci_kk[k])
            hasil['nokk-benar', 'baru'] += int(h['noKK'] == kunci[next(iter(nik_kunci_kk[k]))]['kartuKeluarga']['noKK'])
            hasil['kk', 'baru'] += 1
        if d['file'] in lama:
            hl = lama[d['file']]
            nilai(hl.get('anggota', []), kunci, hasil, 'lama')
            kkl = {kunci[a['nik']]['kartuKeluargaId'] for a in hl.get('anggota', []) if a.get('nik') in kunci}
            for k in kkl:
                hasil['anggota-kk', 'lama'] += len(nik_kunci_kk[k])
                hasil['nokk-benar', 'lama'] += int(hl.get('noKK') == kunci[next(iter(nik_kunci_kk[k]))]['kartuKeluarga']['noKK'])
                hasil['kk', 'lama'] += 1
    for label in ('baru', 'lama') if lama else ('baru',):
        n = hasil['anggota', label]
        print(f"== {label}: {hasil['kk', label]} KK dikenali, {n} anggota cocok NIK dari {hasil['anggota-kk', label]} "
              f"anggota KK itu; No. KK benar {hasil['nokk-benar', label]}/{hasil['kk', label]}")
        print(f"{'kolom':20s} {'benar':>6s} {'salah':>6s} {'kosong':>7s} {'salah tapi ditandai':>20s} {'salah jauh':>11s}")
        for k in KOLOM:
            b, s, ks, sd, j = (hasil[k, label, x] for x in ('benar', 'salah', 'kosong', 'salah-ditandai', 'jauh'))
            print(f"{k:20s} {b/max(n,1):6.0%} {s/max(n,1):6.0%} {ks/max(n,1):7.0%} {sd:>20d} {j:>11d}")


if __name__ == '__main__':
    main(*sys.argv[1:])
