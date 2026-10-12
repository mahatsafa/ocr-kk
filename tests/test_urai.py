"""Tes parser dengan kotak teks buatan (bukan data warga). Jalankan: uv run python -m unittest -v"""
import unittest

from ocr_kk import kamus as K
from ocr_kk.hasil import susun
from ocr_kk.tata import tebak_putaran
from ocr_kk.urai import cari_nik, tanggal, urai_halaman


def kotak(t, x, y, w=None, h=24, s=0.99, miring=0.0):
    """Kotak teks di (x, y) kiri-atas; `miring` = kenaikan y per piksel x (halaman miring)."""
    w = w or max(20, 13 * len(t))
    dy0, dy1 = miring * x, miring * (x + w)
    return {'p': [[x, y + dy0], [x + w, y + dy1], [x + w, y + h + dy1], [x, y + h + dy0]], 't': t, 's': s}


# NIK rekaan: 357901 + DDMMYY (+40 perempuan) + urut
ANGGOTA = [
    ('UJI KEPALA', '3579010101800001', 'LAKI-LAKI', 'BATU', '01-01-1980', 'ISLAM', 'SLTA/SEDERAJAT', 'WIRASWASTA',
     'KAWIN TERCATAT', 'KEPALA KELUARGA', 'AYAH SATU', 'IBU SATU'),
    ('UJI ISTRI', '3579014202850002', 'PEREMPUAN', 'MALANG', '02-02-1985', 'ISLAM', 'DIPLOMA IV/STRATA I',
     'MENGURUS RUMAH TANGGA', 'KAWIN TERCATAT', 'ISTRI', 'AYAH DUA', 'IBU DUA'),
    ('UJI ANAK', '3579010303100003', 'LAKI-LAKI', 'BATU', '03-03-2010', 'ISLAM', 'TAMAT SD/SEDERAJAT',
     'PELAJAR/MAHASISWA', 'BELUM KAWIN', 'ANAK', 'UJI KEPALA', 'UJI ISTRI'),
]


def halaman_kk(miring=0.0, judul_ayah_ibu=True, nomor=True):
    m = miring
    k = [kotak('KARTU KELUARGA', 900, 40, h=60),
         kotak('No. 3579010101200001', 880, 110, h=40),
         kotak('Nama Kepala Keluarga', 100, 170), kotak(': UJI KEPALA', 420, 170),
         kotak('Alamat', 100, 200), kotak(': JL. UJI NO. 1', 420, 200),
         kotak('RT/RW', 100, 230), kotak(': 001/003', 420, 230),
         kotak('Desa/Kelurahan', 1500, 170), kotak(': SISIR', 1750, 170),
         kotak('Kecamatan', 1500, 200), kotak(': BATU', 1750, 200)]
    kol1 = [('Nama Lengkap', 150), ('NIK', 520), ('Jenis Kelamin', 760), ('Tempat Lahir', 930), ('Tanggal Lahir', 1120),
            ('Agama', 1300), ('Pendidikan', 1450), ('Jenis Pekerjaan', 1750)]
    k += [kotak('No', 40, 290, miring=m)] + [kotak(t, x, 290, miring=m) for t, x in kol1]
    for i, a in enumerate(ANGGOTA):
        y = 340 + 34 * i
        if nomor:
            k.append(kotak(str(i + 1), 40, y, miring=m))
        for t, x in zip((a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]), (110, 500, 740, 910, 1100, 1290, 1430, 1700)):
            k.append(kotak(t, x, y, miring=m))
    kol2 = [('Status Perkawinan', 120), ('Status Hubungan Dalam Keluarga', 400), ('Kewarganegaraan', 760),
            ('No. Paspor', 1000), ('No. KITAP', 1200)]
    k += [kotak(t, x, 700, miring=m) for t, x in kol2] + [kotak('Nama Orang Tua', 1650, 690, miring=m)]
    if judul_ayah_ibu:
        k += [kotak('Ayah', 1450, 730, miring=m), kotak('Ibu', 1850, 730, miring=m)]
    if nomor:
        x_no = (110, 250, 390, 770, 1010, 1210, 1460, 1860)
        k += [kotak(f'({n})', x, 765, miring=m) for n, x in zip(range(10, 18), x_no)]
    for i, a in enumerate(ANGGOTA):
        y = 810 + 34 * i
        if nomor:
            k.append(kotak(str(i + 1), 40, y, miring=m))
        for t, x in zip((a[8], a[9], 'WNI', a[10], a[11]), (100, 380, 760, 1400, 1760)):
            k.append(kotak(t, x, y, miring=m))
    k += [kotak('Dikeluarkan Tanggal', 100, 1050), kotak('KEPALA DINAS KEPENDUDUKAN DAN', 1500, 1050)]
    return k


