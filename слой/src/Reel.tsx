import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont as loadSerif} from '@remotion/google-fonts/Prata';
import {loadFont as loadSans} from '@remotion/google-fonts/Manrope';
import {loadFont as loadMono} from '@remotion/google-fonts/PTMono';
import {Subtitles, type Litso, type Replika, type Ton} from './Subtitles';
import {Znak, ЕСТЬ_ЗНАК} from './Znachki';
import {VERT} from './zones';
import {C} from './tokens';
import {Scena} from './Sceny';

const {fontFamily: rech} = loadSerif('normal', {weights: ['400'], subsets: ['cyrillic', 'latin'], ignoreTooManyRequestsWarning: true});
const {fontFamily: sans} = loadSans('normal', {weights: ['400', '500', '600', '700', '800'], subsets: ['cyrillic', 'latin'], ignoreTooManyRequestsWarning: true});
const {fontFamily: mono} = loadMono('normal', {weights: ['400'], subsets: ['cyrillic', 'latin'], ignoreTooManyRequestsWarning: true});

/**
 * СЛОЙ ВЕРТИКАЛЬНОГО РИЛЗА — всё, что рисуется поверх картинки.
 *
 * Разбор правил экрана — `ЭКРАН.md`. Три из них держат этот файл целиком:
 *
 *  1. **Титр открытия не гасит субтитр** (`ЭКРАН.md` §1.1). Крупная надпись по центру
 *     кадра закрывает лицо и выключает расшифровку ровно на первых секундах —
 *     там, где зритель решает, смотреть ли дальше. Поэтому заголовок живёт в
 *     левом верхнем углу (`//. строка` плюс вторая строка в пилюле-контуре,
 *     4–5 с) и работает ВМЕСТЕ с субтитрами, а не вместо них.
 *  2. **Смена и уход — жёсткой склейкой** (`ЭКРАН.md` §1.1). Никаких затуханий: плавное
 *     появление читается как дефект кодека, а не как приём, и съедает те
 *     полсекунды, за которые надпись должна быть прочитана.
 *  3. **Врезка коротка** (`ЭКРАН.md` §1). Слайд держится ровно те секунды, пока звучит
 *     связующая фраза. Врезка на пять секунд закрывает лицо на самой мысли —
 *     то есть глушит ровно то, ради чего ролик снимался.
 */

export type Element = {
  приём: 'принцип' | 'канал' | 'сноска' | 'инфографика';
  t: number;
  конец: number;
  текст: string;
  значки?: string[];
  /** Только для приёма 'инфографика': ключ сцены в наборе `Sceny.tsx`. */
  сцена?: string;
  /** Подписи и числа этой сцены в этом ролик — сцена своя под каждый. */
  данные?: Record<string, string | number>;
};
export type Zagolovok = {строка1: string; строка2: string; t: number; конец: number};
export type ReelPlan = {
  всего: number;
  реплики: Replika[];
  лицо: Litso[];
  тон?: Ton[];
  заголовок: Zagolovok | null;
  элементы: Element[];
  гасить: [number, number][];
};

const useT = () => {
  const {fps} = useVideoConfig();
  return useCurrentFrame() / fps;
};

/**
 * Шапка-заголовок `ЭКРАН.md` §1.2 — покадрово с `ref1b`: строка 1 на 0.0 с, пилюля на
 * 0.4 с, обе держатся ~4–5 с и уходят резко. Тонкий контур, заливки нет.
 */
