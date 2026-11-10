import pytest

from signal_problems.domain.causes import CauseCategory, cause_for, incident_code


@pytest.mark.parametrize(
    ("code", "category"),
    [
        ("EUDO", CauseCategory.EQUIPMENT),
        ("MUIS", CauseCategory.PASSENGERS_AND_OTHER),
        ("PUSI", CauseCategory.INFRASTRUCTURE),
        ("SUDP", CauseCategory.SECURITY),
        ("TUNOA", CauseCategory.OPERATIONS),
        ("XXXXX", CauseCategory.UNKNOWN),
    ],
)
def test_category_from_prefix(code: str, category: CauseCategory) -> None:
    assert cause_for(code).category is category


def test_published_code_has_description() -> None:
    assert cause_for(" pusi ").description == "Signals or Related Components Failure"


def test_unpublished_code_keeps_category_without_description() -> None:
    cause = cause_for("TUNCA")  # used 1,205 times since 2025, missing from the TTC's code list
    assert cause.description is None
    assert cause.category is CauseCategory.OPERATIONS


@pytest.mark.parametrize(
    ("code", "is_signal"),
    [
        ("PUSI", True),  # Signals or Related Components Failure
        ("PUATC", True),  # ATC Signals Other
        ("TUMVS", False),  # Operator Violated Signal: crew, not signals
        ("EUATC", False),  # ATC equipment on the train
        ("MUIS", False),
        ("PUNEW", False),  # infrastructure code that isn't published
    ],
)
def test_signal_problems(code: str, is_signal: bool) -> None:
    assert cause_for(code).is_signal_problem is is_signal


@pytest.mark.parametrize(
    ("word", "mode", "category"),
    [
        ("MECHANICAL", "bus", CauseCategory.EQUIPMENT),
        ("LATE LEAVING GARAGE", "streetcar", CauseCategory.OPERATIONS),
        ("COLLISION - TTC", "bus", CauseCategory.OPERATIONS),  # TFPD, not PFPD, since 2025
        ("DIVERSION", "streetcar", CauseCategory.PASSENGERS_AND_OTHER),  # MTDV
        ("OVERHEAD", "streetcar", CauseCategory.INFRASTRUCTURE),  # PTOV
        ("INVESTIGATION", "streetcar", CauseCategory.PASSENGERS_AND_OTHER),  # MTPOL
        ("INVESTIGATION", "bus", CauseCategory.SECURITY),  # SFPOL
        ("HELD BY", "bus", CauseCategory.UNKNOWN),  # held by police (S) or by a parade (M)?
    ],
)
def test_incident_words_take_the_category_of_the_matching_code(
    word: str, mode: str, category: CauseCategory
) -> None:
    cause = cause_for(word, mode)
    assert (cause.category, cause.description) == (category, word)


def test_incident_words_mean_nothing_to_the_subway() -> None:
    assert cause_for("MECHANICAL").description is None


@pytest.mark.parametrize(
    ("logged", "stored"),
    [("Late  ", "LATE"), ("Collision - TTC ", "COLLISION - TTC"), ("e", ""), ("", "")],
)
def test_incident_code(logged: str, stored: str) -> None:
    assert incident_code(logged) == stored
