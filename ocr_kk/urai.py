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
    bersih = re.sub(r'[^0-9A-Z]', '', angka(re.sub(r'(?i)^[\s,.;:\'"]*(nik|no\.?)\s*[:.]?', '', t)))
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
            # Nomor yang salah baca (mis. "2" terbaca "3") menyimpang ~1 baris dari pergeseran nomor lain: buang.
            if pakai:
                geser = median(k['cy'] - baris[n - 1][0]['cy'] for n, k in pakai)
                pakai = [(n, k) for n, k in pakai if abs(k['cy'] - baris[n - 1][0]['cy'] - geser) < 0.4 * jarak_baris]
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


def sambung_lanjutan(baris, sisa, jarak_baris, semua):
    """Isi sel yang panjang turun ke baris kedua di dalam sel yang sama (mis. nama 4 kata): kotaknya sedikit di
    bawah sel itu, satu kolom, dan tidak sejajar dengan baris anggota mana pun. Kotak seperti itu disambungkan
    ke sel di atasnya (teksnya ditambahkan di belakang). Mengubah `baris` di tempat."""
    for b in sorted(sisa, key=lambda k: k['cy']):
        if not re.search(r'[A-Za-z]{2}', b['t']) or kosong_sel(b['t']):
            continue
        # baris anggota sungguhan (yang tidak terjangkar) punya sel lain sejajar; lanjutan sel berdiri sendiri
        if any(k is not b and abs(k['cy'] - b['cy']) < 0.35 * jarak_baris and not kosong_sel(k['t']) for k in semua):
            continue
        calon = []
        for r in baris:
            for i, k in enumerate(r):
                dy = b['cy'] - k['cy']
                tumpang = min(b['x1'], k['x1']) - max(b['x0'], k['x0'])
                if 0.4 * jarak_baris < dy < 1.15 * jarak_baris and abs(b['x0'] - k['x0']) < 2 * k['h'] and tumpang > 0:
                    calon.append((dy, r, i))
        if not calon:
            continue
        _, r, i = min(calon, key=lambda c: c[0])
        k = r[i]
        # baris di bawahnya kosong di kolom ini: kotak ini lebih mungkin isi baris bawah yang meleset
        urut = sorted(baris, key=lambda x: median(y['cy'] for y in x))
        j = next(n for n, x in enumerate(urut) if x is r)
        if j + 1 < len(urut) and not any(min(b['x1'], y['x1']) - max(b['x0'], y['x0']) > 0 for y in urut[j + 1]):
            continue
        r[i] = {**k, 't': k['t'].rstrip() + ' ' + b['t'].strip(), 's': min(k['s'], b['s']),
                'x1': max(k['x1'], b['x1']), 'y1': max(k['y1'], b['y1'])}


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
    # blanko lama menulis kewarganegaraan "INDONESIA"
    if k == 'INDONESIA' or (len(k) >= 4 and (k.startswith(('INDO', 'INOO', 'INDD')) or K.jarak(k, 'INDONESIA') <= 2)):
        return 'warga', 'WNI', 0 if k == 'INDONESIA' else 1
    # potongan "INDONESIA"/"WNI" yang rusak berdiri sendiri: bukan nama, tetapi juga tidak pasti
    if k in ('AN', 'IN', 'INA', 'INO', 'INON', 'IND', 'INDON'):
        return 'warga', 'WNI', 2
    v, d = K.baku_kawin(s)
    if v:
        return 'kawin', v, d
    v, d = K.baku_hubungan(s)
    if v:
        return 'hub', v, d
    # status hubungan pendek yang rusak ("ISTER", "1STRI"): dikenali longgar, selalu ditandai ragu
    if len(k) <= 7 and re.search(r'STR|ISTE', k) and not re.search(r'[AEIOU]{3}', k):
        return 'hub', 'Istri', 9
    return 'teks', s, 0