class TesDasar(unittest.TestCase):
    def test_tanggal(self):
        self.assertEqual(tanggal('01-02-1990'), '1990-02-01')
        self.assertEqual(tanggal('10062016'), '2016-06-10')
        self.assertEqual(tanggal('31-02-1990'), '')  # tidak ada 31 Februari
        self.assertEqual(tanggal('10-12-1460'), '')  # tahun mustahil: kosong, bukan dikarang

    def test_nik(self):
        self.assertEqual(cari_nik('3579O1O1O18OOOO1'), '3579010101800001')  # huruf O dibaca 0
        self.assertEqual(cari_nik('3579 0101 0180 0001'), '3579010101800001')
        self.assertEqual(cari_nik('357901010180001'), '')  # 15 digit

    def test_kamus(self):
        self.assertEqual(K.baku_pendidikan('SLTAVSEDERAJAT')[0], 'SLTA/Sederajat')
        self.assertEqual(K.baku_pekerjaan('KARYAWAN EWASTA')[0], 'Karyawan Swasta')
        self.assertEqual(K.baku_hubungan('KEDALA KELIARC')[0], 'Kepala Keluarga')
        self.assertEqual(K.baku_hubungan('SUKAMSIH')[0], '')  # nama orang bukan "SUAMI"
        self.assertEqual(K.jenis_kelamin('PEREMPLAN'), 'P')


class TesHalaman(unittest.TestCase):
    def cek(self, h):
        self.assertEqual(h['noKK'], '3579010101200001')
        self.assertEqual(h['kepalaKeluarga'], 'UJI KEPALA')
        self.assertEqual((h['rt'], h['rw']), ('001', '003'))
        self.assertEqual(len(h['anggota']), 3)
        for a, e in zip(h['anggota'], ANGGOTA):
            self.assertEqual(a['namaLengkap'], e[0])
            self.assertEqual(a['nik'], e[1])
            self.assertEqual(a['tempatLahir'], e[3])
            self.assertEqual(a['statusHubungan'].upper(), e[9])
            self.assertEqual(a['namaAyah'], e[10])
            self.assertEqual(a['namaIbu'], e[11])
            self.assertEqual(a['_ragu'], [])

    def test_lurus(self):
        self.cek(susun(urai_halaman(halaman_kk())))

    def test_miring(self):
        # kemiringan 1,5° (kolom kanan lebih rendah ~45 px dari kolom kiri)
        self.cek(susun(urai_halaman(halaman_kk(miring=0.026))))

    def test_tanpa_judul_ayah_ibu(self):
        self.cek(susun(urai_halaman(halaman_kk(judul_ayah_ibu=False))))

    def test_tanpa_nomor_baris(self):
        self.cek(susun(urai_halaman(halaman_kk(nomor=False))))

    def test_bukan_kk(self):
        k = [kotak('DAFTAR USULAN PBI JKN', 100, 40), kotak('3579010101800001', 100, 100), kotak('UJI', 400, 100)]
        r = urai_halaman(k)
        self.assertTrue(r.get('bukanKK'))
        self.assertEqual(r['anggota'], [])

    def test_putaran(self):
        k = halaman_kk()
        self.assertEqual(tebak_putaran(k, 2200, 1100), 0)
        # putar 180°: koordinat dibalik
        terbalik = [{**x, 'p': [[2200 - px, 1100 - py] for px, py in x['p']]} for x in k]
        self.assertEqual(tebak_putaran(terbalik, 2200, 1100), 180)


if __name__ == '__main__':
    unittest.main()
