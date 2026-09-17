# -*- coding: utf-8 -*-
r"""Единственная дверь в папку финалов: копирует рилз только через гейт.

    python finaly.py --проект "ПРИМЕР" --серия "Моя серия"
    python finaly.py --проект "ПРИМЕР" --серия "Моя серия" --почему-без-инфографики "…"

🔑 ЗАЧЕМ ЭТО ВООБЩЕ. У готового файла один дом — папка финалов
(`финалы/<серия>/`, меняется ключом `выход.финалы` в `настройки.json`).
Оттуда ролик и заливается. Значит эта папка — последнее место, где можно
остановить недоделанный ролик, и единственное, где остановка не требует
ничего помнить: если файла там нет, залить его по забывчивости физически
нельзя.

Повод, из которого выросли эти ворота, стоит рассказать целиком. Шаг
«инфографика» стоял в порядке работы, гейт печатал «чисто», а ролики
попадали в папку финалов копированием вручную — мимо гейта. Девять роликов
подряд вышли без инфографики, и заметил это человек на просмотре, а не
механизм. Копирование руками и было дырой: пока у выхода нет одной двери,
любая проверка перед ним необязательна.

Правило общее: такое чинится воротами на ОБЩЕМ ВЫХОДЕ, а не правкой того
места, где заметили. Общий выход здесь один — вот он.

Ключ `--почему-без-инфографики` существует, потому что запрет без легального
обхода обходят нелегально: скопировать файл руками можно всегда. Причина
печатается в отчёт и уходит в `ФИНАЛЫ.md` рядом с роликом — осознанный пропуск
виден, молчаливый невозможен.
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import obshee                                            # noqa: E402

# Дом финалов. Относительный путь считается от корня репозитория, абсолютный
# берётся как есть — финалы часто лежат рядом с сырьём, на другом диске.
_DOM = obshee.nastroyka("выход.финалы", "финалы").replace("\\", os.sep).replace("/", os.sep)
DOM = _DOM if os.path.isabs(_DOM) else os.path.normpath(os.path.join(obshee.KOREN, _DOM))


def sha256(put):
    h = hashlib.sha256()
    with open(put, "rb") as f:
        for kusok in iter(lambda: f.read(1 << 20), b""):
            h.update(kusok)
    return h.hexdigest()


def gejt(imya_proekta):
    """Прогон `proverki.py` как есть. Его вердикт — код возврата, не текст."""
    p = subprocess.run([sys.executable, os.path.join(BASE, "proverki.py"),
                        u"--проект", imya_proekta],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def main():
    pr, a = obshee.argi(
        ([u"--серия"], {"dest": "seriya", "required": True,
                        "help": u"папка внутри финалы"}),
        ([u"--имя"], {"dest": "imya", "default": None,
                      "help": u"имя файла в финалах (по умолчанию — имя проекта)"}),
        ([u"--почему-без-инфографики"], {"dest": "bez", "default": None}))

    ishodnik = os.path.join(pr.out, u"%s — рилз.mp4" % pr.name)
    if not os.path.exists(ishodnik):
        raise SystemExit(u"нет готового рилза: %s\n"
                         u"сначала nalozhit.py — финалом считается композит, "
                         u"а не сборка без слоя" % ishodnik)

    chisto, otchet = gejt(pr.name)
    print(otchet.rstrip())
    if not chisto:
        # Разделяем два разных отказа: инфографика — единственный, который можно
        # пройти словом; остальные дефекты словом не закрываются.
        tolko_v16 = u"В16" in otchet and otchet.count(u" ✗") == 1
        if not (tolko_v16 and a.bez):
            raise SystemExit(
                u"\n⛔ ГЕЙТ НЕ ПРОЙДЕН — в финалы не копирую.\n"
                u"   Ролик остаётся черновиком в %s\n"
                u"   Если дело только в инфографике и её решено не делать — "
                u"скажи почему:\n"
                u"   --почему-без-инфографики \"…\"" % pr.out)
        print(u"\n⚠️ Инфографики нет, пропуск осознанный: %s" % a.bez)

    papka = os.path.join(DOM, a.seriya)
    if not os.path.isdir(papka):
        os.makedirs(papka)
    cel = os.path.join(papka, u"%s.mp4" % (a.imya or pr.name))
    shutil.copy2(ishodnik, cel)

    h1, h2 = sha256(ishodnik), sha256(cel)
    if h1 != h2:
        os.remove(cel)
        raise SystemExit(u"копия не совпала с исходником по SHA-256 — удалил, повтори")

    zapis = [u"# ФИНАЛ — «%s»\n" % pr.name,
             u"Скопирован в `%s`." % cel,
             u"SHA-256 совпал: `%s`.\n" % h1[:16]]
    if a.bez:
        zapis += [u"⚠️ **Без инфографики, осознанно:** %s" % a.bez,
                  u"", u"Правило — `ЭКРАН.md` Пропуск записан здесь, "
                  u"чтобы он был виден в приёмке, а не забылся молча."]
    else:
        zapis += [u"Гейт В1–В16 пройден чисто, инфографика на месте."]
    pr.text(u"ФИНАЛЫ.md", u"\n".join(zapis) + u"\n")

    print(u"\n✅ финал: %s" % cel)
    print(u"   SHA-256 сверен, запись — %s" % pr.path(u"ФИНАЛЫ.md"))


if __name__ == "__main__":
    main()
