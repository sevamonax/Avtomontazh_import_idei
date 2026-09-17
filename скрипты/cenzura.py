# -*- coding: utf-8 -*-
"""Единый механизм цензуры: один якорь управляет звуком, субтитром и гейтом.

В ``proekt.json``:

    "запикивания": [{
      "на": "пиздит",
      "субтитр": "п***ит?",
      "середина": [0.22, 0.78],
      "частота": 1000,
      "уровень": 0.36
    }]

``на`` ищется в словах МОНТАЖНОГО ЛИСТА, а не по ручной секунде сырья. Если
фраза не найдена или нашлась дважды, сборка падает: молча запикать не то место
хуже, чем не собрать ролик. Доля ``середина`` оставляет начало и конец слова
слышимыми — решение для одного из роликов.
"""
from __future__ import division

import array
import math
import re
import subprocess


def golyy(s):
    return re.sub(r"[^0-9a-zа-яё%]+", "", (s or "").lower().replace("ё", "е"))


def slova_edl(edl):
    """Слова листа в часах готовой сборки, с координатами сырья."""
    out = []
    for k in edl["куски"]:
        for w in k.get("слова") or []:
            s = k["t"] + max(0.0, w["s"] - k["s"])
            e = k["t"] + min(k["e"] - k["s"], w["e"] - k["s"])
            if e <= s:
                e = s + 0.08
            if s > k["t"] + k["длит"] + 0.01:
                continue
            out.append({"w": w["w"], "s": round(s, 3), "e": round(e, 3),
                        "idx": k["idx"], "raw_s": w["s"], "raw_e": w["e"]})
    out.sort(key=lambda w: (w["s"], w["e"]))
    return out


def nayti(edl, cfg):
    """Конфиг → точные окна тона на таймлайне. Любая неоднозначность — ошибка."""
    words = slova_edl(edl)
    out = []
    for n, item in enumerate(cfg or [], 1):
        anchor = golyy(item.get("на"))
        if not anchor:
            raise SystemExit("запикивания[%d]: пустой якорь «на»" % n)
        matches = []
        for i, w in enumerate(words):
            acc = ""
            for j in range(i, min(len(words), i + len((item.get("на") or "").split()) + 6)):
                acc += golyy(words[j]["w"])
                if acc == anchor:
                    matches.append((i, j))
                    break
                if len(acc) > len(anchor):
                    break
        if len(matches) != 1:
            raise SystemExit("запикивания[%d]: якорь «%s» найден %d раз; нужен ровно один"
                             % (n, item.get("на"), len(matches)))
        i, j = matches[0]
        # По умолчанию однословный якорь и есть слово. Для фразы можно назвать
        # конкретное слово полем ``слово`` — и снова требуем однозначность.
        target = golyy(item.get("слово") or item.get("на"))
        candidates = [w for w in words[i:j + 1] if golyy(w["w"]) == target]
        if len(candidates) != 1:
            raise SystemExit("запикивания[%d]: слово «%s» внутри якоря найдено %d раз"
                             % (n, item.get("слово") or item.get("на"), len(candidates)))
        w = candidates[0]
        part = item.get("середина") or [0.22, 0.78]
        if (not isinstance(part, list) or len(part) != 2 or
                not (0.0 <= float(part[0]) < float(part[1]) <= 1.0)):
            raise SystemExit("запикивания[%d]: «середина» должна быть долями [0..1, 0..1]" % n)
        dur = max(0.08, w["e"] - w["s"])
        s = w["s"] + dur * float(part[0])
        e = w["s"] + dur * float(part[1])
        out.append({"номер": n, "на": item.get("на"), "слово": w["w"],
                    "субтитр": item.get("субтитр") or "***",
                    "s": round(s, 3), "e": round(e, 3),
                    "частота": int(item.get("частота") or 1000),
                    "уровень": float(item.get("уровень") or 0.36)})
    return out


def primenit_k_subtitram(words, windows):
    """Заменяет ровно то слово субтитра, середина которого закрыта тоном."""
    for x in windows:
        center = (x["s"] + x["e"]) / 2.0
        hits = [w for w in words if w["s"] - 0.02 <= center <= w["e"] + 0.02]
        if len(hits) != 1:
            raise SystemExit("запикивания[%d]: на %.3f найдено %d слов субтитра, нужен один"
                             % (x["номер"], center, len(hits)))
        hits[0]["w"] = x["субтитр"]
    return words


def audio_filter(windows):
    """ffmpeg aeval: в окне не примешивает, а ЗАМЕНЯЕТ речь чистым тоном."""
    expr = "val(0)"
    for x in reversed(windows):
        # Запятые экранируются для парсера фильтров ffmpeg; subprocess передаёт
        # строку напрямую, оболочка тут не участвует.
        tone = "%.4f*sin(2*PI*%d*(t-%.6f))" % (x["уровень"], x["частота"], x["s"])
        expr = "if(between(t\\,%.6f\\,%.6f)\\,%s\\,%s)" % (x["s"], x["e"], tone, expr)
    return "aeval=exprs='%s':c=same" % expr


def zamery_tona(path, windows):
    """Меряет ГОТОВЫЙ AAC: доля энергии, объясняемая заявленной синусоидой."""
    out = []
    for x in windows:
        dur = max(0.08, x["e"] - x["s"])
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", "%.3f" % x["s"], "-i", path,
             "-t", "%.3f" % dur, "-vn", "-ac", "1", "-ar", "48000",
             "-f", "f32le", "-"], capture_output=True)
        if p.returncode != 0 or len(p.stdout) < 4000:
            out.append(dict(x, доля_тона=0.0, rms=0.0))
            continue
        vals = array.array("f")
        vals.frombytes(p.stdout)
        # Края AAC/фильтра не должны решать судьбу проверки.
        pad = min(int(0.012 * 48000), max(0, len(vals) // 10))
        samples = vals[pad:len(vals) - pad] if len(vals) > 2 * pad else vals
        n = len(samples)
        if not n:
            out.append(dict(x, доля_тона=0.0, rms=0.0))
            continue
        omega = 2.0 * math.pi * x["частота"] / 48000.0
        re_part = sum(v * math.cos(omega * i) for i, v in enumerate(samples))
        im_part = sum(v * math.sin(omega * i) for i, v in enumerate(samples))
        amplitude = 2.0 * math.hypot(re_part, im_part) / n
        rms = math.sqrt(sum(v * v for v in samples) / n)
        tone_rms = amplitude / math.sqrt(2.0)
        out.append(dict(x, доля_тона=round(min(1.0, tone_rms / max(rms, 1e-9)), 3),
                        rms=round(rms, 4)))
    return out
