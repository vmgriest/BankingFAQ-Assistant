const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("input");
const followupsEl = document.getElementById("followups");
const langSelect = document.getElementById("lang-select");
const frustrationBanner = document.getElementById("frustration-banner");

const STORAGE_KEY = "banking_faq_session_id";
let sessionId = localStorage.getItem(STORAGE_KEY) || null;

const GREETING = {
  en: "Hi! I'm the Bank FAQ Assistant. Ask me about accounts, interest rates, loans, fees, or transactions.",
  es: "¡Hola! Soy el asistente de preguntas frecuentes del banco. Pregúntame sobre cuentas, tasas de interés, préstamos, tarifas o transacciones.",
};

const STARTER_PROMPTS = {
  en: [
    "What checking account options are available?",
    "What's my savings rate?",
    "What do I need to qualify for a mortgage?",
    "Is there a fee for using another bank's ATM?",
    "How long does a check deposit take to clear?",
  ],
  es: [
    "¿Qué opciones de cuentas corrientes tienen?",
    "¿Cuál es mi tasa de ahorro?",
    "¿Qué necesito para calificar para una hipoteca?",
    "¿Hay una tarifa por usar el cajero de otro banco?",
    "¿Cuánto tarda en procesarse un depósito de cheque?",
  ],
};

function addRow(role, text, meta) {
  const row = document.createElement("div");
  row.className = `row ${role}`;

  const bubbleWrap = document.createElement("div");

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  bubbleWrap.appendChild(bubble);

  if (meta) {
    const metaEl = document.createElement("div");
    metaEl.className = "meta";
    metaEl.innerHTML = meta;
    bubbleWrap.appendChild(metaEl);
  }

  row.appendChild(bubbleWrap);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return row;
}

function addStarterChips(lang) {
  document.getElementById("starter-chips")?.remove();

  const row = document.createElement("div");
  row.className = "row bot";
  row.id = "starter-chips";

  const wrap = document.createElement("div");
  wrap.className = "starters";

  const label = document.createElement("div");
  label.className = "starters-label";
  label.textContent = lang === "es" ? "Prueba preguntar:" : "Try asking:";
  wrap.appendChild(label);

  const chipRow = document.createElement("div");
  chipRow.className = "starters-chips";
  STARTER_PROMPTS[lang].forEach((q) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "followup-chip";
    chip.textContent = q;
    chip.addEventListener("click", () => {
      row.remove();
      sendMessage(q);
    });
    chipRow.appendChild(chip);
  });
  wrap.appendChild(chipRow);

  row.appendChild(wrap);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addTyping() {
  const row = document.createElement("div");
  row.className = "row bot";
  row.id = "typing-row";
  row.innerHTML = `<div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function removeTyping() {
  document.getElementById("typing-row")?.remove();
}

function metaHtml(data) {
  const parts = [];
  if (data.in_scope) {
    const confClass = data.confidence >= 0.3 ? "confidence-high" : "confidence-low";
    parts.push(`<span class="chip ${confClass}">confidence: ${(data.confidence * 100).toFixed(0)}%</span>`);
    if (data.sources && data.sources.length) {
      parts.push(`<span class="chip">source: ${data.sources[0]}</span>`);
    }
  } else {
    parts.push(`<span class="chip confidence-low">out of scope</span>`);
  }
  return parts.join("");
}

function renderFollowups(followUps) {
  followupsEl.innerHTML = "";
  if (!followUps || !followUps.length) {
    followupsEl.classList.add("hidden");
    return;
  }
  followUps.forEach((q) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "followup-chip";
    chip.textContent = q;
    chip.addEventListener("click", () => sendMessage(q));
    followupsEl.appendChild(chip);
  });
  followupsEl.classList.remove("hidden");
}

async function sendMessage(text) {
  const message = (text ?? inputEl.value).trim();
  if (!message) return;

  inputEl.value = "";
  followupsEl.classList.add("hidden");
  document.getElementById("starter-chips")?.remove();
  addRow("user", message);
  addTyping();

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        language: langSelect.value,
      }),
    });
    const data = await resp.json();

    sessionId = data.session_id;
    localStorage.setItem(STORAGE_KEY, sessionId);

    removeTyping();
    addRow("bot", data.reply, metaHtml(data));
    renderFollowups(data.follow_ups);

    if (data.frustration && data.frustration.frustrated) {
      frustrationBanner.classList.remove("hidden");
    }
  } catch (err) {
    removeTyping();
    addRow("bot", "Sorry, I couldn't reach the assistant. Please try again in a moment.");
    console.error(err);
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage();
});

langSelect.addEventListener("change", () => {
  const lang = langSelect.value === "es" ? "es" : "en";
  if (!chatEl.hasChildNodes()) {
    addRow("bot", GREETING[lang]);
    addStarterChips(lang);
  }
});

// Initial greeting + suggested starter prompts
addRow("bot", GREETING.en);
addStarterChips("en");
