const appState = {
  documents: [],
};

const elements = {
  documentList: document.getElementById("document-list"),
  documentCount: document.getElementById("document-count"),
  uploadForm: document.getElementById("upload-form"),
  askForm: document.getElementById("ask-form"),
  questionInput: document.getElementById("question-input"),
  uploadStatus: document.getElementById("upload-status"),
  answerOutput: document.getElementById("answer-output"),
  citationOutput: document.getElementById("citation-output"),
};

function renderDocuments() {
  const documents = appState.documents;
  elements.documentCount.textContent = `${documents.length} 份文档`;

  if (!documents.length) {
    elements.documentList.innerHTML = '<div class="muted">还没有导入文档。</div>';
    return;
  }

  elements.documentList.innerHTML = documents
    .map(
      (document) => `
        <div class="document-item">
          <strong>${escapeHtml(document.name)}</strong>
          <span>${document.chunk_count} 个 chunk</span>
        </div>
      `,
    )
    .join("");
}

function renderAnswer(answer, citations) {
  elements.answerOutput.textContent = answer;
  if (!citations || !citations.length) {
    elements.citationOutput.innerHTML = '<div class="muted">暂无引用。</div>';
    return;
  }

  elements.citationOutput.innerHTML = citations
    .map(
      (citation) => `
        <article class="citation-card">
          <div class="citation-meta">${escapeHtml(citation.source)} · score ${citation.score}</div>
          <p>${escapeHtml(citation.content)}</p>
        </article>
      `,
    )
    .join("");
}

async function loadDocuments() {
  const response = await fetch("/api/documents");
  const payload = await response.json();
  appState.documents = payload.documents || [];
  renderDocuments();
}

async function submitUpload(event) {
  event.preventDefault();
  const formData = new FormData(elements.uploadForm);
  const response = await fetch("/api/documents", {
    method: "POST",
    body: formData,
  });

  const payload = await response.json();
  if (!response.ok) {
    elements.uploadStatus.textContent = payload.detail || "导入失败。";
    return;
  }

  elements.uploadStatus.textContent = `${payload.message} 已切成 ${payload.chunk_count} 个 chunk。`;
  elements.uploadForm.reset();
  await loadDocuments();
}

async function submitQuestion(event) {
  event.preventDefault();
  const question = elements.questionInput.value.trim();
  if (!question) {
    return;
  }

  const response = await fetch("/api/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });

  const payload = await response.json();
  if (!response.ok) {
    elements.answerOutput.textContent = payload.detail || "回答失败。";
    elements.citationOutput.innerHTML = "";
    return;
  }

  renderAnswer(payload.answer, payload.citations);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

elements.uploadForm.addEventListener("submit", submitUpload);
elements.askForm.addEventListener("submit", submitQuestion);
loadDocuments().catch(() => {
  elements.documentList.innerHTML = '<div class="muted">文档列表加载失败。</div>';
});
