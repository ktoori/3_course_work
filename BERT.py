from transformers import AutoTokenizer, AutoModel
import torch

import ReadFile

from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

tokenizer = AutoTokenizer.from_pretrained("cointegrated/rubert-tiny2")
model = AutoModel.from_pretrained("cointegrated/rubert-tiny2")

query = "Код программной инженерии"
document = ReadFile.extract_pdf_text("napravlenia.pdf")

def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state[0][0].numpy()


query_embedding = get_embedding(query)

sentences = document.split('\n')
sentence_embeddings = [get_embedding(sentence) for sentence in sentences]


similarities = [cosine_similarity(query_embedding.reshape(1, -1), sent_embedding.reshape(1, -1))[0][0] for sent_embedding in sentence_embeddings]
best_match_index = np.argmax(similarities)
best_match_sentence = sentences[best_match_index]

print(f"Запрос: {query}")
print(f"Лучшее соответствующее предложение: {best_match_sentence}")
print(f"Схожесть: {similarities[best_match_index]}")