const state = {
  config: null,
  spaces: [],
  currentSpace: null,
  documents: [],
  relations: [],
  conversationId: null,
  polling: null,
  busy: false,
};
const INITIAL_SOURCE_LIMIT = 3;
const EXTERNAL_URL_PATTERN = /https?:\/\/[^\s<>"']+/gi;

const el = (id) => document.getElementById(id);

function appendLinkifiedText(container, text) {
  let cursor = 0;
  for (const match of text.matchAll(EXTERNAL_URL_PATTERN)) {
    const start = match.index;
    const raw = match[0];
    let visible = raw;
    let trailing = "";
    while (/[.,;!\])}]$/.test(visible)) {
      trailing = visible.slice(-1) + trailing;
      visible = visible.slice(0, -1);
    }
    let url;
    try { url = new URL(visible); } catch { continue; }
    if (!(url.protocol === "https:" || url.protocol === "http:")) continue;
    container.append(document.createTextNode(text.slice(cursor, start)));
    const link = document.createElement("a");
    link.className = "answer-link";
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = visible;
    container.append(link, document.createTextNode(trailing));
    cursor = start + raw.length;
  }
  container.append(document.createTextNode(text.slice(cursor)));
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  let payload;
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) throw new Error(payload.detail || `Ошибка HTTP ${response.status}`);
  return payload;
}

