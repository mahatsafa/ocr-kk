"""Halaman uji coba lokal: unggah foto/PDF KK, lihat hasil OCR di samping fotonya.

Pakai:  uv run python -m ocr_kk.web            -> http://localhost:3000
        uv run python -m ocr_kk.web --port 8080

Hanya mendengarkan di 127.0.0.1 (data KK = data pribadi, jangan dibuka ke jaringan). Tidak menyimpan file apa pun:
foto dibaca di memori lalu dibuang. Tidak terhubung ke database atau web SIP MENTARI.
"""
import argparse
import base64
import io
import json
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

from .baca import baca_file
from .gambar import muat
from .tata import putar_gambar

KUNCI = threading.Lock()  # mesin OCR dipakai satu per satu
BATAS_UKURAN = 40 * 1024 * 1024


def pratinjau(data: bytes, derajat: int, halaman: int) -> str:
    """Foto yang sudah ditegakkan (JPEG kecil, base64) supaya bisa dibandingkan dengan hasil."""
    img = putar_gambar(muat(data)[halaman], derajat)
    im = Image.fromarray(img)
    im.thumbnail((1600, 1600))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=80)
    return base64.b64encode(buf.getvalue()).decode()


class Penangan(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # jangan cetak apa pun tentang isi file ke terminal
        pass

    def _kirim(self, kode, isi, jenis='application/json; charset=utf-8'):
        b = isi.encode() if isinstance(isi, str) else isi
        self.send_response(kode)
        self.send_header('Content-Type', jenis)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self._kirim(200, HALAMAN, 'text/html; charset=utf-8')
        else:
            self._kirim(404, '{"galat": "tidak ada"}')

    def do_POST(self):
        if self.path != '/baca':
            return self._kirim(404, '{"galat": "tidak ada"}')
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0 or n > BATAS_UKURAN:
            return self._kirim(400, json.dumps({'galat': 'File kosong atau lebih dari 40 MB.'}))
        data = self.rfile.read(n)
        try:
            t = time.time()
            with KUNCI:
                r = baca_file(data)
                gambar = pratinjau(data, r['derajat'], r['halaman'])
            r['detik'] = round(time.time() - t, 1)
            r['gambar'] = gambar
            self._kirim(200, json.dumps(r, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001 - tampilkan galat di halaman
            self._kirim(500, json.dumps({'galat': str(e) or e.__class__.__name__,
                                         'jejak': traceback.format_exc(limit=4)}, ensure_ascii=False))


HALAMAN = r"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Uji OCR KK</title>
<style>
  :root { --latar:#f6f7f9; --kartu:#fff; --teks:#1d2430; --redup:#667085; --garis:#e4e7ec; --utama:#0f6fde;
          --ragu:#fff3c4; --ragu-garis:#f2c94c; --kosong:#fde7e7; --ok:#e7f6ec; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; background:var(--latar); color:var(--teks); }
  header { padding:20px 24px 8px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .redup { color:var(--redup); font-size:13px; }
  main { padding:8px 24px 40px; }
  #seret { border:2px dashed #b8c2d1; border-radius:12px; background:var(--kartu); padding:28px; text-align:center; cursor:pointer; }
  #seret.aktif { border-color:var(--utama); background:#eef5ff; }
  #seret strong { color:var(--utama); }
  .hasil { background:var(--kartu); border:1px solid var(--garis); border-radius:12px; margin-top:18px; overflow:hidden; }
  .judul { display:flex; gap:12px; align-items:center; justify-content:space-between; padding:12px 16px; border-bottom:1px solid var(--garis); flex-wrap:wrap; }
  .judul b { font-size:15px; }
  .lencana { display:inline-block; font-size:12px; padding:2px 8px; border-radius:999px; background:#eef1f5; color:#344054; margin-left:6px; }
  .lencana.baik { background:var(--ok); color:#18794e; } .lencana.awas { background:var(--ragu); color:#8a6d00; } .lencana.buruk { background:var(--kosong); color:#b42318; }
  .isi { display:grid; grid-template-columns:minmax(260px, 38%) 1fr; gap:0; }
  @media (max-width: 900px) { .isi { grid-template-columns:1fr; } }
  .foto { padding:12px; border-right:1px solid var(--garis); background:#fafbfc; }
  .foto img { width:100%; border-radius:6px; border:1px solid var(--garis); cursor:zoom-in; }
  .data { padding:12px 16px; overflow-x:auto; }
  .kepala { display:grid; grid-template-columns:repeat(auto-fill, minmax(190px, 1fr)); gap:8px 16px; margin-bottom:12px; }
  .kepala div span { display:block; font-size:12px; color:var(--redup); }
  .kepala div.ragu { background:var(--ragu); border-radius:6px; padding:2px 6px; }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  th, td { border:1px solid var(--garis); padding:5px 7px; text-align:left; vertical-align:top; white-space:nowrap; }
  th { background:#f2f4f7; font-weight:600; position:sticky; top:0; }
  td.ragu { background:var(--ragu); outline:1px solid var(--ragu-garis); outline-offset:-1px; }
  td.kosong { background:var(--kosong); color:#b42318; }
  .ket { display:flex; gap:14px; font-size:12px; color:var(--redup); margin:10px 0 0; flex-wrap:wrap; }
  .ket i { display:inline-block; width:12px; height:12px; border-radius:3px; vertical-align:-2px; margin-right:4px; }
  details { margin-top:10px; } summary { cursor:pointer; color:var(--utama); font-size:13px; }
  pre { background:#0f172a; color:#e2e8f0; padding:12px; border-radius:8px; overflow:auto; max-height:420px; font-size:12px; }
  .galat { color:#b42318; padding:16px; white-space:pre-wrap; }
  .tunggu { padding:16px; color:var(--redup); }
  .putar { display:inline-block; width:14px; height:14px; border:2px solid #b8c2d1; border-top-color:var(--utama); border-radius:50%; animation:p 0.8s linear infinite; vertical-align:-2px; margin-right:6px; }
  @keyframes p { to { transform:rotate(360deg); } }
  #besar { position:fixed; inset:0; background:rgba(0,0,0,.85); display:none; align-items:center; justify-content:center; z-index:9; cursor:zoom-out; }
  #besar img { max-width:96vw; max-height:96vh; }
</style>
</head>
<body>
<header>
  <h1>Uji OCR Kartu Keluarga</h1>
  <div class="redup">Lokal saja (127.0.0.1). File tidak disimpan dan tidak dikirim ke mana pun. Satu file butuh ±5–30 detik.</div>
</header>
<main>
  <label id="seret">
    <input id="pilih" type="file" accept="image/*,.pdf" multiple hidden>
    <div><strong>Pilih foto / PDF KK</strong> atau seret ke sini (boleh banyak sekaligus)</div>
  </label>
  <div id="daftar"></div>
</main>
<div id="besar"><img alt=""></div>
<script>
const KOLOM = [
  ['namaLengkap','Nama'], ['nik','NIK'], ['jenisKelamin','JK'], ['tempatLahir','Tempat lahir'], ['tanggalLahir','Tgl lahir'],
  ['agama','Agama'], ['pendidikanTerakhir','Pendidikan'], ['pekerjaan','Pekerjaan'], ['statusPerkawinan','Status kawin'],
  ['tanggalPerkawinan','Tgl kawin'], ['statusHubungan','Hubungan'], ['kewarganegaraan','WN'], ['namaAyah','Ayah'], ['namaIbu','Ibu'],
];
const WAJIB = ['namaLengkap','nik','jenisKelamin','tempatLahir','tanggalLahir','agama','pendidikanTerakhir','pekerjaan',
               'statusPerkawinan','statusHubungan','namaAyah','namaIbu'];
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const tgl = (t) => /^\d{4}-\d{2}-\d{2}$/.test(t || '') ? t.slice(8,10) + '-' + t.slice(5,7) + '-' + t.slice(0,4) : (t || '');

// cek silang NIK (sama seperti web): tanggal lahir & jenis kelamin harus cocok dengan NIK
function dariNik(nik) {
  if (!/^\d{16}$/.test(nik || '')) return null;
  let d = +nik.slice(6,8); const m = +nik.slice(8,10), y = +nik.slice(10,12);
  const p = d > 40; if (p) d -= 40;
  return { d, m, y, jk: p ? 'P' : 'L' };
}
function cekAnggota(a) {
  const n = dariNik(a.nik), masalah = [];
  if (!n) { masalah.push('NIK tidak sah'); return masalah; }
  const t = a.tanggalLahir || '';
  if (t && !(+t.slice(8,10) === n.d && +t.slice(5,7) === n.m && +t.slice(0,4) % 100 === n.y)) masalah.push('tgl lahir ≠ NIK');
  if (a.jenisKelamin && a.jenisKelamin !== n.jk) masalah.push('JK ≠ NIK');
  return masalah;
}

function gambarHasil(kotak, nama, r) {
  if (r.galat) { kotak.innerHTML = `<div class="judul"><b>${esc(nama)}</b></div><div class="galat">${esc(r.galat)}\n${esc(r.jejak || '')}</div>`; return; }
  const h = r.hasil, ang = h.anggota || [];
  let ragu = 0, kosong = 0, masalah = 0;
  const baris = ang.map((a, i) => {
    const m = cekAnggota(a); if (m.length) masalah++;
    const sel = KOLOM.map(([k]) => {
      let v = a[k] || ''; if (k === 'tanggalLahir' || k === 'tanggalPerkawinan') v = tgl(v);
      const r_ = (a._ragu || []).includes(k), ks = !v && WAJIB.includes(k);
      if (r_) ragu++; if (ks) kosong++;
      return `<td class="${r_ ? 'ragu' : ks ? 'kosong' : ''}">${esc(v) || (ks ? '—' : '')}</td>`;
    }).join('');
    return `<tr><td>${i + 1}</td>${sel}<td>${m.map(esc).join('<br>') || '✓'}</td></tr>`;
  }).join('');
  const kepalaRagu = new Set(h._ragu || []);
  const isian = [['No. KK', h.noKK, 'noKK'], ['Kepala keluarga', h.kepalaKeluarga, 'kepalaKeluarga'], ['Alamat', h.alamat, 'alamat'],
                 ['RT / RW', [h.rt, h.rw].filter(Boolean).join(' / ')]];
  const lenc = r.bukanKK ? '<span class="lencana buruk">bukan KK</span>'
    : !ang.length ? '<span class="lencana buruk">tidak ada anggota terbaca</span>'
    : `<span class="lencana ${ragu || kosong || masalah ? 'awas' : 'baik'}">${ang.length} anggota · ${ragu} kolom ragu · ${kosong} kosong · ${masalah} cek NIK</span>`;
  kotak.innerHTML = `
    <div class="judul"><div><b>${esc(nama)}</b>${lenc}</div>
      <div class="redup">${r.detik} dtk · ${esc(r.sumber)}${r.halaman ? ' · halaman ' + (r.halaman + 1) : ''}</div></div>
    <div class="isi">
      <div class="foto"><img src="data:image/jpeg;base64,${r.gambar}" alt="foto KK"></div>
      <div class="data">
        <div class="kepala">${isian.map(([l, v, k]) => `<div class="${k && kepalaRagu.has(k) ? 'ragu' : ''}"><span>${l}</span>${esc(v) || '<span style="color:#b42318">— kosong —</span>'}${k && kepalaRagu.has(k) ? ' ⚠' : ''}</div>`).join('')}</div>
        ${ang.length ? `<table><thead><tr><th>#</th>${KOLOM.map(([, l]) => `<th>${l}</th>`).join('')}<th>Cek NIK</th></tr></thead><tbody>${baris}</tbody></table>` : ''}
        <div class="ket"><span><i style="background:var(--ragu);outline:1px solid var(--ragu-garis)"></i>ragu: cek dengan foto</span>
          <span><i style="background:var(--kosong)"></i>kosong: tidak terbaca</span>
          <span>Cek NIK: tanggal lahir & jenis kelamin dicocokkan dengan NIK</span></div>
        <details><summary>JSON lengkap (yang dikirim ke web)</summary><pre>${esc(JSON.stringify(h, null, 2))}</pre></details>
      </div>
    </div>`;
  kotak.querySelector('.foto img').onclick = (e) => { const b = document.getElementById('besar'); b.querySelector('img').src = e.target.src; b.style.display = 'flex'; };
}

let antre = Promise.resolve();
function tambah(files) {
  for (const f of files) {
    const kotak = document.createElement('section');
    kotak.className = 'hasil';
    kotak.innerHTML = `<div class="judul"><b>${esc(f.name)}</b></div><div class="tunggu"><span class="putar"></span>Menunggu giliran…</div>`;
    document.getElementById('daftar').prepend(kotak);
    antre = antre.then(async () => {
      kotak.querySelector('.tunggu').innerHTML = '<span class="putar"></span>Sedang dibaca…';
      try {
        const res = await fetch('/baca', { method: 'POST', body: f });
        gambarHasil(kotak, f.name, await res.json());
      } catch (e) { gambarHasil(kotak, f.name, { galat: String(e) }); }
    });
  }
}
const seret = document.getElementById('seret');
document.getElementById('pilih').onchange = (e) => { tambah(e.target.files); e.target.value = ''; };
['dragenter','dragover'].forEach((ev) => seret.addEventListener(ev, (e) => { e.preventDefault(); seret.classList.add('aktif'); }));
['dragleave','drop'].forEach((ev) => seret.addEventListener(ev, (e) => { e.preventDefault(); seret.classList.remove('aktif'); }));
seret.addEventListener('drop', (e) => tambah(e.dataTransfer.files));
document.getElementById('besar').onclick = (e) => { e.currentTarget.style.display = 'none'; };
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description='Halaman uji OCR KK (lokal)')
    ap.add_argument('--port', type=int, default=3000)
    a = ap.parse_args()
    from .mesin import mesin
    mesin()  # muat model dulu supaya unggahan pertama tidak lama
    try:
        srv = ThreadingHTTPServer(('127.0.0.1', a.port), Penangan)
    except OSError as e:
        if e.errno == 98:  # port dipakai
            print(f'Port {a.port} sudah dipakai: kemungkinan halaman uji sudah menyala. Buka http://localhost:{a.port}\n'
                  f'atau pakai port lain: uv run python -m ocr_kk.web --port {a.port + 1}')
            raise SystemExit(1)
        raise
    print(f'Uji OCR KK siap: http://localhost:{a.port}  (Ctrl+C untuk berhenti)', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
