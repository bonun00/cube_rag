from backend.domain.alg_extractor import Alg, extract
from backend.domain.alg_picker import case_names, pick, slice_rotation_count


def alg(text, video=None, case="Aa Permutation", group="Speedsolving Algorithms", order=0):
    return Alg(case=case, group=group, alg=text, stage="PLL", video=video, pos=0, order=order)


def test_only_speedsolving_group_of_case(cpll_parse):
    algs = extract(cpll_parse["parse"]["text"]["*"]).algs
    picked = pick(algs, "Aa Permutation", "심화")
    assert 1 <= len(picked) <= 3
    assert all(a.case == "Aa Permutation" and a.group == "Speedsolving Algorithms" for a in picked)


def test_beginner_gets_one_advanced_up_to_three(cpll_parse):
    algs = extract(cpll_parse["parse"]["text"]["*"]).algs
    assert len(pick(algs, "H Permutation", "입문")) == 1
    assert len(pick(algs, "H Permutation", "심화")) == 3


def test_video_first_then_wiki_order():
    algs = [alg("R U R'"), alg("L U L'", video="https://youtube.com/watch?v=x"), alg("F R F'")]
    assert [a.alg for a in pick(algs, "Aa Permutation", "심화")] == ["L U L'", "R U R'", "F R F'"]


def test_beginner_prefers_fewer_slices_and_rotations():
    algs = [alg("x R' U R' D2 R U' R' D2 R2 x'"), alg("R U R' U'")]
    assert pick(algs, "Aa Permutation", "입문")[0].alg == "R U R' U'"
    assert pick(algs, "Aa Permutation", "심화")[0].alg.startswith("x")   # 심화는 위키 순서 그대로


def test_case_match_ignores_spacing_and_case():
    assert pick([alg("R U R'")], "  aa permutation ", "심화")


def test_unknown_case_returns_nothing():
    assert pick([alg("R U R'")], "Z Permutation", "심화") == []


def test_helpers():
    assert slice_rotation_count("M2' U M2' y x2 R") == 4
    assert case_names([alg("a", case="H"), alg("b", case="Aa"), alg("c", case="H")]) == ["H", "Aa"]