function toast(message, type = "info") {
  const node = el("toast");
  node.textContent = message;
  node.className = `toast visible ${type === "error" ? "error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.className = "toast"; }, 3600);
}

function initials(name) {
  return name.split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
}

function renderSpaces() {
  const list = el("space-list");
  list.replaceChildren();
  if (!state.spaces.length) {
    const empty = document.createElement("div");
    empty.className = "empty-compact";
    empty.textContent = "Создайте первое пространство";
    list.append(empty);
    return;
  }
  state.spaces.forEach((space) => {
    const button = document.createElement("button");
    button.className = `space-item ${state.currentSpace?.id === space.id ? "active" : ""}`;
    button.innerHTML = `<span class="space-symbol"></span><span class="space-name"></span><span class="space-count"></span>`;
    button.querySelector(".space-symbol").textContent = initials(space.name);
    button.querySelector(".space-name").textContent = space.name;
    button.querySelector(".space-count").textContent = space.document_count;
    button.addEventListener("click", () => selectSpace(space.id));
    list.append(button);
  });
}

const statusLabels = { queued: "В очереди", processing: "Индексируется", ready: "Готов", error: "Ошибка" };
const relationTypeLabels = {
  supplements: "дополняет",
  amends: "изменяет",
  supersedes: "заменяет",
  implements: "реализует требования",
  references: "ссылается на",
  attachment_to: "является приложением к",
};

function renderDocuments() {
  const list = el("document-list");
  el("document-count").textContent = state.documents.length;
  list.replaceChildren();
  if (!state.documents.length) {
    const empty = document.createElement("div");
    empty.className = "empty-compact";
    empty.textContent = "Документы появятся здесь после загрузки";
    list.append(empty);
  }
  state.documents.forEach((doc) => {
    const item = document.createElement("article");
    item.className = "document-item";
    const extension = doc.filename.split(".").pop().slice(0, 4);
    item.innerHTML = `
      <span class="file-icon"></span>
      <div><span class="document-name"></span><span class="document-meta"><i class="status-dot"></i><span class="status-label"></span><span class="chunk-count"></span></span></div>
      <div class="document-actions"></div>`;
    item.querySelector(".file-icon").textContent = extension;
    item.querySelector(".document-name").textContent = doc.filename;
    item.querySelector(".status-dot").classList.add(doc.status);
    item.querySelector(".status-label").textContent = statusLabels[doc.status] || doc.status;
    item.querySelector(".chunk-count").textContent = doc.chunk_count ? `· ${doc.chunk_count} фрагм.` : "";
    const relationCount = state.relations.filter((relation) => (
      relation.source_document_id === doc.id || relation.target_document_id === doc.id
    )).length;
    if (relationCount) {
      const relationMeta = document.createElement("span");
      relationMeta.className = "document-relation-count";
      relationMeta.textContent = `· ${relationCount} связ.`;
      item.querySelector(".document-meta").append(relationMeta);
    }
    if (doc.error) item.title = doc.error;
    const actions = item.querySelector(".document-actions");
    if (doc.status === "error") {
      const retry = window.document.createElement("button");
      retry.textContent = "↻";
      retry.title = "Повторить";
      retry.addEventListener("click", () => retryDocument(doc.id));
      actions.append(retry);
    }
    const remove = window.document.createElement("button");
    remove.textContent = "×";
    remove.title = "Удалить";
    remove.addEventListener("click", () => deleteDocument(doc.id, doc.filename));
    actions.append(remove);
    list.append(item);
  });
  updateComposer();
  renderRelationManager();
}

function fillDocumentSelect(select, documents, selectedValue) {
  select.replaceChildren();
  documents.forEach((doc) => {
    const option = document.createElement("option");
    option.value = doc.id;
    option.textContent = doc.filename;
    select.append(option);
  });
  if (documents.some((doc) => doc.id === selectedValue)) select.value = selectedValue;
}

function syncRelationTarget() {
  const sourceId = el("relation-source").value;
  const target = el("relation-target");
  [...target.options].forEach((option) => { option.disabled = option.value === sourceId; });
  if (target.value === sourceId) {
    const next = [...target.options].find((option) => !option.disabled);
    target.value = next?.value || "";
  }
}

function renderRelationManager() {
  const readyDocuments = state.documents.filter((doc) => doc.status === "ready");
  el("relation-count").textContent = state.relations.length;
  el("relations-button").disabled = readyDocuments.length < 2;
  const list = el("relation-list");
  list.replaceChildren();
  if (!state.relations.length) {
    const empty = document.createElement("div");
    empty.className = "relation-empty";
    empty.textContent = "Подтверждённых связей пока нет.";
    list.append(empty);
  }
  state.relations.forEach((relation) => {
    const item = document.createElement("article");
    item.className = "relation-item";
    const flow = document.createElement("div");
    flow.className = "relation-flow";
    const source = document.createElement("strong");
    source.textContent = relation.source_filename;
    const type = document.createElement("span");
    type.textContent = relationTypeLabels[relation.relation_type] || relation.relation_type;
    const target = document.createElement("strong");
    target.textContent = relation.target_filename;
    flow.append(source, type, target);
    const evidence = document.createElement("p");
    evidence.textContent = relation.evidence;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "relation-remove";
    remove.textContent = "×";
    remove.title = "Удалить связь";
    remove.setAttribute("aria-label", `Удалить связь ${relation.source_filename} — ${relation.target_filename}`);
    remove.addEventListener("click", () => deleteRelation(relation));
    item.append(flow, evidence, remove);
    list.append(item);
  });

  const sourceSelect = el("relation-source");
  const targetSelect = el("relation-target");
  const previousSource = sourceSelect.value;
  const previousTarget = targetSelect.value;
  fillDocumentSelect(sourceSelect, readyDocuments, previousSource);
  fillDocumentSelect(targetSelect, readyDocuments, previousTarget);
  syncRelationTarget();
  el("create-relation-submit").disabled = readyDocuments.length < 2;
}

function updateComposer() {
  const ready = state.documents.some((doc) => doc.status === "ready");
  el("question-input").disabled = !ready || state.busy;
  el("send-button").disabled = !ready || state.busy;
  el("composer-hint").textContent = ready ? "Ответ будет основан на готовых документах" : "Сначала загрузите документ";
}

async function loadSpaces() {
  state.spaces = await api("/api/spaces");
  const remembered = localStorage.getItem("rag-space-id");
  const selected = state.spaces.find((space) => space.id === remembered) || state.spaces[0];
  if (selected) await selectSpace(selected.id);
  else renderSpaces();
}

async function selectSpace(id) {
  state.currentSpace = state.spaces.find((space) => space.id === id);
  if (!state.currentSpace) return;
  localStorage.setItem("rag-space-id", id);
  state.conversationId = null;
  clearMessages();
  el("space-title").textContent = state.currentSpace.name;
  el("upload-button").disabled = false;
  el("drop-zone").classList.remove("disabled");
  renderSpaces();
  el("sidebar").classList.remove("open");
  state.relations = [];
  await loadDocuments();
  await loadRelations();
}

async function loadDocuments() {
  if (!state.currentSpace) return;
  state.documents = await api(`/api/spaces/${state.currentSpace.id}/documents`);
  renderDocuments();
  const pending = state.documents.some((doc) => ["queued", "processing"].includes(doc.status));
  clearTimeout(state.polling);
  if (pending) state.polling = setTimeout(loadDocuments, 1800);
}

async function loadRelations() {
  if (!state.currentSpace) return;
  state.relations = await api(`/api/spaces/${state.currentSpace.id}/relations`);
  renderDocuments();
}

async function uploadFiles(files) {
  if (!state.currentSpace || !files.length) return;
  const body = new FormData();
  [...files].forEach((file) => body.append("files", file));
  el("drop-zone").classList.add("disabled");
  try {
    const result = await api(`/api/spaces/${state.currentSpace.id}/documents`, { method: "POST", body });
    const message = result.duplicates.length
      ? `Добавлено: ${result.documents.length}. Уже были загружены: ${result.duplicates.length}.`
      : `Документы приняты: ${result.documents.length}`;
    toast(message);
    await loadDocuments();
    await loadSpacesOnly();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    el("drop-zone").classList.remove("disabled");
    el("file-input").value = "";
  }
}

async function loadSpacesOnly() {
  state.spaces = await api("/api/spaces");
  state.currentSpace = state.spaces.find((space) => space.id === state.currentSpace?.id) || null;
  renderSpaces();
}

async function retryDocument(id) {
  try { await api(`/api/documents/${id}/retry`, { method: "POST" }); await loadDocuments(); }
  catch (error) { toast(error.message, "error"); }
}

async function deleteDocument(id, name) {
  if (!confirm(`Удалить «${name}» из пространства?`)) return;
  try {
    await api(`/api/documents/${id}`, { method: "DELETE" });
    await loadDocuments();
    await loadRelations();
    await loadSpacesOnly();
  }
  catch (error) { toast(error.message, "error"); }
}

async function createRelation(event) {
  event.preventDefault();
  if (!state.currentSpace) return;
  const sourceId = el("relation-source").value;
  const targetId = el("relation-target").value;
  if (!sourceId || !targetId || sourceId === targetId) {
    toast("Выберите два разных готовых документа", "error");
    return;
  }
  try {
    await api(`/api/spaces/${state.currentSpace.id}/relations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_document_id: sourceId,
        target_document_id: targetId,
        relation_type: el("relation-type").value,
        evidence: el("relation-evidence").value.trim(),
      }),
    });
    el("relation-evidence").value = "";
    await loadRelations();
    toast("Связь подтверждена");
  } catch (error) { toast(error.message, "error"); }
}

