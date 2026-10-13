"""Alur utama: file KK -> gambar tegak -> kotak teks -> data KK."""
from .gambar import muat
from .mesin import baca_kotak
from .tata import putar_gambar, tebak_putaran


def baca_halaman(img):
    """OCR satu halaman. Kalau halaman terputar, gambar ditegakkan lalu dibaca ulang (angka pendek
    seperti nomor baris dan "WNI" salah baca bila dibaca miring). Mengembalikan (kotak, derajat, img)."""
    kotak = baca_kotak(img)
    h, w = img.shape[:2]
    derajat = tebak_putaran(kotak, w, h)
    if derajat:
        img = putar_gambar(img, derajat)
        kotak = baca_kotak(img)
    return kotak, derajat, img


def perbesar(img, kotak, sisi=2000):
    """Potong area yang berisi tulisan (tepi kosong / meja dibuang) lalu perbesar, untuk KK yang hanya
    menempati sebagian kecil foto sehingga tulisan tabelnya terlalu kecil terbaca. None bila tidak perlu."""
    import numpy as np
    from PIL import Image

    if not kotak:
        return None
    p = np.concatenate([np.asarray(k['p']) for k in kotak])
    (x0, y0), (x1, y1) = p.min(0), p.max(0)
    h, w = img.shape[:2]
    mx, my = 0.03 * (x1 - x0), 0.03 * (y1 - y0)
    x0, y0 = int(max(0, x0 - mx)), int(max(0, y0 - my))
    x1, y1 = int(min(w, x1 + mx)), int(min(h, y1 + my))
    if (x1 - x0) * (y1 - y0) > 0.7 * w * h:
        return None
    potong = Image.fromarray(img[y0:y1, x0:x1])
    s = sisi / max(potong.size)
    if s > 1:
        potong = potong.resize((round(potong.size[0] * s), round(potong.size[1] * s)), Image.LANCZOS)
    return np.asarray(potong)


def tanggal_nik(nik: str) -> tuple:
    """(hari, bulan, 2 digit tahun) dari NIK, atau None. NIK = wilayah(6) + DD(+40 perempuan) MM YY + urut(4)."""
    if not (isinstance(nik, str) and len(nik) == 16 and nik.isdigit()):
        return None
    d, m, y = int(nik[6:8]), int(nik[8:10]), int(nik[10:12])
    d = d - 40 if d > 40 else d
    return (d, m, y) if 1 <= d <= 31 and 1 <= m <= 12 else None


def cocok_nik(a: dict) -> bool:
    t, n = a.get('tanggalLahir') or '', tanggal_nik(a.get('nik'))
    return bool(n and len(t) == 10 and (int(t[8:]), int(t[5:7]), int(t[:4]) % 100) == n)


def nokk_sah(n: str, anggota: list) -> bool:
    """No. KK 16 digit dengan bagian tanggal (digit 7-12, DDMMYY) yang sah dan bukan NIK salah satu anggota."""
    if not (isinstance(n, str) and len(n) == 16 and n.isdigit()):
        return False
    return 1 <= int(n[6:8]) <= 31 and 1 <= int(n[8:10]) <= 12 and all(a.get('nik') != n for a in anggota)


def perbaiki_nokk(r: dict, img) -> bool:
    """Bila No. KK kosong/tidak sah: baca ulang halaman tegak tanpa pengklasifikasi arah baris (cls membalik
    baris No. KK berkotak-kotak pada sebagian blanko). Dipakai hanya bila hasilnya sah."""
    from .urai import urai_halaman

    kep = r['kepala']
    if nokk_sah(kep.get('noKK', ''), r['anggota']):
        return False
    r2 = urai_halaman(baca_kotak(img, cls=False))
    n = r2['kepala'].get('noKK', '') if r2 else ''
    if not nokk_sah(n, r['anggota']):
        return False
    kep['noKK'], kep['_skor_noKK'] = n, r2['kepala'].get('_skor_noKK', 0)
    return True


# Kolom berkamus yang boleh diisi dari bacaan kedua bila kosong/ragu di bacaan pertama.
KAMUS_ISI = ('statusPerkawinan', 'statusHubungan', 'agama', 'pendidikanTerakhir', 'pekerjaan')


