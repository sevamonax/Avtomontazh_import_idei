# -*- coding: utf-8 -*-
"""Чистая речь: выбрасывает мусор и оставляет по одному заходу на мысль.

    python dubli.py --проект "ПРИМЕР"

ЗАЧЕМ ОТДЕЛЬНЫЙ ШАГ. `rech.py` ловит брошенный заход по правилу `ЭКРАН.md` §8 — текст
всплеска является НАЧАЛОМ соседнего. На сырье «ПРИМЕР» это правило
поймало 4 места из полутора десятков: здесь человек не обрывает фразу, а
переговаривает её другими словами —

    37.78  «Вообще моя специализация сон, и все бизнесы связаны со сном. У меня и»
    43.06  «Вообще моя специализация СОН и бизнесы с ними связаны. Я помогаю,»

Приставкой это не поймать. Ловится сходством: общее начало из трёх слов или
половина общих слов.

🔑 ВЫБОР ВНУТРИ ГРУППЫ — СУЖДЕНИЕ, А НЕ НОМЕР (`README.md`). замечание: «иногда я могу записать три и на монтаже выбрать первый, а два следующих
выкинуть»*. Поэтому машина имеет право только НАЙТИ группу; по умолчанию берёт
последний полный заход (человек переснимает, пока не выйдет), а **вся группа
целиком уходит в отчёт на приёмку** — с текстом каждого варианта.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import obshee                                            # noqa: E402
import zvuk                                              # noqa: E402

MAX_GAP = 25.0        # дальше — уже не пересъёмка, а другая мысль
NACHALO = 3           # сколько первых слов должно совпасть
JACCARD = 0.45        # или столько общих слов
MIN_SLOV = 4          # короче — судим только по началу

# whisper дорисовывает это на шуме и на вдохе — в речи такого не было
PRIZRAKI = (r"продолжение следует|субтитры|редактор субтитров|спасибо за просмотр|"
            r"^ы+$|^м+$|^а+$|^э+$|^\W*$")
# технические заходы: проверка звука, ругань между дублями
TEHNICHESKIE = r"проверка (звука|бороды|микрофона)|раз ?-?два ?-?три|^так,? проверка"

# 🔴 ЗАЦИКЛИВАНИЕ WHISPER — НЕ МУСОР, А ПРОВАЛ РАСШИФРОВКИ.
#
# На ролик модель выдала «дададада…» на четырёхсот знаков семь раз подряд. Шесть
# из них пришлись на вдох и паузу, а СЕДЬМОЙ накрыл живую фразу «переобувались
# и давали противоположный» — панч всей второй половины ролика. Правило
# `obryvok` роняло такой всплеск молча: одно слово, знака в конце нет, значит
# огрызок. То есть механизм ронял речь и выглядел при этом исправным.
#
# Отличить зацикливание от речи можно механически: слог, повторённый подряд
# восемь раз и больше, в русской речи не встречается. Такой всплеск в сборку
# по-прежнему не идёт — брать оттуда нечего, — но объявляется отдельной
# строкой и отдельным счётом: место названо, оператор идёт слушать звук.
# Ворота проверяют результат, а не факт проверки (`ЭКРАН.md` п.2).
ZACIKL = re.compile(r"(.{1,3}?)\1{7,}")


def zaciklilos(b):
    """Есть ли в расшифровке всплеска слово-зацикливание. Возвращает само слово."""
    for w in b.get("слова") or []:
        if ZACIKL.search(re.sub(r"\s+", "", w["w"].lower())):
            return w["w"]
    if ZACIKL.search(re.sub(r"\s+", "", b["text"].lower())):
        return b["text"].strip()
    return None


def slova(b):
    return b["norm"]


def musor(b):
    t = b["text"].strip().lower()
    if not slova(b):
        return "пусто"
    if re.search(PRIZRAKI, t):
        return "призрак whisper"
    if re.search(TEHNICHESKIE, t):
        return "техническая проверка"
    return None


def obryvok(b, posledniy):
    """Огрызок фразы: коротко и мысль не закрыта.

    Ловит «вообще польскому», «и так же, и», «нейро, а» — заходы, которые человек
    бросил на втором слове. Приставкой они не ловятся (следующий заход начат
    другими словами), а группировку они РАЗБИВАЮТ: вклинившись между двумя
    пересъёмками одной мысли, огрызок делал их разными группами, и в сборке
    оставались обе. Поэтому огрызки убираются ДО группировки.

    Знак в конце — граница правила: «С английского на русский.» тоже четыре
    слова, но это законченная мысль, и она остаётся. Запятая считается наравне
    с точкой: первая версия правила требовала точку и снесла «Меня зовут Имя
    Фамилия,» — представление автора, ради которого ролик и снимался.
    """
    if posledniy:
        return False
    return len(slova(b)) <= 4 and not re.search(r"[.!?…,;:]\s*$", b["text"].strip())


def pohozhi(a, b):
    wa, wb = slova(a), slova(b)
    if not wa or not wb:
        return False
    if len(wa) >= NACHALO and len(wb) >= NACHALO and wa[:NACHALO] == wb[:NACHALO]:
        return True
    if len(wa) >= MIN_SLOV and len(wb) >= MIN_SLOV:
        sa, sb = set(wa), set(wb)
        if len(sa & sb) / float(len(sa | sb)) >= JACCARD:
            return True
    # приставка (то же правило, что в rech.py, — на случай коротких заходов).
    # Порог в одно слово: «Привет!» и «привет» — это два захода на одно место,
    # а не два разных приветствия.
    short, long_ = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    return long_[:len(short)] == short


def gruppy(bursts):
    """Соседние похожие заходы — в одну группу. Порядок съёмки сохраняется."""
    gr, cur = [], [bursts[0]]
    for b in bursts[1:]:
        if b["a"] - cur[-1]["b"] <= MAX_GAP and any(pohozhi(b, x) for x in cur):
            cur.append(b)
        else:
            gr.append(cur)
            cur = [b]
    gr.append(cur)
    return gr


MUSORNYE_ZACHINY = r"^(ну|а|и|вот|то есть|значит|короче|эм+|э+|мм+)\b"
PARAZITY = r"\b(как бы|типа|вообще|ну|короче|это самое|в общем)\b"


def ocenka_zahoda(b, gruppa, uroven, tempo_med=None):
    """Насколько этот заход хорош. Возвращает (балл, из чего он сложился).

    🔴 Правило: *«надо закрепить, чтоб ты выбирал не последний, а
    лучший вариант»*. Прежняя версия брала последний полный — на том основании,
    что человек переснимает, пока не выйдет. Основание неверное:
    говорил прямо — *«иногда я могу записать три и на монтаже выбрать первый»*.

    Считается то, что можно померить. Дикцию и интонацию машина не слышит,
    поэтому спорные случаи остаются в отчёте с баллами — их видно, и их можно
    перебить одним словом.
    """
    ws = slova(b)
    nizhe = b["text"].strip().lower()
    dlit = max(b["b"] - b["a"], 0.2)
    mx = max(len(slova(x)) for x in gruppa)
    ball, why = 0.0, []

    # 1. Полнота: обрывок хуже целого захода при прочих равных
    ball += 2.0 * len(ws) / max(mx, 1)
    why.append("полнота %d/%d" % (len(ws), mx))

    # 2. Мысль закончена — то же требование, что к экранному тексту (`ЭКРАН.md` §1)
    if re.search(r"[.!?…]$", nizhe):
        ball += 1.5
        why.append("мысль закрыта")
    elif re.search(r"[,;:]$", nizhe):
        ball += 0.3
    else:
        ball -= 1.0
        why.append("−обрыв")

    # 3. Чистый зачин: заход, начатый с «ну» или «а», в монтаже звучит как склейка
    if re.search(MUSORNYE_ZACHINY, nizhe):
        ball -= 1.0
        why.append("−мусорный зачин")

    # 4. Слова-паразиты
    p = len(re.findall(PARAZITY, nizhe))
    if p:
        ball -= 0.4 * p
        why.append("−паразитов %d" % p)

    # 5. Слово подряд дважды — запинка, которую whisper всё-таки записал
    povtor = sum(1 for i in range(len(ws) - 1) if ws[i] == ws[i + 1])
    if povtor:
        ball -= 0.6 * povtor
        why.append("−повтор слова")

    # 6. Темп — ОТ МЕДИАНЫ ЭТОГО ЧЕЛОВЕКА, а не от назначенного порога.
    #    Первая версия ставила полосу 2,0–3,6 сл/с и штрафовала почти каждый
    #    заход: у автора на коротких всплесках нормальные 4 сл/с. Порог, который
    #    срабатывает всегда, не отличает плохое от обычного.
    tempo = len(ws) / dlit
    if tempo_med:
        d = abs(tempo - tempo_med)
        if d > 1.2:
            ball -= 0.5
            why.append("темп %.1f при обычных %.1f" % (tempo, tempo_med))

    # 7. Энергия подачи: уровень речи этого захода против уровня дубля.
    #    Единственный измеримый след того, «как сказано», а не «что сказано».
    #
    # 🔑 ПОДАЧА НЕ ПЕРЕБИВАЕТ ПОЛНОТУ — она разводит близкие заходы, а не
    # поднимает огрызок. Замер 12.09.2026 на доборе хвоста к ролике: заход
    # «Подписывайся на мой канал» (4 слова из 12) выиграл у целого
    # «Подписывайся на мой YouTube Ваш канал, там ещё больше интересного про
    # нейронки» со счётом 2,9 против 2,8. Арифметика: полнота дала целому +1,33,
    # подача дала громкому +1,44 — мера «как сказано» оказалась тяжелее меры
    # «что сказано», и в ролик уехал огрызок без названия канала. Поэтому заход,
    # заметно более короткий, чем самый полный в группе, премии за громкость не
    # получает; штраф за вялую подачу остаётся — вялость портит и целый заход.
    if uroven is not None:
        d = max(-1.0, min(1.0, (uroven - 0.0) / 3.0))
        if len(ws) < 0.8 * max(mx, 1):
            d = min(d, 0.0)
        ball += d
        if abs(d) >= 0.5:
            why.append("подача %+.1f дБ" % uroven)

    return round(ball, 2), why


ZOV = re.compile(r"подпис|присоедин|залетай|переходи")
KANAL = re.compile(r"импорт\s*идей|youtube|ютуб")


def vybor(g, urovni, tempo_med):
    """Лучший заход группы по счёту. При равенстве баллов — последний.

    🔑 ВОРОТА НА ХВОСТ. Правило серии «Серия» от 27.08: в призыве
    НАЗВАНИЕ КАНАЛА ОБЯЗАНО ЗВУЧАТЬ, на монтаже берётся тот заход, где оно есть.
    Баллом это не чинится — счёт мерит полноту и подачу, а не наличие названия,
    и 12.09 пропустил ровно это (см. пункт 7 счёта). Требование, обязательное
    всегда, ставится воротами на выходе, а не весом внутри счёта
    (`ЭКРАН.md` п.1): если в группе кто-то зовёт на канал, заходы без
    названия из выбора выбывают — но только пока есть из чего выбирать.
    """
    ocenki = [ocenka_zahoda(b, g, urovni.get(id(b)), tempo_med) for b in g]
    kand = g
    if any(ZOV.search(b["text"].lower()) for b in g):
        s_nazvaniem = [b for b in g if KANAL.search(b["text"].lower().replace("ё", "е"))]
        if s_nazvaniem:
            kand = s_nazvaniem
    mozhno = {id(b) for b in kand}
    luchshiy, best = kand[-1], None
    for b, (ball, _) in zip(g, ocenki):
        if id(b) not in mozhno:
            continue
        if best is None or ball >= best:
            luchshiy, best = b, ball
    return luchshiy, dict(zip((id(b) for b in g), ocenki))


def uroven_zahodov(pr, idx, bursts):
    """Уровень речи каждого захода в дБ относительно медианы дубля.

    Единственное измеримое свойство ПОДАЧИ, а не текста: заход, сказанный вяло,
    тише соседних на пару децибел. Интонацию и дикцию машина не слышит — это
    честно записано в «Остаётся глазам» гейта.
    """
    import numpy as np
    wav = pr.wav_path(idx)
    if not os.path.exists(wav):
        return {}
    db = zvuk.envelope(wav)
    out, vse = {}, []
    for b in bursts:
        i0, i1 = int(b["a"] / zvuk.FRAME), int(b["b"] / zvuk.FRAME)
        seg = db[i0:i1]
        if len(seg) < 3:
            continue
        gromko = seg[seg > np.percentile(seg, 50)]
        u = float(np.mean(gromko))
        out[id(b)] = u
        vse.append(u)
    if not vse:
        return {}
    med = float(np.median(vse))
    return {k: v - med for k, v in out.items()}


def pravki(pr):
    """Ручная правка отбора из proekt.json — то, что отчёт и так обещает отчёт.

    Счёт в `vybor` слышит полноту, паузы и децибелы, но не слышит дикцию,
    интонацию и смысл соседнего куска (`README.md`, раздел «Чего этот счёт не
    слышит»). До сих пор перебить его было нечем, кроме правки кода — то есть
    решение по конкретному ролику уезжало в общий механизм. Теперь оно живёт
    в данных ролика:

        "правки_отбора": {
          "01": {"убрать": [68.56, 102.32], "вернуть": [512.70]}
        }

    Время — начало всплеска из РЕЧЬ.md, с точностью до сотой. Названного
    времени нет в сырье — падаем громко: молчаливо проигнорированная правка
    неотличима от выполненной (урок 30.07).
    """
    cfg = pr.cfg.get("правки_отбора") or {}
    out = {}
    for idx, d in cfg.items():
        out[idx] = (set(round(float(x), 2) for x in d.get("убрать", [])),
                    set(round(float(x), 2) for x in d.get("вернуть", [])))
    return out


def main():
    pr, _ = obshee.argi()
    rech = pr.load("rech.json")
    ruch = pravki(pr)
    chisto, otchet, zacikl = {}, [], []

    for idx in sorted(rech):
        bs = []
        for n, b in enumerate(rech[idx]):
            prizrak = zaciklilos(b)
            if prizrak:
                # 🔑 РЕАЛЬНАЯ РЕЧЬ ИЗ-ПОД ЗАЦИКЛИВАНИЯ НЕ ВЫБРАСЫВАЕТСЯ.
                # Всплеск 318.10 на одном из роликов — «ты уверен, мне кажется, ответ немножко
                # другой…» плюс «дадада…» хвостом. Выбросить его целиком значило
                # бы потерять реплику ради дефекта расшифровки. Считаем, сколько
                # настоящих слов осталось: два и больше — всплеск идёт в сборку,
                # а подпись чинится `правки_текста`; меньше — брать нечего.
                zhivyh = [w for w in (b.get("слова") or [])
                          if not ZACIKL.search(re.sub(r"\s+", "", w["w"].lower()))]
                zacikl.append((idx, b, len(zhivyh)))
                if len(zhivyh) < 2:
                    otchet.append((idx, b, "🔴 расшифровка ЗАЦИКЛИЛАСЬ, речи под ней нет",
                                   None))
                    continue
                otchet.append((idx, b, "🔴 расшифровка ЗАЦИКЛИЛАСЬ на хвосте — "
                                       "речь оставлена, подпись чинить `правки_текста`", None))
            why = musor(b)
            if why:
                otchet.append((idx, b, "выброшен: " + why, None))
                continue
            if b.get("брошен"):
                otchet.append((idx, b, "брошенный заход (`ЭКРАН.md` §8)", None))
                continue
            if obryvok(b, n == len(rech[idx]) - 1):
                otchet.append((idx, b, "огрызок: коротко и мысль не закрыта", None))
                continue
            bs.append(b)
        if not bs:
            chisto[idx] = []
            continue
        urovni = uroven_zahodov(pr, idx, bs)
        tempy = sorted(len(slova(b)) / max(b["b"] - b["a"], 0.2) for b in bs if slova(b))
        tempo_med = tempy[len(tempy) // 2] if tempy else None
        vzyato = []
        for g in gruppy(bs):
            if len(g) == 1:
                vzyato.append(g[0])
                continue
            best, ocenki = vybor(g, urovni, tempo_med)
            vzyato.append(best)
            for b in g:
                ball, why = ocenki[id(b)]
                otchet.append((idx, b,
                               "%s (%.1f: %s)" % ("ВЗЯТ" if b is best else "не взят",
                                                  ball, " · ".join(why)),
                               "группа %.2f" % g[0]["a"]))
        chisto[idx] = vzyato

    # --- ручная правка поверх счёта ---
    for idx, (ubrat, vernut) in ruch.items():
        if idx not in rech:
            raise SystemExit("правки_отбора: нет дубля %s" % idx)
        vse = dict((round(b["a"], 2), b) for b in rech[idx])
        for t0 in sorted(ubrat | vernut):
            if t0 not in vse:
                raise SystemExit("правки_отбора: в дубле %s нет всплеска на %.2f" % (idx, t0))
        vzyato = [b for b in chisto[idx] if round(b["a"], 2) not in ubrat]
        est = set(round(b["a"], 2) for b in vzyato)
        for t0 in vernut:
            if t0 not in est:
                vzyato.append(vse[t0])
        vzyato.sort(key=lambda b: b["a"])
        for t0 in sorted(ubrat):
            otchet.append((idx, vse[t0], "УБРАН РУКОЙ (правки_отбора)", "рука"))
        for t0 in sorted(vernut):
            otchet.append((idx, vse[t0], "ВЕРНУТ РУКОЙ (правки_отбора)", "рука"))
        chisto[idx] = vzyato

    pr.save("chisto.json", chisto)

    lines = ["# ПЕРЕСЪЁМКИ И МУСОР — «%s»\n" % pr.name,
             "> **Машина нашла группы и выбрала лучший заход по счёту**",
             ">. Считается измеримое: полнота · закончена ли мысль ·",
             "> чистый зачин · слова-паразиты · повторы · темп · уровень подачи в дБ.",
             "> Дикцию и интонацию машина не слышит — если где-то лучше звучит другой",
             "> вариант, скажи номер, поправлю одной строкой.\n",
             "| Дубль | В сырье | Решение | Группа | Текст |", "|---|---|---|---|---|"]
    # Всплески без текста (кашель, стук, вдох) в таблицу не идут: их десятки, и
    # они прячут настоящие решения. Считаем их одной строкой — молчать о них
    # тоже нельзя.
    pusto = sum(1 for _, _, r, _ in otchet if r.endswith("пусто"))
    for idx, b, resh, gr in otchet:
        if resh.endswith("пусто"):
            continue
        lines.append("| %s | %.2f–%.2f | %s | %s | %s |"
                     % (idx, b["a"], b["b"], resh, gr or "—", b["text"][:80]))
    lines.append("")
    lines.append("Плюс **%d всплесков без слов** (кашель, стук, вдох) — выброшены молча."
                 % pusto)
    for idx in sorted(chisto):
        lines.append("")
        lines.append("## Дубль %s — осталось %d заходов, речи %.0f с"
                     % (idx, len(chisto[idx]),
                        sum(b["b"] - b["a"] for b in chisto[idx])))
        for b in chisto[idx]:
            lines.append("- `%7.2f–%7.2f` %s" % (b["a"], b["b"], b["text"]))
    pr.text("ПЕРЕСЪЁМКИ.md", "\n".join(lines) + "\n")

    bylo = sum(len(v) for v in rech.values())
    stalo = sum(len(v) for v in chisto.values())
    print("было всплесков %d → осталось %d (выброшено %d)" % (bylo, stalo, bylo - stalo))
    for idx in sorted(chisto):
        print("  дубль %s: %d заходов, речи %.0f с"
              % (idx, len(chisto[idx]), sum(b["b"] - b["a"] for b in chisto[idx])))
    if zacikl:
        # Молчать об этом нельзя: расшифровка провалилась, и знать об этом должен
        # человек, а не только файл отчёта (`ЭКРАН.md` п.2).
        print("🔴 расшифровка зациклилась на %d всплесках — слушать звук:" % len(zacikl))
        for idx, b, zhivyh in zacikl:
            print("   %s %7.2f–%7.2f · живых слов %d%s"
                  % (idx, b["a"], b["b"], zhivyh,
                     " → всплеск оставлен" if zhivyh >= 2 else " → выброшен"))
    print("отчёт: %s" % pr.path("ПЕРЕСЪЁМКИ.md"))


if __name__ == "__main__":
    main()