async function deleteRelation(relation) {
  if (!confirm(`Удалить связь «${relation.source_filename} → ${relation.target_filename}»?`)) return;
  try {
    await api(`/api/relations/${relation.id}`, { method: "DELETE" });
    await loadRelations();
    toast("Связь удалена");
  } catch (error) { toast(error.message, "error"); }
}

function clearMessages() {
  el("messages").replaceChildren(el("welcome-card"));
  el("welcome-card").style.display = "block";
}

function scrollMessagesToEnd() {
  const messages = el("messages");
  requestAnimationFrame(() => {
    requestAnimationFrame(() => { messages.scrollTop = messages.scrollHeight; });
  });
}

function sourceCitationLabel(source) {
  const numbers = Array.isArray(source.citation_numbers) && source.citation_numbers.length
    ? source.citation_numbers
    : [source.number];
  return numbers.map((number) => `[${number}]`).join(" ");
}

function createSourceCard(source, initiallyHidden) {
  const card = document.createElement("details");
  card.className = "source-card";
  card.hidden = initiallyHidden;

  const summary = document.createElement("summary");
  const heading = document.createElement("span");
  heading.className = "source-summary-main";
  const citations = document.createElement("strong");
  citations.textContent = sourceCitationLabel(source);
  const filename = document.createElement("span");
  filename.className = "source-filename";
  filename.textContent = source.filename;
  heading.append(citations, filename);
  const location = document.createElement("span");
  location.className = "source-location";
  location.textContent = source.location;
  summary.append(heading, location);

  const body = document.createElement("div");
  body.className = "source-card-body";
  const excerpt = document.createElement("p");
  excerpt.className = "source-excerpt";
  appendLinkifiedText(excerpt, source.excerpt);
  if (source.relation) {
    const provenance = document.createElement("div");
    provenance.className = "source-relation";
    const provenanceTitle = document.createElement("strong");
    provenanceTitle.textContent = "Добавлен по подтверждённой связи";
    const provenanceFlow = document.createElement("span");
    const relationLabel = relationTypeLabels[source.relation.type] || source.relation.type;
    provenanceFlow.textContent = `${source.relation.source_filename} ${relationLabel} ${source.relation.target_filename}`;
    const provenanceEvidence = document.createElement("small");
    provenanceEvidence.textContent = `Основание: ${source.relation.evidence}`;
    provenance.append(provenanceTitle, provenanceFlow, provenanceEvidence);
    body.append(provenance);
  }
  body.append(excerpt);

  if (source.image_url) {
    const link = document.createElement("a");
    link.className = "source-page-link";
    link.href = source.image_url;
    link.target = "_blank";
    link.rel = "noopener";
    link.title = `Открыть ${source.filename}, ${source.location}`;
    const action = document.createElement("span");
    action.className = "source-page-action";
    action.textContent = "Открыть страницу ↗";
    const image = document.createElement("img");
    image.className = "source-image";
    image.dataset.src = source.image_url;
    image.alt = `Страница инструкции: ${source.filename}, ${source.location}`;
    link.append(action, image);
    body.append(link);
    card.addEventListener("toggle", () => {
      if (card.open && image.dataset.src) {
        image.src = image.dataset.src;
        delete image.dataset.src;
      }
    });
  }

  card.append(summary, body);
  return card;
}

