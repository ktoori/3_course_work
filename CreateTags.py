import spacy
from collections import defaultdict
import pymorphy3

import Dictionaries

nlp = spacy.load('ru_core_news_sm')

def extract_candidate_keyphrases(doc):
    candidates = []
    candidate_tokens = []

    for token in doc:
        if token.pos_ in ("ADJ", "NOUN", "PROPN"):
            candidate_tokens.append(token.text.lower())
        else:
            if candidate_tokens:
                candidate_phrase = " ".join(candidate_tokens)
                candidates.append(candidate_phrase)
                candidate_tokens = []
    if candidate_tokens:
        candidate_phrase = " ".join(candidate_tokens)
        candidates.append(candidate_phrase)

    return candidates

def compute_candidate_features(candidates, doc):
    total_tokens = len(doc)
    features = defaultdict(lambda: {"freq": 0, "first_occurrence": total_tokens})

    for candidate in candidates:
        features[candidate]["freq"] += 1

    for candidate in features:
        candidate_tokens = candidate.split()
        first_index = total_tokens
        for i in range(total_tokens - len(candidate_tokens) + 1):
            window = [doc[j].text.lower() for j in range(i, i + len(candidate_tokens))]
            if window == candidate_tokens:
                first_index = i
                break
        features[candidate]["first_occurrence"] = first_index

    for candidate, feat in features.items():
        pos_factor = 1 - (feat["first_occurrence"] / total_tokens)
        feat["score"] = feat["freq"] * pos_factor

    return features

def to_nominative_case(phrase):
    morph = pymorphy3.MorphAnalyzer()
    words = phrase.split()
    nominative_words = []

    for word in words:
        word_norm = morph.parse(word)[0].inflect({'sing', 'nomn'})
        if word_norm:
            nominative_words.append(word_norm.word)
        else:
            nominative_words.append(word)
    return ' '.join(nominative_words)

def extract_keywords(text, num_keywords=15):
    doc = nlp(text)
    candidates = extract_candidate_keyphrases(doc)
    candidate_features = compute_candidate_features(candidates, doc)
    sorted_candidates = sorted(candidate_features.items(), key=lambda x: x[1]["score"], reverse=True)

    answer = []
    for candidate, feat in sorted_candidates[:50]:
        tag = to_nominative_case(candidate)
        if (tag) and (tag not in answer) and (tag in Dictionaries.other_tags):
            answer.append(tag)
    return answer[:num_keywords]
