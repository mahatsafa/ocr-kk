"""Mengurai kotak teks OCR dari halaman KK (sudah tegak) menjadi data KK.

Tabel KK dibaca per baris anggota:
  - Tabel atas: tiap baris dijangkarkan pada NIK (16 digit). Kotak lain ditempelkan ke baris terdekat,
    mulai dari kolom yang paling dekat ke kolom NIK, supaya halaman foto yang melengkung tetap terbaca.
  - Tabel bawah: dijangkarkan pada kolom yang paling banyak terbaca (kewarganegaraan, status hubungan,
    status perkawinan), lalu dipasangkan ke baris tabel atas menurut urutan.
  - Isi sel dikenali dari jenisnya (NIK, tanggal, jenis kelamin, kamus agama/pendidikan/pekerjaan/status)
    dan urutannya di baris, bukan dari koordinat kolom yang mudah meleset.
Tidak ada nilai yang dikarang: yang tidak terbaca dibiarkan kosong, yang kurang yakin ditandai `_ragu`.
"""
import re
from statistics import median

from . import kamus as K
from .tata import kunci, luruskan

YAKIN = 0.85  # skor OCR minimal supaya sebuah kolom tidak ditandai ragu
# Ambang per kolom, dari uji banding dengan data yang sudah diverifikasi: salah baca nama dan tanggal
# sering tetap berskor tinggi (0,9-0,96), jadi ambangnya dinaikkan supaya lebih banyak yang ditandai.
YAKIN_KOLOM = {'namaLengkap': 0.96, 'namaAyah': 0.96, 'namaIbu': 0.96, 'tanggalLahir': 0.95, 'tempatLahir': 0.93}


def yakin(kolom):
    return YAKIN_KOLOM.get(kolom, YAKIN)
BUANG = 0.75  # di bawah ini isi kolom dikosongkan (lebih baik kosong daripada salah)

RE_TGL = re.compile(r'(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4})')
RE_NIK = re.compile(r'(?<!\d)(\d{16})(?!\d)')

KEPALA_T1 = ('NAMALENGKAP', 'NIK', 'JENISKELAMIN', 'KELAMIN', 'TEMPATLAHIR', 'TANGGALLAHIR', 'AGAMA', 'PENDIDIKAN',
             'JENISPEKERJAAN', 'PEKERJAAN', 'GOLONGANDARAH', 'GOLONGAN', 'DARAH')
KEPALA_T2 = ('STATUSPERKAWINAN', 'PERKAWINAN', 'TANGGALPERKAWINAN', 'STATUSHUBUNGAN', 'DALAMKELUARGA',
             'KEWARGANEGARAAN', 'DOKUMENIMIGRASI', 'NOPASPOR', 'PASPOR', 'NOKITAP', 'KITAP', 'KITAS', 'NAMAORANGTUA',
             'AYAH', 'IBU')
KAKI = ('DIKELUARKANTANGGAL', 'DIKELUARKAN', 'LEMBAR', 'TANDATANGAN', 'KEPALADINAS', 'PENCATATANSIPIL',
        'DOKUMENINITELAH')


def angka(t):
    """Teks angka dengan salah baca huruf yang umum (O->0, I/l->1, dst.)."""
    t = t.upper().replace(' ', '')
    for a, b in (('O', '0'), ('D', '0'), ('Q', '0'), ('I', '1'), ('L', '1'), ('|', '1'), ('Z', '2'), ('S', '5'),
                 ('B', '8'), ('G', '6'), ('T', '7')):
        t = t.replace(a, b)
    return t


def cari_nik(t):
    """NIK 16 digit di dalam teks (boleh berspasi / ada salah baca huruf), atau ''."""
    bersih = re.sub(r'[^0-9A-Z]', '', angka(re.sub(r'(?i)^\s*(nik|no\.?)\s*[:.]?', '', t)))
    m = RE_NIK.search(bersih)
    return m.group(1) if m else ''


def tanggal(t):
    """'YYYY-MM-DD' dari 'DD-MM-YYYY' (atau 8 digit tanpa pemisah); '' bila tidak sah."""
    from datetime import date

    s = t.replace(' ', '').replace('O', '0').replace('o', '0')
    m = RE_TGL.search(s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r'(\d{2})[-/.]?(\d{2})[-/.]?(\d{4})', s)
        if not m:
            return ''
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        hasil = date(y, mo, d)
    except ValueError:
        return ''
    if not (1890 <= y <= date.today().year):
        return ''
    return hasil.isoformat()