function appendSources(wrapper, sources) {
  const sourceSection = document.createElement("section");
  sourceSection.className = "sources";
  const header = document.createElement("div");
  header.className = "sources-header";
  const heading = document.createElement("strong");
  heading.textContent = `Источники · ${sources.length}`;
  const hint = document.createElement("span");
  hint.textContent = "Нажмите на источник, чтобы проверить страницу";
  header.append(heading, hint);

  const sourceList = document.createElement("div");
  sourceList.className = "source-list";
  const cards = sources.map((source, index) => {
    const card = createSourceCard(source, index >= INITIAL_SOURCE_LIMIT);
    sourceList.append(card);
    return card;
  });
  sourceSection.append(header, sourceList);

  if (cards.length > INITIAL_SOURCE_LIMIT) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "sources-more";
    more.textContent = `Показать ещё ${cards.length - INITIAL_SOURCE_LIMIT}`;
    more.addEventListener("click", () => {
      const expanded = more.dataset.expanded === "true";
      cards.slice(INITIAL_SOURCE_LIMIT).forEach((card) => { card.hidden = expanded; });
      more.dataset.expanded = String(!expanded);
      more.textContent = expanded
        ? `Показать ещё ${cards.length - INITIAL_SOURCE_LIMIT}`
        : "Скрыть дополнительные источники";
    });
    sourceSection.append(more);
  }
  wrapper.append(sourceSection);
}

function appendMessage(role, text, sources = [], loading = false, options = []) {
  el("welcome-card").style.display = "none";
  const wrapper = document.createElement("article");
  wrapper.className = `message ${role}`;
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "Вы" : "Контекст";
  const bubble = document.createElement("div");
  bubble.className = `bubble ${loading ? "loading" : ""}`;
  if (loading) bubble.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
  else appendLinkifiedText(bubble, text);
  wrapper.append(label, bubble);
  if (sources.length) appendSources(wrapper, sources);
  if (options.length) {
    const optionList = document.createElement("div");
    optionList.className = "clarification-options";
    options.forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "clarification-option";
      button.textContent = option;
      button.addEventListener("click", () => ask(option));
      optionList.append(button);
    });
    wrapper.append(optionList);
  }
  el("messages").append(wrapper);
  scrollMessagesToEnd();
  return wrapper;
}

