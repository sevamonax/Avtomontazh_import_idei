# -*- coding: utf-8 -*-
"""Где в кадре лицо и линия глаз. Перенесено из `eyeline.py` конвейера длинного.

Два места здесь стоили работы и переписаны быть не могут:
  · **доля телесного тона** отделяет лицо от находки в окне за спиной. Город в
    жалюзи по геометрии выглядит как лицо, по цвету — нет. 30.07 детектор нашёл
    «лицо» в окне и дал одну и ту же ложь на трёх кадрах из трёх: у неподвижной
    ошибки сходимость лучше, чем у правды — живое лицо дрожит;
  · **каскад глаз роняет весь замер** на некоторых мелких находках. Не нашли
    глаз — берём запасную оценку (42 % высоты бокса), а не теряем час работы.
"""
import os
import subprocess
import tempfile

import cv2
import numpy as np

# Геометрия сырья НЕ назначается, а читается: серия «Серия» снята
# вертикально (2160x3840 после поворота -90), а «ПРИМЕР» — горизонтально
# (3840x2160). Прибитые сюда 3840x2160 давали `scale=1280:720` на портретном
# кадре: лицо сплющивалось вдвое, и каскад не находил его НИ НА ОДНОМ куске.
# Ошибка молчаливая — детектор просто отвечал «лица нет».
W4K, H4K = 3840, 2160
DW, DH = 1280, 720            # детектим на уменьшенном кадре, координаты домножаем
K = W4K / float(DW)           # 3.0
DETEKT = 1280                 # длинная сторона детект-кадра


def razmer(src):
    """Размер кадра ПОСЛЕ поворота — то, что реально выйдет из декодера."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-show_entries", "stream_side_data=rotation",
         "-of", "default=noprint_wrappers=1:nokey=0", src],
        capture_output=True, text=True).stdout
    d = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d.setdefault(k.strip(), v.strip())
    w, h = int(d["width"]), int(d["height"])
    rot = abs(int(float(d.get("rotation", 0)))) % 180
    return (h, w) if rot == 90 else (w, h)


def nastroit(src):
    """Настроить замер под конкретное сырьё. Зовётся до первого `zamer`."""
    global W4K, H4K, DW, DH, K
    W4K, H4K = razmer(src)
    if W4K >= H4K:
        DW, DH = DETEKT, int(round(DETEKT * H4K / float(W4K) / 2)) * 2
    else:
        DH, DW = DETEKT, int(round(DETEKT * W4K / float(H4K) / 2)) * 2
    K = W4K / float(DW)
    return W4K, H4K

SKIN_MIN = 0.35               # доля телесного тона в боксе: ниже — не лицо

FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
EYE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")


def grab(src, t, dst):
    """Кадр из сырья в момент t. Тонмап не нужен — детектору важна геометрия."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", src,
           "-frames:v", "1", "-vf", "scale=%d:%d" % (DW, DH), dst]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def skin_share(img, x, y, w, h):
    box = img[max(y, 0):y + h, max(x, 0):x + w]
    if box.size == 0:
        return 0.0
    ycrcb = cv2.cvtColor(box, cv2.COLOR_BGR2YCrCb)
    m = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
    return float(m.mean()) / 255.0


def candidates(path):
    """Все лица кадра, каждое со своей линией глаз. Координаты — 4K."""
    img = cv2.imread(path)
    if img is None:
        return []
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    out = []
    for x, y, w, h in FACE.detectMultiScale(gray, 1.1, 5, minSize=(80, 80)):
        roi = gray[y:y + h // 2, x:x + w]        # глаза только в верхней половине
        eyes = []
        if roi.shape[0] > w // 8 + 2 and roi.shape[1] > w // 8 + 2:
            try:
                eyes = EYE.detectMultiScale(roi, 1.1, 6, minSize=(w // 8, w // 8))
            except cv2.error:
                eyes = []
        if len(eyes) >= 2:
            eyes = sorted(eyes, key=lambda e: -e[2] * e[3])[:2]
            ey = y + float(np.mean([e[1] + e[3] / 2.0 for e in eyes]))
            ex = x + float(np.mean([e[0] + e[2] / 2.0 for e in eyes]))
        else:
            ey, ex = y + 0.42 * h, x + w / 2.0
        out.append({"cx": (x + w / 2.0) * K, "cy": (y + h / 2.0) * K,
                    "w": w * K, "h": h * K,
                    "eye_y": ey * K, "eye_x": ex * K,
                    "eyes": int(min(len(eyes), 2)),
                    "skin": round(skin_share(img, x, y, w, h), 3)})
    return out


def zamer(src, times):
    """Замер по нескольким моментам одного куска → медиана по надёжным находкам."""
    found = []
    with tempfile.TemporaryDirectory() as td:
        for j, t in enumerate(times):
            p = os.path.join(td, "f%d.png" % j)
            if not grab(src, t, p):
                continue
            good = [c for c in candidates(p) if c["skin"] >= SKIN_MIN]
            if good:
                found.append(max(good, key=lambda c: c["h"]))     # самое крупное лицо
    if not found:
        return None
    return {k: float(np.median([f[k] for f in found]))
            for k in ("cx", "cy", "w", "h", "eye_y", "eye_x")} | {"кадров": len(found)}
