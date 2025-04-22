from rapidfuzz import fuzz

def is_similar(predefined: str, tag: str, threshold: int = 70) -> bool:
    score = fuzz.partial_ratio(predefined.lower(), tag.lower())
    return score >= threshold