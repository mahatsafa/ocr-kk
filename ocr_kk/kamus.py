"""Isian baku KK (Dukcapil) dan pencocokan teks OCR yang salah 1-2 huruf ke entri baku."""
import re

PEKERJAAN = [
    'BELUM/TIDAK BEKERJA', 'MENGURUS RUMAH TANGGA', 'PELAJAR/MAHASISWA', 'PENSIUNAN', 'PEGAWAI NEGERI SIPIL (PNS)',
    'TENTARA NASIONAL INDONESIA (TNI)', 'KEPOLISIAN RI (POLRI)', 'PERDAGANGAN', 'PETANI/PEKEBUN', 'PETERNAK',
    'NELAYAN/PERIKANAN', 'INDUSTRI', 'KONSTRUKSI', 'TRANSPORTASI', 'KARYAWAN SWASTA', 'KARYAWAN BUMN', 'KARYAWAN BUMD',
    'KARYAWAN HONORER', 'BURUH HARIAN LEPAS', 'BURUH TANI/PERKEBUNAN', 'BURUH NELAYAN/PERIKANAN', 'BURUH PETERNAKAN',
    'PEMBANTU RUMAH TANGGA', 'TUKANG CUKUR', 'TUKANG LISTRIK', 'TUKANG BATU', 'TUKANG KAYU', 'TUKANG SOL SEPATU',
    'TUKANG LAS/PANDAI BESI', 'TUKANG JAHIT', 'TUKANG GIGI', 'PENATA RIAS', 'PENATA BUSANA', 'PENATA RAMBUT', 'MEKANIK',
    'SENIMAN', 'TABIB', 'PARAJI', 'PERANCANG BUSANA', 'PENTERJEMAH', 'IMAM MASJID', 'PENDETA', 'PASTOR', 'WARTAWAN',
    'USTADZ/MUBALIGH', 'JURU MASAK', 'PROMOTOR ACARA', 'DOSEN', 'GURU', 'PILOT', 'PENGACARA', 'NOTARIS', 'ARSITEK',
    'AKUNTAN', 'KONSULTAN', 'DOKTER', 'BIDAN', 'PERAWAT', 'APOTEKER', 'PSIKIATER/PSIKOLOG', 'PENYIAR TELEVISI',
    'PENYIAR RADIO', 'PELAUT', 'PENELITI', 'SOPIR', 'PIALANG', 'PARANORMAL', 'PEDAGANG', 'PERANGKAT DESA', 'KEPALA DESA',
    'BIARAWATI', 'WIRASWASTA', 'ANGGOTA DPRD KABUPATEN/KOTA', 'LAINNYA', 'BIARAWAN', 'USTADZ/MUBALIGH',
    'ANGGOTA DPR-RI', 'ANGGOTA DPD', 'ANGGOTA BPK', 'PRESIDEN', 'WAKIL PRESIDEN', 'ANGGOTA MAHKAMAH KONSTITUSI',
    'ANGGOTA KABINET/KEMENTERIAN', 'DUTA BESAR', 'GUBERNUR', 'WAKIL GUBERNUR', 'BUPATI', 'WAKIL BUPATI', 'WALIKOTA',
    'WAKIL WALIKOTA', 'ANGGOTA DPRD PROVINSI', 'KARYAWAN', 'PELAJAR', 'MAHASISWA', 'IBU RUMAH TANGGA', 'TIDAK BEKERJA',
]

# Tampilan di form web = sama dengan lib/ocr/gabungHasil.js
PENDIDIKAN = {
    'TIDAK/BELUM SEKOLAH': 'Tidak/Belum Sekolah', 'BELUM TAMAT SD/SEDERAJAT': 'Belum Tamat SD/Sederajat',
    'TAMAT SD/SEDERAJAT': 'Tamat SD/Sederajat', 'SLTP/SEDERAJAT': 'SLTP/Sederajat', 'SLTA/SEDERAJAT': 'SLTA/Sederajat',
    'DIPLOMA I/II': 'Diploma I/II', 'AKADEMI/DIPLOMA III/S. MUDA': 'Akademi/Diploma III/S. Muda',
    'DIPLOMA IV/STRATA I': 'Diploma IV/Strata I', 'STRATA II': 'Strata II', 'STRATA III': 'Strata III',
}
# Singkatan yang dipakai blanko lama/baru
PENDIDIKAN_LAIN = {
    'TIDAK/BLM SEKOLAH': 'TIDAK/BELUM SEKOLAH', 'BELUM TAMAT SD': 'BELUM TAMAT SD/SEDERAJAT',
    'TAMAT SD': 'TAMAT SD/SEDERAJAT', 'SLTP': 'SLTP/SEDERAJAT', 'SLTA': 'SLTA/SEDERAJAT',
    'DIPLOMA IV/ STRATA I': 'DIPLOMA IV/STRATA I', 'AKADEMI/DIPLOMA III/SARJANA MUDA': 'AKADEMI/DIPLOMA III/S. MUDA',
}

AGAMA = ['ISLAM', 'KRISTEN', 'KATOLIK', 'KATHOLIK', 'HINDU', 'BUDDHA', 'BUDHA', 'KONGHUCU', 'KHONGHUCU']
TAMPIL_AGAMA = {'KATHOLIK': 'Katolik', 'BUDHA': 'Buddha', 'KHONGHUCU': 'Konghucu'}

