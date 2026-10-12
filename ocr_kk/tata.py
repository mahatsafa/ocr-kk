"""Geometri hasil OCR: menegakkan halaman dan meluruskan kemiringan."""
import math
import re
from statistics import median

import numpy as np


def kunci(t: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', t.upper())


# Kata yang letaknya pasti di KK: bagian atas (judul + kepala) dan bagian bawah (kaki).
ATAS = ('KARTUKELUARGA', 'NAMAKEPALAKELUARGA', 'ALAMAT', 'RTRW', 'KODEPOS', 'DESAKELURAHAN', 'KECAMATAN',
        'KABUPATENKOTA', 'PROVINSI', 'NAMALENGKAP')
BAWAH = ('DIKELUARKANTANGGAL', 'LEMBAR', 'TANDATANGANCAPJEMPOL', 'KEPALADINAS', 'PENCATATANSIPIL',
         'DOKUMENINITELAH', 'NAMAORANGTUA', 'KEWARGANEGARAAN')


def pusat(k):
    p = np.asarray(k['p'])
    return p[:, 0].mean(), p[:, 1].mean()


def ukuran(k):
    p = np.asarray(k['p'])
    return p[:, 0].max() - p[:, 0].min(), p[:, 1].max() - p[:, 1].min()


def putar_titik(x, y, w, h, derajat):
    """Koordinat titik (x, y) setelah gambar w x h diputar searah jarum jam sebesar `derajat`."""
    if derajat == 90:
        return h - y, x
    if derajat == 180:
        return w - x, h - y
    if derajat == 270:
        return y, w - x
    return x, y


def tebak_putaran(kotak, w, h) -> int:
    """Putaran searah jarum jam (0/90/180/270) yang membuat KK tegak.

    Kotak teks yang tinggi (bukan lebar) berarti tulisan berdiri -> 90 atau 270. Arah pastinya dipilih
    dari letak kata khas: kata kepala dokumen harus di atas, kata kaki dokumen di bawah."""
    tegak = sum(1 for k in kotak if len(k['t']) >= 4 and ukuran(k)[1] > 1.5 * ukuran(k)[0])
    rebah = sum(1 for k in kotak if len(k['t']) >= 4 and ukuran(k)[0] > 1.5 * ukuran(k)[1])
    calon = (90, 270) if tegak > rebah else (0, 180)

    def skor(derajat):
        ww, hh = (h, w) if derajat in (90, 270) else (w, h)
        s = 0.0
        for k in kotak:
            kk = kunci(k['t'])
            x, y = putar_titik(*pusat(k), w, h, derajat)
            if any(a in kk for a in ATAS):
                s += 0.5 - y / hh
            if any(b in kk for b in BAWAH):
                s += y / hh - 0.5
            # NIK & No. KK diawali kode wilayah: dibaca terbalik tidak akan terlihat seperti ini
            if re.fullmatch(r'(No\.?)?\s*3[1-9]\d{14}', k['t'].strip()):
                s += 0.3
        return s

    return max(calon, key=skor)


def putar_gambar(img: np.ndarray, derajat: int) -> np.ndarray:
    if not derajat:
        return img
    return np.ascontiguousarray(np.rot90(img, k=-(derajat // 90)))


def sudut_miring(kotak) -> float:
    """Kemiringan (radian) median dari kotak teks yang panjang."""
    sudut = []
    for k in kotak:
        p = np.asarray(k['p'])
        lebar = np.linalg.norm(p[1] - p[0])
        if len(k['t']) >= 5 and lebar > 3 * np.linalg.norm(p[3] - p[0]):
            sudut.append(math.atan2(p[1][1] - p[0][1], p[1][0] - p[0][0]))
    return median(sudut) if sudut else 0.0


def luruskan(kotak):
    """Tambahkan x0, x1, y0, y1, cx, cy, h (koordinat setelah kemiringan diluruskan) ke tiap kotak."""
    a = -sudut_miring(kotak)
    c, s = math.cos(a), math.sin(a)
    hasil = []
    for k in kotak:
        p = np.asarray(k['p'])
        xs = p[:, 0] * c - p[:, 1] * s
        ys = p[:, 0] * s + p[:, 1] * c
        hasil.append({**k, 'x0': xs.min(), 'x1': xs.max(), 'y0': ys.min(), 'y1': ys.max(),
                      'cx': xs.mean(), 'cy': ys.mean(), 'h': ys.max() - ys.min()})
    return hasil
