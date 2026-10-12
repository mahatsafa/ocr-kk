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


def baca_file(data: bytes) -> dict:
    """{teks, hasil, derajat, sumber}. `hasil` berformat sama dengan parseTeksKK di web."""
    from .hasil import susun
    from .urai import urai_halaman

    terbaik = None
    for i, img in enumerate(muat(data)):
        kotak, derajat, tegak = baca_halaman(img)
        r = urai_halaman(kotak) or {'kepala': {}, 'anggota': [], 'barisTerlihat': 0}
        if not r['anggota'] and not r.get('bukanKK'):
            besar = perbesar(tegak, kotak)
            if besar is not None:
                kotak2 = baca_kotak(besar)
                r2 = urai_halaman(kotak2)
                if r2 and len(r2['anggota']) > len(r['anggota']):
                    kotak, r = kotak2, r2
        nilai = (not r.get('bukanKK'), len(r['anggota']), bool(r['kepala'].get('noKK')))
        if terbaik is None or nilai > terbaik[0]:
            terbaik = (nilai, i, kotak, derajat, r)
    _, i, kotak, derajat, r = terbaik
    teks = '\n'.join(k['t'] for k in sorted(kotak, key=lambda k: (round(k['p'][0][1] / 20), k['p'][0][0])))
    return {
        'teks': teks,
        'hasil': susun(r),
        'derajat': derajat,
        'halaman': i,
        'bukanKK': bool(r.get('bukanKK')),
        'sumber': f'RapidOCR (ocr-kk){", diputar %d°" % derajat if derajat else ""}',
    }