def mirip_tanggal(t):
    """Teks berbentuk tanggal (walau rusak/tidak sah): banyak angka, hampir tanpa huruf."""
    s = t.replace(' ', '')
    return len(re.sub(r'\D', '', s)) >= 6 and len(re.sub(r'[\d\-/.]', '', s)) <= 2


def bersih_nama(t):
    t = re.sub(r"[^A-Za-z\s'.,-]", ' ', t)
    t = re.sub(r'^\s*[.,\-\s]+|[.,\-\s]+$', '', t)
    return re.sub(r'\s+', ' ', t).strip().upper()


def nama_wajar(t):
    return bool(t) and len(t) <= 60 and any(len(re.sub(r'[^A-Z]', '', k)) >= 2 for k in t.split())


def kosong_sel(t):
    """Isi sel yang berarti kosong: '-', nomor kolom '(5)', nomor baris."""
    s = t.strip()
    return not s or re.fullmatch(r'[-–—_.,:;|]+', s) or re.fullmatch(r'\(\d{1,2}\)', s)


def adalah_kepala(k, daftar):
    kk = kunci(k['t'])
    return any(kk == d or (len(d) >= 6 and d in kk and len(kk) <= len(d) + 6) for d in daftar)


# ---------- pengelompokan baris ----------

def _perkiraan_y(baris, x):
    """Perkiraan tinggi (y) baris di posisi x: interpolasi titik terdekat di kiri dan kanan x."""
    kiri = max((k for k in baris if k['cx'] <= x), key=lambda k: k['cx'], default=None)
    kanan = min((k for k in baris if k['cx'] > x), key=lambda k: k['cx'], default=None)
    if kiri and kanan and kanan['cx'] - kiri['cx'] > 1:
        t = (x - kiri['cx']) / (kanan['cx'] - kiri['cx'])
        return kiri['cy'] + t * (kanan['cy'] - kiri['cy'])
    return (kiri or kanan)['cy']


def kelompokkan(jangkar, lain, jarak_baris, nomor_baris=True):
    """Tempelkan kotak `lain` ke baris yang dibentuk `jangkar` (satu kotak per baris).

    1. Nomor baris di kolom paling kiri (1, 2, 3, ...) langsung ditempel ke baris ke-n.
    2. Kotak lain diproses per kolom, dari kolom terdekat ke jangkar. Posisi tiap baris di kolom itu
       diperkirakan dari titik baris yang sudah ada (interpolasi), lalu seluruh kolom digeser bersama
       sehingga paling banyak baris yang cocok satu-satu. Halaman foto yang melengkung atau miring
       (kolom kiri lebih tinggi dari kolom kanan) tetap terbaca benar."""
    baris = [[a] for a in sorted(jangkar, key=lambda k: k['cy'])]
    if not baris:
        return [], list(lain)
    lain = list(lain)
    x_jangkar = median(a['cx'] for a in jangkar)
    tinggi = median(k['h'] for k in jangkar)

    if nomor_baris:
        nomor = [k for k in lain if re.fullmatch(r'\d{1,2}\.?', k['t'].strip()) and k['cx'] < x_jangkar]
        if nomor:
            x_nomor = min(k['cx'] for k in nomor)
            nomor = sorted((k for k in nomor if k['cx'] < x_nomor + 3 * tinggi), key=lambda k: k['cy'])
            nilai = [int(k['t'].strip().rstrip('.')) for k in nomor]
            urut_naik = all(b > a for a, b in zip(nilai, nilai[1:]))
            pakai = [(n, k) for n, k in zip(nilai, nomor) if 1 <= n <= len(baris)]
            if urut_naik and pakai and all(abs(k['cy'] - baris[n - 1][0]['cy']) < 1.6 * jarak_baris for n, k in pakai):
                for n, k in pakai:
                    baris[n - 1].append(k)
                    lain.remove(k)

    sisa = []
    for k in sorted(lain, key=lambda k: abs(k['cx'] - x_jangkar)):
        d, i = min((abs(k['cy'] - _perkiraan_y(r, k['cx'])), i) for i, r in enumerate(baris))
        if d < 0.5 * jarak_baris:
            baris[i].append(k)
        else:
            sisa.append(k)
    return [sorted(r, key=lambda k: k['x0']) for r in baris], sisa


def jarak_antar(ys, cadangan):
    ys = sorted(ys)
    beda = [b - a for a, b in zip(ys, ys[1:]) if b - a > 0.3 * cadangan]
    return median(beda) if beda else cadangan


# ---------- klasifikasi isi sel ----------

