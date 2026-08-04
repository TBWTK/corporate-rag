const state = {
  config: null,
  spaces: [],
  currentSpace: null,
  documents: [],
  conversationId: null,
  polling: null,
  busy: false,
};

const el = (id) => document.getElementById(id);

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
  await loadDocuments();
}

async function loadDocuments() {
  if (!state.currentSpace) return;
  state.documents = await api(`/api/spaces/${state.currentSpace.id}/documents`);
  renderDocuments();
  const pending = state.documents.some((doc) => ["queued", "processing"].includes(doc.status));
  clearTimeout(state.polling);
  if (pending) state.polling = setTimeout(loadDocuments, 1800);
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
  try { await api(`/api/documents/${id}`, { method: "DELETE" }); await loadDocuments(); await loadSpacesOnly(); }
  catch (error) { toast(error.message, "error"); }
}

function clearMessages() {
  el("messages").replaceChildren(el("welcome-card"));
  el("welcome-card").style.display = "block";
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
  else bubble.textContent = text;
  wrapper.append(label, bubble);
  if (sources.length) {
    const sourceList = document.createElement("div");
    sourceList.className = "sources";
    sources.forEach((source) => {
      const card = document.createElement("div");
      card.className = "source-card";
      const title = document.createElement("strong");
      title.textContent = `[${source.number}] ${source.filename} · ${source.location}`;
      const excerpt = document.createElement("span");
      excerpt.textContent = source.excerpt;
      card.append(title, excerpt);
      sourceList.append(card);
    });
    wrapper.append(sourceList);
  }
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
  el("messages").scrollTop = el("messages").scrollHeight;
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
