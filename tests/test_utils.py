import pytest

from pdfminer.layout import LTTextContainer, LTAnno
from prospector.utils import is_same_bbox, is_similar_element
from prospector.miner import merge_lines

from .conftest import MockLine, MockChar, MockTxt


def test_is_same_bbox():
    elem1, elem2, elem3 = LTTextContainer(), LTTextContainer(), LTTextContainer()
    elem1.set_bbox((45, 45, 50, 50))
    elem2.set_bbox((45, 45, 50, 50))
    elem3.set_bbox((50, 50, 60, 60))
    assert is_same_bbox(elem1.bbox, elem1.bbox)
    assert is_same_bbox(elem1.bbox, elem2.bbox)
    assert not is_same_bbox(elem2.bbox, elem3.bbox)


def test_is_same_bbox_atol():
    elem1, elem2, elem3 = LTTextContainer(), LTTextContainer(), LTTextContainer()
    elem1.set_bbox((45, 45, 50, 50))
    elem2.set_bbox((45.05, 44.95, 50.05, 49.95))
    elem3.set_bbox((45.5, 44.5, 50.5, 49.5))
    assert is_same_bbox(elem1.bbox, elem1.bbox, abs_tol=0.1)
    assert is_same_bbox(elem1.bbox, elem2.bbox, abs_tol=0.1)
    assert not is_same_bbox(elem2.bbox, elem3.bbox, abs_tol=0.1)


@pytest.mark.parametrize("idx,res", [((0, 1), (True, True)), ((0, 2), (False, True)),
                                     ((0, 3), (False, False)), ((0, 4), (False, True)),
                                     ((4, 5), (True, True)), ((4, 6), (True, True)),
                                     ((0, 7), (False, True)), ((7, 8), (True, True)),
                                     ((9, 10), (True, True)), ((9, 11), (False, True)),
                                     ((9, 12), (True, True))])
def test_is_similar_element(mock_texts, idx, res):
    assert is_similar_element(mock_texts[idx[0]], mock_texts[idx[1]]) == res


@pytest.mark.parametrize("x", [True, False])
@pytest.mark.parametrize("kwargs,diff,res", [({}, 0, True), ({}, 0.009, True),
                                             ({}, 1, False), ({"abs_tol": 1}, 1, True),
                                             ({"abs_tol": 1}, 3, False)])
def test_is_similar_element_margin(kwargs, diff, res, x):
    e1 = MockTxt(x1=100, y1=100, txt="Test")
    e2 = MockTxt(
        x1=100 + diff if x else 100,
        y1=100 + diff if not x else 100,
        txt="Test"
    )
    assert is_similar_element(e1, e2, **kwargs)[0] == res


def test_merge_lines_wrong_type():
    with pytest.raises(AssertionError):
        merge_lines(0, 0)

    with pytest.raises(AssertionError):
        merge_lines(0, MockLine([]))

    with pytest.raises(AssertionError):
        merge_lines(MockLine([]), 0)


def test_merge_lines_empty():
    line = MockLine([])
    merge_lines(line, MockLine([]))
    assert len(line) == 0


def test_merge_lines_simple():
    line1 = MockLine([LTAnno('a')])
    line2 = MockLine([LTAnno('b')])
    merge_lines(line1, line2)
    assert len(line1) == 2 and line1.get_text() == "ab"
    assert len(line2) == 1 and line2.get_text() == "b"


def test_merge_lines_clean_l1():
    line1 = MockLine([LTAnno('a'), LTAnno(' '), LTAnno('\n')])
    line2 = MockLine([LTAnno('b')])
    merge_lines(line1, line2)
    assert len(line1) == 4 and line1.get_text() == "a b"


def test_merge_lines_no_clean_l2():
    line1 = MockLine([LTAnno('a')])
    line2 = MockLine([LTAnno('b'), LTAnno(' '), LTAnno('\n')])
    merge_lines(line1, line2)
    assert len(line1) == 4 and line1.get_text() == "ab \n"


def test_merge_lines_pos():
    line1 = MockLine([MockChar(txt='a')])
    line2 = MockLine([MockChar(txt='b', x0=3, x1=4)])
    merge_lines(line1, line2)
    assert line1.get_text() == "ab"
    assert line1.x0 == 0 and line1.x1 == 4
