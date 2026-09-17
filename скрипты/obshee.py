# -*- coding: utf-8 -*-
"""Где что лежит, какой проект собираем и по каким настройкам — один ответ
на все скрипты конвейера.

🔑 СКРИПТЫ ЛЕЖАТ ОТДЕЛЬНО ОТ ДАННЫХ, РОЛИК ПРИХОДИТ КЛЮЧОМ. Это главное
устройство конвейера, и оно не косметическое. Если скрипты живут внутри папки
ролика, то «механизм для любого ролика» держится на том, что папку копируют
целиком — вместе с решениями по прошлому ролику, зашитыми в код. Через полгода
таких копий пять, и ни в одной не понять, где механизм, а где чужая правка.

Здесь код общий, а конкретный ролик — аргумент:

    python rech.py --проект "ПРИМЕР"

Новый ролик = новая папка в `проекты/` + `proekt.json` внутри. Кода не трогаем.

🔑 ПУТЬ ИЩЕТСЯ, А НЕ НАЗНАЧАЕТСЯ. Нет файла — скрипт говорит об этом вслух и
падает. Молчащая проверка неотличима от чистой сборки: если `load` вернёт
`None`, дальше по конвейеру поедет пустота, и узнается об этом только на
просмотре готового ролика.
"""
import argparse
import io
import json
import os

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
KOREN = os.path.dirname(SCRIPTS)                     # корень репозитория
PROEKTY = os.path.join(KOREN, "проекты")             # папки роликов
SLOI = os.path.join(KOREN, "слой")                   # проект Remotion (экранный слой)

_NASTROYKI = {}


def nastroyki():
    """Настройки репозитория — `настройки.json` в корне.

    Читается один раз и раздаётся всем скриптам. Здесь живёт всё, что зависит
    от машины и от канала, а не от механизма: кодировщик, целевая громкость,
    модель расшифровки, название канала, куда класть финалы.

    Файла нет — берутся значения из `настройки.пример.json`, лежащего рядом.
    Это сделано нарочно: конвейер обязан запускаться сразу после `git clone`,
    а не после заполнения анкеты. Своё вписывается потом, по одному ключу.
    """
    if _NASTROYKI:
        return _NASTROYKI
    svoi = os.path.join(KOREN, "настройки.json")
    obrazec = os.path.join(KOREN, "настройки.пример.json")
    put = svoi if os.path.exists(svoi) else obrazec
    if not os.path.exists(put):
        raise IOError("нет ни настройки.json, ни настройки.пример.json в %s" % KOREN)
    with io.open(put, encoding="utf-8") as f:
        _NASTROYKI.update(json.load(f))
    _NASTROYKI["_файл"] = put
    return _NASTROYKI


def nastroyka(put, po_umolchaniyu=None):
    """Значение по пути через точку: nastroyka("звук.громкость_lufs", -16.0)."""
    uzel = nastroyki()
    for kusok in put.split("."):
        if not isinstance(uzel, dict) or kusok not in uzel:
            return po_umolchaniyu
        uzel = uzel[kusok]
    return uzel


_KODIROVSHCHIK = []


def _rabotaet(imya):
    """Кодирует один кадр этим кодировщиком. Работает — значит работает.

    🔴 СПИСОК `ffmpeg -encoders` ОТВЕЧАЕТ НА ДРУГОЙ ВОПРОС. Он печатает то, что
    в эту сборку ffmpeg ВКОМПИЛИРОВАНО, а не то, что умеет здешнее железо.
    Сборки из репозиториев несут `h264_qsv`, `h264_nvenc` и `h264_videotoolbox`
    одновременно — на машине, где нет ни встроенной графики Intel, ни видеокарты
    NVIDIA, ни Mac. Проверка по списку такой кодировщик находит, объявляет
    доступным и отдаёт конвейеру, а падает всё на первом настоящем куске —
    после самого долгого шага. То есть проверка, отвечающая не на тот вопрос,
    хуже отсутствующей: она ещё и обещает.

    Поэтому проверяем делом: один кадр 64×64 в никуда. Стоит это доли секунды и
    разом закрывает и «кодировщика нет», и «кодировщик есть, а устройства нет».
    """
    import subprocess
    try:
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
             "-frames:v", "1", "-c:v", imya, "-f", "null", "-"],
            capture_output=True, text=True)
        return p.returncode == 0
    except OSError:
        raise IOError("ffmpeg не найден — поставьте его и повторите (см. УСТАНОВКА.md)")


