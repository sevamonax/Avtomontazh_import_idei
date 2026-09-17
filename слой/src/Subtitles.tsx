import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont as loadSerif} from '@remotion/google-fonts/Prata';
import {loadFont as loadSans} from '@remotion/google-fonts/Manrope';
import {loadFont as loadMono} from '@remotion/google-fonts/PTMono';
import {C} from './tokens';

/**
 * СУБТИТРЫ ШОРТСА — тихая школа референсов `ref1a`/`ref1b` (`ЭКРАН.md`).
 *
 * 🔴 Переписано 04.08.2026 после приёмки: *«хорош только монтаж пауз.
 * Остальное — очень плохо»*. Первая версия строилась по своду `ЭКРАН.md` §0 и потеряла
 * сам разбор референсов — `ЭКРАН.md` §1.1–`ЭКРАН.md` §1.2. Что вернулось на место:
 *
 *   `ЭКРАН.md` §1 — **шрифт речи Prata**, а не Manrope. Плюс баг: у Manrope просили
 *              вес 800, которого не загружали, и браузер подставлял дефолт.
 *              Любой вес из стилей обязан быть в списке загрузки.
 *   `ЭКРАН.md` §1.1     — **позиция плавает** от плана к плану, включая углы, а не четыре
 *              гнезда по центру корпуса. Смена — **жёсткой склейкой**, без
 *              затухания.
 *   `ЭКРАН.md` §1.5     — **знаки-маркеры**: `//. N`, `( … )`, `<< … >>`, `•`, `✕ … ✕`,
 *              `< СЛОВО >`. Ставятся по смыслу реплики, не по её номеру.
 *   `ЭКРАН.md` §1.6     — опорное слово **КАПСОМ** и крупнее в 1,5–2 раза.
 *   `ЭКРАН.md` §1.3     — печать чанками по слову с блок-курсором `▮`.
 *   `ЭКРАН.md` §1.4     — ремарка живёт **в другой зоне кадра**, чем реплика.
 *   `ЭКРАН.md` §1 — **надпись не заезжает на лицо**: гнездо выбирается по замеру
 *              лица на этом куске, а не по счётчику.
 */

const {fontFamily: rech} = loadSerif('normal', {weights: ['400'], subsets: ['cyrillic', 'latin'], ignoreTooManyRequestsWarning: true});
const {fontFamily: sans} = loadSans('normal', {weights: ['400', '500', '600', '700', '800'], subsets: ['cyrillic', 'latin'], ignoreTooManyRequestsWarning: true});
const {fontFamily: mono} = loadMono('normal', {weights: ['400'], subsets: ['cyrillic', 'latin'], ignoreTooManyRequestsWarning: true});

export type Word = {w: string; s: number; e: number};

/** Яркость фона под каждым гнездом на этом куске — замер из `titry.py`. */
export type Ton = {t: number; конец: number; L: number[]};

/**
 * Порог, за которым светлый текст перестаёт читаться и субтитр уходит в тёмный.
 * 0,60 — не вкус: на серии «Серия» яркость гнёзд лежит в 0,57…0,94
 * (белая футболка, белая кирпичная стена), на «Посте знакомство» — заметно
 * ниже. `ЭКРАН.md` §1.1 запрещает подложку и обводку, `ЭКРАН.md` §0 разрешает нижний скрим, но
 * скрим гасит картинку на всём ролик ради нескольких кусков. Меняем не фон,
 * а тон текста — и только там, где замер этого требует.
 */
const PORG_TONA = 0.60;

/** Прямоугольник лица в долях готового кадра — приходит из `titry.py`. */
export type Litso = {t: number; конец: number; x0: number; x1: number; y0: number; y1: number};

export type Znak = '//.' | '(' | '<<' | '•' | '✕' | '<' | null;

