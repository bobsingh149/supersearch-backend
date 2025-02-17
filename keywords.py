from rake_nltk import Rake
import nltk

# nltk.download('punkt_tab')

# Uses stopwords for english from NLTK, and all puntuation characters by
# default
r = Rake()

# Extraction given the text.
r.extract_keywords_from_text("I am looking for a yellow sundress that was wore on last year paris fashion week")

# # Extraction given the list of strings where each string is a sentence.
# r.extract_keywords_from_sentences(<list of sentences>)

# To get keyword phrases ranked highest to lowest.
res = r.get_ranked_phrases()


# To get keyword phrases ranked highest to lowest with scores.
# res=r.get_ranked_phrases_with_scores()
print(res)