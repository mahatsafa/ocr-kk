"""Menyusun hasil urai menjadi format `hasil` yang dipakai web SIP MENTARI (sama dengan parseTeksKK)."""
import re

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


def susun(r):
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