/** Реплика, размеченная механизмом: знак, анимация и ремарочность решены в Python. */
export type Replika = {
  слова: Word[];
  знак: Znak;
  номер?: number;
  анимация: 'рез' | 'печать' | 'по-слову';
  ремарка?: boolean;
  /** индекс опорного слова (`ЭКРАН.md` §1.6). −1 — опоры нет, вся реплика ровная */
  опора: number;
  /** капсить ли опору, или это имя собственное (`ЭКРАН.md` §1.6; решает `titry.py`) */
  опора_капсом?: boolean;
  /** индекс гнезда, назначенный механизмом в `titry.py` (`ЭКРАН.md` §1.1) */
  гнездо?: number;
};

/* ─────────────────────────── ГНЁЗДА ───────────────────────────
 * `ЭКРАН.md` §1.1: «Живёт не внизу экрана, а в средней трети, на уровне груди. Позиция
 * плавает от плана к плану: сдвигается влево/вправо/выше». В референсе реплики
 * стоят и в левом верхнем углу, и над плечом, и справа у края — восемь мест, а
 * не четыре. Координаты в долях кадра, чтобы пересечение с лицом считалось
 * в одних единицах.
 */
type Gnezdo = {
  x0: number; x1: number;      // границы коробки по ширине, доли
  y: number;                    // верх коробки, доля высоты
  kegl: number;                 // базовый кегль при ширине 1080
  align: 'left' | 'center' | 'right';
};

export const GNEZDA: Gnezdo[] = [
  {x0: 0.065, x1: 0.60, y: 0.555, kegl: 50, align: 'left'},
  {x0: 0.12, x1: 0.88, y: 0.605, kegl: 52, align: 'center'},
  {x0: 0.42, x1: 0.935, y: 0.545, kegl: 48, align: 'right'},
  {x0: 0.065, x1: 0.62, y: 0.655, kegl: 46, align: 'left'},
  {x0: 0.065, x1: 0.56, y: 0.215, kegl: 46, align: 'left'},
  {x0: 0.46, x1: 0.935, y: 0.195, kegl: 52, align: 'right'},
  {x0: 0.065, x1: 0.58, y: 0.455, kegl: 50, align: 'left'},
  {x0: 0.16, x1: 0.84, y: 0.285, kegl: 48, align: 'center'},
  // Два гнезда добавлены 27.08.2026 по замеру: в вертикали коробка лица
  // занимает y 0,05–0,55, поэтому четыре верхних гнезда почти всегда заняты,
  // и работали ровно четыре нижних. Эти два расширяют полосу корпуса вниз и
  // влево, не залезая под лицо.
  {x0: 0.30, x1: 0.935, y: 0.700, kegl: 46, align: 'right'},
  {x0: 0.065, x1: 0.50, y: 0.510, kegl: 48, align: 'left'},
];

/** Ремарка (`ЭКРАН.md` §1.4) живёт в верхней трети — всегда в другой зоне, чем реплика. */
export const GNEZDO_REMARKI: Gnezdo = {x0: 0.065, x1: 0.62, y: 0.145, kegl: 40, align: 'left'};

/**
 * Ширина слова МЕРЯЕТСЯ БРАУЗЕРОМ, а не оценивается коэффициентом.
 *
 * 🔴 Было: `0.5 * длина слова`. 28.08 на одном из роликов опорное «ПРОТИВОПОЛОЖНЫЙ.» уехало
 * за левый край кадра — замер альфы показал строку шире 1009 px в гнезде
 * шириной 686. Оценка обещала 82 px кегля, влезало 60.
 *
 * Коэффициент здесь не спасти подбором: у Prata прописная почти вдвое шире
 * строчной (замер по слою: строчные ~0,58 кегля, прописные ~0,79), а опорное
 * слово как раз идёт КАПСОМ и в 1,8 кегля — то есть ошибка оценки приходится
 * ровно на то слово, которое ломает кадр. Один коэффициент на два регистра —
 * это оговорка внутри правила (`ЭКРАН.md` п.5).
 *
 * Компонент живёт в Chrome, где шрифт уже загружен, — значит ширину можно не
 * угадывать, а спросить. `measureText` даёт точное число теми же метриками,
 * какими строка потом и нарисуется.
 */
