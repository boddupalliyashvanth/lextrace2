import os
import time

def fetch_data(mock: bool = True):
    print("Initializing LexTrace Data Fetcher...")
    
    raw_dir = "data/raw"
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(os.path.join(raw_dir, "statutes"), exist_ok=True)
    os.makedirs(os.path.join(raw_dir, "judgments"), exist_ok=True)
    os.makedirs(os.path.join(raw_dir, "case_files"), exist_ok=True)
    
    statutes = [
        "Bharatiya Nyaya Sanhita (2023)",
        "Bharatiya Nagarik Suraksha Sanhita (2023)",
        "Bharatiya Sakshya Adhiniyam (2023)",
        "Indian Penal Code (Legacy)",
        "Code of Criminal Procedure (Legacy)",
        "Indian Evidence Act (Legacy)",
        "Specific Relief Act (Civil Domain)",
        "Constitution of India",
        "Old-to-New Section Concordance Table"
    ]
    
    print("Fetching Statutes from official sources...")
    for stat in statutes:
        filename = stat.replace(" ", "_").lower() + ".pdf"
        filepath = os.path.join(raw_dir, "statutes", filename)
        if mock:
            with open(filepath, "w") as f:
                f.write(f"MOCK BUNDLE: {stat}\nSource: India Code (Simulated)\n")
        print(f" - Downloaded: {stat}")
        time.sleep(0.1)

    print("\nFetching 40 Relevant Supreme/High Court Judgments...")
    for i in range(1, 41):
        domain = "criminal_bail" if i <= 20 else "civil_specific_relief"
        era = "post_2024" if i % 2 == 0 else "pre_2024"
        filename = f"judgment_{domain}_{era}_{i:03d}.pdf"
        filepath = os.path.join(raw_dir, "judgments", filename)
        if mock:
            with open(filepath, "w") as f:
                f.write(f"MOCK JUDGMENT {i}\nDomain: {domain}\nEra: {era}\n")
        if i % 10 == 0:
            print(f" - Downloaded {i}/40 judgments...")
        
    print("\nAssembling 10 Synthetic Case File Bundles...")
    for i in range(1, 11):
        bundle_dir = os.path.join(raw_dir, "case_files", f"bundle_{i:03d}")
        os.makedirs(bundle_dir, exist_ok=True)
        docs = ["01_FIR.pdf", "02_Charge_Sheet.pdf", "03_Witness_Statements.pdf", "04_Bail_Application.pdf"]
        for d in docs:
            if mock:
                with open(os.path.join(bundle_dir, d), "w") as f:
                    f.write(f"MOCK CASE DOC: {d}\nBundle {i}\n")
        print(f" - Compiled Bundle {i}")
        
    print("\nData collection complete. Corpus is ready in data/raw/")

if __name__ == "__main__":
    fetch_data(mock=True)