def jenis_sel_t1(t):
    """('nik'|'jk'|'tgl'|'agama'|'pend'|'kerja'|'darah'|'nomor'|'teks', nilai, jarak_kamus)."""
    s = t.strip()
    if re.fullmatch(r'\d{1,2}\.?', s):
        return 'nomor', s, 0
    nik = cari_nik(s)
    if nik and len(re.sub(r'\D', '', angka(s))) <= 18:
        return 'nik', nik, 0
    if mirip_tanggal(s):
        tg = tanggal(s)
        return 'tgl', tg, 0 if tg else 9
    jk = K.jenis_kelamin(s)
    if jk and len(K.kunci(s)) <= 11:
        return 'jk', jk, 0
    for nama, f in (('agama', K.baku_agama), ('pend', K.baku_pendidikan), ('kerja', K.baku_pekerjaan)):
        v, d = f(s)
        if v:
            return nama, v, d
    if K.kunci(s) in ('A', 'B', 'AB', 'O') or K.jarak(K.kunci(s), 'TIDAKTAHU') <= 2 or K.kunci(s).startswith('TIDAKTA'):
        return 'darah', s, 0
    return 'teks', s, 0


def jenis_sel_t2(t):
    s = t.strip()
    k = K.kunci(s)
    if re.fullmatch(r'\d{1,2}\.?', s):
        return 'nomor', s, 0
    if mirip_tanggal(s):
        tg = tanggal(s)
        return 'tgl', tg, 0 if tg else 9
    if k in ('WNI', 'WNA') or (len(k) == 3 and K.jarak(k, 'WNI') <= 1 and k != 'WNA') or k in ('WN', 'NI'):
        return 'warga', 'WNA' if k == 'WNA' else 'WNI', 0 if k in ('WNI', 'WNA') else 1
    v, d = K.baku_kawin(s)
    if v:
        return 'kawin', v, d
    v, d = K.baku_hubungan(s)
    if v:
        return 'hub', v, d
    return 'teks', s, 0


def pecah(kotak, jenis_sel):
    """Kotak yang memuat dua sel sekaligus (mis. 'PEREMPUAN BATU', 'BUDI 3579...') dipecah per kata."""
    hasil = []
    for k in kotak:
        j = jenis_sel(k['t'])[0]
        kata = k['t'].split()
        if j != 'teks' or len(kata) < 2:
            hasil.append(k)
            continue
        # coba pisahkan awalan/akhiran yang dikenali
        dipecah = None
        for i in range(1, len(kata)):
            kiri, kanan = ' '.join(kata[:i]), ' '.join(kata[i:])
            jk, jn = jenis_sel(kiri)[0], jenis_sel(kanan)[0]
            if jk not in ('teks', 'nomor') or jn not in ('teks', 'nomor'):
                dipecah = (kiri, kanan, i / len(kata))
                break
        if not dipecah:
            hasil.append(k)
            continue
        kiri, kanan, r = dipecah
        lebar = k['x1'] - k['x0']
        xm = k['x0'] + lebar * r
        hasil.append({**k, 't': kiri, 'x1': xm, 'cx': (k['x0'] + xm) / 2})
        hasil.append({**k, 't': kanan, 'x0': xm, 'cx': (xm + k['x1']) / 2})
    return hasil


def gabung_teks(kotak):
    if not kotak:
        return '', 1.0
    return ' '.join(k['t'].strip() for k in kotak), min(k['s'] for k in kotak)


# ---------- baris tabel ----------

def sel_t1(baris):
    """Sel-sel satu baris tabel atas: [(kotak, jenis, nilai, jarak_kamus)], urut kiri ke kanan."""
    return [(k, *jenis_sel_t1(k['t'])) for k in pecah(baris, jenis_sel_t1) if not kosong_sel(k['t'])]


BERJENIS = ('jk', 'tgl', 'agama', 'pend', 'kerja', 'darah')


def pelajari_kolom(semua_sel):
    """Posisi tengah (x) tiap kolom tabel atas, dari sel yang jenisnya sudah pasti di semua baris."""
    xs = {}
    for sel in semua_sel:
        for k, j, v, d in sel:
            if j in BERJENIS and (v or j == 'darah') and d <= 1:
                xs.setdefault(j, []).append(k['cx'])
        jenis = [s[1] for s in sel]
        if 'jk' in jenis and 'tgl' in jenis:
            i, j = jenis.index('jk'), jenis.index('tgl')
            xs.setdefault('tempat', []).extend(s[0]['cx'] for s in sel[i + 1:j] if s[1] == 'teks')
    return {j: median(v) for j, v in xs.items() if v}


