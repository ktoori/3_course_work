import spacy
import pymorphy3

from mongoDB import TagStructure


class TagGenerate:
    """
    Класс функций для извлечения тегов из текста документа
    """

    def __init__(self):
        self.nlp = spacy.load('ru_core_news_sm')
        self.morph = pymorphy3.MorphAnalyzer()


    def get_candidates(self, text):
        """
        Возвращает словарь фраз и слов - возможных тегов с индексами их вхождения
        :param text: текст документа, обработанный с помощью spacy
        :return: массив тегов
        """
        candidates = {}
        candidates_tokens = []

        for i in range(0, len(text)):
            token = text[i]

            if token.pos_ == "NOUN":
                candidates.setdefault(self.to_nominative_case(token.text.lower()), []).append(i)
            if token.pos_ in ("ADJ", "NOUN", "PROPN"):
                candidates_tokens.append(self.to_nominative_case(token.text.lower()))
            else:
                if len(candidates_tokens) == 2:
                    cand_phrase = " ".join(candidates_tokens)
                    candidates.setdefault(cand_phrase, []).append(i - 2)
                    candidates_tokens = []
                else:
                    candidates_tokens = []

        if len(candidates_tokens) == 2:
            cand_phrase = " ".join(candidates_tokens)
            candidates.setdefault(cand_phrase, []).append(len(text)-2)

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

        for candidate, positions in candidates.items():
            first_enter = min(positions)
            frequency = len(positions)
            pos_score = 1 - (first_enter/total_tokens)
            score = frequency*pos_score
            features[candidate] = {
                "frequency": frequency,
                "first_enter": first_enter,
                "score": score
            }

        return features


    def to_nominative_case(self, phrase):
        """
        Приводит фразу к именительному падежу слова
        :param phrase: входной текст
        :return: текст в именительном падеже
        """
        words = phrase.split()

        nominative_words = []

        for word in words:
            word_norm = self.morph.parse(word)[0].inflect({'sing', 'nomn'})
            if word_norm:
                nominative_words.append(word_norm.word)
            else:
                nominative_words.append(word)

        if len(nominative_words) == 0:
            return ""
        return " ".join(nominative_words)


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
        tag_structure = TagStructure()
        other_tags = tag_structure.get_dict_by_name("other_tags")
        for candidate, feature in sorted_candidates:
            tag = self.to_nominative_case(candidate)
            if (tag) and (tag not in answer) and (tag in other_tags):
                answer.append(tag)

        return answer[:num_keywords]
