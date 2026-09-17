# -*- coding: utf-8 -*-
"""Лист контрольных кадров к приёмке: по кадру на кусок + все акценты.

    python kadry.py --проект "ПРИМЕР"

ЗАЧЕМ. Приёмка идёт пачкой по 5–10 клипов, и листать каждый —
то самое «уходит столько же времени, только не на монтаж, а на проверку»
(`ЭКРАН.md` §9). Лист даёт увидеть кадрирование, крупности и все акценты одним взглядом;
в ролик он лезет уже прицельно — к тому месту, что не понравилось на листе.

Кадры берутся из ГОТОВОГО рилза, а не из плана: сверяется то, что вышло.
"""
import os
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import obshee                                            # noqa: E402

STOLBCOV = 6
SHIRINA = 320        # ширина миниатюры


def mmss(t):
    return "%d:%05.2f" % (int(t // 60), t % 60)


def main():
    pr, a = obshee.argi((["--файл"], {"dest": "fajl", "default": None}))
    edl = pr.load("edl.json")
    titry = pr.load("titry.json", required=False) or {"элементы": []}
    video = a.fajl or os.path.join(pr.out, "%s — рилз.mp4" % pr.name)
    if not os.path.exists(video):
        # ❗Молчаливая подмена — тот же дефект, что и молчащая проверка. Когда
        # рендер слоя падал, лист собирался из голой сборки и выглядел как
        # «всё на месте, только пусто». Подмена разрешена, но объявлена вслух.
        zapas = os.path.join(pr.out, "%s — сборка.mp4" % pr.name)
        if not os.path.exists(zapas):
            raise SystemExit("нет ни %s, ни сборки — сначала sborka.py и nalozhit.py" % video)
        print("⚠ нет %s — лист собираю из СБОРКИ БЕЗ СЛОЯ" % os.path.basename(video))
        video = zapas

    # середина каждого куска + середина каждого акцента
    tochki = [(k["t"] + k["длит"] / 2.0, "кусок %d" % (i + 1))
              for i, k in enumerate(edl["куски"])]
    tochki += [((e["t"] + e["конец"]) / 2.0, e["приём"]) for e in titry["элементы"]]
    tochki.sort()

    with tempfile.TemporaryDirectory() as td:
        files = []
        for n, (t, _) in enumerate(tochki):
            p = os.path.join(td, "k%03d.png" % n)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", video,
                            "-frames:v", "1", "-vf", "scale=%d:-2" % SHIRINA, p], check=True)
            files.append(p)
        spisok = os.path.join(td, "list.txt")
        with open(spisok, "w", encoding="utf-8") as f:
            for p in files:
                f.write("file '%s'\n" % p.replace("\\", "/"))
        out = os.path.join(pr.out, "%s — лист кадров.png" % pr.name)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", spisok, "-vf", "tile=%dx%d:padding=8:margin=8:color=black"
                        % (STOLBCOV, (len(files) + STOLBCOV - 1) // STOLBCOV),
                        "-frames:v", "1", out], check=True)

    lines = ["# ЛИСТ КАДРОВ — «%s»\n" % pr.name,
             "Картинка: `выход\\%s — лист кадров.png` (%d кадров, %d в ряд).\n"
             % (pr.name, len(tochki), STOLBCOV),
             "Порядок чтения — слева направо, сверху вниз.\n",
             "| № | Время | Что это |", "|---|---|---|"]
    for n, (t, chto) in enumerate(tochki, 1):
        lines.append("| %d | %s | %s |" % (n, mmss(t), chto))
    pr.text("ЛИСТ_КАДРОВ.md", "\n".join(lines) + "\n")
    print("кадров %d → %s" % (len(tochki), out))


if __name__ == "__main__":
    main()