def pecah(kotak, jenis_sel):
    """Kotak yang memuat dua sel sekaligus (mis. 'PEREMPUAN BATU', 'BUDI 3579...') dipecah per kata."""
    hasil = []
    for k in kotak:
        # NIK yang menempel ke sel sebelah tanpa spasi ("3579...0003LAKI-LAKI", "BUDI3579...")
        t = re.sub(r'(?<=[A-Za-z])(\d{16})(?!\d)', r' \1', re.sub(r'(?<!\d)(\d{16})(?=[A-Za-z])', r'\1 ', k['t']))
        if t != k['t']:
            k = {**k, 't': t}
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
    if jenis == 'kawin':
        if re.search(r'CER', k):
            if re.search(r'HID|IDU', k):
                return 'Cerai Hidup'
            if re.search(r'MAT|ATI', k):
                return 'Cerai Mati'
            return ''
        if re.match(r'BE[LI1]', k) or re.search(r'BELUM|ELUM', k):
            return 'Belum Kawin'
        if re.search(r'TERC|RCAT|CATAT|ERCA', k):
            return 'Kawin Belum Tercatat' if re.search(r'BEL', k) else 'Kawin Tercatat'
        # 'KAVMN', 'KAWN': W sering terbaca V/VV/M
        if re.search(r'KAW|AWIN', k) or re.fullmatch(r'KA[VWM]{1,2}[I1]?N', k):
            return 'Kawin'
        return ''
    if jenis == 'hub':
        for pola, v in ((r'KEP|EPAL|KELU|LUAR', 'Kepala Keluarga'), (r'STR|ISTR', 'Istri'), (r'SUAM|UAMI', 'Suami'),
                        (r'^ANA|^AN[AK]', 'Anak'), (r'MENAN|NANTU', 'Menantu'), (r'^CUC', 'Cucu'),
                        (r'MERT|RTUA', 'Mertua'), (r'ORANG|GTUA', 'Orang Tua'), (r'FAMI|MILI', 'Famili Lain')):
            if re.search(pola, k):
                return v
        return ''
    if jenis == 'warga':
        return 'WNI' if re.fullmatch(r'W?N[I1L]?|WN.?|.NI', k) else ''
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
    # Sisa nomor baris yang salah baca ("J", "3.") di ujung kiri bukan bagian nama.
    while len(kiri) > 1 and len(re.sub(r'[^A-Za-z0-9]', '', kiri[0]['t'])) <= 2:
        kiri = kiri[1:]
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


def sel_t2(baris):
    return [(k, *jenis_sel_t2(k['t'])) for k in pecah(baris, jenis_sel_t2) if not kosong_sel(k['t'])]


def pelajari_kolom2(semua_sel):
    """Posisi tengah (x) kolom tabel bawah dari sel yang jenisnya pasti: kawin, tgl, hub, warga, dan
    'ortu' (teks di kanan kewarganegaraan)."""
    xs = {}
    for sel in semua_sel:
        for k, j, v, d in sel:
            if j in ('kawin', 'tgl', 'hub', 'warga') and v and d <= 3:
                xs.setdefault(j, []).append(k['cx'])
                xs.setdefault(j + '_x0', []).append(k['x0'])  # tepi kiri (tulisan rata kiri)
        w = next((k for k, j, v, d in sel if j == 'warga' and d <= 1), None)
        if w:
            xs.setdefault('ortu', []).extend(k['cx'] for k, j, v, d in sel if j == 'teks' and k['x0'] > w['x1'])
    return {j: median(v) for j, v in xs.items() if v}


