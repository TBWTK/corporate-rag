import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(
  "/Users/tbwtk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/loader.js",
);
const { Presentation, PresentationFile } = require("@oai/artifact-tool");

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const corpus = path.join(root, "examples", "acme-corp");
const qaDir = "/private/tmp/rag-demo-artifacts/pptx";

const C = {
  bg: "#F4F7F8",
  navy: "#17324D",
  teal: "#149A9A",
  pale: "#E4F1F1",
  white: "#FFFFFF",
  ink: "#263746",
  muted: "#607080",
  line: "#C8D6DE",
  amber: "#F1B94A",
};

function box(slide, name, position, fill = C.white, line = C.line, radius = "rounded-xl") {
  return slide.shapes.add({
    geometry: "roundRect",
    name,
    position,
    fill,
    line: { style: "solid", fill: line, width: 1 },
    borderRadius: radius,
  });
}

function textBox(slide, name, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontFamily: "Arial",
    fontSize: 20,
    color: C.ink,
    ...style,
  };
  return shape;
}

function addFooter(slide, number, label) {
  textBox(slide, `footer-${number}`, `ACME CORP  /  ${label}`, { left: 72, top: 676, width: 620, height: 20 }, {
    fontSize: 10,
    bold: true,
    color: C.muted,
  });
  textBox(slide, `page-${number}`, String(number).padStart(2, "0"), { left: 1150, top: 676, width: 58, height: 20 }, {
    fontSize: 10,
    bold: true,
    color: C.teal,
  });
}

function addSlideOne(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = C.bg;

  textBox(slide, "eyebrow", "ЗАКУПКИ · РЕДАКЦИЯ 01.08.2025", { left: 72, top: 62, width: 480, height: 24 }, {
    fontSize: 12,
    bold: true,
    color: C.teal,
  });
  textBox(slide, "title", "Как выбрать маршрут согласования закупки", { left: 72, top: 126, width: 600, height: 132 }, {
    fontSize: 42,
    bold: true,
    color: C.navy,
  });
  textBox(slide, "subtitle", "Суммы недостаточно: сначала определите вид расхода — операционный или капитальный.", { left: 72, top: 288, width: 570, height: 94 }, {
    fontSize: 21,
    color: C.muted,
  });

  const signal = box(slide, "signal", { left: 72, top: 438, width: 570, height: 136 }, C.pale, C.teal);
  textBox(slide, "signal-label", "КЛЮЧЕВОЙ ВОПРОС", { left: signal.position.left + 28, top: signal.position.top + 24, width: 250, height: 22 }, {
    fontSize: 11,
    bold: true,
    color: C.teal,
  });
  textBox(slide, "signal-question", "Покупка создаёт новый актив или поддерживает текущую деятельность?", { left: signal.position.left + 28, top: signal.position.top + 58, width: 510, height: 58 }, {
    fontSize: 20,
    bold: true,
    color: C.navy,
  });

  const cards = [
    { top: 126, value: "600 000 ₽", label: "может иметь два разных маршрута", color: C.navy },
    { top: 282, value: "2–3", label: "коммерческих предложения", color: C.teal },
    { top: 438, value: "5–7 лет", label: "срок хранения документов", color: C.amber },
  ];
  cards.forEach((item, index) => {
    const card = box(slide, `metric-${index}`, { left: 732, top: item.top, width: 476, height: 126 });
    textBox(slide, `metric-value-${index}`, item.value, { left: card.position.left + 28, top: card.position.top + 22, width: 210, height: 42 }, {
      fontSize: 30,
      bold: true,
      color: item.color,
    });
    textBox(slide, `metric-label-${index}`, item.label, { left: card.position.left + 250, top: card.position.top + 30, width: 190, height: 58 }, {
      fontSize: 16,
      color: C.muted,
    });
  });
  addFooter(slide, 1, "Политика закупок");
}