const Zagolovok: React.FC<{з: Zagolovok}> = ({з}) => {
  const t = useT();
  const {width} = useVideoConfig();
  const k = width / 1080;
  return (
    <div
      style={{
        position: 'absolute',
        left: `${VERT.бок * 100}%`,
        top: `${VERT.верх * 100 - 3.5}%`,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: 12 * k,
        textShadow: '0 2px 18px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{display: 'flex', alignItems: 'baseline', gap: 10 * k}}>
        {/* Знак `//.` кобальтом и мелко читался как две запятые — на проверке
            кадра он превращался в шум вместо префикса. Белый и вровень со
            строкой: это часть заголовка, а не значок рядом с ним. */}
        <span style={{fontFamily: mono, fontSize: 46 * k, color: C.white, opacity: 0.72}}>//.</span>
        <span style={{fontFamily: rech, fontSize: 56 * k, color: C.white}}>{з.строка1}</span>
      </div>
      {з.строка2 && t >= з.t + 0.4 ? (
        <span
          style={{
            fontFamily: rech,
            fontSize: 46 * k,
            color: C.white,
            border: `${Math.max(1.5, 2 * k)}px solid rgba(255,255,255,0.85)`,
            borderRadius: 999,
            padding: `${8 * k}px ${26 * k}px ${11 * k}px`,
          }}
        >
          {з.строка2}
        </span>
      ) : null}
    </div>
  );
};

/**
 * Врезка сплошным кобальтом (`ЭКРАН.md` §2, `НАСТРОЙКА.md`). Возникает и уходит РЕЗКО — `ЭКРАН.md` §1.1.
 * Текст — короткая главная мысль; длинную фразу режет `titry.py`, здесь только
 * оформление.
 */
const Princip: React.FC<{э: Element}> = ({э}) => {
  const {width} = useVideoConfig();
  const k = width / 1080;
  const знаки = (э.значки || []).filter(ЕСТЬ_ЗНАК).slice(0, 2);
  return (
    <AbsoluteFill style={{background: C.blue}}>
      {/* Правка: не резкая черта между цветами, а градиент. Диагональ
          дизайн-кода остаётся направлением света, но края у неё больше нет —
          жёсткая граница читалась как шов, а не как приём. */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'linear-gradient(115deg, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.06) 38%, rgba(0,0,0,0.10) 78%, rgba(0,0,0,0.20) 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: '9%',
          right: '9%',
          top: '50%',
          transform: 'translateY(-50%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 62 * k,
        }}
      >
        {/* 1–2 знака по смыслу (`ЭКРАН.md` §3). Подбирает механизм по словарю в
            `titry.py`; пустой список — просто нет знака, а не заглушка. */}
        {знаки.length ? (
          <div style={{display: 'flex', gap: 34 * k, opacity: 0.92}}>
            {знаки.map((з) => (
              <Znak key={з} имя={з} размер={116 * k} цвет={C.white} />
            ))}
          </div>
        ) : null}
        <div
          style={{
            fontFamily: rech,
            fontSize: 92 * k,
            lineHeight: 1.14,
            color: C.white,
            textAlign: 'center',
          }}
        >
          {э.текст}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/**
 * Плашка канала: знак файлом + название. Вход и уход резкие.
 *
 * 🔑 ЗНАК — ФАЙЛ, А НЕ КОД (`ЭКРАН.md` §3). Логотип не рисуется примитивами по памяти:
 * точность знака — это и есть знак, а нарисованный «похожий» контур читается
 * как чужая подделка. Кладите свой в `слой/public/бренд/знак.png`.
 *
 * Файла нет — плашка показывает одно название. Так и задумано: свежий клон
 * репозитория обязан рендериться, а не падать на отсутствующем логотипе.
 */
const ZNAK_FAJL = 'бренд/знак.png';

const Kanal: React.FC<{э: Element}> = ({э}) => {
  const {width} = useVideoConfig();
  const k = width / 1080;
  const [естьЗнак, setЕстьЗнак] = React.useState(true);
  return (
    <div
      style={{
        position: 'absolute',
        left: `${VERT.бок * 100}%`,
        bottom: `${VERT.низ * 100 + 3}%`,
        display: 'flex',
        alignItems: 'center',
        gap: естьЗнак ? 20 * k : 0,
        padding: `${14 * k}px ${28 * k}px ${14 * k}px ${естьЗнак ? 18 * k : 28 * k}px`,
        borderRadius: 16 * k,
        background: 'rgba(0,0,0,0.55)',
      }}
    >
      {естьЗнак ? (
        <Img
          src={staticFile(ZNAK_FAJL)}
          onError={() => setЕстьЗнак(false)}
          style={{width: 84 * k, height: 84 * k, objectFit: 'contain'}}
        />
      ) : null}
      <span style={{fontFamily: rech, fontSize: 52 * k, color: C.white}}>{э.текст}</span>
    </div>
  );
};

/**
 * Сноска — знак `*` из `ЭКРАН.md` §1.5. Наше уточнение к тому, что сказано в кадре: дата
 * опыта, точное написание фамилии, год работы. Живёт в зоне «низ» (`zones.ts`),
 * там же, где плашка канала, — но одновременно с ней не появляется, за этим
 * следит `titry.py`. Мельче и тусклее реплики: роль держат кегль и
 * прозрачность, а не вторая гарнитура (§«Шрифт», правка автора).
 * Вход и уход — резкие (`ЭКРАН.md` §1.1).
 */
const Snoska: React.FC<{э: Element}> = ({э}) => {
  const {width} = useVideoConfig();
  const k = width / 1080;
  return (
    <div
      style={{
        position: 'absolute',
        left: `${VERT.бок * 100}%`,
        bottom: `${VERT.низ * 100 + 3}%`,
        // Ширина ОГРАНИЧЕНА, и не на глаз: справа лежит колонка иконок Reels
        // (`zones.ts`, `праваяКолонка`), правее её границы ничего значимого
        // стоять не может. Предела не было вовсе — плашка росла по тексту, и на
        // ролик сноска «Google DeepMind — ИИ-подразделение Google» дотянулась до
        // правого края кадра. Поймала В12 замером альфы; текст здесь приходит от
        // автора, то есть длина его ничем не ограничена — значит предел нужен в
        // компоненте, а не в договорённости «писать покороче».
        maxWidth: `${(1 - VERT.бок - VERT.праваяКолонка) * 100}%`,
        display: 'flex',
        alignItems: 'baseline',
        gap: 14 * k,
        padding: `${10 * k}px ${24 * k}px ${13 * k}px ${20 * k}px`,
        borderRadius: 14 * k,
        background: 'rgba(0,0,0,0.55)',
      }}
    >
      <span style={{fontFamily: rech, fontSize: 40 * k, color: C.blueLight, opacity: 0.9}}>*</span>
      <span style={{fontFamily: rech, fontSize: 40 * k, color: C.white, opacity: 0.88}}>{э.текст}</span>
    </div>
  );
};

export const Reel: React.FC<{план: ReelPlan}> = ({план}) => {
  const t = useT();
  const gasnet = план.гасить.some(([a, b]) => t >= a && t < b);
  const zag = план.заголовок;

  return (
    <AbsoluteFill>
      {gasnet ? null : (
        <Subtitles репликы={план.реплики} лицо={план.лицо} тон={план.тон} />
      )}
      {zag && t >= zag.t && t < zag.конец ? <Zagolovok з={zag} /> : null}
      {план.элементы.map((э, i) => {
        if (t < э.t || t >= э.конец) return null;
        if (э.приём === 'принцип') return <Princip key={i} э={э} />;
        if (э.приём === 'сноска') return <Snoska key={i} э={э} />;
        if (э.приём === 'инфографика') {
          // Сцена, показывающая сам опыт (`ЭКРАН.md`). Неизвестное имя
          // рисует пустоту сознательно: кричать про это — работа гейта В16,
          // а падение рендера посреди пачки лечится дольше, чем красный гейт.
          const ход = (t - э.t) / Math.max(э.конец - э.t, 0.001);
          return (
            <Scena
              key={i}
              имя={э.сцена ?? ''}
              ход={Math.min(Math.max(ход, 0), 1)}
              данные={э.данные ?? {}}
            />
          );
        }
        return <Kanal key={i} э={э} />;
      })}
    </AbsoluteFill>
  );
};