def baca_longgar(jenis, t):
    """Pembacaan cadangan untuk sel yang posisinya pasti di kolom `jenis` tetapi tulisannya rusak.
    Mengembalikan nilai baku atau '' (hasilnya selalu ditandai ragu)."""
    k = K.kunci(t)
    if jenis == 'jk':
        if re.search(r'EMP|RPU|PUAN|^PER', k):
            return 'P'
        if re.search(r'LAK|AKI|^LA.?LA', k):
            return 'L'
        return ''
    if jenis == 'agama':
        for pola, v in ((r'SLAM|ISL|^1?8?LAM$', 'Islam'), (r'KRIS|STEN', 'Kristen'), (r'KATO|THOL|OLIK', 'Katolik'),
                        (r'HIND', 'Hindu'), (r'BUD|DHA', 'Buddha'), (r'KONG|HUCU', 'Konghucu')):
            if re.search(pola, k):
                return v
        return ''
    if jenis == 'pend':
        from .kamus import PENDIDIKAN, PENDIDIKAN_LAIN, cocok_longgar
        e, _ = cocok_longgar(t, list(PENDIDIKAN) + list(PENDIDIKAN_LAIN), 0.62)
        return PENDIDIKAN[PENDIDIKAN_LAIN.get(e, e)] if e else ''
    if jenis == 'kerja':
        from .kamus import PEKERJAAN, cocok_longgar
        e, _ = cocok_longgar(t, PEKERJAAN, 0.68)
        return K.judul(e) if e else ''
    return ''


def urai_baris_t1(baris, kolom=None):
    kolom = kolom or {}
    sel = sel_t1(baris)
    a, ragu, skor = {}, set(), {}
    i_nik = next((i for i, s in enumerate(sel) if s[1] == 'nik'), None)
    if i_nik is None:
        return None
    a['nik'] = sel[i_nik][2]
    skor['nik'] = sel[i_nik][0]['s']

    no = [s[2] for s in sel[:i_nik] if s[1] == 'nomor']
    if no:
        a['_no'] = int(no[0].rstrip('.'))
    kiri = [s[0] for s in sel[:i_nik] if s[1] != 'nomor']
    nama, sk = gabung_teks(kiri)
    nama = bersih_nama(re.sub(r'^\s*\d{1,2}[.\s]+', '', nama))
    a['namaLengkap'] = nama if nama_wajar(nama) else ''
    skor['namaLengkap'] = sk

    # Sel teks bebas yang posisinya tepat di kolom berjenis (mis. "LAKOHLAI" di kolom jenis kelamin) adalah
    # isian yang rusak: dibaca longgar, dan tidak boleh ikut menjadi tempat lahir.
    kanan = []
    for k, j, v, d in sel[i_nik + 1:]:
        if j == 'teks' and kolom:
            dekat = min(kolom, key=lambda c: abs(kolom[c] - k['cx']))
            if dekat in BERJENIS:
                v2 = baca_longgar(dekat, k['t'])
                j, v, d = dekat, v2, 9
        kanan.append((k, j, v, d))

    for jenis, nama_kolom in (('jk', 'jenisKelamin'), ('tgl', 'tanggalLahir'), ('agama', 'agama'),
                              ('pend', 'pendidikanTerakhir'), ('kerja', 'pekerjaan')):
        cocok = [s for s in kanan if s[1] == jenis]
        if not cocok:
            continue
        s = next((c for c in cocok if c[2]), cocok[0])
        if s[2]:
            a[nama_kolom] = s[2]
            skor[nama_kolom] = s[0]['s'] if s[3] <= 0 else min(s[0]['s'], 0.8 if s[3] > 2 else 0.9)
        else:
            ragu.add(nama_kolom)  # sel ada tetapi tidak terbaca

    # Tempat lahir = teks bebas sesudah jenis kelamin dan sebelum tanggal lahir.
    idx = {s[1]: i for i, s in reversed(list(enumerate(kanan)))}
    mulai = idx.get('jk', -1) + 1
    akhir = idx.get('tgl', len(kanan))
    tempat = [s[0] for s in kanan[mulai:akhir] if s[1] == 'teks']
    if 'tempat' in kolom and 'tgl' not in idx:
        tempat = [k for k in tempat if abs(k['cx'] - kolom['tempat']) < abs(k['cx'] - kolom.get('agama', 1e9))]
    t, sk = gabung_teks(tempat)
    t = bersih_nama(t)
    a['tempatLahir'] = t if nama_wajar(t) else ''
    skor['tempatLahir'] = sk

    # Pekerjaan di luar kamus: teks bebas sesudah pendidikan dan sebelum golongan darah.
    if not a.get('pekerjaan') and 'pend' in idx:
        sisa = [s[0] for s in kanan[idx['pend'] + 1:] if s[1] == 'teks']
        t, sk = gabung_teks(sisa[:1])
        t = bersih_nama(t)
        if nama_wajar(t):
            a['pekerjaan'] = K.judul(t)
            skor['pekerjaan'] = min(sk, 0.8)  # bukan isian baku: selalu dicek manusia

    for nama_kolom, s in skor.items():
        if a.get(nama_kolom) and s < yakin(nama_kolom):
            ragu.add(nama_kolom)
    a['_skor'] = skor
    a['_ragu'] = ragu
    return a


