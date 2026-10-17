"""Menyusun hasil urai menjadi format `hasil` yang dipakai web SIP MENTARI (sama dengan parseTeksKK)."""
import re
from datetime import date

from .urai import BUANG

KOLOM = ['namaLengkap', 'nik', 'jenisKelamin', 'tempatLahir', 'tanggalLahir', 'agama', 'pendidikanTerakhir',
         'pekerjaan', 'statusPerkawinan', 'statusHubungan', 'kewarganegaraan', 'tanggalPerkawinan',
         'nomorPaspor', 'nomorKitap', 'namaAyah', 'namaIbu']


def _rt_rw(t):
    m = re.search(r'(\d{1,3})\s*[/|\\]\s*(\d{1,3})', t or '')
    return (m.group(1).zfill(3), m.group(2).zfill(3)) if m else ('', '')


def _alamat(t):
    t = re.sub(r'\s+', ' ', re.sub(r"[^A-Za-z0-9.,'/ -]", ' ', t or '')).strip(' .,-')
    return t.upper() if len(re.sub(r'[^A-Za-z]', '', t)) >= 3 else ''


WAJIB = ['namaLengkap', 'nik', 'jenisKelamin', 'tempatLahir', 'tanggalLahir', 'agama', 'pendidikanTerakhir',
         'pekerjaan', 'statusPerkawinan', 'statusHubungan', 'namaAyah', 'namaIbu']


def dari_nik(nik, tahun_ini=None):
    """(tanggal lahir 'YYYY-MM-DD', jenis kelamin 'L'/'P') dari NIK sah, atau None.
    NIK = wilayah(6) + DD(+40 perempuan) MM YY + urut(4). Abad: 20xx bila belum lewat tahun ini, selain itu 19xx."""
    if not (isinstance(nik, str) and len(nik) == 16 and nik.isdigit()):
        return None
    d, m, yy = int(nik[6:8]), int(nik[8:10]), int(nik[10:12])
    jk = 'P' if d > 40 else 'L'
    d = d - 40 if d > 40 else d
    tahun_ini = tahun_ini or date.today().year
    y = 2000 + yy if 2000 + yy <= tahun_ini else 1900 + yy
    try:
        return date(y, m, d).isoformat(), jk
    except ValueError:
        return None


def susun(r, tahun_ini=None):
    """r = keluaran urai_halaman."""
    kep = r['kepala']
    anggota = []
    for a in r['anggota']:
        skor = a.get('_skor', {})
        ragu = set(a.get('_ragu', set()))
        b = {k: a.get(k, '') or '' for k in KOLOM}
        for k in KOLOM:
            if b[k] and skor.get(k, 1) < BUANG:
                b[k] = ''
                ragu.add(k)
        if not b['kewarganegaraan']:
            b['kewarganegaraan'] = 'WNI'
        # Tanggal lahir & jenis kelamin tercetak juga di NIK. Tanggal yang kosong/tidak sepakat dengan NIK diisi
        # dari NIK dan SELALU ditandai ragu (manusia mencocokkan foto). Tanggal yang sepakat (hari, bulan, 2 digit
        # tahun) dibiarkan, supaya abad yang tercetak tidak ditimpa tebakan.
        n = dari_nik(b['nik'], tahun_ini)
        if n:
            t = b['tanggalLahir']
            if not (len(t) == 10 and t[5:] == n[0][5:] and t[2:4] == n[0][2:4]):
                b['tanggalLahir'] = n[0]
                ragu.add('tanggalLahir')
            if not b['jenisKelamin']:
                b['jenisKelamin'] = n[1]
        # Kolom wajib yang kosong selalu ditandai, supaya terlihat di form.
        ragu |= {k for k in WAJIB if not b[k]}
        b['_ragu'] = sorted(ragu)
        anggota.append(b)
    rt, rw = _rt_rw(kep.get('rtrw', ''))
    kepala = re.sub(r'\s+', ' ', re.sub(r"[^A-Za-z'., -]", ' ', kep.get('kepalaKeluarga', ''))).strip().upper()
    if not kepala:
        kepala = next((a['namaLengkap'] for a in anggota if a['statusHubungan'] == 'Kepala Keluarga'), '')
    return {
        'noKK': kep.get('noKK', ''),
        'kepalaKeluarga': kepala,
        'alamat': _alamat(kep.get('alamat', '')),
        'rt': rt,
        'rw': rw,
        'kelurahanId': '',
        'kelurahanBaru': None,
        'anggota': anggota,
        'barisTerlihat': r['barisTerlihat'],
        '_ragu': sorted(k for k in ('noKK', 'kepalaKeluarga', 'alamat')
                        if kep.get('_skor_' + k, 1) < 0.85 and kep.get(k)),
    }
