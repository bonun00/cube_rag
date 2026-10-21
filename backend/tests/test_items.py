import mwparserfromhell

from backend.domain.items import clean_value, first_int, parse_infobox, split_proposers, summarize


def test_br_separated_proposers_are_split():
    raw = "[[Don Taylor|Donald Taylor]]<br/>[[John Conway]]<br />[[Anneke Treep]]"
    assert split_proposers(clean_value(raw)) == ["Donald Taylor", "John Conway", "Anneke Treep"]


def test_comma_and_ampersand_split():
    assert split_proposers("A, B and C & D") == ["A", "B", "C", "D"]
    assert split_proposers("Brandon Lee") == ["Brandon Lee"]          # 이름 속 'and'는 나누지 않음


def test_link_followed_by_text_gets_space():
    assert clean_value("[[Jessica Fridrich]]while inventing pll?") == "Jessica Fridrich while inventing pll?"


def test_numeric_infobox_keys_dropped():
    code = mwparserfromhell.parse("{{Method Infobox|name=Roux|anames|algs=9-42}}")
    name, fields = parse_infobox(code)
    assert name == "Method Infobox"
    assert fields == {"name": "Roux", "algs": "9-42"}


def test_first_int():
    assert first_int("~49") == 49
    assert first_int("Total: 78 to 119") == 78
    assert first_int("") is None and first_int(None) is None


def test_summary_cut_at_last_sentence_not_list_number():
    text = ("Sentence one is long enough to keep here. " * 12) + "Steps are listed below. 1. First block 2. Second"
    s = summarize(mwparserfromhell.parse(text), 500)
    assert len(s) <= 500 and s.endswith(".")
    assert not s.endswith(" 1.") and not s.endswith(" 2.")