def urai_baris_t2(baris, pisah=None, kolom=None):
    """`pisah(kotak)` -> 'ayah' | 'ibu' | None, dari letak judul kolom (lihat pemisah_ortu).
    `kolom` = posisi kolom dari pelajari_kolom2: sel rusak di kolom status/kewarganegaraan dibaca longgar
    (ditandai ragu) dan tidak pernah ikut menjadi nama orang tua."""
    sel = sel_t2(baris)
    if kolom and 'warga' in kolom:
        baru = []
        x_warga = kolom['warga']
        for k, j, v, d in sel:
            # hanya sel di kiri area nama orang tua (batas: tengah antara kolom WNI dan kolom nama)
            batas = (x_warga + kolom['ortu']) / 2 if 'ortu' in kolom else x_warga + 3 * k['h']
            if j == 'teks' and k['cx'] < batas:
                dekat = min((c for c in ('kawin', 'tgl', 'hub', 'warga') if c in kolom),
                            key=lambda c: abs(kolom[c] - k['cx']))
                # kolom status perkawinan tidak pernah terbaca bersih: sel teks yang berakhir sebelum tepi kiri
                # kolom tanggal perkawinan / status hubungan adalah status perkawinan
                tepi = min((kolom[c + '_x0'] for c in ('tgl', 'hub') if c + '_x0' in kolom), default=None)
                if 'kawin' not in kolom and tepi is not None and k['x1'] < tepi:
                    dekat = 'kawin'
                if dekat in ('kawin', 'hub', 'warga'):
                    v2 = baca_longgar(dekat, k['t'])
                    j, v, d = (dekat, v2, 9) if v2 else ('rusak', '', 9)
            baru.append((k, j, v, d))
        sel = baru
    a, skor = {}, {}
    x_warga = next((s[0]['x0'] for s in sel if s[1] == 'warga'), 1e9)
    for jenis, kolom in (('kawin', 'statusPerkawinan'), ('hub', 'statusHubungan'), ('warga', 'kewarganegaraan'),
                         ('tgl', 'tanggalPerkawinan')):
        cocok = [s for s in sel if s[1] == jenis and (jenis == 'warga' or s[0]['x1'] <= x_warga + 5)]
        if cocok:
            s = cocok[0]
            if s[2]:
                a[kolom] = s[2]
                skor[kolom] = s[0]['s'] if s[3] <= 0 else min(s[0]['s'], 0.8 if s[3] > 2 else 0.9)

    # Nama orang tua = teks bebas di kanan kolom kewarganegaraan (atau status hubungan).
    # Batasnya sel kewarganegaraan bila ada; semua sel di kanannya dianggap nama (nama orang tua bisa saja
    # mengandung kata seperti ISTRI/ANAK).
    warga = [s for s in sel if s[1] == 'warga']
    if warga:
        batas = warga[0][0]['x1']
        teks = [s[0] for s in sel if s[0]['x0'] >= batas - 5 and s[1] in ('teks', 'hub', 'kawin')]
    else:
        # tanpa kewarganegaraan: batas = sel status hubungan PERTAMA dari kiri (nama orang tua di kanannya bisa
        # saja memuat kata seperti ISTRI/ANAK)
        hub = [s[0]['x1'] for s in sel if s[1] == 'hub']
        batas = hub[0] if hub else max((s[0]['x1'] for s in sel if s[1] in ('kawin', 'tgl')), default=None)
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
    # toleran terhadap salah baca 1-2 huruf (mis. "Nama Kepaia Keluarga", "Alamal")
    ('kepalaKeluarga', r'NAMA\s*KE\S{2,4}\s*KEL\S{3,6}'),
    ('alamat', r'A[LI1]AMA[TL7I]'),
    ('rtrw', r'RT\s*[/I1l|]?\s*RW'),
    ('kodePos', r'K[O0]DE\s*P[O0]S'),
    ('desa', r'DESA\s*[/I1l|]?\s*KEL\S{4,8}'),
    ('kecamatan', r'KECAMA\S{1,3}'),
    ('kabupaten', r'KABUPA\S{2,4}\s*[/I1l|]?\s*K[O0]TA'),
    ('provinsi', r'PR[O0]VIN\S{1,2}'),
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
              'HUBUNGAN', 'DALAMKELUARGA', 'REPUBLIK', 'PERCERAIAN')


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


def samakan_nama(anggota, kep):
    """Satu nama sering tercetak beberapa kali di KK (nama kepala di bagian atas & di tabel; nama ayah/ibu anak =
    nama lengkap orang tuanya di tabel). Tulisan yang hampir sama (beda 1-2 huruf/spasi) adalah orang yang sama:
    semuanya diganti bacaan dengan keyakinan tertinggi. Bila dua bacaan atau lebih tepat sama, nama itu
    terkonfirmasi dan tidak ditandai ragu. Tidak ada nama baru yang dibuat."""
    isian = []  # (wadah, kolom, kunci skor)
    for a in anggota:
        for k in ('namaLengkap', 'namaAyah', 'namaIbu'):
            if a.get(k):
                isian.append((a, k))
    if kep.get('kepalaKeluarga'):
        isian.append((kep, 'kepalaKeluarga'))

    def teks(w, k):
        return bersih_nama(w[k]) if k == 'kepalaKeluarga' else w[k]

    def skor(w, k):
        return w.get('_skor_kepalaKeluarga', 0) if k == 'kepalaKeluarga' else w['_skor'].get(k, 0)

    kunci_ = [K.kunci(teks(w, k)) for w, k in isian]
    induk = list(range(len(isian)))

    def akar(i):
        while induk[i] != i:
            i = induk[i]
        return i

    for i in range(len(isian)):
        for j in range(i + 1, len(isian)):
            a, b = kunci_[i], kunci_[j]
            if len(a) < 6 or len(b) < 6:
                continue
            batas = 0 if min(len(a), len(b)) < 8 else 1 if min(len(a), len(b)) < 14 else 2
            if a == b or (a[0] == b[0] and K.jarak(a, b) <= batas):
                induk[akar(j)] = akar(i)
    kelompok = {}
    for i in range(len(isian)):
        kelompok.setdefault(akar(i), []).append(i)
    for anggota_kel in kelompok.values():
        if len(anggota_kel) < 2:
            continue
        hitung = {}
        for i in anggota_kel:
            hitung[kunci_[i]] = hitung.get(kunci_[i], 0) + 1
        # pilih: paling banyak bacaan yang sama, lalu skor tertinggi, lalu versi yang punya spasi
        terbaik = max(anggota_kel, key=lambda i: (hitung[kunci_[i]], skor(*isian[i]), teks(*isian[i]).count(' ')))
        nama = teks(*isian[terbaik])
        terkonfirmasi = hitung[kunci_[terbaik]] >= 2
        s_baru = max(skor(*isian[i]) for i in anggota_kel if kunci_[i] == kunci_[terbaik])
        if terkonfirmasi:
            s_baru = max(s_baru, 0.99)
        for i in anggota_kel:
            w, k = isian[i]
            if k == 'kepalaKeluarga':
                w[k] = nama
                w['_skor_kepalaKeluarga'] = s_baru
                continue
            w[k] = nama
            w['_skor'][k] = s_baru
            if s_baru >= yakin(k):
                w['_ragu'].discard(k)
            else:
                w['_ragu'].add(k)


