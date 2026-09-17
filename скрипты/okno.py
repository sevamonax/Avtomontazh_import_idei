# -*- coding: utf-8 -*-
"""Сверка спорного места: расшифровка непрерывного окна сырья.

Зачем отдельный скрипт. `rech.py` расшифровывает не подряд, а всплесками,
упакованными по три дорожки в 27-секундные окна: так дешевле и так видны
брошенные заходы. Цена — на стыках whisper теряет контекст фразы и иногда
выдаёт призрак («Сейчас» там, где в звуке «чат GPT»), а зацикливание
(«дададада…») накрывает живые слова. Поймать это можно только одним способом:
послушать спорный кусок ПОДРЯД.

Раньше это делалось разовыми скриптами: в `почему_правки` оставалась пометка
«сверено окном 105–114», а самого механизма в конвейере не было. Теперь есть:

    python okno.py --проект "ПРИМЕР" --окно 105-114
    python okno.py --проект "ПРИМЕР" --окно 105-114 --дубль 02

Ничего не пишет в проект: это чтение, а не решение. Решение — руками в
`правки_отбора` с записью причины в `почему_правки`.
"""
import io
import os
import sys
import wave

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import obshee                                            # noqa: E402
import zvuk                                              # noqa: E402


def main():
    pr, a = obshee.argi(
        (("--окно",), {"dest": "okno", "required": True,
                       "help": "границы в секундах сырья, например 105-114"}),
        (("--дубль",), {"dest": "dubl", "default": "01",
                        "help": "какой файл сырья, если их несколько"}),
    )
    try:
        t0, t1 = [float(x) for x in a.okno.replace(",", ".").split("-")]
    except ValueError:
        raise SystemExit("окно задаётся как «105-114», получено: %s" % a.okno)
    if t1 <= t0:
        raise SystemExit("конец окна не позже начала: %s" % a.okno)

    src = dict(pr.dubli()).get(a.dubl)
    if src is None:
        raise SystemExit("нет дубля %s; есть: %s"
                         % (a.dubl, ", ".join(k for k, _ in pr.dubli())))
    wav = pr.wav_path(a.dubl)
    if not os.path.exists(wav):
        zvuk.izvlech_wav(src, wav)
    audio = zvuk.read_wav(wav)
    i0, i1 = int(t0 * zvuk.SR), int(min(t1, len(audio) / float(zvuk.SR)) * zvuk.SR)
    if i1 <= i0:
        raise SystemExit("окно %s лежит за концом дорожки (%.1f с)"
                         % (a.okno, len(audio) / float(zvuk.SR)))

    tmp = os.path.join(pr.wav, "_okno.wav")
    w = wave.open(tmp, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(zvuk.SR)
    w.writeframes(audio[i0:i1].tobytes())
    w.close()

    from faster_whisper import WhisperModel
    ustr = obshee.nastroyka(u"расшифровка.устройство", "cpu")
    model = WhisperModel(obshee.nastroyka(u"расшифровка.модель", "large-v3-turbo"),
                         device=ustr,
                         compute_type="int8" if ustr == "cpu" else "float16",
                         cpu_threads=int(obshee.nastroyka(u"расшифровка.потоков", 8)))
    segs, _ = model.transcribe(tmp,
                               language=obshee.nastroyka(u"расшифровка.язык", "ru"),
                               vad_filter=False,
                               word_timestamps=True,
                               condition_on_previous_text=False,
                               temperature=0.0, beam_size=5)
    print(u"окно %.2f–%.2f, дубль %s\n" % (t0, t1, a.dubl))
    pusto = True
    for s in segs:
        pusto = False
        print(u"`%7.2f–%7.2f` %s" % (t0 + s.start, t0 + s.end, s.text.strip()))
        slova = [u"%s(%.2f)" % (x.word.strip(), t0 + x.start) for x in (s.words or [])]
        if slova:
            print(u"          " + u" ".join(slova))
    if pusto:
        print(u"речи в окне нет")
    os.remove(tmp)


if __name__ == "__main__":
    main()
