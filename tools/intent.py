import joblib

_model = None


def classify_intent(text: str) -> str:
    global _model
    if _model is None:
        _model = joblib.load("models/intent.joblib")
    return _model.predict([text])[0]