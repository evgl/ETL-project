import pytest
from prospector.nodes.headers import Header

from .conftest import MockTxt


def test_header_constructor():
    h = Header(elements=[1, 2, 3], p=10, indices=[4, 5, 6])
    assert h.elements == [1, 2, 3]
    assert h.ref == {10: [4, 5, 6]}


def test_header_match(mock_texts):
    h1 = Header(elements=[mock_texts[0], mock_texts[3], mock_texts[0]], p=0, indices=[])
    h2 = Header(elements=[mock_texts[4], mock_texts[0], mock_texts[5], mock_texts[1]], p=0, indices=[])
    assert h1.match(h2) == {0: 1, 2: 3} or h1.match(h2) == {0: 3, 2: 1}


def test_header_match_with_digits(mock_texts):
    h1 = Header(elements=[mock_texts[0], mock_texts[4]], p=0, indices=[])
    h2 = Header(elements=[mock_texts[2], mock_texts[5]], p=0, indices=[])
    assert h1.match(h2) == {1: 1}


def test_header_match_not_strict(mock_texts):
    h1 = Header(elements=[mock_texts[0], mock_texts[3]], p=0, indices=[])
    h2 = Header(elements=[mock_texts[4], mock_texts[2]], p=0, indices=[])
    assert h1.match(h2) == {}
    assert h1.match(h2, strict=False) == {0: 1}


def test_header_multiple_match(mock_texts):
    h1 = Header(elements=[mock_texts[0], mock_texts[0]], p=0, indices=[])
    h2 = Header(elements=[mock_texts[1], mock_texts[1]], p=0, indices=[])
    assert h1.match(h2) == {0: 1, 1: 0} or h1.match(h2) == {0: 0, 1: 1}


@pytest.mark.parametrize("pos,match", [((0, 1, 0, 1), {1: 0}), ((0.5, 1.5, 0, 1), {1: 0}),
                                       ((0, 1, 0.5, 1.5), {1: 0}), ((0.5, 1.5, 0.5, 1.5), {1: 0}),
                                       ((2, 3, 0, 1), {}), ((0, 1, 2, 3), {}),
                                       ((2, 3, 2, 3), {}), ((-0.5, 0.5, 0, 1), {1: 0}),
                                       ((0, 1, -0.5, 0.5), {1: 0}), ((-0.5, 0.5, -0.5, 0.5), {1: 0}),
                                       ((-3, -2, 0, 1), {}), ((0, 1, -3, -2), {}),
                                       ((-3, -2, -3, -2), {})])
def test_header_ov_match(pos, match):
    h1 = Header(elements=[MockTxt(x0=-10, x1=-9, y0=-10, y1=-9), MockTxt()], p=0, indices=[])
    h2 = Header(elements=[MockTxt(x0=pos[0], x1=pos[1], y0=pos[2], y1=pos[3])], p=0, indices=[])
    assert h1.ov_match(h2) == match


def test_header_ov_match_multiple():
    h1 = Header(elements=[MockTxt(x0=-10, x1=-9, y0=-10, y1=-9), MockTxt()], p=0, indices=[])
    h2 = Header(elements=[MockTxt(x0=0, x1=0.9, y0=0, y1=0.9), MockTxt(x0=0, x1=0.5, y0=0, y1=0.5)], p=0, indices=[])
    assert h1.ov_match(h2) == {1: 0}


def test_header_merge(mock_texts):
    h1 = Header(elements=[mock_texts[0], mock_texts[3], mock_texts[0]], p=0, indices=[0, 1, 2])
    h2 = Header(elements=[mock_texts[4], mock_texts[0], mock_texts[5], mock_texts[1]], p=1, indices=[4, 5, 6, 7])
    h1.merge(h2, h1.match(h2))
    assert h1.elements == [mock_texts[0], mock_texts[0]]
    assert 0 in h1.ref and set(h1.ref[0]) == set([0, 2])
    assert 1 in h1.ref and set(h1.ref[1]) == set([5, 7])


def test_header_assign(mock_texts):
    h1 = Header(elements=[mock_texts[0], mock_texts[3], mock_texts[0]], p=0, indices=[0, 1, 2])
    h2 = Header(elements=[mock_texts[4], mock_texts[0], mock_texts[5], mock_texts[1]], p=1, indices=[4, 5, 6, 7])
    h1.assign(h2, h1.match(h2))
    assert h1.elements == [mock_texts[0], mock_texts[3], mock_texts[0]]
    assert 0 in h1.ref and set(h1.ref[0]) == set([0, 1, 2])
    assert 1 in h1.ref and set(h1.ref[1]) == set([5, None, 7])
