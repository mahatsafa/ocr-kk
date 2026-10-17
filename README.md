# ocr-kk

Mesin baca (OCR) Kartu Keluarga untuk **SIP MENTARI**. Menggantikan pembacaan Tesseract di
`sipmentari/lib/ocr/` yang hasilnya sering kosong/salah.

- OCR: [RapidOCR](https://github.com/RapidAI/RapidOCR) (PP-OCRv6 dalam ONNX, cukup CPU, tanpa internet
  setelah model terunduh). Detektor & pengenal `small` (`medium` sedikit lebih tepat tetapi >10 menit/KK di CPU tanpa AVX).
- Tata letak: halaman ditegakkan (0/90/180/270°) dari letak kata judul & kaki KK, kemiringan diluruskan,
  lalu tabel dibaca per baris anggota dengan NIK sebagai jangkar (lihat `ocr_kk/urai.py`).
- Bacaan kedua (kotak deteksi lebih lebar) hanya bila ada tanggal lahir yang tidak cocok NIK atau kolom berkamus
  kosong/ragu: tanggal dipakai hanya bila tepat sama dengan tanggal di NIK; kolom berkamus hanya bila yakin.
- No. KK kosong/tidak sah (16 digit, bagian tanggal DDMMYY sah, bukan NIK anggota): halaman tegak dibaca ulang tanpa
  pengklasifikasi arah baris, karena cls kadang membalik baris No. KK berkotak-kotak. Dipakai hanya bila hasilnya sah.
- Nama yang tercetak beberapa kali di satu KK (kepala di atas & di tabel; ayah/ibu anak = nama orang tuanya)
  disamakan ke bacaan terbaik; nama yang turun ke baris kedua sel disambung; NIK yang menempel ke sel sebelah dipecah.
- Blanko lama ("INDONESIA" sebagai kewarganegaraan), nomor baris salah baca, label salah baca 1-2 huruf,
  foto KK kecil (diperbesar), foto terbalik 180° (dicoba ulang) ditangani.
- Keluaran: JSON `{teks, hasil, derajat, halaman, sumber}`; `hasil` berformat sama dengan
  `parseTeksKK` di web (noKK, kepalaKeluarga, alamat, rt, rw, anggota[...]), ditambah `_ragu` per anggota
  untuk kolom yang keyakinan OCR-nya rendah. **Tidak ada nilai yang dikarang**: tidak terbaca = kosong.
  Pengecualian: tanggal lahir & jenis kelamin juga tercetak di NIK. Tanggal lahir yang kosong atau tidak sepakat
  dengan NIK diisi dari NIK dan **selalu** masuk `_ragu`; tanggal yang sepakat (hari, bulan, 2 digit tahun) tidak
  diubah supaya abad yang tercetak tetap dipakai. Jenis kelamin kosong diisi dari NIK (sama dengan web).
  Kolom wajib yang kosong selalu masuk `_ragu`. Uji 100 KK berkunci (2026-10-17): tanggal lahir 90% -> 100%,
  jenis kelamin 94% -> 100%, kolom lain tidak berubah; pada 18 konflik tanggal vs NIK, tidak sekali pun
  tanggal OCR benar sementara NIK salah.

## Pasang

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh   # sekali saja, tanpa sudo
uv sync
```

## Pakai

```sh
uv run python -m ocr_kk foto-kk.jpg            # satu JSON per file
uv run python -m ocr_kk --layan                 # path per baris dari stdin -> JSON per baris (model dimuat sekali)
```

`--layan` dipakai `pekerja/pekerja-kantor.mjs` di komputer kantor (pc-a).

## Alat uji (data KK tidak pernah masuk repo)

- `alat/ukur.py <folder>`: ukur mutu dari kotak OCR tersimpan tanpa kunci jawaban (NIK valid, tanggal
  lahir & jenis kelamin cocok NIK, kolom terisi). Hanya mencetak angka.
- `alat/banding.py`: bandingkan hasil dengan data yang sudah diverifikasi manusia (kunci jawaban privat).

Simpan data uji di luar repo (mis. `~/data-kk/ocr-kk-uji/`, chmod 700).