let holst: CanvasRenderingContext2D | null | undefined;
const shirinaPx = (slovo: string, size: number, family: string) => {
  if (holst === undefined) holst = document.createElement('canvas').getContext('2d');
  if (!holst) return size * 0.79 * Math.max(slovo.length, 1);   // запас по прописным
  holst.font = `${size}px ${family}`;
  return holst.measureText(slovo).width;
};

export const vlezaet = (size: number, slovo: string, boxPx: number, family: string) => {
  const w = shirinaPx(slovo, size, family);
  return w <= boxPx ? size : Math.max(1, (size * boxPx) / w);
};

/** Сколько высоты кадра займёт коробка реплики — грубо, для проверки на лицо. */
const vysota = (g: Gnezdo, strok: number, H: number) => (g.kegl * 1.25 * strok) / H;

const peresekaet = (g: Gnezdo, l: Litso | undefined, strok: number, H: number) => {
  if (!l) return false;
  const y1 = g.y + vysota(g, strok, H);
  return g.x0 < l.x1 && g.x1 > l.x0 && g.y < l.y1 && y1 > l.y0;
};

/* ─────────────────────────── РЕНДЕР ─────────────────────────── */

const cifra = (w: string) => /\d/.test(w);

export type SubtitlesProps = {
  репликы: Replika[];
  лицо?: Litso[];
  тон?: Ton[];
  /** индексы слов внутри реплики, которые надо зачеркнуть (`ЭКРАН.md` §1.1) */
  зачеркнуть?: Record<number, number[]>;
};

