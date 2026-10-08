import re

from contracts.schemas import Chunk


def fixed_chunks(text: str, size: int = 1000):
    chunks = []
    for i in range(0, len(text), size):
        chunks.append(text[i:i+size])
    return chunks

def structure_aware_chunk(doc_id: str, full_text: str, pages: list, doc_type: str):
    chunks = []
    
    # Regex for Statutes: matches "Section 1", "Section 3A", "3A.", etc.
    # Excludes lines starting with "Provided" to avoid splitting on provisos.
    statute_pattern = re.compile(r"^(?!Provided)(?:Section\s+\d+[A-Z]?|\d+[A-Z]?\.)\s+", re.MULTILINE | re.IGNORECASE)
    # Regex for Judgments: numbered paragraphs like "1.", "12.", "12. "
    judgment_pattern = re.compile(r"^\d+\.\s+", re.MULTILINE)
    
    pattern = statute_pattern if doc_type == "statute" else judgment_pattern
    
    matches = list(pattern.finditer(full_text))
    
    if not matches:
        # Fallback to fixed chunks if structure not found
        raw_chunks = [(i, i+500) for i in range(0, len(full_text), 500)]
    else:
        raw_chunks = []
        for i in range(len(matches)):
            start = matches[i].start()
            end = matches[i+1].start() if i + 1 < len(matches) else len(full_text)
            raw_chunks.append((start, end))
            
    for idx, (c_start, c_end) in enumerate(raw_chunks):
        text = full_text[c_start:c_end]
        
        # Determine page boundaries
        page_start = next((p["page_num"] for p in pages if p["char_start"] <= c_start <= p["char_end"]), 0)
        page_end = next((p["page_num"] for p in pages if p["char_start"] <= c_end <= p["char_end"]), page_start)
        
        section_path = text.split("\n")[0][:50].strip() if matches else None
        
        chunks.append(Chunk(
            chunk_id=f"{doc_id}::p{page_start}::c{idx}",
            doc_id=doc_id,
            text=text.strip(),
            page_start=page_start,
            page_end=page_end,
            char_start=c_start,
            char_end=c_start + len(text.strip()),
            section_path=section_path
        ))
    return chunks