async function ask(question) {
  if (!state.currentSpace || state.busy || !question.trim()) return;
  state.busy = true;
  updateComposer();
  appendMessage("user", question.trim());
  const loading = appendMessage("assistant", "", [], true);
  try {
    const result = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        space_id: state.currentSpace.id,
        question: question.trim(),
        conversation_id: state.conversationId,
      }),
    });
    state.conversationId = result.conversation_id;
    loading.remove();
    appendMessage(
      "assistant",
      result.answer,
      result.sources,
      false,
      result.clarification_options || [],
    );
  } catch (error) {
    loading.remove();
    appendMessage("assistant", `Не удалось получить ответ: ${error.message}`);
  } finally {
    state.busy = false;
    updateComposer();
    el("question-input").focus();
  }
}

async function createSpace(event) {
  event.preventDefault();
  const name = el("space-name").value.trim();
  if (!name) return;
  try {
    const space = await api("/api/spaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: el("space-description").value.trim() }),
    });
    el("space-dialog").close();
    el("space-form").reset();
    state.spaces = await api("/api/spaces");
    await selectSpace(space.id);
    toast("Пространство создано");
  } catch (error) { toast(error.message, "error"); }
}

async function checkHealth() {
  try {
    const health = await api("/api/health");
    el("health-dot").className = `health-dot ${health.status === "ok" ? "ok" : "error"}`;
    el("health-label").textContent = health.status === "ok" ? `Сервис готов · ${health.provider}` : "Сервис требует настройки";
  } catch {
    el("health-dot").className = "health-dot error";
    el("health-label").textContent = "Нет связи с сервисом";
  }
}

function bindEvents() {
  el("new-space-button").addEventListener("click", () => el("space-dialog").showModal());
  el("space-form").addEventListener("submit", createSpace);
  el("relations-button").addEventListener("click", () => {
    renderRelationManager();
    el("relation-dialog").showModal();
  });
  el("close-relation-dialog").addEventListener("click", () => el("relation-dialog").close());
  el("relation-form").addEventListener("submit", createRelation);
  el("relation-source").addEventListener("change", syncRelationTarget);
  el("upload-button").addEventListener("click", () => el("file-input").click());
  el("file-input").addEventListener("change", (event) => uploadFiles(event.target.files));
  el("drop-zone").addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) el("file-input").click(); });
  ["dragenter", "dragover"].forEach((name) => el("drop-zone").addEventListener(name, (event) => { event.preventDefault(); el("drop-zone").classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((name) => el("drop-zone").addEventListener(name, (event) => { event.preventDefault(); el("drop-zone").classList.remove("dragging"); }));
  el("drop-zone").addEventListener("drop", (event) => uploadFiles(event.dataTransfer.files));
  el("chat-form").addEventListener("submit", (event) => { event.preventDefault(); const input = el("question-input"); const question = input.value; input.value = ""; input.style.height = "auto"; ask(question); });
  el("question-input").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); el("chat-form").requestSubmit(); } });
  el("question-input").addEventListener("input", (event) => { event.target.style.height = "auto"; event.target.style.height = `${Math.min(event.target.scrollHeight, 130)}px`; });
  el("suggestions").addEventListener("click", (event) => { const question = event.target.dataset.question; if (question) ask(question); });
  el("new-chat-button").addEventListener("click", () => { state.conversationId = null; clearMessages(); toast("Начат новый диалог"); });
  el("mobile-menu").addEventListener("click", () => el("sidebar").classList.toggle("open"));
}

async function init() {
  bindEvents();
  try {
    state.config = await api("/api/config");
    el("format-hint").textContent = `${state.config.supported_extensions.join(", ")} · до ${state.config.max_upload_mb} МБ`;
    await Promise.all([loadSpaces(), checkHealth()]);
  } catch (error) {
    toast(`Не удалось запустить интерфейс: ${error.message}`, "error");
    checkHealth();
  }
}

document.addEventListener("DOMContentLoaded", init);
