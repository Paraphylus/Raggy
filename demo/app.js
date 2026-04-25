const API_URL = window.location.protocol === "file:"
  ? "http://127.0.0.1:8080/ask"
  : new URL("/ask", window.location.origin).toString();
const DOCUMENTS_URL = window.location.protocol === "file:"
  ? "http://127.0.0.1:8080/documents"
  : new URL("/documents", window.location.origin).toString();
const UPLOAD_URL = window.location.protocol === "file:"
  ? "http://127.0.0.1:8080/upload"
  : new URL("/upload", window.location.origin).toString();
const TOP_K = 5;

const chat = document.getElementById("chat");
const composer = document.getElementById("composer");
const input = document.getElementById("question");
const sendButton = document.getElementById("send-button");
const statusPill = document.getElementById("status-pill");
const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("document-file");
const uploadButton = document.getElementById("upload-button");
const documentList = document.getElementById("document-list");
const libraryCount = document.getElementById("library-count");
const metricDocuments = document.getElementById("metric-documents");
const metricChunks = document.getElementById("metric-chunks");
const metricIndexSize = document.getElementById("metric-index-size");
const metricLatency = document.getElementById("metric-latency");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    };

    return entities[char];
  });
}

function formatAnswer(answer) {
  return escapeHtml(answer).replace(/\n/g, "<br>");
}

function scrollChatToBottom() {
  chat.scrollTo({
    top: chat.scrollHeight,
    behavior: "smooth"
  });
}

function setStatus(text, state = "idle") {
  statusPill.textContent = text;
  statusPill.classList.remove("is-loading", "is-error");

  if (state === "loading") {
    statusPill.classList.add("is-loading");
  }

  if (state === "error") {
    statusPill.classList.add("is-error");
  }
}

function updateMetrics(metrics = null, latencySeconds = null) {
  if (metrics) {
    metricDocuments.textContent = String(metrics.documents ?? 0);
    metricChunks.textContent = String(metrics.chunks ?? 0);
    metricIndexSize.textContent = metrics.index_size_human ?? "0 B";
  }

  if (latencySeconds !== null) {
    metricLatency.textContent = `${Number(latencySeconds).toFixed(2)}s`;
  } else if (!metricLatency.textContent.trim()) {
    metricLatency.textContent = "N/A";
  }
}

function renderDocumentList(documents = [], indexedChunks = 0) {
  libraryCount.textContent = `${documents.length} docs - ${indexedChunks} chunks`;

  if (!documents.length) {
    documentList.innerHTML = '<span class="document-pill is-empty">No documents indexed yet</span>';
    return;
  }

  documentList.innerHTML = documents
    .map((document) => `<span class="document-pill">${escapeHtml(document)}</span>`)
    .join("");
}

async function refreshDocuments() {
  try {
    const response = await fetch(DOCUMENTS_URL);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data?.detail || `HTTP ${response.status}`);
    }

    renderDocumentList(data.documents || [], data.indexed_chunks || 0);
    updateMetrics(data.metrics || {});
  } catch (error) {
    libraryCount.textContent = "Unavailable";
    documentList.innerHTML = '<span class="document-pill is-empty">Could not load indexed documents</span>';
    updateMetrics({});
    console.error("Failed to load documents:", error);
  }
}

function createMessage({ role, label, avatar, content, isHtml = false, extraClass = "" }) {
  const message = document.createElement("article");
  const roleClass = role === "user" ? "message-user" : "message-bot";

  message.className = `message ${roleClass} ${extraClass}`.trim();
  message.innerHTML = `
    <div class="message-avatar">${escapeHtml(avatar)}</div>
    <div class="message-bubble">
      <p class="message-label">${escapeHtml(label)}</p>
      <div class="message-body">${isHtml ? content : `<p>${escapeHtml(content)}</p>`}</div>
    </div>
  `;

  chat.appendChild(message);
  scrollChatToBottom();
  return message;
}

