"""TF-IDF based FAQ retrieval — no vector DB required."""
import json
import threading
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = Path(__file__).parent / "data"
FAQ_PATH = DATA_DIR / "faq.json"

# sklearn's built-in "english" stop word list strips domain-critical terms like
# "interest" and "system", so we use a small custom list of true filler words instead.
STOP_WORDS = [
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing", "to", "of", "in", "on", "at", "for", "and",
    "or", "but", "if", "so", "as", "with", "about", "from", "by",
    "i", "me", "my", "you", "your", "yours", "he", "she", "it", "its", "we",
    "our", "they", "their", "them", "this", "that", "these", "those",
    "what", "how", "when", "where", "which", "who", "whom", "why",
    "can", "could", "would", "will", "shall", "should", "may", "might", "must",
    "please", "just", "like", "yall", "tell", "want", "know", "have", "has", "had",
]

# Below this score a match is considered out-of-scope
CONFIDENCE_THRESHOLD = 0.12
# A single shared token (often a near-stopword) isn't enough evidence of relevance
MIN_QUERY_TOKENS = 2


class FaqStore:
    def __init__(self, path: Path = FAQ_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.faqs: list[dict] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self.reload()

    def reload(self):
        with self._lock:
            self.faqs = json.loads(self.path.read_text(encoding="utf-8"))
            corpus = [self._doc_text(f) for f in self.faqs]
            if corpus:
                self._vectorizer = TfidfVectorizer(stop_words=STOP_WORDS, ngram_range=(1, 2))
                self._matrix = self._vectorizer.fit_transform(corpus)
            else:
                self._vectorizer = None
                self._matrix = None

    @staticmethod
    def _doc_text(faq: dict) -> str:
        return " ".join([faq["question"], faq["answer"], " ".join(faq.get("keywords", []))])

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self.faqs or self._vectorizer is None:
            return []
        query_vec = self._vectorizer.transform([query])
        self._last_query_nnz = query_vec.nnz
        scores = cosine_similarity(query_vec, self._matrix)[0]
        ranked = sorted(zip(self.faqs, scores), key=lambda x: x[1], reverse=True)
        results = []
        for faq, score in ranked[:top_k]:
            results.append({**faq, "score": float(score)})
        return results

    def is_in_scope(self, results: list[dict]) -> bool:
        if not results or results[0]["score"] < CONFIDENCE_THRESHOLD:
            return False
        # Guard against a single spurious shared token inflating the score
        return getattr(self, "_last_query_nnz", 0) >= MIN_QUERY_TOKENS

    # --- Admin CRUD -----------------------------------------------------
    def list_all(self) -> list[dict]:
        return self.faqs

    def add(self, faq: dict) -> dict:
        with self._lock:
            next_id = max((f["id"] for f in self.faqs), default=0) + 1
            faq = {**faq, "id": next_id}
            self.faqs.append(faq)
            self._persist()
        self.reload()
        return faq

    def update(self, faq_id: int, updates: dict) -> dict | None:
        with self._lock:
            for i, f in enumerate(self.faqs):
                if f["id"] == faq_id:
                    self.faqs[i] = {**f, **updates, "id": faq_id}
                    self._persist()
                    break
            else:
                return None
        self.reload()
        return next(f for f in self.faqs if f["id"] == faq_id)

    def delete(self, faq_id: int) -> bool:
        with self._lock:
            before = len(self.faqs)
            self.faqs = [f for f in self.faqs if f["id"] != faq_id]
            if len(self.faqs) == before:
                return False
            self._persist()
        self.reload()
        return True

    def _persist(self):
        self.path.write_text(json.dumps(self.faqs, indent=2, ensure_ascii=False), encoding="utf-8")


faq_store = FaqStore()
