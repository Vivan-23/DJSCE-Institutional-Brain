import structlog
from typing import TypedDict

log = structlog.get_logger()


class EntityResult(TypedDict):
    persons: list[str]
    orgs: list[str]


class NERService:
    def __init__(self) -> None:
        self.nlp = None
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
            self.nlp.max_length = 2_000_000
            log.info("spaCy model loaded", model="en_core_web_sm")
        except OSError:
            log.warning(
                "spaCy model not found — NER disabled. "
                "Run: python -m spacy download en_core_web_sm"
            )
        except Exception as e:
            log.error("spaCy load error", error=str(e))

    def extract_entities(self, text: str) -> EntityResult:
        if not self.nlp:
            return {"persons": [], "orgs": []}

        # Truncate to avoid runaway processing on huge documents
        doc = self.nlp(text[:100_000])

        persons = sorted({
            ent.text.strip()
            for ent in doc.ents
            if ent.label_ == "PERSON" and len(ent.text.strip()) > 2
        })
        orgs = sorted({
            ent.text.strip()
            for ent in doc.ents
            if ent.label_ in ("ORG", "PRODUCT") and len(ent.text.strip()) > 2
        })

        return {"persons": persons, "orgs": orgs}


ner_service = NERService()