def perbaiki_bacaan(r: dict, img) -> int:
    """Bacaan kedua dengan kotak deteksi lebih lebar (angka/huruf di tepi kotak tidak terpotong), hanya bila
    ada tanggal lahir yang tidak cocok NIK atau kolom berkamus yang kosong/ragu. Isi bacaan kedua dipakai:
      - tanggal lahir: HANYA bila tepat sama dengan tanggal di NIK (dua sumber tercetak yang sepakat);
      - kolom berkamus: HANYA bila bacaan kedua yakin (tidak ragu) sedangkan bacaan pertama kosong/ragu.
    Tidak ada yang dikarang: semuanya hasil membaca kertas. Mengembalikan jumlah kolom yang diperbaiki."""
    from .urai import YAKIN_KOLOM, urai_halaman

    def perlu(a):
        return ((tanggal_nik(a.get('nik')) and not cocok_nik(a))
                or any(not a.get(k) or k in a['_ragu'] for k in KAMUS_ISI))

    if not any(perlu(a) for a in r['anggota']):
        return 0
    r2 = urai_halaman(baca_kotak(img, lebar=True)) or {'anggota': []}
    per_nik = {b['nik']: b for b in r2['anggota']}
    n = 0
    for a in r['anggota']:
        b = per_nik.get(a['nik'])
        if not b:
            continue
        if tanggal_nik(a.get('nik')) and not cocok_nik(a) and cocok_nik(b):
            a['tanggalLahir'] = b['tanggalLahir']
            a['_skor']['tanggalLahir'] = max(b['_skor'].get('tanggalLahir', 0), YAKIN_KOLOM['tanggalLahir'])
            a['_ragu'].discard('tanggalLahir')
            n += 1
        for k in KAMUS_ISI:
            if (not a.get(k) or k in a['_ragu']) and b.get(k) and k not in b['_ragu']:
                a[k] = b[k]
                a['_skor'][k] = b['_skor'].get(k, 1)
                a['_ragu'].discard(k)
                n += 1
    return n


def baca_file(data: bytes) -> dict:
    """{teks, hasil, derajat, sumber}. `hasil` berformat sama dengan parseTeksKK di web."""
    from .hasil import susun
    from .urai import urai_halaman

    terbaik = None
    for i, img in enumerate(muat(data)):
        kotak, derajat, tegak = baca_halaman(img)
        r = urai_halaman(kotak) or {'kepala': {}, 'anggota': [], 'barisTerlihat': 0}
        dipakai = tegak
        if not r['anggota'] and not r.get('bukanKK'):
            # tebakan putaran bisa salah pada foto pudar: coba juga diputar 180°
            balik = putar_gambar(tegak, 180)
            kotak3 = baca_kotak(balik)
            r3 = urai_halaman(kotak3)
            if r3 and len(r3['anggota']) > len(r['anggota']):
                kotak, r, dipakai, tegak, derajat = kotak3, r3, balik, balik, (derajat + 180) % 360
        if not r['anggota'] and not r.get('bukanKK'):
            besar = perbesar(tegak, kotak)
            if besar is not None:
                kotak2 = baca_kotak(besar)
                r2 = urai_halaman(kotak2)
                if r2 and len(r2['anggota']) > len(r['anggota']):
                    kotak, r, dipakai = kotak2, r2, besar
        if r['anggota']:
            perbaiki_bacaan(r, dipakai)
        nilai = (not r.get('bukanKK'), len(r['anggota']), bool(r['kepala'].get('noKK')))
        if terbaik is None or nilai > terbaik[0]:
            terbaik = (nilai, i, kotak, derajat, r, dipakai)
    _, i, kotak, derajat, r, dipakai = terbaik
    if r['anggota']:
        perbaiki_nokk(r, dipakai)
    teks = '\n'.join(k['t'] for k in sorted(kotak, key=lambda k: (round(k['p'][0][1] / 20), k['p'][0][0])))
    return {
        'teks': teks,
        'hasil': susun(r),
        'derajat': derajat,
        'halaman': i,
        'bukanKK': bool(r.get('bukanKK')),
        'sumber': f'RapidOCR (ocr-kk){", diputar %d°" % derajat if derajat else ""}',
    }
