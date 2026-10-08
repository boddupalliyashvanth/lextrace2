import random

def compute_usefulness(text: str, gold_points: list[str]) -> dict:
    """
    Rubric 0 to 4 for completeness against gold_points, correctness, 
    structure and actionability, and appropriate abstention.
    LLM judge plus human-scored 20% sample (mocked here).
    """
    # Mock LLM judge
    score = 4.0 if text else 0.0
    
    # Mock Cohen's kappa for the human sample
    kappa = 0.85
    
    return {
        "usefulness_score": score,
        "human_kappa": kappa
    }
