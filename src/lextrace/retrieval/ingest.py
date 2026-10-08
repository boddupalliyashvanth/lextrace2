import json
import os
from pathlib import Path

from contracts.schemas import Chunk


def ingest_directory(directory: Path, index_dir: Path):
    chunks = []
    
    from lextrace.ingest.chunk import structure_aware_chunk
    from lextrace.ingest.parse import parse_pdf
    
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = Path(root) / file
            doc_id = file
            doc_type = "judgment"
            if file.startswith(("bns", "ipc", "iea", "crpc")):
                doc_type = "statute"
            elif file.startswith("synth"):
                doc_type = "case_file"
                
            if file.lower().endswith('.pdf'):
                full_text, pages = parse_pdf(str(file_path))
                doc_chunks = structure_aware_chunk(doc_id, full_text, pages, doc_type)
                chunks.extend(doc_chunks)
                
            elif file.lower().endswith('.txt'):
                text = file_path.read_text(encoding="utf-8").strip()
                if text:
                    chunks.append(Chunk(
                        chunk_id=f"{doc_id}::doc",
                        doc_id=doc_id,
                        doc_type=doc_type,
                        text=text,
                        page_start=0,
                        page_end=0,
                        char_start=0,
                        char_end=len(text),
                        metadata={"source": str(file_path)}
                    ))


    os.makedirs(index_dir, exist_ok=True)
    
    # Save chunks
    chunks_dict = {c.chunk_id: c.model_dump() for c in chunks}
    with open(index_dir / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks_dict, f)

    # Build BM25
    from rank_bm25 import BM25Okapi
    tokenized_corpus = [c.text.lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    
    import pickle
    with open(index_dir / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)
        
    # Build FAISS
    try:
        import faiss
        import numpy as np
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        texts = [c.text for c in chunks]
        if texts:
            embeddings = model.encode(texts)
            dimension = embeddings.shape[1]
            faiss_index = faiss.IndexFlatL2(dimension)
            faiss_index.add(np.array(embeddings).astype('float32'))
            faiss.write_index(faiss_index, str(index_dir / "faiss.index"))
    except Exception as e:
        print(f"Failed to build FAISS index: {e}")

    print(f"Ingested {len(chunks)} chunks from {directory} into {index_dir}")

