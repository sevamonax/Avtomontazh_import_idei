# -*- coding: utf-8 -*-
"""Наложение слоя на сборку → готовый рилз.

    python nalozhit.py --проект "ПРИМЕР"
    python nalozhit.py --проект "ПРИМЕР" --версия 2

Слой рендерит Remotion (`render_reel.mjs`), здесь только композит и упаковка.
Версия выходного файла не перезаписывает предыдущую (`_v2`, `_v3`) — на приёмке
надо сравнивать «было / стало», а не гадать, что лежит в папке.
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import obshee                                            # noqa: E402


def main():
    pr, a = obshee.argi((["--версия"], {"dest": "v", "type": int, "default": 1}),
                        (["--слой"], {"dest": "sloi", "default": None}),
                        (["--оставить-слой"], {"dest": "ostavit", "action": "store_true"}))
    video = os.path.join(pr.out, "%s — сборка.mp4" % pr.name)
    sloi = a.sloi or os.path.join(pr.out, "слой.mov")
    for p in (video, sloi):
        if not os.path.exists(p):
            raise SystemExit("нет файла: %s" % p)

    out = os.path.join(pr.out, "%s — рилз%s.mp4"
                       % (pr.name, "" if a.v == 1 else " v%d" % a.v))
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", video, "-i", sloi,
           "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
           "-map", "[v]", "-map", "0:a",
           ] + obshee.kodirovshchik(22) + [
           "-c:a", "copy", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)

    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", out], capture_output=True, text=True)
    dlit = float(p.stdout.strip())
    print("готово: %s\nдлительность %.2f с" % (out, dlit))

    # 🔑 СЛОЙ УДАЛЯЕТСЯ ЗДЕСЬ, А НЕ РУКАМИ. `README.md` с самого начала обещал:
    # «слой временный, ~6 ГБ, после наложения его удаляет `nalozhit.py`». Кода
    # под этим обещанием не было — удалял человек, когда вспоминал. На ролик файл
    # пролежал 775 МБ до отдельной просьбы, на «ПРИМЕР» тем же
    # порядком копились кэши. Обещание в документе, которого не делает код, —
    # это не правило, а надежда (`ЭКРАН.md`: механизм это не только
    # «находит само», но и «не даёт нарушить»).
    #
    # Удаляем ТОЛЬКО после того, как композит проверен ffprobe и оказался
    # непустым: иначе можно снести восьмиминутный рендер ради битого выхода.
    # Нужен слой ещё на одну версию композита — `--оставить-слой`.
    if a.ostavit:
        print("слой оставлен по просьбе: %s" % sloi)
    elif a.sloi:
        print("слой задан руками — не трогаю: %s" % sloi)
    elif dlit > 0 and os.path.exists(sloi):
        mb = os.path.getsize(sloi) / (1024.0 * 1024.0)
        os.remove(sloi)
        print("слой удалён (%.0f МБ) — пересобирается render_reel.mjs" % mb)


if __name__ == "__main__":
    main()
