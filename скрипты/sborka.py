# -*- coding: utf-8 -*-
"""Сборка рилза: куски из 4K → вертикаль 1080×1920 → склейка → громкость.

    python sborka.py --проект "ПРИМЕР"
    python sborka.py --проект "ПРИМЕР" --плоско     # без крупностей

СЫРЬЁ СНЯТО В HLG HDR (BT.2020, 10 бит). Без тонмапа картинка выцветает — это
уже стоило одной пересборки в горизонтали (`README.md`).

ДВА ПУТИ КАДРИРОВАНИЯ, намеренно разные (перенесено из `render.py` В13):
  · кусок без наезда — `crop` целыми пикселями ДО тонмапа: точно и вдвое быстрее;
  · кусок с наездом  — `zoompan` ПОСЛЕ тонмапа, потому что окно меняется покадрово.

СУПЕР-СЕМПЛИНГ ПЕРЕД ДВИЖЕНИЕМ. `zoompan` считает окно целыми пикселями входа;
при медленном наезде остаток копится и кадр дёргается («картинка дёргается»). Лечится разрешением, в котором считается движение. В
горизонтали брали ×4 от полного кадра. Здесь дешевле: окно вырезается ДО
апскейла, поэтому ×2 от окна даёт ту же четверть пикселя, а не 15360×8640.

ГРОМКОСТЬ — ЗАМЕР. Опубликованный рилз идёт на −23,2 LUFS (`zamer.py`), это
тише площадок: YouTube и Instagram нормализуют примерно к −14. Цель канала
поставлена на −16 LUFS с запасом по пику −1,5 dBTP.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import kadr                                              # noqa: E402
import obshee                                            # noqa: E402
import cenzura                                           # noqa: E402

OUT_W, OUT_H = 1080, 1920
FPS = 30
SS = 2
LUFS = float(obshee.nastroyka(u"звук.громкость_lufs", -16.0))
TP = float(obshee.nastroyka(u"звук.пик_dbtp", -1.5))
FADE = 0.02

# 🎨 ЦВЕТ — ВЫБРАН ГЛАЗОМ ИЗ НЕСКОЛЬКИХ ВАРИАНТОВ. Не трогать числа без
# новой пробы: они не выведены из теории, а выбраны глазом на движущемся куске.
#
# Съёмка идёт в HLG HDR, ролик отдаётся в SDR — между ними эта цепочка. Три
# круга приёмки дали три вывода, и все три против интуиции:
#
#   · `npl` — опорная яркость линеаризации — главный рычаг КОНТРАСТА, а не
#     яркости. 100 давало плоскую пересвеченную картинку, «книжные» 203 —
#     бледную. Лицо ожило только от 400 и выше; принято **550**;
#   · `desat` — гашение насыщенности в светах — главный рычаг ЦВЕТА. Лицо
#     освещено спереди и почти целиком лежит в верхней части диапазона, то есть
#     ровно там, где это гашение работает: кожа обесцвечивалась первой, а стена
#     и стол оставались. про вариант с desat=0.5: «по контрасту норма, а
#     цвета не хватает». Принято **0** — гашения нет совсем;
#   · оставшийся недобор цвета добирается ПОСЛЕ тонмапа: `saturation=1.15`.
#
# ⚠️ Ошибка, которую тут уже сделали дважды: крутить один параметр, объясняя
# результат словами про другой. Первый раз «оранжевое» списали на desat=0, хотя
# виноват был npl; второй раз бледность списали на npl, хотя виноват был desat.
# Цвет проверяется СРАВНЕНИЕМ НЕСКОЛЬКИХ ВАРИАНТОВ НА ОДНОМ КУСКЕ, а не одним
# прогоном и рассуждением. Порядок — `ЭКРАН.md`
TONEMAP = ("zscale=t=linear:npl=550,format=gbrpf32le,zscale=p=bt709,"
           "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,"
           "format=yuv420p,eq=saturation=1.15")


def vfilter(cp, dur):
    if cp is None:                       # --плоско: окно по центру кадра
        cw = kadr.even(kadr.H4K * kadr.AR)
        x = (kadr.W4K - cw) // 2
        return ("crop=%d:%d:%d:0," % (cw, kadr.H4K, x)) + TONEMAP + \
               ",scale=%d:%d" % (OUT_W, OUT_H)

    if not cp["наезд"]:
        cw, ch, x, y = kadr.okno(cp["f0"], cp["eye_x"], cp["eye_y"], cp["py"])
        return ("crop=%d:%d:%d:%d," % (cw, ch, x, y)) + TONEMAP + \
               ",scale=%d:%d" % (OUT_W, OUT_H)

    # ❗Вырезаем САМОЕ ШИРОКОЕ окно куска, а внутри него ходим. `zoompan` умеет
    # только приближать (z ≥ 1); если кроп взять по началу, то кусок с отъездом
    # (f1 > f0) молча остановится. Отсюда база — max(f0, f1), а движение идёт
    # долями от неё в обе стороны. Правка: кадр обязан жить всегда,
    # значит отъезды теперь бывают, и путь для них должен работать.
    baza = max(cp["f0"], cp["f1"])
    cw, ch, x, y = kadr.okno(baza, cp["eye_x"], cp["eye_y"], cp["py"])
    n = max(int(round(dur * FPS)) - 1, 1)
    g0, g1 = cp["f0"] / baza, cp["f1"] / baza      # оба ≤ 1
    ex = (cp["eye_x"] - x) * SS
    ey = (cp["eye_y"] - y) * SS
    g = "(%.6f+(%.6f)*on/%d)" % (g0, g1 - g0, n)
    xs = "max(0,min(iw-iw*%s,%.1f-0.5*iw*%s))" % (g, ex, g)
    ys = "max(0,min(ih-ih*%s,%.1f-%.4f*ih*%s))" % (g, ey, cp["py"], g)
    return ("crop=%d:%d:%d:%d," % (cw, ch, x, y)) + TONEMAP + \
           (",scale=%d:%d:flags=bilinear"
            ",zoompan=z='1/%s':x='%s':y='%s':d=1:s=%dx%d:fps=%d"
            % (cw * SS, ch * SS, g, xs, ys, OUT_W, OUT_H, FPS))


def imya(k, cp):
    # 🔑 ЦЕПОЧКА ЦВЕТА ВХОДИТ В КЛЮЧ. Кэш куска считался по времени и кадру, а
    # тонмап в него не входил — то есть правка цвета не пересобирала НИЧЕГО:
    # старые куски подхватывались как готовые, и ролик оставался того же цвета.
    # Кэш обязан зависеть от всего, что влияет на картинку, иначе это не кэш, а
    # способ не заметить правку.
    key = "%s|%.3f|%.3f|%d|%s" % (k["idx"], k["s"], k["e"], OUT_W, TONEMAP)
    if cp:
        key += "|%.5f|%.5f|%.0f|%.0f|%.4f|ss%d" % (
            cp["f0"], cp["f1"], cp["eye_x"], cp["eye_y"], cp["py"], SS)
    return hashlib.md5(key.encode()).hexdigest()[:12]


def render_one(job):
    i, k, cp, src, seg = job
    dst = os.path.join(seg, imya(k, cp) + ".mp4")
    if os.path.exists(dst) and os.path.getsize(dst) > 10000:
        return i, "кэш", dst
    dur = k["e"] - k["s"]
    af = ("afade=t=in:st=0:d=%.3f,afade=t=out:st=%.3f:d=%.3f,aresample=async=1:first_pts=0"
          % (FADE, max(0.0, dur - FADE), FADE))
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % k["s"], "-i", src,
           "-t", "%.3f" % dur, "-vf", vfilter(cp, dur),
           ] + obshee.kodirovshchik(23) + [
           "-af", af, "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
           "-video_track_timescale", "30000", "-movflags", "+faststart", dst]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        return i, "ОШИБКА: " + (r.stderr or "")[-300:], None
    return i, "ok", dst


def main():
    pr, a = obshee.argi((["--плоско"], {"dest": "flat", "action": "store_true"}))
    edl = pr.load("edl.json")
    crops = None if a.flat else pr.load("crops.json", required=False)
    if crops is None and not a.flat:
        raise SystemExit("нет crops.json — сначала kadr.py (или запусти с --плоско)")
    plan = {p["i"]: p for p in crops["план"]} if crops else {}
    if crops:
        kadr.geometriya_iz(crops)
    if crops and len(plan) != len(edl["куски"]):
        raise SystemExit("план крупностей на %d кусков, лист на %d — пересобери kadr.py"
                         % (len(plan), len(edl["куски"])))

    istochniki = dict(pr.dubli())      # ролик может быть снят в несколько файлов
    seg = os.path.join(pr.dir, "seg")
    if not os.path.isdir(seg):
        os.makedirs(seg)

    jobs = [(i, k, plan.get(i), istochniki[k["idx"]], seg) for i, k in enumerate(edl["куски"])]
    files = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, msg, dst in ex.map(render_one, jobs):
            files[i] = dst
            print("  кусок %2d/%d: %s" % (i + 1, len(jobs), msg), flush=True)
    if any(f is None for f in files):
        raise SystemExit("часть кусков не отрендерилась — смотреть сообщения выше")

    lst = os.path.join(seg, "concat.txt")
    with io.open(lst, "w", encoding="utf-8") as f:
        for p in files:
            f.write("file '%s'\n" % p.replace("\\", "/"))

    out = os.path.join(pr.out, "%s — сборка.mp4" % pr.name)
    zapiki = cenzura.nayti(edl, pr.cfg.get("запикивания") or [])
    # ГРОМКОСТЬ: ЗАМЕРИТЬ → ПОДНЯТЬ → ОГРАНИЧИТЬ ПИК.
    #
    # Однопроходный `loudnorm` работал вслепую и промахивался: первая сборка ролике
    # вышла на −16,7 при цели −16, вторая — на −17,8, и гейт В9 закричал.
    # Замер показал, почему цель недостижима «просто громче»: у дорожки
    # input_tp = −0,45 dBTP, то есть пик почти у нуля, а до цели не хватает
    # полутора децибел. `loudnorm` в такой ситуации молча оставляет тише —
    # поднять уровень, не тронув пики, физически нельзя.
    #
    # Поэтому уровень поднимается ровно на недостачу, а пики держит лимитер на
    # −1,5 dBTP. Полтора децибела лимитирования речь переносит без слышимого
    # призвука; проверка В9 меряет результат и скажет, если это не так.
    izm = subprocess.run(
        ["ffmpeg", "-v", "info", "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-af", "loudnorm=I=%.1f:TP=%.1f:LRA=11:print_format=json" % (LUFS, TP),
         "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    err = izm.stderr or ""
    zamer = {}
    if "{" in err:
        i0 = err.rfind("{")
        i1 = err.find("}", i0)
        if i1 > i0:
            try:
                zamer = json.loads(err[i0:i1 + 1])
            except Exception:
                zamer = {}
    if "input_i" in zamer:
        pribavka = LUFS - float(zamer["input_i"])
        predel = 10.0 ** (TP / 20.0)
        af = ("volume=%.2fdB,alimiter=limit=%.4f:attack=5:release=50:level=disabled"
              % (pribavka, predel))
        print("громкость: замер %s LUFS, пик %s dBTP → прибавка %+.2f дБ, лимитер на %.1f dBTP"
              % (zamer["input_i"], zamer.get("input_tp", "?"), pribavka, TP))
    else:
        af = "loudnorm=I=%.1f:TP=%.1f:LRA=11" % (LUFS, TP)
        print("⚠️ замер громкости не прочитался — иду одним проходом loudnorm")
    if zapiki:
        af = cenzura.audio_filter(zapiki) + "," + af
        print("цензура: %d окно(а), середина слова заменяется тоном" % len(zapiki))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-af", af,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    "-movflags", "+faststart", out], check=True)
    # ГЕЙТ: файл обязан совпасть с листом. Расхождение здесь означает, что все
    # времена субтитров и акцентов поедут — ровно это и случилось в первой
    # сборке (лист 2:21, файл 2:16: пауза на склейке считалась, но не резалась).
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", out], capture_output=True, text=True)
    fakt = float(p.stdout.strip())
    if abs(fakt - edl["всего"]) > 0.25:
        raise SystemExit("❌ файл %.2f с, а лист обещает %.2f с — слой ляжет мимо"
                         % (fakt, edl["всего"]))
    print("\nготово: %s\nдлительность %.2f с — сходится с листом" % (out, fakt))


if __name__ == "__main__":
    main()
