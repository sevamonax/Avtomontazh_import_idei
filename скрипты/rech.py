# -*- coding: utf-8 -*-
"""Расшифровка сырья по всплескам речи + пословный тайминг + брошенные заходы.

    python rech.py --проект "ПРИМЕР"

ПОЧЕМУ НЕ ЦЕЛИКОМ. Whisper вычищает запинки: «Так вот, так вот, так вот» он
выписывает ОДИН раз, растягивая слово на всю длину повтора. По тексту дубля
повторов не видно — первая сборка длинного протащила полтора десятка запинок
(`ЭКРАН.md` §8). Поэтому расшифровывается каждый всплеск отдельно: на
коротком куске модели нечего чистить.

ЦЕНА СБИТА упаковкой: всплески кладутся по 15 штук в одно 27-секундное окно
через шумовые проставки, а СОСЕДИ РАЗВОДЯТСЯ ПО РАЗНЫМ ФАЙЛАМ (всплеск i идёт в
дорожку i % 3) — вычищать повтор модели становится не с чем.

ЧТО ДОБАВЛЕНО ПРОТИВ ДЛИННОГО. Вертикаль требует пословного синхрона субтитров
(`ЭКРАН.md`), поэтому здесь же снимаются времена каждого слова и
пересчитываются обратно в секунды сырья. Отдельного прохода `transcribe_words`,
как в В13, больше нет — это была та же работа второй раз.
"""
import io
import os
import re
import sys
import wave

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import obshee                                            # noqa: E402
import zvuk                                              # noqa: E402

SR = zvuk.SR
PAD = 0.25          # подклад по краям всплеска
SEP = 0.70          # проставка между всплесками в окне
WINDOW = 27.0       # окно упаковки, с (у whisper их 30)
LANES = 3           # на сколько дорожек разводим соседей
LOOK = 3            # на сколько всплесков вперёд смотрим в поиске повтора
MAX_GAP = 22.0      # дальше — уже не «переспросил», а другая мысль
MIN_WORDS = 2       # заход короче двух слов автоматом не судим


def norm(t):
    t = t.lower().replace("ё", "е")
    return [x for x in re.sub(r"[^а-яa-z0-9 ]+", " ", t).split() if x]


def pack(audio, runs, lane, pads):
    """Раскладывает всплески одной дорожки по окнам. Возвращает окна и карту мест."""
    windows, cur, cur_map, t = [], [], [], 0.0
    for bi, (a, b) in enumerate(runs):
        if bi % LANES != lane:
            continue
        pb, pa = pads[bi]
        src0 = max(0.0, a - pb)
        i0, i1 = int(src0 * SR), int(min(len(audio) / SR, b + pa) * SR)
        dur = (i1 - i0) / SR
        if t + dur + SEP > WINDOW and cur:
            windows.append((np.concatenate(cur), cur_map))
            cur, cur_map, t = [], [], 0.0
        # проставка — не цифровой ноль: на нём whisper дорисовывает титры
        cur.append((np.random.randn(int(SEP * SR)) * 3).astype(np.int16))
        t += SEP
        cur.append(audio[i0:i1])
        cur_map.append({"bi": bi, "a": a, "b": b, "t0": t, "t1": t + dur, "src0": src0})
        t += dur
    if cur:
        windows.append((np.concatenate(cur), cur_map))
    return windows


