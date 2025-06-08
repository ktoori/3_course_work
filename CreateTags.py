import spacy
import pymorphy3

import Dictionaries

class TagService:
    """
    Класс функций для извлечения тегов из текста документа
    """

    def __init__(self):
        self.nlp = spacy.load('ru_core_news_sm')


    def get_candidates(self, text):
        """
        Возвращает список фраз и слов - возможных тегов
        :param text: текст документа, обработанный с помощью spacy
        :return: массив тегов
        """
        candidates = []
        candidates_tokens = []

        for token in text:
            if token.pos_ in ("ADJ", "NOUN", "PROPN"):
                candidates_tokens.append(token.text.lower())
            else:
                if candidates_tokens:
                    cand_phrase = " ".join(candidates_tokens)
                    candidates.append(cand_phrase)
                    candidates_tokens = []

        if candidates_tokens:
            cand_phrase = " ".join(candidates_tokens)
            candidates.append(cand_phrase)

        return candidates


    def feature_counting(self, candidates, doc_text):
        """
        Подсчитывает вероятность, что кандидат является тегом
        :param candidates: список кандидатов
        :param doc_text: текст документа, обработанный spacy
        :return: словарь, где ключ - кандидат, значение - словарь с полями: частота, первое вхождение, вероятность
        """
        total_tokens = len(doc_text)
        features = {}

        for candidate in candidates:
            if candidate not in features:
                features[candidate] = {"frequency": 0, "first_enter": total_tokens}
            features[candidate]["frequency"] += 1

        for candidate in features:
            candidate_tokens = candidate.split()
            first_index = total_tokens
            for i in range(total_tokens - len(candidate_tokens) + 1):
                window = []
                for j in range(i, i + len(candidate_tokens)):
                    window.append(doc_text[j].text.lower())
                if window == candidate_tokens:
                    first_index = i
                    break
            features[candidate]["first_enter"] = first_index

        for candidate, feat in features.items():
            pos_score = 1 - (feat["first_enter"]/total_tokens)
            feat["score"] = feat["frequency"]*pos_score

        return features


    def to_nominative_case(self, phrase):
        """
        Приводит фразу к именительному падежу слова
        :param phrase: входной текст
        :return: текст в именительном падеже
        """
        morph = pymorphy3.MorphAnalyzer()
        words = phrase.split()
        nominative_words = []

        for word in words:
            word_norm = morph.parse(word)[0].inflect({'sing', 'nomn'})
            if word_norm:
                nominative_words.append(word)
            else:
                nominative_words.append(word)

        return ' '.join(nominative_words)


    def extract_keywords(self, text, num_keywords=15):
        """
        Функция извлечения ключевого слова из текста
        :param text: текст документа
        :param num_keywords: количество ключевых слов в результате
        :return: массив ключевых слов
        """
        doc = self.nlp(text)
        candidates = self.get_candidates(doc)
        candidates_features = self.feature_counting(candidates, doc)
        sorted_candidates = sorted(candidates_features.items(), key=lambda x: x[1]["score"], reverse = True)

        answer = []
        for candidate, feature in sorted_candidates:
            tag = self.to_nominative_case(candidate)
            if (tag) and (tag not in answer) and (tag in Dictionaries.other_tags):
                answer.append(tag)

        return answer[:num_keywords]
