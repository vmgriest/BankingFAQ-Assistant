import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm import detect_language, generate_answer, generate_followups, translate_to_english
from retrieval import faq_store
from sentiment import detect_frustration

app = FastAPI(title="Banking FAQ Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# session_id -> {"history": [{"role": "user"/"assistant", "content": str}], "language": "en"|"es"}
SESSIONS: dict[str, dict] = {}
MAX_HISTORY_TURNS = 8


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    language: Literal["auto", "en", "es"] = "auto"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    language: str
    in_scope: bool
    confidence: float
    sources: list[str]
    follow_ups: list[str]
    frustration: dict


class FaqIn(BaseModel):
    category: str
    question: str
    answer: str
    keywords: list[str] = []
    source: str = ""


def get_session(session_id: str | None) -> tuple[str, dict]:
    if session_id and session_id in SESSIONS:
        return session_id, SESSIONS[session_id]
    new_id = session_id or str(uuid.uuid4())
    SESSIONS[new_id] = {"history": [], "language": "en"}
    return new_id, SESSIONS[new_id]


@app.get("/health")
def health():
    return {"status": "ok", "faq_count": len(faq_store.list_all())}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    sid, session = get_session(req.session_id)

    language = req.language
    if language == "auto":
        language = detect_language(req.message) if not session["history"] else session["language"]
    session["language"] = language

    frustration = detect_frustration(req.message)

    retrieval_query = translate_to_english(req.message) if language != "en" else req.message
    results = faq_store.search(retrieval_query, top_k=3)
    in_scope = faq_store.is_in_scope(results)
    top_score = results[0]["score"] if results else 0.0

    session["history"].append({"role": "user", "content": req.message})

    if in_scope:
        relevant = [r for r in results if r["score"] >= 0.08]
        reply = generate_answer(session["history"][-MAX_HISTORY_TURNS:], relevant, language)
        sources = [r["source"] for r in relevant]
    else:
        from llm import FALLBACK

        reply = FALLBACK.get(language, FALLBACK["en"])
        sources = []

    if frustration["frustrated"]:
        prefix = {
            "en": "I can see this is frustrating, and I'm sorry for the trouble. ",
            "es": "Entiendo que esto es frustrante y lamento el inconveniente. ",
        }.get(language, "")
        if not reply.startswith(prefix.strip()[:10]):
            reply = prefix + reply
        reply += {
            "en": " If you'd like to speak with a person directly, call 1-800-555-0199.",
            "es": " Si prefieres hablar con una persona, llama al 1-800-555-0199.",
        }.get(language, "")

    session["history"].append({"role": "assistant", "content": reply})
    session["history"] = session["history"][-(MAX_HISTORY_TURNS * 2) :]

    follow_ups = generate_followups(session["history"][-MAX_HISTORY_TURNS:], language) if in_scope else []

    return ChatResponse(
        session_id=sid,
        reply=reply,
        language=language,
        in_scope=in_scope,
        confidence=round(top_score, 3),
        sources=sources,
        follow_ups=follow_ups,
        frustration=frustration,
    )


@app.post("/api/session/reset")
def reset_session(session_id: str):
    SESSIONS.pop(session_id, None)
    return {"status": "reset"}


# --- Admin FAQ CRUD ---------------------------------------------------------

@app.get("/api/faqs")
def list_faqs():
    return faq_store.list_all()


@app.post("/api/faqs")
def create_faq(faq: FaqIn):
    return faq_store.add(faq.model_dump())


@app.put("/api/faqs/{faq_id}")
def update_faq(faq_id: int, faq: FaqIn):
    updated = faq_store.update(faq_id, faq.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return updated


@app.delete("/api/faqs/{faq_id}")
def delete_faq(faq_id: int):
    if not faq_store.delete(faq_id):
        raise HTTPException(status_code=404, detail="FAQ not found")
    return {"status": "deleted"}


# --- Static frontend ---------------------------------------------------------
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
