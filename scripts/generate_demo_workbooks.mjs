import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(
  "/Users/tbwtk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/loader.js",
);
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const corpus = path.join(root, "examples", "acme-corp");
const qaDir = "/private/tmp/rag-demo-artifacts/xlsx";

const colors = {
  navy: "#17324D",
  teal: "#149A9A",
  pale: "#EAF3F3",
  ink: "#263746",
  muted: "#607080",
  white: "#FFFFFF",
  line: "#CBD7DF",
};

async function renderSheet(workbook, sheetName, outputName) {
  const preview = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(qaDir, outputName),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

function applyTitle(sheet, range, title) {
  sheet.getRange(range).merge();
  const cell = sheet.getRange(range.split(":")[0]);
  cell.values = [[title]];
  cell.format = {
    fill: colors.navy,
    font: { bold: true, color: colors.white, size: 18 },
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 34;
}

function applyHeader(sheet, range) {
  sheet.getRange(range).format = {
    fill: colors.teal,
    font: { bold: true, color: colors.white },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: colors.white },
  };
  sheet.getRange(range).format.rowHeight = 30;
}

function applyBody(sheet, range) {
  sheet.getRange(range).format = {
    font: { color: colors.ink },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: colors.line },
  };
}

async function createEquipmentRegister() {
  const workbook = Workbook.create();
  const registry = workbook.worksheets.add("Оборудование");
  const summary = workbook.worksheets.add("Сводка");

  registry.showGridLines = false;
  applyTitle(registry, "A1:H1", "ACME CORP  /  Реестр оборудования");
  registry.getRange("A2:H2").merge();
  registry.getRange("A2").values = [[
    "Контрольная выгрузка на 01.08.2025 • владелец: IT Operations • статусы используются при возврате и замене техники",
  ]];
  registry.getRange("A2:H2").format = {
    fill: colors.pale,
    font: { color: colors.muted, italic: true },
    wrapText: true,
  };
  registry.getRange("A3:H11").values = [
    ["Инв. номер", "Категория", "Модель", "Сотрудник", "Подразделение", "Дата выдачи", "Статус", "Стоимость, ₽"],
    ["AC-LT-0142", "Ноутбук", "ThinkPad T14", "Анна Белова", "Продажи", "02.09.2024", "Выдано", 168000],
    ["AC-LT-0157", "Ноутбук", "MacBook Pro 14", "Илья Морозов", "Инженерный отдел", "13.01.2025", "Выдано", 245000],
    ["AC-LT-0161", "Ноутбук", "MacBook Air 13", "Мария Волкова", "Продукт", "03.02.2025", "Выдано", 154000],
    ["AC-MN-0088", "Монитор", "Dell U2723QE", "Илья Морозов", "Инженерный отдел", "13.01.2025", "Выдано", 72000],
    ["AC-PH-0041", "Телефон", "iPhone 15", "Анна Белова", "Продажи", "02.09.2024", "Выдано", 98000],
    ["AC-LT-0172", "Ноутбук", "ThinkPad T14", "Резерв", "IT Operations", null, "На складе", 171000],
    ["AC-MN-0094", "Монитор", "Dell U2723QE", "Резерв", "IT Operations", null, "На складе", 74000],
    ["AC-LT-0099", "Ноутбук", "ThinkPad X1", "Списание", "IT Operations", "10.05.2021", "К списанию", 187000],
  ];
  applyHeader(registry, "A3:H3");
  applyBody(registry, "A4:H11");
  registry.getRange("H4:H11").format.numberFormat = "#,##0 [$₽-ru-RU]";
  registry.getRange("A4:H11").conditionalFormats.add("Custom", {
    formula: "=$G4=\"К списанию\"",
    format: { fill: "#FDECEC", font: { color: "#9B2C2C" } },
  });
  registry.freezePanes.freezeRows(3);
  const widths = [15, 15, 22, 20, 21, 15, 15, 17];
  widths.forEach((width, index) => {
    registry.getRangeByIndexes(0, index, 11, 1).format.columnWidth = width;
  });

  summary.showGridLines = false;
  applyTitle(summary, "A1:D1", "Сводка по активам");
  summary.getRange("A3:B7").values = [
    ["Показатель", "Значение"],
    ["Всего объектов", null],
    ["Выдано сотрудникам", null],
    ["На складе", null],
    ["К списанию", null],
  ];
  summary.getRange("B4").formulas = [["=COUNTA('Оборудование'!A4:A11)"]];
  summary.getRange("B5").formulas = [["=COUNTIF('Оборудование'!G4:G11,\"Выдано\")"]];
  summary.getRange("B6").formulas = [["=COUNTIF('Оборудование'!G4:G11,\"На складе\")"]];
  summary.getRange("B7").formulas = [["=COUNTIF('Оборудование'!G4:G11,\"К списанию\")"]];
  applyHeader(summary, "A3:B3");
  applyBody(summary, "A4:B7");
  summary.getRange("A9:D9").merge();
  summary.getRange("A9").values = [[
    "Правило: сотрудник возвращает оборудование в IT Operations в последний рабочий день. Замена оформляется новой строкой с уникальным инвентарным номером.",
  ]];
  summary.getRange("A9:D9").format = {
    fill: colors.pale,
    font: { color: colors.ink },
    wrapText: true,
  };
  summary.getRange("A9:D9").format.rowHeight = 52;
  summary.getRange("A:D").format.columnWidth = 22;

  await renderSheet(workbook, "Оборудование", "equipment-register.png");
  await renderSheet(workbook, "Сводка", "equipment-summary.png");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(path.join(corpus, "equipment_register.xlsx"));
}