# ---------- halaman utuh ----------

def pisah_nik(ks):
    """NIK yang terbaca menempel dengan sel sebelahnya dalam satu kotak tanpa spasi ("3579...0003LAKI-LAKI",
    "BUDI SANTOSO3579...") dipecah menjadi dua kotak; lebar dibagi menurut jumlah huruf."""
    hasil = []
    for k in ks:
        m = re.fullmatch(r'\s*(\d{16})\s*([A-Za-z].*)', k['t']) or re.fullmatch(r'(.*[A-Za-z])\s*(\d{16})\s*', k['t'])
        if not m:
            hasil.append(k)
            continue
        a, b = m.group(1).strip(), m.group(2).strip()
        xm = k['x0'] + (k['x1'] - k['x0']) * len(a) / max(1, len(a) + len(b))
        hasil.append({**k, 't': a, 'x1': xm, 'cx': (k['x0'] + xm) / 2})
        hasil.append({**k, 't': b, 'x0': xm, 'cx': (xm + k['x1']) / 2})
    return hasil


def urai_halaman(kotak):
    ks = pisah_nik(luruskan(kotak))
    if not ks:
        return None
    tinggi = median(k['h'] for k in ks)

    # Bukan KK (mis. daftar usulan JKN yang juga memuat NIK): tidak ada judul "KARTU KELUARGA"
    # maupun judul kolom khas KK.
    kunci_semua = ' '.join(kunci(k['t']) for k in ks)
    ciri = sum(c in kunci_semua for c in ('KARTUKELUARGA', 'NAMALENGKAP', 'JENISKELAMIN', 'TEMPATLAHIR',
                                           'STATUSHUBUNGAN', 'KEWARGANEGARAAN', 'NAMAORANGTUA', 'PENDIDIKAN'))
    # "KARTU KELUARGA" sebagai judul (huruf besar, kotak sendiri); kalimat "...foto Kartu Keluarga" di formulir lain
    # tidak dihitung.
    judul_kk = any(kunci(k['t']) in ('KARTUKELUARGA', 'KARTUKELUARCA', 'KARTUKELUAROA') and k['h'] > 1.5 * median(x['h'] for x in ks)
                   for k in ks)
    if ciri < 3 and not judul_kk:
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
        baris1, sisa1 = kelompokkan(nik, isi1, jarak1)
        sambung_lanjutan(baris1, sisa1, jarak1, isi1)
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
            baris2, sisa2 = kelompokkan(nomor2, [k for k in isi2 if k not in nomor2], jarak2, nomor_baris=False)
            sambung_lanjutan(baris2, sisa2, jarak2, isi2)
            pisah = pemisah_ortu(ks, y_kepala2, tinggi)
            kolom2 = pelajari_kolom2([sel_t2([k for k in b if k not in nomor2]) for b in baris2])
            bagian2 = []
            for b in baris2:
                no = int(b[0]['t'].strip().rstrip('.')) if b[0] in nomor2 else None
                b = [k for k in b if k not in nomor2]
                bagian2.append({**urai_baris_t2(b, pisah, kolom2), '_no': no})
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
            baris2, sisa2 = kelompokkan(jangkar, [k for k in isi2 if k not in jangkar], jarak2)
            sambung_lanjutan(baris2, sisa2, jarak2, isi2)
            baris2.sort(key=lambda b: median(k['cy'] for k in b))
            pisah = pemisah_ortu(ks, y_kepala2, tinggi)
            # Kolom nama ditulis rata kiri: batas kolom ayah|ibu ~ tengah judul "Ayah" dan "Ibu"
            kolom2 = pelajari_kolom2([sel_t2(b) for b in baris2])
            bagian2 = [urai_baris_t2(b, pisah, kolom2) for b in baris2]
            bagian2 = [b for b in bagian2 if len([k for k in b if not k.startswith('_')]) >= 2]
            pasangkan(anggota, bagian2)

    samakan_nama(anggota, kep)
    return {'kepala': kep, 'anggota': anggota, 'barisTerlihat': len(nik)}
