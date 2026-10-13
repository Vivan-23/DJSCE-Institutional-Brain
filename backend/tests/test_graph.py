"""Knowledge-graph entity cleaning: what NER output is allowed into Neo4j."""
from app.services.graph_service import clean_entity, graph_entities, is_credible_person, person_name


class TestCleanEntity:
    def test_rejects_multiline_and_sentence_fragments(self):
        assert clean_entity("Department of Computer Engineering: Laboratory Upgrades\nAcademic Year:") is None
        assert clean_entity("a b c d e f g h") is None
        assert clean_entity("AI") is None

    def test_normalizes_whitespace_and_punctuation(self):
        assert clean_entity("  IQAC, ") == "IQAC"


class TestPeople:
    def test_titles_are_stripped(self):
        assert person_name("Dr. (Mrs.) Meera   Narvekar") == "Meera Narvekar"

    def test_honorific_in_text_is_evidence(self):
        assert is_credible_person("Meera Narvekar", "Head of Department is Dr. (Mrs.) Meera Narvekar.")

    def test_course_and_tool_names_are_rejected(self):
        text = "Electives include Machine Learning and labs have 32 GB RAM workstations."
        assert not is_credible_person("Machine Learning", text)
        assert not is_credible_person("GB RAM", text)
        assert not is_credible_person("Embeddings", text)

    def test_roster_match_is_evidence(self):
        assert is_credible_person("Karan Shah", "Karan Shah will compile the syllabus.", known=["Prof. Karan Shah"])


class TestGraphEntities:
    def test_speakers_always_included_and_bodies_cleaned(self):
        text = "Dr. Aditi Rao: The IQAC review is complete.\nProf. Neha Iyer: Agreed."
        people, bodies = graph_entities(
            text,
            {"persons": ["Machine Learning"], "orgs": ["IQAC", "Bad\nfragment"]},
            known_people=["Dr. Aditi Rao", "Prof. Neha Iyer"],
        )
        assert sorted(p["name"] for p in people) == ["Aditi Rao", "Neha Iyer"]
        assert all(p["email"].endswith("@example.com") for p in people)
        assert bodies == ["IQAC"]


class TestBodies:
    def test_keeps_institutional_units_and_acronyms(self):
        from app.services.graph_service import body_name

        assert body_name("the Advanced Computing Laboratory") == "Advanced Computing Laboratory"
        assert body_name("Iqac") == "IQAC"
        assert body_name("J. Sanghvi College of Engineering") == "DJSCE"

    def test_drops_courses_companies_and_fragments(self):
        from app.services.graph_service import body_name

        for noise in ("Machine Learning", "Institute Level Optional Course", "Microsoft", "? Big Data Analysis (Dept", "Data Mining and", "Head of Department"):
            assert body_name(noise) is None, noise

    def test_offices_from_profile_are_linked_when_named(self):
        _, bodies = graph_entities("Escalate to the Examination Cell and the Board of Studies.", {"persons": [], "orgs": []})
        assert {"Examination Cell", "Board of Studies"} <= set(bodies)


class TestSpeakers:
    def test_header_lines_are_not_speakers(self):
        from app.services.transcript_service import transcript_service

        transcript = (
            "Academic Council Meeting: Elective review\nDate: October 4, 2026\n"
            "Attendees: Dr. Aditi Rao\nDr. Aditi Rao: Welcome everyone.\nProf. Karan Shah: I will compile it."
        )
        speakers = {s for s, _ in transcript_service._split_utterances(transcript)}
        assert speakers == {"Dr. Aditi Rao", "Prof. Karan Shah"}