async function createLeaveCalendar() {
  const workbook = Workbook.create();
  const absences = workbook.worksheets.add("Отсутствия");
  const rules = workbook.worksheets.add("Правила");

  absences.showGridLines = false;
  applyTitle(absences, "A1:H1", "ACME CORP  /  Календарь отсутствий");
  absences.getRange("A2:H2").merge();
  absences.getRange("A2").values = [[
    "План на август—октябрь 2025 • рабочие дни приведены для планирования нагрузки и не заменяют кадровый приказ",
  ]];
  absences.getRange("A2:H2").format = {
    fill: colors.pale,
    font: { color: colors.muted, italic: true },
    wrapText: true,
  };
  absences.getRange("A3:H9").values = [
    ["Сотрудник", "Подразделение", "Вид отсутствия", "Начало", "Окончание", "Календарных дней", "Статус", "Замещающий"],
    ["Анна Белова", "Продажи", "Ежегодный отпуск", "11.08.2025", "22.08.2025", 12, "Утверждено", "Павел Орлов"],
    ["Илья Морозов", "Инженерный отдел", "Ежегодный отпуск", "01.09.2025", "12.09.2025", 12, "Утверждено", "Ольга Ким"],
    ["Мария Волкова", "Продукт", "Учебный отпуск", "15.09.2025", "19.09.2025", 5, "На согласовании", "Денис Лебедев"],
    ["Павел Орлов", "Продажи", "Ежегодный отпуск", "06.10.2025", "17.10.2025", 12, "Запланировано", "Анна Белова"],
    ["Ольга Ким", "Инженерный отдел", "Ежегодный отпуск", "25.08.2025", "29.08.2025", 5, "Утверждено", "Илья Морозов"],
    ["Денис Лебедев", "Продукт", "Отгул", "15.08.2025", "15.08.2025", 1, "Утверждено", "Мария Волкова"],
  ];
  applyHeader(absences, "A3:H3");
  applyBody(absences, "A4:H9");
  absences.getRange("F4:F9").format.numberFormat = "0";
  absences.getRange("A4:H9").conditionalFormats.add("Custom", {
    formula: "=$G4=\"На согласовании\"",
    format: { fill: "#FFF4D6", font: { color: "#7A5600" } },
  });
  absences.freezePanes.freezeRows(3);
  [20, 21, 21, 14, 14, 17, 18, 20].forEach((width, index) => {
    absences.getRangeByIndexes(0, index, 9, 1).format.columnWidth = width;
  });

  rules.showGridLines = false;
  applyTitle(rules, "A1:D1", "Правила планирования отсутствий");
  rules.getRange("A3:D3").values = [["№", "Правило", "Кто согласует", "Срок"]];
  rules.getRange("A4:D8").values = [
    [1, "Ежегодный отпуск продолжительностью более пяти рабочих дней", "Руководитель и HR", "Не позднее чем за 14 календарных дней"],
    [2, "Одновременное отсутствие двух сотрудников одной критической роли", "Директор подразделения", "До утверждения обеих заявок"],
    [3, "Учебный отпуск", "Руководитель и HR после проверки справки-вызова", "Не позднее чем за 7 календарных дней"],
    [4, "Отгул за ранее отработанное время", "Непосредственный руководитель", "Не позднее предыдущего рабочего дня"],
    [5, "Изменение уже утверждённого периода", "Те же согласующие, что для исходной заявки", "До начала нового периода"],
  ];
  applyHeader(rules, "A3:D3");
  applyBody(rules, "A4:D8");
  rules.getRange("A:A").format.columnWidth = 7;
  rules.getRange("B:B").format.columnWidth = 45;
  rules.getRange("C:C").format.columnWidth = 32;
  rules.getRange("D:D").format.columnWidth = 32;
  rules.getRange("A4:D8").format.rowHeight = 44;

  await renderSheet(workbook, "Отсутствия", "leave-absences.png");
  await renderSheet(workbook, "Правила", "leave-rules.png");
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(path.join(corpus, "leave_calendar.xlsx"));
}

await fs.mkdir(qaDir, { recursive: true });
await createEquipmentRegister();
await createLeaveCalendar();
