import json
from pathlib import Path

from contracts.schemas import Chunk, SourceDoc


def persist_ingest(doc: SourceDoc, chunks: list[Chunk], full_text: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    docs_file = output_dir / "docs.jsonl"
    chunks_file = output_dir / "chunks.jsonl"
    
    existing_sha = set()
    if docs_file.exists():
        with open(docs_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    existing_sha.add(d.get("sha256"))
                except json.JSONDecodeError:
                    pass
                
    if doc.sha256 in existing_sha:
        return False # Skipped
        
    with open(docs_file, "a", encoding="utf-8") as f:
        f.write(doc.model_dump_json() + "\n")
        
    with open(chunks_file, "a", encoding="utf-8") as f:
        f.writelines(c.model_dump_json() + "\n" for c in chunks)
            
    with open(output_dir / f"{doc.doc_id}.txt", "w", encoding="utf-8") as f:
        f.write(full_text)
        
    return True