def urai_baris_t2(baris, pisah=None):
    """`pisah(kotak)` -> 'ayah' | 'ibu' | None, dari letak judul kolom (lihat pemisah_ortu)."""
    sel = [(k, *jenis_sel_t2(k['t'])) for k in pecah(baris, jenis_sel_t2) if not kosong_sel(k['t'])]
    a, skor = {}, {}
    x_warga = next((s[0]['x0'] for s in sel if s[1] == 'warga'), 1e9)
    for jenis, kolom in (('kawin', 'statusPerkawinan'), ('hub', 'statusHubungan'), ('warga', 'kewarganegaraan'),
                         ('tgl', 'tanggalPerkawinan')):
        cocok = [s for s in sel if s[1] == jenis and (jenis == 'warga' or s[0]['x1'] <= x_warga + 5)]
        if cocok:
            s = cocok[0]
            a[kolom] = s[2]
            skor[kolom] = s[0]['s'] if s[3] <= 0 else min(s[0]['s'], 0.9)

    # Nama orang tua = teks bebas di kanan kolom kewarganegaraan (atau status hubungan).
    # Batasnya sel kewarganegaraan bila ada; semua sel di kanannya dianggap nama (nama orang tua bisa saja
    # mengandung kata seperti ISTRI/ANAK).
    warga = [s for s in sel if s[1] == 'warga']
    if warga:
        batas = warga[0][0]['x1']
        teks = [s[0] for s in sel if s[0]['x0'] >= batas - 5 and s[1] in ('teks', 'hub', 'kawin')]
    else:
        batas = max((s[0]['x1'] for s in sel if s[1] in ('hub', 'kawin', 'tgl')), default=None)
        teks = [s[0] for s in sel if s[1] == 'teks' and (batas is None or s[0]['x0'] >= batas - 5)]
    teks = [k for k in teks if nama_wajar(bersih_nama(k['t'])) and not re.search(r'\d{4}', k['t'])]
    ayah, ibu = [], []
    if pisah is not None and teks:
        for k in teks:
            (ayah if pisah(k) == 'ayah' else ibu).append(k)
    elif len(teks) >= 2:
        # tanpa judul kolom: celah terlebar memisahkan ayah dan ibu
        celah = [(teks[i + 1]['x0'] - teks[i]['x1'], i) for i in range(len(teks) - 1)]
        i = max(celah)[1]
        ayah, ibu = teks[:i + 1], teks[i + 1:]
    elif teks:
        ayah = teks  # satu nama tanpa judul kolom: belum pasti ayah atau ibu
        skor['_ayahIbu'] = 0.0
    for kolom, ks in (('namaAyah', ayah), ('namaIbu', ibu)):
        t, sk = gabung_teks(ks)
        t = bersih_nama(t)
        if nama_wajar(t):
            a[kolom] = t
            skor[kolom] = sk if '_ayahIbu' not in skor else 0.0
    a['_skor'] = skor
    a['_ragu'] = {k for k, s in skor.items() if not k.startswith('_') and a.get(k) and s < yakin(k)}
    return a


def pemisah_ortu(ks, y_kepala2, tinggi):
    """Fungsi penentu kolom ayah/ibu dari judul kolom tabel bawah. Nama ditulis rata kiri, jadi yang
    dipakai tepi kiri nama (x0). Urutan bukti: judul "Ayah" & "Ibu", nomor kolom (16) & (17), judul
    "Ayah" saja (foto terpotong), judul "Nama Orang Tua" (tepat di atas batas kedua kolom)."""
    dekat = [k for k in ks if abs(k['cy'] - y_kepala2) < 6 * tinggi]

    def cari(*pola):
        return next((k for k in dekat if kunci(k['t']) in pola), None)

    ayah, ibu = cari('AYAH'), cari('IBU', 'LBU', '1BU')
    n16, n17 = cari('16'), cari('17')
    if n16 and not re.fullmatch(r'\(?16\)?', n16['t'].strip()):
        n16 = None
    if n17 and not re.fullmatch(r'\(?17\)?', n17['t'].strip()):
        n17 = None
    ortu = next((k for k in dekat if 'ORANGTUA' in kunci(k['t'])), None)
    for a, b in ((ayah, ibu), (n16, n17), (ayah, n17), (n16, ibu)):
        if a and b and b['cx'] > a['cx']:
            # nama ibu mulai di tepi kiri kolom ibu (~tengah kedua judul); nama ayah mulai jauh di kirinya
            batas = a['cx'] + 0.25 * (b['cx'] - a['cx'])
            return lambda k: 'ayah' if k['x0'] < batas else 'ibu'
    kiri = ayah or n16
    if kiri:  # hanya kolom ayah yang tampak: kolom ibu mulai sesudah tengah judul ayah
        return lambda k: 'ayah' if k['x0'] < kiri['cx'] else 'ibu'
    if ortu:
        return lambda k: 'ayah' if k['cx'] < ortu['cx'] else 'ibu'
    return None


