const form = document.getElementById("faq-form");
const idField = document.getElementById("faq-id");
const categoryField = document.getElementById("category");
const questionField = document.getElementById("question");
const answerField = document.getElementById("answer");
const keywordsField = document.getElementById("keywords");
const sourceField = document.getElementById("source");
const submitBtn = document.getElementById("submit-btn");
const cancelBtn = document.getElementById("cancel-btn");
const formTitle = document.getElementById("form-title");
const listEl = document.getElementById("faq-list");
const countEl = document.getElementById("count");

async function loadFaqs() {
  const resp = await fetch("/api/faqs");
  const faqs = await resp.json();
  countEl.textContent = faqs.length;
  listEl.innerHTML = "";
  faqs
    .slice()
    .sort((a, b) => a.category.localeCompare(b.category))
    .forEach((faq) => {
      const item = document.createElement("div");
      item.className = "faq-item";
      item.innerHTML = `
        <div class="cat">${faq.category.replace("_", " ")}</div>
        <div class="q">${escapeHtml(faq.question)}</div>
        <div class="a">${escapeHtml(faq.answer)}</div>
        <div class="faq-item-actions">
          <button data-action="edit">Edit</button>
          <button data-action="delete" class="danger">Delete</button>
        </div>
      `;
      item.querySelector('[data-action="edit"]').addEventListener("click", () => startEdit(faq));
      item.querySelector('[data-action="delete"]').addEventListener("click", () => deleteFaq(faq.id));
      listEl.appendChild(item);
    });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function startEdit(faq) {
  idField.value = faq.id;
  categoryField.value = faq.category;
  questionField.value = faq.question;
  answerField.value = faq.answer;
  keywordsField.value = (faq.keywords || []).join(", ");
  sourceField.value = faq.source || "";
  formTitle.textContent = `Edit FAQ #${faq.id}`;
  submitBtn.textContent = "Save changes";
  cancelBtn.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetForm() {
  form.reset();
  idField.value = "";
  formTitle.textContent = "Add new FAQ";
  submitBtn.textContent = "Add FAQ";
  cancelBtn.classList.add("hidden");
}

cancelBtn.addEventListener("click", resetForm);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    category: categoryField.value,
    question: questionField.value.trim(),
    answer: answerField.value.trim(),
    keywords: keywordsField.value
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean),
    source: sourceField.value.trim(),
  };

  const isEdit = Boolean(idField.value);
  const url = isEdit ? `/api/faqs/${idField.value}` : "/api/faqs";
  const method = isEdit ? "PUT" : "POST";

  await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  resetForm();
  loadFaqs();
});

async function deleteFaq(id) {
  if (!confirm(`Delete FAQ #${id}? This cannot be undone.`)) return;
  await fetch(`/api/faqs/${id}`, { method: "DELETE" });
  loadFaqs();
}

loadFaqs();
