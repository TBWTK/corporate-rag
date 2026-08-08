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

async function saveWorkbook(workbook, outputName) {
  const outputPath = path.join(corpus, outputName);
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  await fs.rm(`${outputPath}.inspect.ndjson`, { force: true });
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
  await saveWorkbook(workbook, "equipment_register.xlsx");
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
  await saveWorkbook(workbook, "leave_calendar.xlsx");
}

async function createWorkScheduleAndAdaptation() {
  const workbook = Workbook.create();
  const schedules = workbook.worksheets.add("Графики");
  const adaptation = workbook.worksheets.add("Адаптация");
  const access = workbook.worksheets.add("Доступы");

  schedules.showGridLines = false;
  applyTitle(schedules, "A1:H1", "ACME CORP  /  Графики и форматы работы");
  schedules.getRange("A2:H2").merge();
  schedules.getRange("A2").values = [[
    "Базовая матрица на 01.10.2025 • действующее дополнительное соглашение имеет приоритет в своей области",
  ]];
  schedules.getRange("A2:H2").format = {
    fill: colors.pale,
    font: { color: colors.muted, italic: true },
    wrapText: true,
  };
  schedules.getRange("A3:H11").values = [
    ["Подразделение / роль", "Формат", "Рабочий цикл", "Начало", "Окончание", "Обязательный офис", "Удалённый лимит", "Приоритетный источник"],
    ["Продажи", "Гибрид", "Пн–Пт", "09:00", "18:00", "Вторник и четверг", "До 3 дней", "RW-SALES-2025"],
    ["Инженерный отдел", "Гибрид", "Пн–Пт", "10:00", "19:00", "Среда", "До 4 дней", "RW-ENG-2025"],
    ["Продукт", "Гибрид", "Пн–Пт", "10:00", "19:00", "Вторник и четверг", "До 2 дней", "Политика форматов работы"],
    ["Финансы", "Преимущественно офис", "Пн–Пт", "09:00", "18:00", "Пн–Чт и последние 3 дня месяца", "Пятница", "RW-FIN-2025"],
    ["Поддержка L1", "Сменный", "2/2", "08:00 или 20:00", "20:00 или 08:00", "Дневная смена", "Ночная смена", "SHIFT-SUPPORT-2025"],
    ["Поддержка L2", "Сменный гибрид", "2/2", "08:00 или 20:00", "20:00 или 08:00", "По графику", "2 дневные смены в месяц + ночные", "SHIFT-SUPPORT-2025"],
    ["Дизайн", "Гибрид", "Пн–Пт", "10:00", "19:00", "Вторник и четверг", "До 3 дней", "RW-DESIGN-2025"],
    ["Региональный офис", "Гибрид", "Пн–Пт", "09:00", "18:00", "Не менее 1 дня", "До 4 дней", "RW-REG-2025"],
  ];
  applyHeader(schedules, "A3:H3");
  applyBody(schedules, "A4:H11");
  schedules.freezePanes.freezeRows(3);
  schedules.getRange("A4:H11").format.rowHeight = 42;
  [24, 20, 16, 17, 17, 30, 28, 28].forEach((width, index) => {
    schedules.getRangeByIndexes(0, index, 11, 1).format.columnWidth = width;
  });

  adaptation.showGridLines = false;
  applyTitle(adaptation, "A1:G1", "ACME CORP  /  План адаптации 30–60–90");
  adaptation.getRange("A2").values = [["Дата выхода"]];
  adaptation.getRange("B2").values = [[new Date("2025-10-06T00:00:00Z")]];
  adaptation.getRange("B2").format.numberFormat = "yyyy-mm-dd";
  adaptation.getRange("C2:G2").merge();
  adaptation.getRange("C2").values = [[
    "Контрольные даты рассчитываются от даты выхода; фактическое завершение фиксируется в HR Portal",
  ]];
  adaptation.getRange("A2:G2").format = {
    fill: colors.pale,
    font: { color: colors.muted, italic: true },
    wrapText: true,
  };
  adaptation.getRange("A4:G13").values = [
    ["День", "Контрольная дата", "Действие", "Ответственный", "Результат", "Особенность подразделения", "Статус"],
    [0, null, "Активировать ACME ID и получить оборудование", "Сотрудник + IT", "MFA и MDM работают", "Для всех", "Обязательно"],
    [1, null, "Пройти охрану труда и безопасность", "Сотрудник", "Тест не ниже 80%", "До выдачи специальных доступов", "Обязательно"],
    [2, null, "Встреча с наставником и обзор инструментов", "Наставник", "Чек-лист первой недели", "Инженеры: обзор GitLab; продажи: CRM", "Обязательно"],
    [4, null, "Изучить продукты и культурный код", "Сотрудник", "Ответы на контрольные вопросы", "Продукт: разбор пользовательского сценария", "Обязательно"],
    [7, null, "Согласовать цели на 30 дней", "Руководитель", "Три измеримые цели", "Поддержка: допуск к самостоятельной смене", "Обязательно"],
    [14, null, "Выполнить первую задачу с наставником", "Сотрудник", "Принятый рабочий результат", "Зависит от роли", "Обязательно"],
    [30, null, "Контрольная встреча 30 дней", "Руководитель", "Обратная связь и обновлённые цели", "Для всех", "Контроль"],
    [60, null, "Контрольная встреча 60 дней", "Руководитель", "Оценка самостоятельности", "Для всех", "Контроль"],
    [90, null, "Итоги испытательного срока", "Руководитель + People Ops", "Решение зафиксировано в HR Portal", "Для всех", "Контроль"],
  ];
  adaptation.getRange("B5").formulas = [["=$B$2+A5"]];
  adaptation.getRange("B5:B13").fillDown();
  adaptation.getRange("B5:B13").format.numberFormat = "yyyy-mm-dd";
  applyHeader(adaptation, "A4:G4");
  applyBody(adaptation, "A5:G13");
  adaptation.getRange("A5:A13").format.numberFormat = "0";
  adaptation.getRange("A5:G13").format.rowHeight = 44;
  adaptation.getRange("A5:G13").conditionalFormats.add("Custom", {
    formula: "=$G5=\"Обязательно\"",
    format: { fill: "#EAF3F3", font: { color: colors.navy } },
  });
  adaptation.freezePanes.freezeRows(4);
  [10, 18, 38, 25, 32, 38, 16].forEach((width, index) => {
    adaptation.getRangeByIndexes(0, index, 13, 1).format.columnWidth = width;
  });

  access.showGridLines = false;
  applyTitle(access, "A1:F1", "Доступы нового сотрудника");
  access.getRange("A3:F10").values = [
    ["Система", "Назначение", "Кому нужна", "Согласующие", "Целевой срок", "Предусловие"],
    ["CorpMail / Connect", "Почта и коммуникации", "Все сотрудники", "Автоматически", "До 4 часов", "Активация HR"],
    ["Corporate VPN", "Удалённый доступ", "Гибрид и удалённые роли", "IT Security", "1 рабочий день", "Тренинг по ИБ"],
    ["CRM", "Сделки и клиенты", "Продажи", "Руководитель + Sales Ops", "2 рабочих дня", "Обучение CRM"],
    ["GitLab", "Код и CI/CD", "Инженерия", "Руководитель + владелец репозитория", "1 рабочий день", "Тренинг по ИБ"],
    ["BI", "Отчётность", "Аналитики и руководители", "Руководитель + владелец данных", "3 рабочих дня", "Обоснование набора данных"],
    ["HR Portal", "Кадровые документы", "Все сотрудники", "Автоматически", "До 4 часов", "Активация HR"],
    ["Привилегированный", "Администрирование", "Назначенные администраторы", "Руководитель + IT Security", "5 рабочих дней", "Отдельное обоснование"],
  ];
  applyHeader(access, "A3:F3");
  applyBody(access, "A4:F10");
  access.getRange("A4:F10").format.rowHeight = 42;
  access.freezePanes.freezeRows(3);
  [24, 30, 28, 38, 20, 30].forEach((width, index) => {
    access.getRangeByIndexes(0, index, 10, 1).format.columnWidth = width;
  });

  await renderSheet(workbook, "Графики", "work-schedules.png");
  await renderSheet(workbook, "Адаптация", "adaptation-plan.png");
  await renderSheet(workbook, "Доступы", "onboarding-access.png");
  await saveWorkbook(workbook, "work_schedule_and_adaptation.xlsx");
}

await fs.mkdir(qaDir, { recursive: true });
await createEquipmentRegister();
await createLeaveCalendar();
await createWorkScheduleAndAdaptation();
