"""Local LLM integration via Ollama for grounded answer + follow-up generation."""
import json
import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
REQUEST_TIMEOUT = 60

FALLBACK = {
    "en": (
        "I'm not able to find an answer to that in our banking FAQ. "
        "For help with this, please contact our support team at 1-800-555-0199 "
        "or support@meridianbank.example — they're available 24/7."
    ),
    "es": (
        "No encuentro una respuesta a eso en nuestras preguntas frecuentes bancarias. "
        "Para obtener ayuda, comunícate con nuestro equipo de soporte al 1-800-555-0199 "
        "o support@meridianbank.example, disponible las 24 horas."
    ),
}

SYSTEM_TEMPLATE = {
    "en": (
        "You are a helpful, concise banking customer service assistant for Meridian Bank. "
        "Answer ONLY using the FAQ context and policy excerpts provided below — do not invent "
        "rates, fees, or policies that aren't stated. You do NOT know which specific account tier "
        "the customer holds, and you must NEVER ask them which account type they have. Instead, "
        "immediately state the facts for every relevant variant listed in the context (e.g. list the "
        "rate for each account tier) in one short answer. Do not ask any clarifying question unless "
        "the context has zero relevant information. Keep answers short (2-4 sentences), warm, and "
        "professional. If the user seems frustrated, acknowledge it briefly before answering. Respond "
        "in English.\n\n"
        "EXAMPLE — customer asks 'What's my savings rate?' and context lists Basic/Premium/Youth "
        "savings rates. WRONG reply: 'Which account type do you have — Basic, Premium, or Youth?' "
        "CORRECT reply: 'It depends on your account: Basic Savings earns 0.50% APY, Premium Savings "
        "earns 1.75% APY (with a $2,500 minimum balance), and Youth Savings earns 1.00% APY.'\n\n"
        "CONTEXT:\n{context}"
    ),
    "es": (
        "Eres un asistente de servicio al cliente bancario, útil y conciso, para Meridian Bank. "
        "Responde SOLO usando el contexto de las preguntas frecuentes y las políticas que se "
        "proporcionan a continuación; no inventes tasas, tarifas ni políticas que no se mencionen. "
        "No sabes qué tipo específico de cuenta tiene el cliente y NUNCA debes preguntarle qué tipo "
        "de cuenta tiene. En su lugar, indica de inmediato los datos de cada variante relevante que "
        "aparezca en el contexto (por ejemplo, la tasa de cada nivel de cuenta) en una respuesta breve. "
        "No hagas ninguna pregunta aclaratoria a menos que el contexto no tenga absolutamente nada "
        "relevante. Mantén las respuestas breves (2-4 oraciones), cálidas y profesionales. Si el "
        "usuario parece frustrado, reconócelo brevemente antes de responder. Responde en español.\n\n"
        "EJEMPLO — el cliente pregunta '¿Cuál es mi tasa de ahorro?' y el contexto enumera las tasas "
        "de Basic/Premium/Youth. Respuesta INCORRECTA: '¿Qué tipo de cuenta tienes — Basic, Premium "
        "o Youth?' Respuesta CORRECTA: 'Depende de tu cuenta: Basic Savings gana 0.50% APY, Premium "
        "Savings gana 1.75% APY (con saldo mínimo de $2,500), y Youth Savings gana 1.00% APY.'\n\n"
        "CONTEXTO:\n{context}"
    ),
}

FOLLOWUP_PROMPT = {
    "en": (
        "Based on the conversation so far, suggest exactly 3 short, natural follow-up questions "
        "the customer might ask next. Return ONLY a JSON array of 3 strings, nothing else."
    ),
    "es": (
        "Según la conversación hasta ahora, sugiere exactamente 3 preguntas de seguimiento breves y "
        "naturales que el cliente podría hacer a continuación. Devuelve SOLO un arreglo JSON de 3 "
        "cadenas, nada más."
    ),
}


def _chat(messages: list[dict]) -> str:
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": MODEL, "messages": messages, "stream": False},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def build_context(retrieved: list[dict]) -> str:
    blocks = []
    for r in retrieved:
        blocks.append(f"- Q: {r['question']}\n  A: {r['answer']}\n  (source: {r['source']})")
    return "\n".join(blocks) if blocks else "No relevant FAQ entries found."


def generate_answer(history: list[dict], retrieved: list[dict], language: str) -> str:
    context = build_context(retrieved)
    system = SYSTEM_TEMPLATE.get(language, SYSTEM_TEMPLATE["en"]).format(context=context)
    messages = [{"role": "system", "content": system}] + history
    try:
        return _chat(messages)
    except Exception:
        return FALLBACK.get(language, FALLBACK["en"])


def generate_followups(history: list[dict], language: str) -> list[str]:
    prompt = FOLLOWUP_PROMPT.get(language, FOLLOWUP_PROMPT["en"])
    messages = history + [{"role": "user", "content": prompt}]
    try:
        raw = _chat(messages)
        start, end = raw.find("["), raw.rfind("]")
        if start != -1 and end != -1:
            parsed = json.loads(raw[start : end + 1])
            return [str(q).strip() for q in parsed][:3]
    except Exception:
        pass
    return []


def translate_to_english(text: str) -> str:
    """Used only to drive English-language FAQ retrieval for non-English queries."""
    messages = [
        {
            "role": "system",
            "content": "Translate the user's message to English. Reply with ONLY the translation, nothing else.",
        },
        {"role": "user", "content": text},
    ]
    try:
        return _chat(messages)
    except Exception:
        return text


def detect_language(text: str) -> str:
    """Very lightweight heuristic language detection (en/es) — no extra model needed."""
    spanish_markers = [
        "qué", "cómo", "cuál", "cuánto", "dónde", "por qué", "gracias", "cuenta",
        "préstamo", "tarjeta", "interés", "ó", "¿", "¡", " el ", " la ", " los ", " las ",
        "mi cuenta", "ahorro",
    ]
    lowered = f" {text.lower()} "
    hits = sum(1 for m in spanish_markers if m in lowered)
    return "es" if hits >= 1 else "en"
