# -*- coding: utf-8 -*-
"""Отбор самодостаточных кусков под рилз — главная дыра плана 04.08, теперь код.

    python otbor.py --проект "ПРИМЕР"
    python otbor.py --проект "ПРИМЕР" --мин 25 --макс 95

ЧТО ЗДЕСЬ РЕШАЕТСЯ. Правила отбора были записаны словами в `README.md` и `ОТБОР.md`, но выполнялись глазами. Здесь они стали
счётом: кусок оценивается по первой фразе (что держит зрителя), по концовке
(мысль закончена) и по самодостаточности (нет отсылок назад).

ОПОРА — ЦИФРЫ КАНАЛА, а не вкус. `ОТБОР.md`:
  · держат (VTR 70–89 %): конкретика + ставка + интрига результата —
    «кто заработал на ЧМ», «при чём тут бабушка», «дети разучились писать»;
  · пролистывают (VTR 23–43 %): декларации и абстрактные дихотомии —
    «работать умнее, а не больше», «прогресс или деградация?», «учёные спорят».

ВЫХОД — ТАБЛИЦА, А НЕ ВИДЕО. Остановка №1 по регламенту `ЭКРАН.md`:
правка в таблице стоит минуту, та же правка после рендера — час.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import obshee                                            # noqa: E402

MIN_SEC, MAX_SEC = 25.0, 95.0     # ОТБОР.md: блок-история 45–90 с; края с запасом
CEL_SEC = 60.0                    # к чему тянемся
PAUZA_FRAZY = 0.45                # пауза, по которой рвём на фразы, если нет точки

# --- ЧТО ДЕРЖИТ (плюсы первой фразе) ---------------------------------------
DENGI = r"рубл|доллар|тысяч|миллион|миллиард|процент|зарплат|деньг|стоит|платит|заработ|бюджет|цена|прибыл"
KONFLIKT = (r"но |зато|оказал|проблем|ошибк|провал|не работа|никто|зря|вместо|"
            r"спор|против|обман|сломал|потерял|рискн|страшно|боится|уволил")
STAVKA = r"работ|бизнес|клиент|команд|карьер|уволь|наняд|конкурент|рынок|будущ"
LICHNOE = r"\bя\b|\bмне\b|\bменя\b|\bу меня\b|\bмой\b|\bмоя\b|\bмоё\b"

# --- ЧТО ПРОЛИСТЫВАЮТ (минусы первой фразе) --------------------------------
# Отсылка назад: вырезанный кусок обязан стоять сам по себе (`README.md` шаг 1).
OTSYLKA = (r"^(и|а|но|вот|то есть|значит|поэтому|потому что|так вот|в общем|"
           r"короче|кстати|ну|да|итак|тем не менее|при этом|соответственно)\b|"
           r"как я (уже )?(говорил|сказал|рассказ)|в прошл(ом|ый)|"
           r"об этом|про это|эт(от|а|о|и) (сам|же)|как мы|выше|ранее|"
           r"возвраща(ясь|юсь)|продолж(ая|им)")
DEKLARACIYA = (r"прогресс|мир меняется|важно понимать|нужно думать|надо развива|"
               r"всё меняется|каждый (кризис|день)|главное не|учёные спорят|"
               r"работать умнее|думай сам")

MESTOIMENIE = r"^(он|она|оно|они|это|этот|эта|эти|там|тут|туда|такой|такое)\b"


def frazy(rech):
    """Речь → фразы. Границы по знаку препинания или паузе, порядок съёмки."""
    out = []
    for idx in sorted(rech):
        for b in rech[idx]:
            cur = []
            for i, w in enumerate(b["слова"]):
                cur.append(w)
                nxt = b["слова"][i + 1] if i + 1 < len(b["слова"]) else None
                konec = re.search(r"[.!?…]$", w["w"]) is not None
                pauza = (nxt["s"] - w["e"]) > PAUZA_FRAZY if nxt else True
                if konec or pauza or nxt is None:
                    out.append({"idx": idx, "s": cur[0]["s"], "e": cur[-1]["e"],
                                "text": " ".join(x["w"] for x in cur),
                                "слова": cur, "точка": konec})
                    cur = []
            # хвост всплеска, если знак так и не встретился
            if cur:
                out.append({"idx": idx, "s": cur[0]["s"], "e": cur[-1]["e"],
                            "text": " ".join(x["w"] for x in cur),
                            "слова": cur, "точка": False})
    return out


def hits(pattern, text):
    return len(re.findall(pattern, text, re.I))


def ocenka_hooka(text):
    """Сила первой фразы. Возвращает (баллы, из чего они сложились)."""
    t = text.strip().lower()
    b, why = 0.0, []
    if re.search(r"\d", t):
        b += 3.0
        why.append("цифра")
    if hits(DENGI, t):
        b += 2.0
        why.append("деньги")
    if hits(KONFLIKT, t):
        b += 2.0
        why.append("конфликт")
    if hits(STAVKA, t):
        b += 1.0
        why.append("ставка")
    if hits(LICHNOE, t):
        b += 1.0
        why.append("личное")
    if re.search(OTSYLKA, t):
        b -= 4.0
        why.append("−отсылка назад")
    if re.search(MESTOIMENIE, t):
        b -= 2.0
        why.append("−местоимение без хозяина")
    if hits(DEKLARACIYA, t):
        b -= 3.0
        why.append("−декларация")
    if len(t.split()) < 3:
        b -= 2.0
        why.append("−слишком коротко")
    return b, why


def ocenka_kuska(fr, i, j):
    """Кусок фраз [i, j). Хук + концовка + самодостаточность + длительность."""
    blok = fr[i:j]
    dur = blok[-1]["e"] - blok[0]["s"]
    b, why = ocenka_hooka(blok[0]["text"])

    if blok[-1]["точка"]:
        b += 1.5
        why.append("мысль закрыта")
    else:
        b -= 1.5
        why.append("−обрыв на полуслове")

    telo = " ".join(x["text"] for x in blok[1:]).lower()
    nazad = hits(r"как я (уже )?(говорил|сказал)|в прошл(ом|ый)|как мы (помним|говорили)", telo)
    if nazad:
        b -= 1.5 * nazad
        why.append("−отсылки в теле (%d)" % nazad)

    # длительность: колокол вокруг цели, за краями отбраковка
    b -= abs(dur - CEL_SEC) / 30.0
    return round(b, 2), dur, why


def kuski(fr, mn, mx):
    out = []
    for i in range(len(fr)):
        for j in range(i + 1, len(fr) + 1):
            if fr[j - 1]["idx"] != fr[i]["idx"]:
                break                       # кусок не переходит из дубля в дубль
            dur = fr[j - 1]["e"] - fr[i]["s"]
            if dur < mn:
                continue
            if dur > mx:
                break
            ball, dur, why = ocenka_kuska(fr, i, j)
            out.append({"i": i, "j": j, "idx": fr[i]["idx"],
                        "s": fr[i]["s"], "e": fr[j - 1]["e"], "длит": round(dur, 1),
                        "балл": ball, "почему": why,
                        "хук": fr[i]["text"], "конец": fr[j - 1]["text"]})
    return sorted(out, key=lambda x: -x["балл"])


def bez_peresecheniy(cands):
    """`README.md`: границы по предложениям, без пересечений."""
    vzyato = []
    for c in cands:
        if any(c["idx"] == v["idx"] and c["i"] < v["j"] and v["i"] < c["j"] for v in vzyato):
            continue
        vzyato.append(c)
    return vzyato


def mmss(t):
    return "%d:%05.2f" % (int(t // 60), t % 60)


def main():
    pr, a = obshee.argi((["--мин"], {"dest": "mn", "type": float, "default": MIN_SEC}),
                        (["--макс"], {"dest": "mx", "type": float, "default": MAX_SEC}))
    # чистая речь, а не сырая: пересъёмки уже разобраны `dubli.py`, иначе счёт
    # отдал бы первое место куску, где одна мысль сказана трижды
    rech = pr.load("chisto.json")
    fr = frazy(rech)
    cands = bez_peresecheniy(kuski(fr, a.mn, a.mx))
    pr.save("kandidaty.json", cands[:20])

    lines = ["# КАНДИДАТЫ В РИЛЗЫ — «%s»\n" % pr.name,
             "> **Остановка №1.** Рендера ещё нет: правка в таблице стоит минуту,",
             "> та же правка после рендера — час (`ЭКРАН.md`).",
             "",
             "> Счёт по `ОТБОР.md`: держат конкретика + ставка + интрига результата,",
             "> пролистывают декларации и абстракции. Минусы — за отсылку назад",
             "> (вырезанный кусок обязан стоять сам по себе, `README.md`).",
             "",
             "| # | Дубль | В сырье | Длит. | Балл | Из чего балл | Первая фраза (хук) |",
             "|---|---|---|---|---|---|---|"]
    for n, c in enumerate(cands[:12], 1):
        lines.append("| %d | %s | %s–%s | %.0f с | **%.1f** | %s | %s |"
                     % (n, c["idx"], mmss(c["s"]), mmss(c["e"]), c["длит"], c["балл"],
                        " · ".join(c["почему"]), c["хук"][:90]))
    lines += ["", "## Расшифровка кандидатов (первые 5)", ""]
    for n, c in enumerate(cands[:5], 1):
        blok = fr[c["i"]:c["j"]]
        lines.append("### %d. дубль %s, %s–%s (%.0f с, балл %.1f)\n"
                     % (n, c["idx"], mmss(c["s"]), mmss(c["e"]), c["длит"], c["балл"]))
        lines.append(" ".join(x["text"] for x in blok))
        lines.append("")
    pr.text("КАНДИДАТЫ.md", "\n".join(lines) + "\n")

    print("фраз: %d, кандидатов без пересечений: %d" % (len(fr), len(cands)))
    for c in cands[:8]:
        print("  %s %s–%s  %5.1f с  балл %5.1f  %s"
              % (c["idx"], mmss(c["s"]), mmss(c["e"]), c["длит"], c["балл"], c["хук"][:60]))
    print("\nтаблица: %s" % pr.path("КАНДИДАТЫ.md"))


if __name__ == "__main__":
    main()
