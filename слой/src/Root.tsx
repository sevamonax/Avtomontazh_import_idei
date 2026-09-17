import React from 'react';
import {Composition} from 'remotion';
import {Reel} from './Reel';

/**
 * Композиция одна на все ролики.
 *
 * 🔑 ПОЧЕМУ НЕ ПО КОМПОЗИЦИИ НА РОЛИК. Роликов за один заход выходит пять-десять.
 * Заводить каждому свою композицию — это то же самое, что писать монтаж руками:
 * механизм перестаёт быть механизмом ровно в тот момент, когда под новый ролик
 * надо трогать код. Весь план приходит `inputProps` из `render_reel.mjs`,
 * поэтому композиция здесь ровно одна и меняться от ролика к ролику ей нечем.
 *
 * `calculateMetadata` берёт длину из плана. Без этого слой обрежется по
 * `durationInFrames` ниже, и хвост ролика уедет без субтитров — причём тихо:
 * файл отрендерится, наложится и будет выглядеть исправным.
 */
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Reel"
      component={Reel}
      durationInFrames={900}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        план: {
          всего: 30,
          реплики: [],
          лицо: [],
          заголовок: null,
          элементы: [],
          гасить: [],
        },
      }}
      calculateMetadata={({props}) => ({
        durationInFrames: Math.max(
          30,
          Math.round(((props as {план: {всего: number}}).план.всего ?? 30) * 30),
        ),
      })}
    />
  );
};