def kodirovshchik(kachestvo=23):
    """Аргументы ffmpeg для кодировщика видео — с проверкой, что он тут работает.

    🔑 ЗАЧЕМ ПРОВЕРКА, А НЕ КОНСТАНТА. Быстрые кодировщики — аппаратные:
    `h264_qsv` умеет только встроенная графика Intel, `h264_nvenc` — только
    NVIDIA, `h264_videotoolbox` — только Mac. Собранный на одной машине
    конвейер, приехав на другую, падает посреди сборки, и человек думает, что
    сломан механизм, а не что у него другое железо.

    Не завёлся — берём `libx264`: он есть везде, где есть ffmpeg, и считает
    медленнее, но не иначе. Подмена объявляется вслух, иначе она станет
    необъяснимой разницей в скорости.

    Значение `авто` перебирает аппаратные кодировщики в порядке скорости и
    останавливается на первом, который действительно закодировал кадр.
    """
    if _KODIROVSHCHIK:
        return _sobrat(kachestvo)
    imya = nastroyka("видео.кодировщик", "авто")
    poryadok = [imya] if imya != "авто" else \
        ["h264_qsv", "h264_nvenc", "h264_videotoolbox", "libx264"]
    vybran = None
    for k in poryadok:
        if _rabotaet(k):
            vybran = k
            break
    if vybran is None:
        if not _rabotaet("libx264"):
            raise IOError("ffmpeg не умеет даже libx264 — сборка ffmpeg неполная "
                          "(см. УСТАНОВКА.md)")
        print(u"   кодировщик %s на этой машине не работает — беру libx264" % (imya,))
        vybran = "libx264"
    elif imya == "авто" and vybran != "libx264":
        print(u"   кодировщик: %s" % vybran)
    _KODIROVSHCHIK.append(vybran)
    return _sobrat(kachestvo)


def _sobrat(kachestvo):
    """Кодировщик + ключ качества. У каждого кодировщика ключ называется по-своему."""
    k = _KODIROVSHCHIK[0]
    if k == "libx264":
        return ["-c:v", k, "-crf", str(kachestvo), "-preset",
                nastroyka("видео.preset", "medium"), "-pix_fmt", "yuv420p", "-g", "60"]
    if k == "h264_nvenc":
        return ["-c:v", k, "-cq", str(kachestvo), "-preset", "p5", "-g", "60"]
    if k == "h264_videotoolbox":
        return ["-c:v", k, "-q:v", str(max(1, 100 - kachestvo * 3)), "-g", "60"]
    return ["-c:v", k, "-global_quality", str(kachestvo), "-g", "60"]


class Proekt(object):
    def __init__(self, name):
        self.name = name
        self.dir = os.path.join(PROEKTY, name)
        if not os.path.isdir(self.dir):
            raise IOError("нет папки проекта: %s" % self.dir)
        self.cfg = self.load("proekt.json")
        self.raw = self._syryo()
        if not os.path.isdir(self.raw):
            raise IOError("нет папки сырья: %s (ключ «сырьё» в proekt.json)" % self.raw)
        self.wav = os.path.join(self.dir, "wav")
        self.out = os.path.join(self.dir, "выход")
        for d in (self.wav, self.out):
            if not os.path.isdir(d):
                os.makedirs(d)

    def _syryo(self):
        """Папка сырья. Относительный путь считается от корня репозитория.

        Абсолютный путь тоже принимается — сырьё обычно лежит на другом диске,
        и тащить десятки гигабайт внутрь репозитория незачем. Разделители
        приводятся к системным: `proekt.json`, написанный на Windows, должен
        открываться на macOS и Linux без правки.
        """
        put = self.cfg.get("сырьё")
        if not put:
            raise IOError("в proekt.json нет ключа «сырьё» — где лежат исходные файлы")
        put = put.replace("\\", os.sep).replace("/", os.sep)
        if os.path.isabs(put):
            return put
        return os.path.normpath(os.path.join(KOREN, put))

    # --- файлы сырья: idx («01», «02»…) → полный путь ---
    def dubli(self):
        exts = (".mov", ".mp4", ".m4v")
        # Ключ «файлы» в proekt.json — когда в папке сырья лежит несколько
        # роликов сразу (частый случай: серия снята одним заходом и пришла
        # одной папкой). Порядок берётся из списка, а не из имён: второй файл
        # может быть продолжением первого, и тогда алфавит врёт.
        # Сами файлы при этом не двигаются и не переименовываются.
        spisok = self.cfg.get("файлы")
        if spisok:
            files = []
            for f in spisok:
                if not os.path.exists(os.path.join(self.raw, f)):
                    raise IOError("в proekt.json назван файл, которого нет в сырье: %s" % f)
                files.append(f)
        else:
            files = sorted(f for f in os.listdir(self.raw) if f.lower().endswith(exts))
        if not files:
            raise IOError("в папке сырья нет видеофайлов: %s" % self.raw)
        return [("%02d" % (i + 1), os.path.join(self.raw, f)) for i, f in enumerate(files)]

    def wav_path(self, idx):
        return os.path.join(self.wav, idx + ".wav")

    # --- данные ---
    def path(self, name):
        return os.path.join(self.dir, name)

    def load(self, name, required=True):
        p = os.path.join(self.dir, name)
        if not os.path.exists(p):
            if required:
                raise IOError("не найден %s — искал в %s" % (name, self.dir))
            return None
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)

    def save(self, name, obj):
        p = os.path.join(self.dir, name)
        with io.open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        return p

    def text(self, name, body):
        p = os.path.join(self.dir, name)
        with io.open(p, "w", encoding="utf-8") as f:
            f.write(body)
        return p


def argi(*extra):
    """Общий разбор аргументов: --проект обязателен всем скриптам конвейера."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--проект", dest="proekt", required=True)
    for args, kw in extra:
        ap.add_argument(*args, **kw)
    a = ap.parse_args()
    return Proekt(a.proekt), a