function buildSourcesMarkup(sources) {
  if (!Array.isArray(sources) || sources.length === 0) {
    return "";
  }

  const items = sources.map((source) => {
    const sourceName = source?.source ?? "Unknown source";
    const chunk = source?.chunk ?? "N/A";
    const score = source?.score === undefined || source?.score === null
      ? "N/A"
      : Number(source.score).toFixed(3);

    return `
      <div class="source-item">
        <strong>${escapeHtml(sourceName)}</strong><br>
        Chunk ${escapeHtml(chunk)} &middot; Score ${escapeHtml(score)}
      </div>
    `;
  }).join("");

  return `
    <section class="sources-card">
      <p class="source-label">Retrieved Sources</p>
      <div class="sources-list">${items}</div>
    </section>
  `;
}

function buildAnswerMarkup(data) {
  const latency = data?.latency_s === undefined || data?.latency_s === null
    ? "N/A"
    : Number(data.latency_s).toFixed(2);

  return `
    <p>${formatAnswer(data.answer)}</p>
    <p class="meta-row">Latency ${escapeHtml(latency)}s &middot; Top ${TOP_K} retrieval results</p>
    ${buildSourcesMarkup(data.sources)}
  `;
}

function createLoadingMessage(text = "Retrieving relevant chunks and preparing a grounded answer") {
  return createMessage({
    role: "bot",
    label: "RAG Assistant",
    avatar: "AI",
    extraClass: "loading-message",
    isHtml: true,
    content: `
      <p>${escapeHtml(text)}</p>
      <div class="typing-dots" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </div>
    `
  });
}

async function askQuestion(question) {
  setStatus("Retrieving relevant context...", "loading");
  sendButton.disabled = true;
  input.disabled = true;

  createMessage({
    role: "user",
    label: "You",
    avatar: "You",
    content: question
  });

  const loadingMessage = createLoadingMessage();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        question,
        top_k: TOP_K
      })
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(data?.detail || `HTTP ${response.status}`);
    }

    if (!data?.answer) {
      throw new Error(data?.detail || "The backend returned an invalid response.");
    }

    loadingMessage.querySelector(".message-body").innerHTML = buildAnswerMarkup(data);

    const latencyText = data?.latency_s === undefined || data?.latency_s === null
      ? "N/A"
      : Number(data.latency_s).toFixed(2);

    setStatus("Upload a file or ask a question");
    updateMetrics(data.metrics || null, data?.latency_s ?? null);
  } catch (error) {
    loadingMessage.classList.add("error-message");
    loadingMessage.querySelector(".message-body").innerHTML = `
      <p>${escapeHtml(error.message || "Something went wrong while fetching the answer.")}</p>
      <p class="meta-row">Upload a document first or check that the backend is running at ${escapeHtml(new URL("/", API_URL).origin)}.</p>
    `;

    setStatus("Request failed", "error");
    console.error("RAG request failed:", error);
  } finally {
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
    scrollChatToBottom();
  }
}

async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  uploadButton.disabled = true;
  setStatus(`Indexing ${file.name}...`, "loading");
  const loadingMessage = createLoadingMessage(`Chunking, embedding, and indexing ${file.name}`);

  try {
    const response = await fetch(UPLOAD_URL, {
      method: "POST",
      body: formData
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(data?.detail || `HTTP ${response.status}`);
    }

    loadingMessage.querySelector(".message-body").innerHTML = `
      <p>${escapeHtml(data.message || `${file.name} uploaded successfully.`)}</p>
      <p class="meta-row">${escapeHtml(String(data.chunks_added ?? 0))} chunks added to the vector index.</p>
    `;

    setStatus(`${file.name} indexed`);
    updateMetrics(data.metrics || {});
    await refreshDocuments();
    input.focus();
  } catch (error) {
    loadingMessage.classList.add("error-message");
    loadingMessage.querySelector(".message-body").innerHTML = `
      <p>${escapeHtml(error.message || "Upload failed.")}</p>
      <p class="meta-row">Try a readable TXT file or a text-based PDF.</p>
    `;

    setStatus("Upload failed", "error");
    console.error("Document upload failed:", error);
  } finally {
    uploadButton.disabled = false;
    uploadForm.reset();
    scrollChatToBottom();
  }
}

composer.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = input.value.trim();
  if (!question || sendButton.disabled) {
    return;
  }

  input.value = "";
  await askQuestion(question);
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = fileInput.files?.[0];
  if (!file || uploadButton.disabled) {
    return;
  }

  await uploadDocument(file);
});

refreshDocuments();
