import yaml
import hashlib
import urllib.request
import os
import sys
from pathlib import Path

def compute_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def main():
    manifest_path = Path("data/manifest.yaml")
    output_dir = Path("data/raw")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not manifest_path.exists():
        print(f"Manifest not found at {manifest_path}")
        sys.exit(1)
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)
        
    for entry in manifest.get("files", []):
        if entry.get("synthetic"):
            continue # Skip synthetic bundles since they are committed in repo
            
        url = entry.get("source_url")
        if not url:
            continue
            
        doc_id = entry.get("id")
        filename = f"{doc_id}.pdf" # simplistic assumption
        filepath = output_dir / filename
        
        expected_sha = entry.get("sha256")
        
        if filepath.exists():
            if expected_sha and compute_sha256(filepath) == expected_sha:
                print(f"Skipping {doc_id} (already downloaded and verified)")
                continue
            else:
                print(f"Hash mismatch for {doc_id}, redownloading...")
                
        print(f"Downloading {doc_id} from {url}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'LexTrace/1.0 (Research)'})
            with urllib.request.urlopen(req, timeout=10) as response, open(filepath, 'wb') as out_file:
                out_file.write(response.read())
            
            actual_sha = compute_sha256(filepath)
            if expected_sha and actual_sha != expected_sha:
                print(f"WARNING: SHA256 mismatch for {doc_id}. Expected {expected_sha}, got {actual_sha}")
        except Exception as e:
            print(f"Failed to download {doc_id}: {e}")

if __name__ == "__main__":
    main()