export const Subtitles: React.FC<SubtitlesProps> = ({репликы, лицо = [], тон = [], зачеркнуть = {}}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;

  // Ищем ПОСЛЕДНЮЮ подходящую реплику, а не первую: хвост в 0,3 с после
  // последнего слова перекрывается с началом следующей, и поиск сверху вниз
  // держал бы на экране предыдущую строку, пока звучит уже новая.
  let ri = -1;
  for (let i = репликы.length - 1; i >= 0; i--) {
    const r0 = репликы[i];
    const hvost = r0.анимация === 'печать' ? 0.55 : 0.30;
    if (t >= r0.слова[0].s - 0.06 && t <= r0.слова[r0.слова.length - 1].e + hvost) {
      ri = i;
      break;
    }
  }
  if (ri < 0) return null;

  const r = репликы[ri];
  const start = r.слова[0].s;
  const end = r.слова[r.слова.length - 1].e;
  const l = лицо.find((x) => t >= x.t && t < x.конец);

  // 🔑 Гнездо выбирается ЗАМЕРОМ, а не счётчиком: перебираем места, начиная со
  // своего по очереди, и берём первое, которое не ложится на лицо. Правило
  // `ЭКРАН.md` §1 — «надпись не заезжает на лицо» — иначе снова окажется на голове.
  // 🔑 ГНЕЗДО НАЗНАЧАЕТ МЕХАНИЗМ (`titry.py`), а не компонент.
  //
  // Здесь стоял перебор «первое свободное, начиная со своего». Замер 27.08
  // показал, к чему это привело на трёх собранных роликах: работали четыре
  // гнезда из восьми, «корпус слева» забирал 44 %, «корпус справа» — 2,6 %,
  // верхние — 0,0 %. Свободны всегда одни и те же, значит и берутся одни и те
  // же. Решение (какое гнездо и почему) теперь принимается в Python, где виден
  // весь ролик разом; компонент только ставит текст на назначенное место.
  const strok = r.слова.length > 3 ? 2 : 1;
  let gi = typeof r.гнездо === 'number' ? r.гнездо : ri % GNEZDA.length;
  let g = r.ремарка ? GNEZDO_REMARKI : GNEZDA[gi];
  if (!r.ремарка && typeof r.гнездо !== 'number') {
    for (let k = 0; k < GNEZDA.length; k++) {
      const j = (ri + k) % GNEZDA.length;
      if (!peresekaet(GNEZDA[j], l, strok, height)) {
        gi = j;
        g = GNEZDA[j];
        break;
      }
    }
  }

  // Тон текста — по замеру фона под выбранным гнездом (см. PORG_TONA).
  // У ремарки своё гнездо, замера под ним нет: берём среднее по кадру.
  const zam = тон.find((x) => t >= x.t && t < x.конец);
  const svet = zam
    ? (r.ремарка ? zam.L.reduce((a, b) => a + b, 0) / zam.L.length : zam.L[gi])
    : 0;
  const temno = svet > PORG_TONA;
  const cvetTeksta = temno ? C.n900 : C.white;
  const ten = temno ? '0 1px 10px rgba(255,255,255,0.75)' : '0 2px 18px rgba(0,0,0,0.55)';
  const cvetZnaka = temno ? C.blue : C.blueLight;

  const boxPx = (g.x1 - g.x0) * width;
  const k = width / 1080;                       // кегли записаны для 1080
  const base = g.kegl * k;

  // Опорное слово выбирает механизм в `titry.py` — там есть словарь служебных
  // слов и весь текст реплики. Здесь только оформление: КАПС и 1,8 кегля (`ЭКРАН.md` §1.6).
  const opora = r.опора;

  // Печать: чанк по слову с блок-курсором (`ЭКРАН.md` §1.3).
  // Правка: «сейчас очень быстро появляется и сразу исчезает».
  // Шаг 0,2 с был взят из замера референса, но там печатались длинные тезисы, а
  // у нас реплика в четыре слова успевала набраться за 0,8 с и дальше просто
  // висела. Теперь набор растянут на саму реплику: последнее слово встаёт под
  // конец фразы, и приём успевает прочитаться.
  // Правка по приёмке роликае: «анимация с Сергеем Брином не доведена
  // до конца, она исчезает с экрана быстрее, чем её можно прочитать». Набор
  // занимал ВСЮ длину реплики, поэтому целиком строка стояла доли секунды.
  // Теперь печать укладывается в 55 % реплики, остальное строка просто стоит.
  const NABOR = 0.55;
  const shag = Math.max(0.13, ((end - start) * NABOR) / Math.max(r.слова.length, 1));
  const napechatano = r.анимация === 'печать'
    ? Math.floor((t - start) / shag) + 1
    : r.слова.length;

  const znakStyle: React.CSSProperties = {
    fontFamily: mono,
    fontSize: base * 0.72,
    color: cvetZnaka,
    opacity: 0.9,
    marginRight: base * 0.22,
  };

  return (
    <div
      style={{
        position: 'absolute',
        left: `${g.x0 * 100}%`,
        width: `${(g.x1 - g.x0) * 100}%`,
        top: `${g.y * 100}%`,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'baseline',
        justifyContent: g.align === 'center' ? 'center' : g.align === 'right' ? 'flex-end' : 'flex-start',
        textAlign: g.align,
        gap: `${base * 0.12}px ${base * 0.28}px`,
        fontFamily: rech,
        color: cvetTeksta,
        // `ЭКРАН.md` §1.1: без подложки и обводки. Тень волосяная и в тон фону: на светлом
        // кадре текст тёмный, на тёмном светлый — решает замер, а не привычка.
        textShadow: ten,
        lineHeight: 1.18,
      }}
    >
      {r.знак === '//.' ? <span style={znakStyle}>{`//.${r.номер ? ' ' + r.номер : ''}`}</span> : null}
      {r.знак === '•' ? <span style={znakStyle}>•</span> : null}
      {r.знак === '(' ? <span style={znakStyle}>(</span> : null}
      {r.знак === '<<' ? <span style={znakStyle}>&laquo;&laquo;</span> : null}
      {r.знак === '✕' ? <span style={{...znakStyle, color: cvetTeksta, opacity: 0.6}}>✕</span> : null}

      {r.слова.map((w, i) => {
        if (i >= napechatano) return null;
        const slovo = w.w;
        const isOpora = i === opora;
        const num = cifra(slovo);
        // `ЭКРАН.md` §1.6 — опорное слово КАПСОМ. Исключение: имя собственное. «CHATGPT»
        // или «ИМПОРТ идей» на экране — это уже не акцент, а чужое написание
        // имени: `ЭКРАН.md` §3 требует не выдумывать фактуру, а имя пишется так, как
        // его пишет владелец. Крупность акцент держит и без капса — ровно как
        // с числом, которое тоже не капсится.
        //
        // Само решение сюда ПРИХОДИТ полем `опора_капсом` (`titry.py`,
        // `bez_kapsa`), а не считается здесь: признак — кончилась ли предыдущая
        // фраза, а этого внутри одной реплики не видно. Считать его в трёх
        // местах (компонент, В8, СЛОЙ.md) значит однажды разойтись — `ЭКРАН.md` §9
        // ровно про такую щель между «посчитали» и «нарисовалось».
        const pokaz = isOpora && r.опора_капсом !== false ? slovo.toUpperCase() : slovo;
        const razmer = vlezaet(
          num ? base * 1.4 : isOpora ? base * 1.8 : base,
          pokaz,
          boxPx,
          rech,
        );
        // по-слову: слово появляется, когда звучит. рез: вся реплика сразу.
        if (r.анимация === 'по-слову' && t < w.s - 0.02) return null;
        const struck = (зачеркнуть[ri] || []).includes(i);

        return (
          <span
            key={i}
            style={{
              position: 'relative',
              display: 'inline-block',
              // Правка: опорное слово НЕ меняет шрифт — только
              // размер и капс. Manrope рядом с Prata читался как чужая
              // вставка, а `ЭКРАН.md` §1 требует одного шрифта на все реплики.
              //
              // Правка: то же самое относится и к числам. PT Mono
              // стоял здесь по `ЭКРАН.md` §0 («число внутри строки — PT Mono»), но на
              // приёмке ролик читался как чужая гарнитура посреди Prata. Число
              // осталось крупнее и с кобальтовой полосой — этого хватает,
              // чтобы оно выделялось, а шрифт теперь один на всю реплику.
              fontFamily: rech,
              fontWeight: 400,
              fontSize: razmer,
              letterSpacing: isOpora ? '-0.01em' : 0,
            }}
          >
            {r.знак === '<' && isOpora ? <span style={{opacity: 0.55}}>&lt;&nbsp;</span> : null}
            {pokaz}
            {r.знак === '<' && isOpora ? <span style={{opacity: 0.55}}>&nbsp;&gt;</span> : null}
            {num && !struck ? (
              <span
                style={{
                  position: 'absolute',
                  left: 0,
                  right: 0,
                  bottom: -razmer * 0.14,
                  height: Math.max(3, razmer * 0.07),
                  borderRadius: 99,
                  background: C.blue,
                }}
              />
            ) : null}
            {struck ? (
              <span
                style={{
                  position: 'absolute',
                  left: -4,
                  right: -4,
                  top: '48%',
                  height: Math.max(4, razmer * 0.08),
                  borderRadius: 99,
                  background: C.blue,
                  transform: `scaleX(${interpolate(t, [w.e + 0.04, w.e + 0.3], [0, 1], {
                    extrapolateLeft: 'clamp',
                    extrapolateRight: 'clamp',
                  })})`,
                  transformOrigin: 'left center',
                }}
              />
            ) : null}
          </span>
        );
      })}

      {r.анимация === 'печать' && napechatano <= r.слова.length ? (
        // курсор кобальтовый — тот же цвет, что у подчёркивания числа и у
        // знаков-маркеров: на экране один служебный цвет, а не два
        <span
          style={{
            fontFamily: mono,
            fontSize: base * 0.9,
            color: C.blue,
            opacity: frame % 16 < 8 ? 1 : 0.2,
          }}
        >
          ▮
        </span>
      ) : null}
      {r.знак === '(' ? <span style={znakStyle}>)</span> : null}
      {r.знак === '<<' ? <span style={znakStyle}>&raquo;&raquo;</span> : null}
      {r.знак === '✕' ? <span style={{...znakStyle, color: cvetTeksta, opacity: 0.6}}>✕</span> : null}
      {/* конец реплики — жёсткая склейка: затухания нет (`ЭКРАН.md` §1.1) */}
      <span style={{display: 'none'}}>{end}</span>
    </div>
  );
};
