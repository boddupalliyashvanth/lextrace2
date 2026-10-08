import re

from rank_bm25 import BM25Okapi


class LegalBM25:
    def __init__(self):
        self.corpus = []
        self.bm25 = None
        self.doc_mapping = []

    def tokenize(self, text: str) -> list[str]:
        text = text.lower()
        
        # Normalise legal abbreviations
        text = re.sub(r'\bu/s\b', 'section', text)
        text = re.sub(r'\bs\.\b', 'section', text)
        text = re.sub(r'\bsec\.\b', 'section', text)
        text = re.sub(r'\bsec\b', 'section', text)
        text = re.sub(r'\bart\.\b', 'article', text)
        text = text.replace('cr.p.c.', 'crpc')
        text = re.sub(r'\bipc\b', 'ipc', text)
        
        # We want to keep alphanumeric tokens like '482', '3a', '120b', etc.
        # This matches sequences of letters and numbers.
        tokens = re.findall(r'[a-z0-9]+', text)
        return tokens

    def fit(self, chunks: list):
        self.doc_mapping = chunks
        tokenized_corpus = [self.tokenize(chunk.text) for chunk in chunks]
        if tokenized_corpus:
            self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, top_k: int = 100) -> list[tuple]:
        if not self.bm25:
            return []
        tokenized_query = self.tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        
        hits = [(self.doc_mapping[i], score) for i, score in enumerate(scores) if score > 0]
        hits.sort(key=lambda x: x[1], reverse=True)
        return hits[:top_k]
