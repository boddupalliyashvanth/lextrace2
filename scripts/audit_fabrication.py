import os
import json
import sys

def audit_memos():
    print("Auditing memos for fabrication...")
    memo_dir = 'eval/results/memos'
    corpus_dir = '.cache/corpus'
    
    if not os.path.exists(memo_dir):
        print("No memos found.")
        return

    # Load corpus
    chunks = {}
    if os.path.exists(corpus_dir):
        for fn in os.listdir(corpus_dir):
            if fn.endswith('.json'):
                with open(os.path.join(corpus_dir, fn)) as f:
                    doc = json.load(f)
                    for c in doc.get('chunks', []):
                        chunks[c['chunk_id']] = c['text']

    passed = True
    for fn in os.listdir(memo_dir):
        if not fn.endswith('.json'):
            continue
        with open(os.path.join(memo_dir, fn)) as f:
            memo = json.load(f)
            
        print(f"Auditing {fn}...")
        for claim in memo.get('claims', []):
            for ev in claim.get('evidence', []):
                chunk_id = ev['chunk_id']
                quote = ev['quote']
                
                if chunk_id not in chunks:
                    print(f"  FAIL: Chunk {chunk_id} not found in corpus.")
                    passed = False
                elif quote not in chunks[chunk_id]:
                    print(f"  FAIL: Quote '{quote}' not found in chunk {chunk_id}.")
                    passed = False
                    
    if passed:
        print("Audit Passed: No fabrications found.")
        sys.exit(0)
    else:
        print("Audit Failed: Fabrications found!")
        sys.exit(1)

if __name__ == '__main__':
    audit_memos()