# ---------- kepala dokumen ----------

LABEL = [
    ('kepalaKeluarga', r'NAMA\s*KEPALA\s*KELUARGA'),
    ('alamat', r'ALAMAT'),
    ('rtrw', r'RT\s*/?\s*RW'),
    ('kodePos', r'KODE\s*POS'),
    ('desa', r'DESA\s*/?\s*KELURAHAN'),
    ('kecamatan', r'KECAMATAN'),
    ('kabupaten', r'KABUPATEN\s*/?\s*KOTA'),
    ('provinsi', r'PROVINSI'),
]


def urai_kepala(kotak, y_batas):
    """Isian bagian atas (di atas tabel): nilai = teks sesudah label di kotak yang sama, atau kotak
    terdekat di kanan label pada ketinggian yang sama (sebelum label berikutnya)."""
    atas = [k for k in kotak if k['cy'] < y_batas]
    hasil = {}
    no_kk = ''
    for k in sorted(atas, key=lambda k: k['cy']):
        if re.match(r'(?i)\s*N[oO0]\b|\s*N[oO0]\.', k['t']) or len(re.sub(r'\D', '', k['t'])) >= 15:
            n = cari_nik(k['t'])
            if n and not no_kk:
                no_kk = n
                hasil['_skor_noKK'] = k['s']
    hasil['noKK'] = no_kk

    label = []  # (kotak, nama, sisa teks sesudah label)
    for k in atas:
        for nama, pola in LABEL:
            m = re.search(pola, k['t'], re.I)
            if m and m.start() <= 3:
                label.append((k, nama, k['t'][m.end():]))
                break
    def pemilik(b):
        # label terdekat (ketinggian) di sebelah kiri kotak nilai
        kiri = [l[0] for l in label if l[0]['x1'] < b['x0'] + 0.5 * l[0]['h']]
        sebaris = [l for l in kiri if abs(l['cy'] - b['cy']) < 0.6 * max(l['h'], b['h'])]
        if not sebaris:
            return None
        terdekat = max(sebaris, key=lambda l: l['x1'])  # kolom label kanan (Desa/Kec) atau kiri (Alamat/RT)
        sejajar = [l for l in sebaris if abs(l['x0'] - terdekat['x0']) < 3 * l['h']]
        return min(sejajar, key=lambda l: abs(l['cy'] - b['cy']))

    for k, nama, sisa in label:
        if nama in hasil:
            continue
        nilai = sisa.strip().lstrip(':;.').strip()
        skor = k['s']
        if not nilai:
            kanan = [b for b in atas if b is not k and b['x0'] > k['x1'] - 0.5 * k['h']
                     and abs(b['cy'] - k['cy']) < 0.6 * max(k['h'], b['h']) and pemilik(b) is k]
            kanan.sort(key=lambda b: b['x0'])
            ambil = []
            for b in kanan:
                if any(b is l[0] for l in label) or (ambil and b['x0'] - ambil[-1]['x1'] > 6 * k['h']):
                    break
                ambil.append(b)
                if b['x0'] - k['x1'] > 15 * k['h']:
                    break
            nilai = ' '.join(b['t'] for b in ambil).strip().lstrip(':;.').strip()
            skor = min([b['s'] for b in ambil], default=0)
        if nilai:
            hasil[nama] = nilai
            hasil['_skor_' + nama] = skor
    return hasil


JUDUL_LAIN = ('KEWARGA', 'NEGARAAN', 'DOKUMEN', 'IMIGRAS', 'PASPOR', 'KITAP', 'KITAS', 'ORANGTUA', 'PERKAWINAN',
              'HUBUNGAN', 'DALAMKELUARGA', 'INDONESIA', 'REPUBLIK', 'PERCERAIAN')


