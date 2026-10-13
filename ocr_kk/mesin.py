"""Pembungkus RapidOCR (PP-OCR dalam ONNX, cukup CPU). Model dimuat sekali per proses."""
import json
import os

import numpy as np

# Pengaturan model, bisa ditimpa lewat env OCR_PARAMS (JSON) untuk uji banding.
PARAMS = {'Global.log_level': 'error', 'Rec.model_type': 'small'}

_mesin = None


def mesin():
    global _mesin
    if _mesin is None:
        from rapidocr import RapidOCR

        from rapidocr.utils.typings import ModelType, OCRVersion, LangRec

        p = {**PARAMS, **json.loads(os.environ.get('OCR_PARAMS', '{}'))}
        ubah = {'Rec.model_type': ModelType, 'Det.model_type': ModelType, 'Rec.ocr_version': OCRVersion,
                'Det.ocr_version': OCRVersion, 'Rec.lang_type': LangRec}
        p = {k: (ubah[k](v) if k in ubah else v) for k, v in p.items()}
        _mesin = RapidOCR(params=p)
    return _mesin


UNCLIP = 1.6  # lebar kotak deteksi bawaan RapidOCR
UNCLIP_LEBAR = 2.0  # kotak lebih lebar: angka tanggal di tepi kotak tidak terpotong, tetapi kolom nama bisa tergabung


def baca_kotak(img: np.ndarray, lebar: bool = False) -> list[dict]:
    """Daftar kotak teks: {'p': [[x,y]*4], 't': teks, 's': skor}."""
    unclip = UNCLIP_LEBAR if lebar else float(json.loads(os.environ.get('OCR_PARAMS', '{}')).get('Det.unclip_ratio', UNCLIP))
    r = mesin()(img, unclip_ratio=unclip)
    if r.boxes is None:
        return []
    return [
        {'p': [[float(x), float(y)] for x, y in b], 't': str(t), 's': float(s)}
        for b, t, s in zip(r.boxes, r.txts, r.scores)
    ]
