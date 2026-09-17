# -*- coding: utf-8 -*-
"""Замер принятого шортса: ритм пауз и громкость. Шаг 4 плана 04.08.

    python zamer.py "путь\\к\\ролику.mp4"

ЗАЧЕМ. Проверка К5 (ритм пауз) в `preflight.py` считает профиль, снятый с
ДЛИННЫХ роликов. `README.md` велит прямо: для шортса профиль надо
замерить отдельно по принятым роликам, до тех пор К5 работает как замечание, а
не как блокировка. Стандарта громкости у канала нет вообще — тоже отсюда.

⚠️ Замеряется РИТМ, а не монтаж. Ролик, снятый с полки, — источник чисел о
паузах и уровне, а не образец для копирования.
"""
import json
import subprocess
import sys
import os
import tempfile

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import zvuk                                              # noqa: E402


def lufs(path):
    """Интегральная громкость по EBU R128 — то, во что упирается площадка."""
    p = subprocess.run(["ffmpeg", "-v", "info", "-i", path, "-af",
                        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    txt = p.stderr
    i = txt.rfind("{")
    if i < 0:
        return None
    try:
        return json.loads(txt[i:txt.rfind("}") + 1])
    except ValueError:
        return None


def main():
    src = sys.argv[1]
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        zvuk.izvlech_wav(src, wav)
        runs = zvuk.speech_runs(wav)
        dur = len(zvuk.envelope(wav)) * zvuk.FRAME

    gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
    rechi = sum(b - a for a, b in runs)
    g = np.array(gaps) if gaps else np.array([0.0])

    print("файл: %s" % os.path.basename(src))
    print("длительность: %.1f с · речи %.1f с (%.0f %%) · всплесков %d"
          % (dur, rechi, 100 * rechi / dur, len(runs)))
    print("\nПАУЗЫ между всплесками (ритм, профиль К5 для вертикали):")
    print("  всего %d · медиана %.2f с · среднее %.2f с" % (len(g), np.median(g), g.mean()))
    for q in (10, 25, 50, 75, 90, 100):
        print("  %3d %%: %.2f с" % (q, np.percentile(g, q)))
    print("  длиннее 0.50 с: %d · длиннее 1.00 с: %d"
          % (int((g > 0.5).sum()), int((g > 1.0).sum())))
    print("\nДЛИНА КУСКОВ речи:")
    d = np.array([b - a for a, b in runs])
    print("  медиана %.2f с · среднее %.2f с · максимум %.2f с"
          % (np.median(d), d.mean(), d.max()))

    L = lufs(src)
    if L:
        print("\nГРОМКОСТЬ (EBU R128):")
        print("  интегральная %s LUFS · пик %s dBTP · диапазон %s LU"
              % (L.get("input_i"), L.get("input_tp"), L.get("input_lra")))


if __name__ == "__main__":
    main()