def kata_judul(t):
    """Teks judul kolom tabel (termasuk yang salah baca), bukan isi."""
    k = kunci(t)
    if k in ('AYAH', 'IBU', 'LBU', '1BU', 'IBV', 'NO', 'NAMA', 'STATUS', 'TANGGAL'):
        return True
    return any(j in k for j in JUDUL_LAIN) or any(K.jarak(k, j) <= 2 for j in ('KEWARGANEGARAAN', 'PERKAWINAN'))


def nomor_kiri(isi2, kelas, tinggi, n):
    """Kotak nomor baris 1..n di kolom paling kiri tabel bawah, atau [] bila tidak lengkap/berurutan."""
    if not n:
        return []
    x_kelas = min((k['cx'] for v in kelas.values() for k in v), default=1e9)
    nomor = [k for k in isi2 if re.fullmatch(r'\d{1,2}\.?', k['t'].strip()) and k['cx'] < x_kelas]
    if not nomor:
        return []
    x0 = min(k['cx'] for k in nomor)
    nomor = sorted((k for k in nomor if k['cx'] < x0 + 3 * tinggi), key=lambda k: k['cy'])
    nilai = [int(k['t'].strip().rstrip('.')) for k in nomor]
    if any(b <= a for a, b in zip(nilai, nilai[1:])):
        return []
    pakai = [k for v, k in zip(nilai, nomor) if v <= n]
    return pakai if [int(k['t'].strip().rstrip('.')) for k in pakai] == list(range(1, n + 1)) else []


def pasangkan(anggota, bagian2):
    """Gabungkan baris tabel bawah ke anggota: lewat nomor baris bila kedua tabel punya nomor, selain itu
    menurut urutan. Anggota tanpa pasangan ditandai ragu di kolom tabel bawah."""
    pakai_nomor = (all('_no' in a for a in anggota) and len({a['_no'] for a in anggota}) == len(anggota)
                   and all(b.get('_no') for b in bagian2))
    if pakai_nomor:
        per_no = {b['_no']: b for b in bagian2}
        pasangan = [(a, per_no.get(a['_no'])) for a in anggota]
    else:
        pasangan = list(zip(anggota, bagian2 + [None] * (len(anggota) - len(bagian2))))
    for a, b in pasangan:
        if not b:
            a['_ragu'] |= {'statusPerkawinan', 'statusHubungan', 'namaAyah', 'namaIbu'}
            continue
        a['_ragu'] |= b['_ragu']
        a['_skor'].update(b['_skor'])
        for kk, v in b.items():
            if not kk.startswith('_'):
                a.setdefault(kk, v)


# ---------- halaman utuh ----------

