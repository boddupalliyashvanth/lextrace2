import uuid

from contracts.interfaces import Retriever, SlotFiller
from contracts.schemas import Claim, Evidence, MissingItem, SlotSpec


class DefaultSlotFiller(SlotFiller):
    def fill(self, slots: list[SlotSpec], retriever: Retriever, case_doc_ids: list[str]) -> tuple[dict[str, Claim], list[MissingItem]]:
        filled_claims = {}
        missing = []
        
        for slot in slots:
            # Step 1: Search the case file for this specific slot
            query = f"{slot.name} {slot.description} {' '.join(slot.source_hints)}"
            hits = retriever.search(query, k=3, doc_types=['case_file'], doc_ids=case_doc_ids)
            
            if hits:
                # Mock extracting the value from the best hit
                best_hit = hits[0]
                claim = Claim(
                    claim_id=str(uuid.uuid4()),
                    text=f"Value for {slot.name} is extracted.",
                    kind='fact',
                    evidence=[Evidence(chunk_id=best_hit.chunk.chunk_id, quote=best_hit.chunk.text[:20])],
                    depends_on=[]
                )
                filled_claims[slot.name] = claim
            else:
                # Step 2: Handle missing value
                if slot.required:
                    missing.append(MissingItem(
                        slot=slot.name,
                        why_needed=slot.description,
                        queries_tried=[query],
                        status="not_found"
                    ))
                    
        return filled_claims, missing
