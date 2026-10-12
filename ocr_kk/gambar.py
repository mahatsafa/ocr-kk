"""Memuat file KK (JPG/PNG/PDF) menjadi gambar RGB (numpy) yang siap dibaca OCR."""
import io
import os

import numpy as np
from PIL import Image, ImageOps

# Sisi terpanjang gambar yang dibaca. Lebih besar tidak menambah ketepatan (detektor RapidOCR
# membatasi 2000 px) tetapi memperlambat dan memakan memori pc-a.
SISI_MAKS = int(os.environ.get('OCR_SISI_MAKS', 2400))
# Foto yang terlalu kecil (mis. kiriman WhatsApp) diperbesar dulu supaya tulisan tabel terdeteksi.
SISI_MIN = 2000


def jenis_file(data: bytes) -> str | None:
    if data[:5] == b'%PDF-':
        return 'application/pdf'
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:4] == b'\x89PNG':
        return 'image/png'
    if data[:4] in (b'RIFF',) and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _kecilkan(im: Image.Image) -> Image.Image:
    im = im.convert('RGB')
    w, h = im.size
    s = SISI_MAKS / max(w, h) if max(w, h) > SISI_MAKS else SISI_MIN / max(w, h) if max(w, h) < SISI_MIN else 1
    if s != 1:
        im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    return im


def halaman_pdf(data: bytes, maks: int = 2) -> list[Image.Image]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    hasil = []
    for i in range(min(len(pdf), maks)):
        hal = pdf[i]
        w, h = hal.get_size()
        skala = SISI_MAKS / max(w, h)
        hasil.append(_kecilkan(hal.render(scale=skala).to_pil()))
    return hasil


def muat(data: bytes) -> list[np.ndarray]:
    """Semua halaman yang perlu dicoba (PDF: maks 2 halaman), sudah ditegakkan menurut EXIF."""
    jenis = jenis_file(data)
    if jenis == 'application/pdf':
        return [np.asarray(im) for im in halaman_pdf(data)]
    if jenis is None:
        raise ValueError('BUKAN_GAMBAR')
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    return [np.asarray(_kecilkan(im))]