def urai_halaman(kotak):
    ks = luruskan(kotak)
    if not ks:
        return None
    tinggi = median(k['h'] for k in ks)

    # Bukan KK (mis. daftar usulan JKN yang juga memuat NIK): tidak ada judul "KARTU KELUARGA"
    # maupun judul kolom khas KK.
    kunci_semua = ' '.join(kunci(k['t']) for k in ks)
    ciri = sum(c in kunci_semua for c in ('KARTUKELUARGA', 'NAMALENGKAP', 'JENISKELAMIN', 'TEMPATLAHIR',
                                           'STATUSHUBUNGAN', 'KEWARGANEGARAAN', 'NAMAORANGTUA', 'PENDIDIKAN'))
    if ciri < 3 and 'KARTUKELUARGA' not in kunci_semua:
        return {'kepala': {}, 'anggota': [], 'barisTerlihat': 0, 'bukanKK': True}

    kepala1 = [k for k in ks if adalah_kepala(k, KEPALA_T1)]
    kepala2 = [k for k in ks if adalah_kepala(k, KEPALA_T2)]
    kaki = [k for k in ks if any(c in kunci(k['t']) for c in KAKI)]

    # Jangkar tabel atas: NIK. NIK di bagian atas yang diawali "No." adalah No. KK.
    nik = []
    for k in ks:
        j = jenis_sel_t1(k['t'])
        if j[0] == 'nik' and not re.match(r'(?i)\s*no', k['t']):
            nik.append(k)
    y_kepala1 = median(k['cy'] for k in kepala1) if kepala1 else None
    if y_kepala1 is not None:
        nik = [k for k in nik if k['cy'] > y_kepala1 - tinggi]
    y_kepala2 = min((k['cy'] for k in kepala2 if not nik or k['cy'] > max(n['cy'] for n in nik)), default=None)
    if y_kepala2 is not None:
        nik = [k for k in nik if k['cy'] < y_kepala2]
    # Satu NIK per baris: buang duplikat pada ketinggian yang sama
    nik.sort(key=lambda k: k['cy'])
    unik = []
    for k in nik:
        if unik and abs(k['cy'] - unik[-1]['cy']) < 0.6 * tinggi:
            if k['s'] > unik[-1]['s']:
                unik[-1] = k
            continue
        unik.append(k)
    nik = unik

    y_atas = y_kepala1 if y_kepala1 is not None else (min(k['cy'] for k in nik) - 2 * tinggi if nik else 0)
    kep = urai_kepala(ks, y_atas - 0.5 * tinggi if y_atas else 0)

    anggota = []
    jarak1 = jarak_antar([k['cy'] for k in nik], 2.2 * tinggi)
    if nik:
        y_bawah1 = y_kepala2 if y_kepala2 is not None else max(k['cy'] for k in nik) + jarak1
        isi1 = [k for k in ks if y_atas < k['cy'] < y_bawah1 and k not in nik and not adalah_kepala(k, KEPALA_T1)]
        baris1, _ = kelompokkan(nik, isi1, jarak1)
        kolom = pelajari_kolom([sel_t1(b) for b in baris1])
        for b in baris1:
            a = urai_baris_t1(b, kolom)
            if a:
                anggota.append(a)

    # Tabel bawah
    if y_kepala2 is not None:
        y_kaki = min((k['cy'] for k in kaki if k['cy'] > y_kepala2), default=1e9)
        # Isi tabel mulai di bawah baris nomor kolom "(10) (11) ... (17)" bila terbaca.
        nokol = [k for k in ks if re.fullmatch(r'[(\[{]?1[0-7][)\]}]?', k['t'].strip()) and y_kepala2 - tinggi < k['cy'] < y_kaki]
        y_mulai2 = max(y_kepala2, median(k['cy'] for k in nokol) + 0.5 * tinggi) if len(nokol) >= 3 else y_kepala2
        isi2 = [k for k in ks if y_mulai2 < k['cy'] < y_kaki and not adalah_kepala(k, KEPALA_T2) and not kata_judul(k['t'])]
        kelas = {}
        for k in isi2:
            j = jenis_sel_t2(k['t'])[0]
            if j in ('warga', 'hub', 'kawin'):
                kelas.setdefault(j, []).append(k)
        nomor2 = nomor_kiri(isi2, kelas, tinggi, len(anggota))
        if nomor2:
            # Nomor baris 1..n di kolom kiri tabel bawah terbaca lengkap: jadi jangkar pasti.
            jarak2 = jarak_antar([k['cy'] for k in nomor2], jarak1)
            baris2, _ = kelompokkan(nomor2, [k for k in isi2 if k not in nomor2], jarak2, nomor_baris=False)
            pisah = pemisah_ortu(ks, y_kepala2, tinggi)
            bagian2 = []
            for b in baris2:
                no = int(b[0]['t'].strip().rstrip('.')) if b[0] in nomor2 else None
                b = [k for k in b if k not in nomor2]
                bagian2.append({**urai_baris_t2(b, pisah), '_no': no})
            pasangkan(anggota, bagian2)
        elif kelas:
            # Jangkar = kolom berjenis yang paling banyak terbaca; sel berjenis dari kolom lain yang tidak
            # masuk baris mana pun (mis. sel jangkar barisnya rusak) menjadi jangkar baris baru.
            urut = sorted(kelas.values(), key=len, reverse=True)
            jangkar = []
            for k in sorted(urut[0], key=lambda k: k['cy']):
                if jangkar and abs(k['cy'] - jangkar[-1]['cy']) < 0.6 * tinggi:
                    continue
                jangkar.append(k)
            jarak2 = jarak_antar([k['cy'] for k in jangkar], jarak1)
            for lain in urut[1:]:
                _, sisa = kelompokkan(jangkar, lain, jarak2)
                for k in sorted(sisa, key=lambda k: k['cy']):
                    if all(abs(k['cy'] - j['cy']) > 0.6 * jarak2 for j in jangkar if abs(j['cx'] - k['cx']) < 3 * jarak2):
                        jangkar.append(k)
            baris2, _ = kelompokkan(jangkar, [k for k in isi2 if k not in jangkar], jarak2)
            baris2.sort(key=lambda b: median(k['cy'] for k in b))
            pisah = pemisah_ortu(ks, y_kepala2, tinggi)
            # Kolom nama ditulis rata kiri: batas kolom ayah|ibu ~ tengah judul "Ayah" dan "Ibu"
            bagian2 = [urai_baris_t2(b, pisah) for b in baris2]
            bagian2 = [b for b in bagian2 if len([k for k in b if not k.startswith('_')]) >= 2]
            pasangkan(anggota, bagian2)

    return {'kepala': kep, 'anggota': anggota, 'barisTerlihat': len(nik)}
