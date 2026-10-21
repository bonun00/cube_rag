import re

from backend.domain.alg_extractor import extract

CPLL_CASES = ["H Permutation", "Aa Permutation", "Ab Permutation", "E Permutation"]


def template_alg_calls(html: str) -> int:
    """페이지 하단 Transclusion 보고서의 Template:Alg 호출 수."""
    return int(re.search(r"\s(\d+) Template:Alg\n", html).group(1))


def test_cpll_has_exactly_33_algs(cpll_parse):
    html = cpll_parse["parse"]["text"]["*"]
    assert template_alg_calls(html) == 33
    assert len(extract(html).algs) == 33


def test_alg_count_matches_template_calls_on_pll(pll_parse):
    html = pll_parse["parse"]["text"]["*"]
    assert len(extract(html).algs) == template_alg_calls(html)


def test_cpll_cases_and_groups(cpll_parse):
    algs = extract(cpll_parse["parse"]["text"]["*"]).algs
    cases = list(dict.fromkeys(a.case for a in algs))
    assert cases == CPLL_CASES                      # "CPLL Algorithms" h2는 공식이 없어 케이스가 아니다
    assert {a.group for a in algs} == {"Speedsolving Algorithms", "Optimal Algorithms"}


def test_alg_and_stage_decoded(cpll_parse):
    algs = extract(cpll_parse["parse"]["text"]["*"]).algs
    first = algs[0]
    assert (first.case, first.group, first.stage) == ("H Permutation", "Speedsolving Algorithms", "PLL")
    assert first.alg == "M2' U M2' U2 M2' U M2'"
    optimal_stages = {a.stage for a in algs if a.group == "Optimal Algorithms"}
    assert "HTM 9" in optimal_stages                # stage의 +는 공백


def test_youtube_link_is_video_of_previous_alg(cpll_parse):
    algs = extract(cpll_parse["parse"]["text"]["*"]).algs
    with_video = [a for a in algs if a.video]
    assert len(with_video) == 4                     # 영상 링크 8개 = 카메라 아이콘 + [1] 번호, 공식당 1개
    assert algs[1].video and "youtube.com/watch?v=pmA8ToRfOXQ" in algs[1].video
    assert algs[0].video is None


def test_text_is_clean_and_positions_align(cpll_parse):
    content = extract(cpll_parse["parse"]["text"]["*"])
    assert "[edit]" not in content.text
    assert "NewPP" not in content.text and "Template:Alg" not in content.text
    assert "\nH Permutation\n" in content.text
    for a in content.algs:
        assert content.text[a.pos:].startswith(a.alg.split()[0])
