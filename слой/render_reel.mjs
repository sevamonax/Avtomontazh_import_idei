// Рендер слоя вертикального рилза: субтитры + акценты, одним файлом с альфой.
//
//   node render_reel.mjs "../проекты/ПРИМЕР/titry.json" "../проекты/ПРИМЕР/выход/слой.mov"
//
// Почему одним файлом, а не по клипу на элемент: в вертикали субтитры
// сплошные и занимают почти весь хронометраж
// (`ЭКРАН.md`). Резать такой слой на клипы смысла нет — экономии не будет,
// а стыков станет столько же, сколько реплик.
//
// ProRes 4444, а не VP9 с альфой: слой — это текст, и лишнее сжатие видно на
// краях букв. Файл получается тяжёлым, но он временный — после наложения его
// удаляет `nalozhit.py`.

import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const планФайл = process.argv[2];
const выход = process.argv[3];
if (!планФайл || !выход) {
  console.error('нужно: node render_reel.mjs <titry.json> <выход.mov>');
  process.exit(1);
}

const план = JSON.parse(fs.readFileSync(планФайл, 'utf8'));
fs.mkdirSync(path.dirname(выход), {recursive: true});

// Структура плана поменялась после приёмки 04.08: слова теперь лежат внутри
// реплик, а не общим списком. Проверяем её здесь, чтобы падать понятно, а не
// на `undefined.length` посреди бандла.
for (const поле of ['реплики', 'элементы', 'всего']) {
  if (план[поле] === undefined) {
    console.error(`в плане нет поля «${поле}» — пересобери titry.py`);
    process.exit(1);
  }
}
const словВсего = план.реплики.reduce((n, р) => n + р.слова.length, 0);
console.log(`бандл… (${словВсего} слов в ${план.реплики.length} репликах, ${план.элементы.length} акцентов, ${план.всего.toFixed(1)} с)`);
const t0 = Date.now();
const serveUrl = await bundle({entryPoint: path.join(ROOT, 'src/index.ts')});
console.log('бандл: %s c', ((Date.now() - t0) / 1000).toFixed(1));

const inputProps = {план};
const composition = await selectComposition({serveUrl, id: 'Reel', inputProps});
console.log(`композиция: ${composition.width}×${composition.height}, ${composition.durationInFrames} кадров`);

const tR = Date.now();
await renderMedia({
  composition,
  serveUrl,
  codec: 'prores',
  proResProfile: '4444',
  imageFormat: 'png',
  pixelFormat: 'yuva444p10le',
  outputLocation: выход,
  inputProps,
  concurrency: 4,
  logLevel: 'error',
  onProgress: ({renderedFrames}) => {
    if (renderedFrames % 300 === 0) {
      const с = (Date.now() - tR) / 1000;
      const всего = composition.durationInFrames;
      console.log(
        `  ${renderedFrames}/${всего} · ${с.toFixed(0)} c, осталось ~${(
          (с / Math.max(renderedFrames, 1)) * (всего - renderedFrames)
        ).toFixed(0)} c`,
      );
    }
  },
});

console.log(`готово за ${((Date.now() - tR) / 1000).toFixed(0)} c → ${выход}`);
