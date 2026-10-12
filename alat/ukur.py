"""Ukur mutu urai tanpa kunci jawaban, dari kotak OCR yang sudah disimpan (folder hasil alat/kumpul.py).

Hanya mencetak angka (tanpa data pribadi). Pemeriksaan silang memakai NIK:
NIK = wilayah(6) + DDMMYY (DD+40 perempuan) + urut(4)."""
import json
import sys
from datetime import date
from pathlib import Path

from ocr_kk.hasil import susun
from ocr_kk.urai import urai_halaman

WAJIB = ['namaLengkap', 'nik', 'jenisKelamin', 'tempatLahir', 'tanggalLahir', 'agama', 'pendidikanTerakhir',
         'pekerjaan', 'statusPerkawinan', 'statusHubungan', 'namaAyah', 'namaIbu']


def dari_nik(nik):
    try:
        d, m, y = int(nik[6:8]), int(nik[8:10]), int(nik[10:12])
    except ValueError:
        return None, None
    p = d > 40
    d -= 40 * p
    y += 2000 if y <= date.today().year % 100 else 1900
    try:
        return date(y, m, d).isoformat(), 'P' if p else 'L'
    except ValueError:
        return None, None


def nilai(h):
    a = h['anggota']
    n = len(a)
    nik_ok = sum(1 for x in a if dari_nik(x['nik'])[0])
    tgl_ok = sum(1 for x in a if dari_nik(x['nik'])[0] and dari_nik(x['nik'])[0] == x['tanggalLahir'])
    jk_ok = sum(1 for x in a if dari_nik(x['nik'])[1] and dari_nik(x['nik'])[1] == x['jenisKelamin'])
    tgl_salah = sum(1 for x in a if x['tanggalLahir'] and dari_nik(x['nik'])[0] != x['tanggalLahir'])
    jk_salah = sum(1 for x in a if x['jenisKelamin'] and dari_nik(x['nik'])[1] != x['jenisKelamin'])
    isi = sum(1 for x in a for k in WAJIB if x.get(k))
    bersih = sum(1 for x in a if all(x.get(k) for k in WAJIB) and not x['_ragu'])
    return {'n': n, 'baris': h['barisTerlihat'], 'nik': nik_ok, 'tgl': tgl_ok, 'jk': jk_ok, 'tglSalah': tgl_salah, 'jkSalah': jk_salah, 'isi': isi,
            'slot': n * len(WAJIB), 'bersih': bersih, 'noKK': int(len(h['noKK']) == 16),
            'kepala': int(bool(h['kepalaKeluarga'])), 'alamat': int(bool(h['alamat']))}


def main(folder):
    total = {}
    for f in sorted(Path(folder).glob('*.json')):
        d = json.loads(f.read_text())
        terbaik = None
        for hal in d['halaman']:
            r = urai_halaman(hal['kotak']) or {'kepala': {}, 'anggota': [], 'barisTerlihat': 0}
            h = susun(r)
            if terbaik is None or len(h['anggota']) > len(terbaik['anggota']):
                terbaik = h
        v = nilai(terbaik)
        print(f.stem[:10], ' '.join(f'{k}={x}' for k, x in v.items()))
        for k, x in v.items():
            total[k] = total.get(k, 0) + x
    total['file'] = len(list(Path(folder).glob('*.json')))
    print('TOTAL', total)
    n = max(total['n'], 1)
    print(f"anggota={total['n']} | NIK valid {total['nik']/n:.0%} | tgl=NIK {total['tgl']/n:.0%} | "
          f"jk=NIK {total['jk']/n:.0%} | kolom terisi {total['isi']/max(total['slot'],1):.0%} | "
          f"anggota bersih {total['bersih']/n:.0%} | noKK {total['noKK']}/{total['file']} | "
          f"kepala {total['kepala']}/{total['file']} | alamat {total['alamat']}/{total['file']}")


if __name__ == '__main__':
    main(sys.argv[1])