def rasshifrovat(pr, model):
    data = {}
    for idx, src in pr.dubli():
        wav = pr.wav_path(idx)
        if not os.path.exists(wav):
            zvuk.izvlech_wav(src, wav)
        audio = zvuk.read_wav(wav)
        runs = zvuk.speech_runs(wav)
        # Гейт падает громко (правило 30.07): всплески не могут пересекаться и в
        # сумме превышать дорожку. Первая версия `zvuk.py` растягивала их края и
        # давала 110 % речи — соседи делили звук, детектор выдумывал бы повторы.
        dlina = len(audio) / float(SR)
        summa = sum(b - a for a, b in runs)
        naezd = [i for i in range(len(runs) - 1) if runs[i + 1][0] < runs[i][1]]
        if summa > dlina or naezd:
            raise SystemExit("всплески дубля %s негодны: речи %.1f с при дорожке %.1f с, "
                             "наездов %d" % (idx, summa, dlina, len(naezd)))
        # ❗Подклад не может быть больше половины паузы до соседа: иначе соседние
        # всплески делят один звук и детектор ВЫДУМЫВАЕТ повтор (30.07: три
        # срабатывания из шести оказались ложными).
        pads = {}
        for i, (a, b) in enumerate(runs):
            gb = a - runs[i - 1][1] if i > 0 else 10.0
            ga = runs[i + 1][0] - b if i + 1 < len(runs) else 10.0
            pads[i] = (max(0.05, min(PAD, gb / 2 - 0.02)),
                       max(0.05, min(PAD, ga / 2 - 0.02)))

        out, nwin = {}, 0
        tmp = os.path.join(pr.wav, "_pack.wav")
        for lane in range(LANES):
            for win, wmap in pack(audio, runs, lane, pads):
                w = wave.open(tmp, "wb")
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes(win.tobytes())
                w.close()
                segs, _ = model.transcribe(tmp,
                               language=obshee.nastroyka(u"расшифровка.язык", "ru"),
                               vad_filter=False,
                                           word_timestamps=True,
                                           condition_on_previous_text=False,
                                           temperature=0.0, beam_size=5)
                words = [(x.start, x.end, x.word.strip())
                         for s in segs for x in (s.words or [])]
                for it in wmap:
                    mine = [(s2, e2, w2) for s2, e2, w2 in words
                            if e2 > it["t0"] + 0.05 and s2 < it["t1"] - 0.05]
                    # время слова из окна обратно в секунды сырья
                    sl = [{"w": w2,
                           "s": round(min(max(it["src0"] + (s2 - it["t0"]), it["a"] - 0.3), it["b"]), 3),
                           "e": round(min(max(it["src0"] + (e2 - it["t0"]), it["a"]), it["b"] + 0.3), 3)}
                          for s2, e2, w2 in mine]
                    txt = " ".join(w2 for _, _, w2 in mine)
                    out[it["bi"]] = {"i": it["bi"], "a": it["a"], "b": it["b"],
                                     "text": txt, "norm": norm(txt), "слова": sl}
                nwin += 1
                print("   дубль %s: окно %d, всплесков %d" % (idx, nwin, len(wmap)), flush=True)
        data[idx] = [out[k] for k in sorted(out)]
        print("дубль %s готов: %d всплесков, %d окон" % (idx, len(data[idx]), nwin), flush=True)
    return data


def broshennye(data):
    """Правило `ЭКРАН.md` §8: если текст всплеска — начало текста соседнего, это заход."""
    total = 0
    for idx, bs in data.items():
        for k, cur in enumerate(bs):
            cur["брошен"] = False
            if len(cur["norm"]) < MIN_WORDS:
                continue
            for m in range(1, LOOK + 1):
                if k + m >= len(bs):
                    break
                nxt = bs[k + m]
                if nxt["a"] - cur["b"] > MAX_GAP:
                    break
                if len(nxt["norm"]) < len(cur["norm"]):
                    continue
                if nxt["norm"][:len(cur["norm"])] == cur["norm"]:
                    cur["брошен"] = True
                    cur["повтор_в"] = nxt["a"]
                    total += 1
                    break
    return total


def main():
    pr, _ = obshee.argi()
    cache = "rech.json"
    data = pr.load(cache, required=False)
    if data is None:
        from faster_whisper import WhisperModel
        # Модель, устройство и точность — из настроек: это про машину, а не про
        # механизм. На CPU держим int8 (иначе расшифровка часа сырья уходит за
        # ночь), на видеокарте — float16. Первый запуск скачивает веса модели,
        # дальше они берутся из кэша huggingface.
        ustr = obshee.nastroyka(u"расшифровка.устройство", "cpu")
        model = WhisperModel(
            obshee.nastroyka(u"расшифровка.модель", "large-v3-turbo"),
            device=ustr,
            compute_type="int8" if ustr == "cpu" else "float16",
            cpu_threads=int(obshee.nastroyka(u"расшифровка.потоков", 8)))
        data = rasshifrovat(pr, model)
    n = broshennye(data)
    pr.save(cache, data)

    lines = ["# РЕЧЬ СЫРЬЯ — «%s»\n" % pr.name,
             "> Всплески речи, а не дубли целиком: только так видны брошенные заходы",
             "> (`ЭКРАН.md` §8). Пометка ⟲ — заход, повторённый дальше.\n"]
    for idx, bs in sorted(data.items()):
        secs = sum(b["b"] - b["a"] for b in bs)
        lines.append("\n## Дубль %s — %d всплесков, речи %.0f с\n" % (idx, len(bs), secs))
        prev = None
        for b in bs:
            gap = "" if prev is None else "  (пауза %.2f)" % (b["a"] - prev)
            mark = "⟲" if b.get("брошен") else " "
            lines.append("%s `%7.2f–%7.2f` %s%s" % (mark, b["a"], b["b"], b["text"], gap))
            prev = b["b"]
    pr.text("РЕЧЬ.md", "\n".join(lines) + "\n")

    print("\nвсплесков всего: %d" % sum(len(v) for v in data.values()))
    print("брошенных заходов: %d" % n)
    print("речь: %s" % pr.path("РЕЧЬ.md"))


if __name__ == "__main__":
    main()