STATUS_KAWIN = ['BELUM KAWIN', 'KAWIN', 'KAWIN TERCATAT', 'KAWIN BELUM TERCATAT', 'CERAI HIDUP', 'CERAI MATI',
                'CERAI HIDUP TERCATAT', 'CERAI MATI TERCATAT', 'CERAI HIDUP BELUM TERCATAT', 'CERAI MATI BELUM TERCATAT']
TAMPIL_KAWIN = {
    'CERAI HIDUP TERCATAT': 'Cerai Hidup', 'CERAI MATI TERCATAT': 'Cerai Mati',
    'CERAI HIDUP BELUM TERCATAT': 'Cerai Hidup', 'CERAI MATI BELUM TERCATAT': 'Cerai Mati',
}

HUBUNGAN = ['KEPALA KELUARGA', 'SUAMI', 'ISTRI', 'ANAK', 'MENANTU', 'CUCU', 'ORANG TUA', 'MERTUA', 'FAMILI LAIN',
            'PEMBANTU', 'LAINNYA']

GOL_DARAH = ['A', 'B', 'AB', 'O', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'TIDAK TAHU', 'TIDAKTAHU']


def kunci(t: str) -> str:
    return re.sub(r'[^A-Z]', '', str(t or '').upper())


def jarak(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cocok(teks: str, daftar, batas_rasio=0.22) -> tuple[str, int]:
    """(entri, jarak) terdekat bila cukup dekat dan tidak seri; ('', -1) bila tidak ada."""
    k = kunci(teks)
    if len(k) < 3:
        return '', -1
    batas = 1 if len(k) <= 5 else max(1, round(len(k) * batas_rasio))
    terbaik, d_terbaik, seri = '', 10**9, False
    for e in daftar:
        d = jarak(k, kunci(e))
        if d < d_terbaik:
            terbaik, d_terbaik, seri = e, d, False
        elif d == d_terbaik and kunci(e) != kunci(terbaik):
            seri = True
    if d_terbaik <= batas and not seri:
        return terbaik, d_terbaik
    return '', -1


def judul(t: str) -> str:
    t = str(t or '').lower()
    t = re.sub(r'(^|[\s/(])([a-z])', lambda m: m.group(1) + m.group(2).upper(), t)
    # singkatan dalam kurung tetap huruf besar: (PNS), (TNI), (POLRI)
    return re.sub(r'\(([a-z]+)\)', lambda m: '(' + m.group(1).upper() + ')', t, flags=re.I)


def baku_pendidikan(t):
    semua = list(PENDIDIKAN) + list(PENDIDIKAN_LAIN)
    e, d = cocok(t, semua, 0.25)
    if not e:
        return '', -1
    e = PENDIDIKAN_LAIN.get(e, e)
    return PENDIDIKAN[e], d


def baku_agama(t):
    e, d = cocok(t, AGAMA)
    return (TAMPIL_AGAMA.get(e, judul(e)), d) if e else ('', -1)


def baku_kawin(t):
    e, d = cocok(t, STATUS_KAWIN, 0.2)
    if not e:
        e, d = cocok_longgar(t, STATUS_KAWIN)
    return (TAMPIL_KAWIN.get(e, judul(e)), d) if e else ('', -1)


def baku_hubungan(t):
    e, d = cocok(t, HUBUNGAN, 0.25)
    if not e:
        e, d = cocok_longgar(t, HUBUNGAN)
    return (judul(e), d) if e else ('', -1)


def baku_pekerjaan(t):
    e, d = cocok(t, PEKERJAAN, 0.2)
    return (judul(e), d) if e else ('', -1)


def jenis_kelamin(t):
    k = kunci(t)
    if not k:
        return ''
    if jarak(k, 'PEREMPUAN') <= 2 or k.startswith('PEREM') or k.endswith('EMPUAN'):
        return 'P'
    if jarak(k, 'LAKILAKI') <= 2 or k.startswith('LAKI') or k in ('LK', 'L'):
        return 'L'
    return ''


def cocok_longgar(teks, daftar, ambang=0.72):
    """Cadangan untuk teks buram: kemiripan urutan huruf >= ambang dan jelas lebih mirip dari entri lain.
    Jarak dikembalikan 3 supaya kolomnya selalu ditandai ragu."""
    from difflib import SequenceMatcher

    k = kunci(teks)
    if len(k) < 6:
        return '', -1
    # hanya entri panjang (KEPALA KELUARGA, BELUM KAWIN, ...) yang aman dicocokkan longgar, dan panjangnya
    # harus sebanding; nama orang (mis. SUKAMSIH) tidak boleh terbaca sebagai SUAMI.
    daftar = [e for e in daftar if len(kunci(e)) >= 8 and abs(len(kunci(e)) - len(k)) <= max(3, len(k) // 3)]
    if not daftar:
        return '', -1
    nilai = sorted(((SequenceMatcher(None, k, kunci(e)).ratio(), e) for e in daftar), reverse=True)
    if nilai[0][0] >= ambang and (len(nilai) < 2 or nilai[0][0] - nilai[1][0] >= 0.08):
        return nilai[0][1], 3
    return '', -1
