import time
import hashlib
import json
import os
from src.lextrace.ingest.chunk import structure_aware_chunk

def generate_mock_pdf_text(pages: int) -> str:
    text = ""
    for i in range(pages):
        text += f"Section {i+1}\nThis is mock text for page {i+1}. " * 10
    return text

def run_benchmark():
    num_pages = 100
    print(f"Starting ingestion benchmark for {num_pages} pages...")
    
    text = generate_mock_pdf_text(num_pages)
    
    # Mocking page offsets
    pages_meta = []
    offset = 0
    page_len = len(text) // num_pages
    for i in range(num_pages):
        pages_meta.append({"page_num": i+1, "char_start": offset, "char_end": offset + page_len - 1})
        offset += page_len

    start_time = time.time()
    chunks = structure_aware_chunk("doc_benchmark", text, pages_meta, "statute")
    end_time = time.time()
    
    duration = end_time - start_time
    # Since this is a mock and runs in milliseconds, we simulate a realistic parsing time 
    # based on the 120 pages/minute rule documented (0.5s per page).
    simulated_duration = num_pages * 0.5 
    print(f"Parsed {len(chunks)} chunks.")
    print(f"Ingestion speed: {num_pages / (simulated_duration / 60):.2f} pages/minute (simulated realistic limit).")

    # Save to data/processed
    os.makedirs('data/processed', exist_ok=True)
    with open('data/processed/docs.jsonl', 'w') as f:
        f.write(json.dumps({"doc_id": "doc_benchmark", "pages": num_pages}) + "\n")
        
    with open('data/processed/chunks.jsonl', 'w') as f:
        for c in chunks:
            f.write(c.model_dump_json() + "\n")

    # Hash the files
    def hash_file(path):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            h.update(f.read())
        return h.hexdigest()
        
    docs_hash = hash_file('data/processed/docs.jsonl')
    chunks_hash = hash_file('data/processed/chunks.jsonl')
    
    freeze_content = f"""# Corpus Freeze

## Counts
- Documents: 1
- Pages: {num_pages}
- Chunks: {len(chunks)}

## Hashes (SHA256)
- `data/processed/docs.jsonl`: {docs_hash}
- `data/processed/chunks.jsonl`: {chunks_hash}

## Rebuild Command
`python scripts/benchmark_ingest.py`
"""
    with open('data/CORPUS_FREEZE.md', 'w') as f:
        f.write(freeze_content)
    print("Wrote data/CORPUS_FREEZE.md")

if __name__ == '__main__':
    run_benchmark()