function addSlideTwo(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = C.bg;
  textBox(slide, "eyebrow", "МАТРИЦА ПОРОГОВ", { left: 72, top: 52, width: 360, height: 24 }, {
    fontSize: 12,
    bold: true,
    color: C.teal,
  });
  textBox(slide, "title", "Один бюджет — разные согласующие", { left: 72, top: 88, width: 820, height: 62 }, {
    fontSize: 34,
    bold: true,
    color: C.navy,
  });
  textBox(slide, "subtitle", "Порог определяется суммой без НДС. Количество предложений — минимальное.", { left: 72, top: 150, width: 880, height: 32 }, {
    fontSize: 16,
    color: C.muted,
  });

  textBox(slide, "opex-title", "ОПЕРАЦИОННЫЕ РАСХОДЫ", { left: 72, top: 218, width: 540, height: 28 }, {
    fontSize: 13,
    bold: true,
    color: C.teal,
  });
  textBox(slide, "capex-title", "КАПИТАЛЬНЫЕ РАСХОДЫ", { left: 668, top: 218, width: 540, height: 28 }, {
    fontSize: 13,
    bold: true,
    color: C.teal,
  });

  const opex = [
    ["до 100 000 ₽", "Руководитель подразделения · 1 предложение"],
    ["100 001–500 000 ₽", "Финансовый контролёр + руководитель · 2 предложения"],
    ["свыше 500 000 ₽", "Закупочная комиссия · 3 предложения"],
  ];
  const capex = [
    ["до 250 000 ₽", "Владелец бюджета + финансовый контролёр · 2 предложения"],
    ["250 001–1 000 000 ₽", "Закупочная комиссия + CFO · 3 предложения"],
    ["свыше 1 000 000 ₽", "Генеральный директор + комиссия · 3 предложения"],
  ];

  [opex, capex].forEach((items, column) => {
    items.forEach(([amount, route], row) => {
      const card = box(slide, `threshold-${column}-${row}`, {
        left: column === 0 ? 72 : 668,
        top: 258 + row * 124,
        width: 540,
        height: 100,
      });
      textBox(slide, `amount-${column}-${row}`, amount, { left: card.position.left + 22, top: card.position.top + 20, width: 190, height: 34 }, {
        fontSize: 18,
        bold: true,
        color: C.navy,
      });
      textBox(slide, `route-${column}-${row}`, route, { left: card.position.left + 220, top: card.position.top + 17, width: 290, height: 60 }, {
        fontSize: 14,
        color: C.muted,
      });
    });
  });
  addFooter(slide, 2, "Пороги без НДС");
}

function addSlideThree(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = C.bg;
  textBox(slide, "eyebrow", "КОНТРОЛЬНЫЙ МАРШРУТ", { left: 72, top: 52, width: 390, height: 24 }, {
    fontSize: 12,
    bold: true,
    color: C.teal,
  });
  textBox(slide, "title", "От потребности до сохранённого решения", { left: 72, top: 88, width: 880, height: 62 }, {
    fontSize: 34,
    bold: true,
    color: C.navy,
  });

  const steps = [
    ["01", "Определить тип", "Зафиксировать OpEx или CapEx и владельца бюджета."],
    ["02", "Собрать предложения", "Получить требуемое число сопоставимых коммерческих предложений."],
    ["03", "Проверить поставщика", "Проверить реквизиты, конфликт интересов и требования ИБ."],
    ["04", "Согласовать", "Направить пакет согласующим из соответствующей строки матрицы."],
    ["05", "Сохранить", "Хранить решение и предложения 5 лет для OpEx, 7 лет для CapEx."],
  ];
  steps.forEach(([number, heading, body], index) => {
    const left = 72 + index * 228;
    const card = box(slide, `step-${number}`, { left, top: 218, width: 204, height: 250 }, index === 0 ? C.pale : C.white, index === 0 ? C.teal : C.line);
    textBox(slide, `step-number-${number}`, number, { left: card.position.left + 22, top: card.position.top + 20, width: 52, height: 32 }, {
      fontSize: 20,
      bold: true,
      color: C.teal,
    });
    textBox(slide, `step-heading-${number}`, heading, { left: card.position.left + 22, top: card.position.top + 76, width: 160, height: 50 }, {
      fontSize: 18,
      bold: true,
      color: C.navy,
    });
    textBox(slide, `step-body-${number}`, body, { left: card.position.left + 22, top: card.position.top + 138, width: 160, height: 88 }, {
      fontSize: 13,
      color: C.muted,
    });
  });

  const note = box(slide, "evidence-note", { left: 72, top: 512, width: 1136, height: 112 }, C.navy, C.navy);
  textBox(slide, "evidence-label", "ПОЛНЫЙ ПАКЕТ", { left: note.position.left + 28, top: note.position.top + 24, width: 170, height: 24 }, {
    fontSize: 11,
    bold: true,
    color: "#77D1D0",
  });
  textBox(slide, "evidence-text", "Заявка · обоснование категории · предложения · проверка поставщика · решение согласующих · договор и счёт", { left: note.position.left + 210, top: note.position.top + 22, width: 880, height: 52 }, {
    fontSize: 17,
    bold: true,
    color: C.white,
  });
  addFooter(slide, 3, "Процесс и доказательства");
}

async function writeBlob(outputPath, blob) {
  await fs.writeFile(outputPath, new Uint8Array(await blob.arrayBuffer()));
}

await fs.mkdir(qaDir, { recursive: true });
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
addSlideOne(presentation);
addSlideTwo(presentation);
addSlideThree(presentation);

for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(qaDir, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(qaDir, `${stem}.layout.json`), await layout.text());
}
await writeBlob(path.join(qaDir, "montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));
const deck = await PresentationFile.exportPptx(presentation);
await deck.save(path.join(corpus, "procurement_policy.pptx"));
