from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "expense_data_1.csv"

# Starter training examples.
TRAINING_DATA = [
    ("pizza burger sandwich dinner lunch breakfast", "Food"),
    ("restaurant cafe coffee tea snacks groceries", "Food"),
    ("milk vegetables fruits food delivery", "Food"),
    ("jeans shirt shoes clothes shopping", "Shopping"),
    ("bought trousers jacket dress online shopping", "Shopping"),
    ("amazon purchase bag watch", "Shopping"),
    ("metro bus train taxi cab petrol fuel", "Transport"),
    ("uber ola auto fare parking", "Transport"),
    ("electricity water gas internet phone bill", "Bills"),
    ("rent house maintenance", "Bills"),
    ("doctor medicine pharmacy hospital", "Healthcare"),
    ("movie cinema concert entertainment", "Entertainment"),
    ("hotel vacation flight travel ticket", "Travel"),
    ("course books tuition education stationery", "Education"),
    ("salary bonus freelance income", "Income"),
]

# Direct rules help with obvious descriptions.
KEYWORDS = {
    "Shopping": [
        "jeans", "shirt", "clothes", "clothing", "shoes",
        "dress", "jacket", "trousers", "shopping", "amazon",
        "flipkart", "bag", "watch"
    ],
    "Food": [
        "pizza", "burger", "brownie", "dinner", "lunch",
        "breakfast", "restaurant", "grocery", "groceries",
        "coffee", "tea", "snacks", "food", "sandwich"
    ],
    "Transport": [
        "metro", "bus", "train", "taxi", "uber", "ola",
        "petrol", "fuel", "parking", "auto fare", "fare"
    ],
    "Bills": [
        "electricity", "water bill", "gas bill", "internet",
        "mobile recharge", "phone bill", "rent"
    ],
    "Healthcare": [
        "doctor", "medicine", "pharmacy", "hospital", "medical"
    ],
    "Entertainment": [
        "movie", "cinema", "concert", "game ticket"
    ],
    "Travel": [
        "hotel", "flight", "vacation", "travel ticket"
    ],
    "Education": [
        "course", "tuition", "textbook", "stationery", "college fee"
    ],
}

# Read optional training examples from the CSV.
if CSV_PATH.exists():
    try:
        df = pd.read_csv(CSV_PATH)

        if {"Note", "Category"}.issubset(df.columns):
            for _, row in df.iterrows():
                note = str(row["Note"]).strip()
                category = str(row["Category"]).strip()

                if (
                    note
                    and note.lower() != "nan"
                    and category
                    and category.lower() != "nan"
                ):
                    TRAINING_DATA.append((note, category))

    except Exception as error:
        print("CSV training data could not be loaded:", error)


# Remove blank examples and categories with too few examples
# are still allowed because LinearSVC supports the available labels.
TRAINING_DATA = [
    (description, category)
    for description, category in TRAINING_DATA
    if description.strip() and category.strip()
]

descriptions = [item[0] for item in TRAINING_DATA]
categories = [item[1] for item in TRAINING_DATA]

model = Pipeline([
    (
        "tfidf",
        TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True
        )
    ),
    ("classifier", LinearSVC())
])

model.fit(descriptions, categories)


def predict_category(description):
    text = str(description).strip()
    lower_text = text.lower()

    if not text:
        return "Other"

    # Keyword rules take priority for common, clear descriptions.
    for category, words in KEYWORDS.items():
        if any(word in lower_text for word in words):
            return category

    # Otherwise, use the trained machine learning model.
    return str(model.predict([text])[0])