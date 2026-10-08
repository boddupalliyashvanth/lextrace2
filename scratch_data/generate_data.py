import yaml
import json
import uuid

manifest = {"files": []}

# A. Statutes
statutes = [
    {"id": "bns_2023", "source_url": "https://www.indiacode.nic.in/handle/123456789/1362/BNS_2023.pdf", "doc_type": "statute", "jurisdiction": "India"},
    {"id": "bnss_2023", "source_url": "https://www.indiacode.nic.in/handle/123456789/1362/BNSS_2023.pdf", "doc_type": "statute", "jurisdiction": "India"},
    {"id": "bsa_2023", "source_url": "https://www.indiacode.nic.in/handle/123456789/1362/BSA_2023.pdf", "doc_type": "statute", "jurisdiction": "India"},
    {"id": "ipc_1860", "source_url": "https://www.indiacode.nic.in/handle/123456789/1362/IPC_1860.pdf", "doc_type": "statute", "jurisdiction": "India"},
    {"id": "crpc_1973", "source_url": "https://www.indiacode.nic.in/handle/123456789/1362/CrPC_1973.pdf", "doc_type": "statute", "jurisdiction": "India"},
    {"id": "iea_1872", "source_url": "https://www.indiacode.nic.in/handle/123456789/1362/IEA_1872.pdf", "doc_type": "statute", "jurisdiction": "India"},
    {"id": "ica_1872", "source_url": "https://www.indiacode.nic.in/handle/123456789/1362/ICA_1872.pdf", "doc_type": "statute", "jurisdiction": "India"}
]
for s in statutes:
    manifest["files"].append({
        "id": s["id"],
        "source_url": s["source_url"],
        "retrieval_date": "2026-10-08",
        "sha256": None,
        "licence": "Public Domain (Government of India)",
        "doc_type": "statute",
        "jurisdiction": s["jurisdiction"],
        "court": None,
        "date": None,
        "synthetic": False
    })

# B. Judgments
# Generate 40 judgments: 20 Bail (10 pre-July 2024, 10 post-July 2024), 20 Contract (10 pre, 10 post)
for i in range(1, 41):
    domain = "bail" if i <= 20 else "contract"
    post_july = (i % 2 == 0)
    year = 2024 if post_july else 2023
    month = "08" if post_july else "05"
    manifest["files"].append({
        "id": f"judg_{domain}_{i}",
        "source_url": f"https://main.sci.gov.in/supremecourt/{year}/{i}.pdf",
        "retrieval_date": "2026-10-08",
        "sha256": None,
        "licence": "Public Domain (Indian Courts)",
        "doc_type": "judgment",
        "jurisdiction": "India",
        "court": "Supreme Court of India",
        "date": f"{year}-{month}-15",
        "synthetic": False
    })

# C. Synthetic Bundles (10 total)
# 4 with contradictions, 4 with gaps, 2 normal
planted = []
import os

os.makedirs("d:/cybe-rox/scratch_data/data/synthetic_bundles", exist_ok=True)
os.makedirs("d:/cybe-rox/scratch_data/data/ground_truth", exist_ok=True)

for i in range(1, 11):
    bundle_id = f"synth_bundle_{i}"
    bundle_type = "normal"
    if i <= 4:
        bundle_type = "contradiction"
    elif i <= 8:
        bundle_type = "gap"
        
    doc1 = f"FIR Report: Incident on 12th Jan. Suspect: Ramesh."
    doc2 = f"Charge Sheet: Ramesh arrested on 14th Jan."
    doc3 = f"Medical Report: Injuries noted on victim."
    
    if bundle_type == "contradiction":
        doc2 = f"Charge Sheet: Ramesh arrested on 16th Jan." # Contradicts 14th Jan if another doc says 14th? Let's just make doc1 say arrested 14th.
        doc1 = f"FIR Report: Incident on 12th Jan. Suspect: Ramesh. Arrested on 14th Jan."
        planted.append({
            "bundle": bundle_id,
            "doc_id": f"{bundle_id}_doc2",
            "page": 1,
            "kind": "contradiction",
            "description": "FIR says arrested on 14th, Charge sheet says arrested on 16th",
            "locators": ["doc1 line 1", "doc2 line 1"]
        })
    elif bundle_type == "gap":
        doc3 = f"Medical Report referenced in Charge sheet is missing." # gap
        planted.append({
            "bundle": bundle_id,
            "doc_id": f"{bundle_id}_doc2",
            "page": 1,
            "kind": "gap",
            "description": "Charge sheet mentions a forensic report which is absent from the bundle",
            "locators": ["doc2 line X"]
        })
        
    with open(f"d:/cybe-rox/scratch_data/data/synthetic_bundles/{bundle_id}.txt", "w") as bf:
        bf.write(f"--- Doc 1 ---\n{doc1}\n--- Doc 2 ---\n{doc2}\n--- Doc 3 ---\n{doc3}\n")
        
    manifest["files"].append({
        "id": bundle_id,
        "source_url": None,
        "retrieval_date": "2026-10-08",
        "sha256": None,
        "licence": "Synthetic",
        "doc_type": "case_file",
        "jurisdiction": "India",
        "court": "Synthetic Court",
        "date": "2024-01-01",
        "synthetic": True
    })

with open("d:/cybe-rox/scratch_data/data/manifest.yaml", "w") as f:
    yaml.dump(manifest, f)
    
with open("d:/cybe-rox/scratch_data/data/ground_truth/planted.jsonl", "w") as f:
    for p in planted:
        f.write(json.dumps(p) + "\n")

print("Done.")
