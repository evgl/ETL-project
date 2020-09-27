import os
import copy
import tempfile

import pytest
from pdfminer.layout import LTTextContainer, LTRect, LTPage, LTAnno
from prospector import nodes
from prospector.nodes import Font, TableFont
from prospector.miner import LTTable
from prospector.document import Document
from prospector.nodes.headers import Header
from prospector.utils import get_unique_filename

from .conftest import Txt, MockPage, MockText, MockLine, MockChar, MockTxt, MockTable2


def test_one_by_one_single_elem():
    node_gen = nodes.OneByOne('1')()
    assert next(node_gen) == '1'
    with pytest.raises(StopIteration):
        next(node_gen)


def test_one_by_one_several_elem():
    node_gen = nodes.OneByOne(['1', '2', '3'])()
    assert next(node_gen) == '1'
    assert next(node_gen) == '2'
    assert next(node_gen) == '3'
    with pytest.raises(StopIteration):
        next(node_gen)


def test_extract_font_info():
    node = nodes.ExtractFontInfo()
    pages = [MockPage([
        MockText([MockLine([MockChar(font="Base")])]),
        MockText([MockLine([MockChar(font="BaseBold")])]),
        MockText([MockLine([MockChar(font="ItalicBase")])]),
        MockText([MockLine([MockChar(font="BoldBaseItalic")])]),
        MockText([MockLine([MockChar(font="Base", size=20)])]),
        MockText([MockLine([MockChar(font="Base")])], x0=100),
        MockText([MockLine([MockChar(font="Base", txt="X")])]),
        MockText([MockLine([MockChar(font="Base", txt="X"), MockChar(font="Base", txt="?")])]),
        MockText([MockLine([MockChar(font="Base", txt="X"), MockChar(font="Base", txt="'"), MockChar(font="Base", txt="s")])]),
        MockText([MockLine([MockChar(font="Base", txt="2"), MockChar(font="Base", txt=" "), MockChar(font="Base", txt="T")])]),
        MockText([MockLine([MockChar(font="Base", txt="2"), MockChar(font="Base", txt=" "), MockChar(font="Base", txt="T"),
                            MockChar(font="Base", txt=".")])]),
        MockText([MockLine([MockChar(font="Base"), MockChar(font="BoldBaseItalic", size=20)])]),
        MockText([MockLine([MockChar(font="Base", txt=","), MockChar(font="BoldBaseItalic", size=20)])]),
        MockText([MockLine([MockChar(font="Base", txt=","), MockChar(font="Base", txt=",")])]),
    ])]

    _, _, pages = node("x", "x", pages)

    assert pages[0]._objs[0].font == Font(size=10, bold=False, italic=False, caps=False, underline=False,
                                          title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[1].font == Font(size=10, bold=True, italic=False, caps=False, underline=False,
                                          title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[2].font == Font(size=10, bold=False, italic=True, caps=False, underline=False,
                                          title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[3].font == Font(size=10, bold=True, italic=True, caps=False, underline=False,
                                          title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[4].font == Font(size=20, bold=False, italic=False, caps=False, underline=False,
                                          title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[5].font == Font(size=10, bold=False, italic=False, caps=False, underline=False,
                                          title_like=False, sep_in_title=False, alignement=100)
    assert pages[0]._objs[6].font == Font(size=10, bold=False, italic=False, caps=True, underline=False,
                                          title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[7].font == Font(size=10, bold=False, italic=False, caps=True, underline=False,
                                          title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[8].font == Font(size=10, bold=False, italic=False, caps=True, underline=False,
                                          title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[9].font == Font(size=10, bold=False, italic=False, caps=True, underline=False,
                                          title_like=True, sep_in_title=False, alignement=0)
    assert pages[0]._objs[10].font == Font(size=10, bold=False, italic=False, caps=True, underline=False,
                                           title_like=True, sep_in_title=True, alignement=0)
    assert pages[0]._objs[11].font == Font(size=10, bold=False, italic=False, caps=False, underline=False,
                                           title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[12].font == Font(size=20, bold=True, italic=True, caps=False, underline=False,
                                           title_like=False, sep_in_title=False, alignement=0)
    assert pages[0]._objs[13].font is None


@pytest.mark.parametrize("kwargs,line_pos,txt_pos,res", [({}, (0, 50, 100, 50), (0, 50.5, 100, 50.5), True),
                                                         ({}, (0, 50, 100, 50), (0, 60, 100, 60), False),
                                                         ({'margin': 10}, (0, 50, 100, 50), (0, 60, 100, 60), True),
                                                         ({}, (0, 50, 100, 50), (0, 50.5, 30, 50.5), True),
                                                         ({}, (-5, 50, 100, 50), (0, 50.5, 100, 50.5), True),
                                                         ({}, (5, 50, 100, 50), (0, 50.5, 100, 50.5), True),
                                                         ({'margin': 10}, (5, 50, 100, 50), (0, 50.5, 100, 50.5), True),
                                                         ({}, (-100, 50, -1, 50), (0, 50.5, 100, 50.5), False),
                                                         ({}, (101, 50, 200, 50), (0, 50.5, 100, 50.5), False)])
def test_underline_font(kwargs, line_pos, txt_pos, res):
    node = nodes.ExtractFontInfo(**kwargs)

    class MockTxtWithLine(LTTextContainer):
        def __init__(self, x0, y0, x1, y1):
            super().__init__()
            self.x = [LTTextContainer()]
            self.x[0].get_text = lambda: "x"
            self.font = Font(size=1, bold=False, italic=False, caps=False, underline=False,
                             title_like=False, sep_in_title=False, alignement=1)
            self.x[0].x0, self.x[0].x1, self.x[0].y0, self.x[0].y1 = x0, x1, y0, y1

        def __iter__(self):
            return self.x.__iter__()

    pages = [[MockTxtWithLine(*txt_pos)]]
    lines = [LTRect(1, line_pos)]

    node._underline_elements(pages[0], lines)

    assert pages[0][0].font.underline == res


@pytest.mark.parametrize("idx,res", [(0, False), (1, False), (2, False), (3, False),
                                     (4, False), (5, True), (6, True), (7, True)])
def test_is_similar_text_font(font_reference, modified_fonts, idx, res):
    node = nodes.FindTitles()
    assert node._is_similar_text_font(modified_fonts[idx], font_reference) == res


def test_is_similar_text_font_self(font_reference):
    node = nodes.FindTitles()
    assert node._is_similar_text_font(font_reference, font_reference)


@pytest.mark.parametrize("size1,size2,res", [(10, 10, False), (10, 11, True),
                                             (11, 10, False), ("t", 10, False),
                                             (10, "t", False), ("t", "t", False)])
def test_is_smaller_font(size1, size2, res):
    node = nodes.FindTitles()
    f1 = TableFont() if size1 == "t" else Font(size=size1, bold=False, italic=False, underline=False, caps=False,
                                               title_like=False, sep_in_title=False, alignement=189)
    f2 = TableFont() if size2 == "t" else Font(size=size2, bold=False, italic=False, underline=False, caps=False,
                                               title_like=False, sep_in_title=False, alignement=189)
    assert node._is_smaller_font(f1, f2) == res


def test_find_similar_text_font(font_reference, modified_fonts):
    node = nodes.FindTitles()
    similar, other = node._find_similar_text_font(modified_fonts, font_reference)
    assert other == modified_fonts[:5]
    assert similar == modified_fonts[5:]


def test_get_next_font(font_data):
    node = nodes.FindTitles()
    ft_data, fonts = font_data
    header_1, header_2, text, weird_text, solo_last, tf = fonts

    i, font = node._get_next_font(ft_data[0], 1)
    assert font == header_2 and i == 2

    i, font = node._get_next_font(ft_data[0], 2)
    assert font == text and i == 4

    i, font = node._get_next_font(ft_data[0], 15)
    assert font == tf and i == 16

    i, font = node._get_next_font(ft_data[0], len(ft_data[0]) - 1)
    assert font is None and i == len(ft_data[0]) - 1


def test_has_text_between(font_data):
    node = nodes.FindTitles()
    ft_data, fonts = font_data
    header_1, header_2, text, weird_text, solo_last, tf = fonts

    assert node._has_text_between(ft_data[0], 1, [text])
    assert node._has_text_between(ft_data[0], 2, [text])
    assert node._has_text_between(ft_data[0], 15, [text, tf])
    assert not node._has_text_between(ft_data[0], len(ft_data[0]) - 1, [text])
    assert not node._has_text_between(ft_data[0], len(ft_data[0]) - 2, [text])


def test_find_next_title_font(font_data):
    node = nodes.FindTitles()
    ft_data, fonts = font_data
    header_1, header_2, text, weird_text, solo_last, tf = fonts

    # First it detect the weird edge case (a non-title)
    ft, rest, is_title = node._find_next_title_font(ft_data, [header_1, header_2, weird_text, solo_last], [text, tf])
    assert not is_title and ft == [solo_last] and rest == [header_1, header_2, weird_text]

    # Then it detect a non-title
    ft, rest, is_title = node._find_next_title_font(ft_data, [header_1, header_2, weird_text], [text, tf, solo_last])
    assert not is_title and ft == [weird_text] and rest == [header_1, header_2]

    # Then it detects header 2
    ft, rest, is_title = node._find_next_title_font(ft_data, [header_1, header_2], [text, tf, solo_last, weird_text])
    assert is_title and ft == [header_2] and rest == [header_1]

    # And finally header 1
    ft, rest, is_title = node._find_next_title_font(ft_data, [header_1], [text, tf, solo_last, weird_text, header_2])
    assert is_title and ft == [header_1] and rest == []


def test_find_titles(font_data_more_text):
    node = nodes.FindTitles()
    ft_data, fonts = font_data_more_text

    _, _, pages = node("x", "x", ft_data)

    # Find all titles in the page
    titles = []
    for page in pages:
        for e, elem in enumerate(page):
            if hasattr(elem, 'title_level') and elem.title_level is not None:
                titles.append((e, elem.title_level))

    assert titles == [(1, 0), (2, 1), (18, 1), (21, 1), (24, 0), (25, 1), (27, 0)]


@pytest.mark.parametrize("kwargs", [{}, {'formt': 'html'}, {'formt': 'HTML'}, {'formt': 'json'}, {'formt': 'JSon'}])
def test_save_as(document, kwargs):
    folder = "/tmp/"
    node = nodes.SaveAs(directory=folder, **kwargs)

    node(document)  # Save the doc

    file_path = "{}.{}".format(os.path.join(folder, document.name),
                               "html" if 'formt' not in kwargs else kwargs['formt'].lower())
    with open(file_path) as f:
        file_content = f.read()

    if 'formt' not in kwargs:
        expected_content = document.to_html(flatten=True) if 'flatten' in kwargs else document.to_html()
    elif kwargs['formt'].lower() == 'html':
        expected_content = document.to_html(flatten=True) if 'flatten' in kwargs else document.to_html()
    elif kwargs['formt'].lower() == 'json':
        expected_content = document.to_json(flatten=True) if 'flatten' in kwargs else document.to_json()
    assert file_content == expected_content

    # Don't forget to delete file
    os.remove(file_path)


def test_save_as_wrong_format():
    node = nodes.SaveAs(formt="unknown")
    with pytest.raises(ValueError):
        node("x")


def test_parse_elements(page_data, expected_elements):
    node = nodes.CreateDocument()

    # Duplicate pages : 2 pages to ensure we get the right page number
    page_data.append(page_data[0])
    expected_elements_p2 = copy.deepcopy(expected_elements)
    for e in expected_elements_p2:
        e.page = 1
    expect_eleme = expected_elements + expected_elements_p2

    elements = node._parse_elements(page_data)
    assert elements == expect_eleme


def test_create_document(page_data, expected_elements):
    node = nodes.CreateDocument()

    doc = node("x", "x", page_data)

    assert doc == Document(name="x", content=expected_elements)


@pytest.mark.parametrize("cross,kwargs,res", [('all', {}, True), ('none', {}, False),
                                              ('almost', {}, True), ('none', {'margin': 999}, True)])
def test_is_approx_overlap(lines, cross, kwargs, res):
    h, v = lines[cross]
    node = nodes.CleanTables(**kwargs)
    l1 = h.pop()
    l2 = v.pop()
    assert node._is_approx_overlap(l1, l2) == res


@pytest.mark.parametrize("cross,kwargs,nb_match", [('all', {}, 7), ('none', {}, 0), ('some', {}, 5),
                                                   ('almost', {}, 1), ('none', {'margin': 999}, 7),
                                                   ('some', {'margin': 999}, 7), ('all_type', {}, 7),
                                                   ('all_mixed', {}, 7), ('empty', {}, 0),
                                                   ('touching', {}, 3), ('only_touching', {}, 0)])
def test_find_crossing(lines, cross, kwargs, nb_match):
    h, v = lines[cross]
    node = nodes.CleanTables(**kwargs)
    hline = h.pop()
    crossing_lines = node._find_crossing(hline, v, h)
    assert len(crossing_lines) == nb_match


def test_find_tables_pdf_with_tables(pages_with_table):
    node = nodes.CleanTables()
    tables = node._find_tables(pages_with_table)
    assert len(tables) == 1     # Nb page
    assert len(tables[0]) == 1 and type(tables[0][0]) == LTTable


def test_find_tables_pdf_no_tables(pages_no_columns):
    node = nodes.CleanTables()
    tables = node._find_tables(pages_no_columns)
    assert len(tables) == 1     # Nb page
    assert len(tables[0]) == 0


def test_clean_tables_pdf_no_tables(pages_no_columns):
    node = nodes.CleanTables()
    _, _, pages = node("x", "x", pages_no_columns)
    assert len(pages[0]) == 4
    for e in pages[0]:
        assert type(e) != LTTable


def test_clean_tables_pdf_with_tables(pages_with_table):
    node = nodes.CleanTables(camelot=False)
    _, _, pages = node("x", "x", pages_with_table)
    print(pages[0]._objs)
    assert len(pages[0]) == 3
    assert pages[0]._objs[0].get_text() == "b"      # a was removed because located inside the table
    assert type(pages[0]._objs[1]) == LTTable
    assert pages[0]._objs[2].get_text() == "c"


@pytest.mark.parametrize("kwargs,dist,is_close", [({}, 0.05, True), ({}, 2, False),
                                                  ({'line_margin': 5}, 2, True),
                                                  ({'line_margin': 5}, 20, False)])
def test_fix_indentation_is_close(kwargs, dist, is_close):
    node = nodes.FixIndentationSeparatedText(**kwargs)
    e1 = MockText([MockLine(x0=3, x1=4, y0=dist, y1=dist + 1)])
    e2 = MockText([MockLine()])
    assert node._is_close(e1, e2) == is_close


def test_fix_indentation_is_close_wrong_object():
    node = nodes.FixIndentationSeparatedText()
    e1 = LTAnno("x")
    e2 = MockText([MockLine()])
    assert not node._is_close(e1, e2)
    assert not node._is_close(e2, e1)
    assert not node._is_close(e1, e1)
    assert node._is_close(e2, e2)


@pytest.mark.parametrize("x0,x1,w,kwargs,is_indent", [(0, 100, 100, {}, False),
                                                      (50, 100, 100, {}, True),
                                                      (-50, 100, 100, {}, False),
                                                      (50, 150, 100, {}, False),
                                                      (50, 100, 200, {}, False),
                                                      (50, 100, 200, {'end_area_ratio': 0.5}, True),
                                                      (50, 100, 50, {}, True)])
def test_fix_indentation_is_indented(x0, x1, w, kwargs, is_indent):
    node = nodes.FixIndentationSeparatedText(**kwargs)
    e1 = MockText([MockLine(x1=100)])
    e2 = MockText([MockLine(x0=x0, x1=x1)])
    assert node._is_indented_item(e1, e2, w) == is_indent


def test_fix_indentation_overline_long_word():
    node = nodes.FixIndentationSeparatedText()
    e1 = MockText([MockLine(x1=100)])
    e2 = MockText([MockLine([LTAnno('x'), MockChar(), LTAnno('x'), MockChar(),
                   MockChar(), MockChar(), MockChar(), MockChar()], x0=10, x1=105)])
    assert node._is_indented_item(e1, e2, 100)


def test_fix_indentation_overline_short_word():
    node = nodes.FixIndentationSeparatedText()
    e1 = MockText([MockLine(x1=100)])
    e2 = MockText([MockLine([LTAnno('x'), MockChar(), LTAnno('x'), MockChar(),
                   MockChar(), MockChar(), MockChar(txt=' '), MockChar(), MockChar(),
                   MockChar(), MockChar(), MockChar()], x0=10, x1=105)])
    assert not node._is_indented_item(e1, e2, 100)


def test_fix_indentation_is_indented_multi_lines():
    node = nodes.FixIndentationSeparatedText()
    e1 = MockText([MockLine(), MockLine()])
    e2 = MockText([MockLine()])
    assert not node._is_indented_item(e1, e2, e1.x1)


@pytest.mark.parametrize("x0,x1,is_middle", [(0, 100, True), (45, 55, True),
                                             (-45, 145, True), (0, 90, False),
                                             (-50, -30, False), (150, 180, False),
                                             (10, 100, False), (-10, 90, False),
                                             (10, 110, False), (0, 100.1, True),
                                             (0, 101.1, False)])
def test_fix_indentation_is_middle(x0, x1, is_middle):
    node = nodes.FixIndentationSeparatedText()
    e1 = MockText([MockLine(x1=100)])
    e2 = MockText([MockLine(x0=x0, x1=x1)])
    assert node._is_middle_text(e1, e2) == is_middle


def test_fix_indentation_separated_text():
    node = nodes.FixIndentationSeparatedText()
    pages = [MockPage([
        MockText([MockLine(x1=100)]),
        MockText([MockLine(x0=50, x1=100)]),
        MockText([MockLine(x1=100, y0=10, y1=11)]),
        MockText([MockLine(x1=100, y0=10, y1=11)])
    ])]

    _, _, pages = node("x", "x", pages)

    assert len(pages[0]) == 2


@pytest.mark.parametrize("text,result", [('content', True), ('contents', True), ('CONTENT', True), ('cONtENts', True),
                                         ('table of cONtENts', True), ('TABLE OF CONTENT', True),
                                         ('1. CONTENTS', False),
                                         ('whatever', False)])
def test_is_toc_title(text, result):
    node = nodes.RemoveContentTable()
    assert node._is_toc_title(text) == result


@pytest.mark.parametrize("lines,kwargs,result",
                         [(['A1', 'B2'], {}, True), (['AA', 'B2'], {}, False),
                          (['AA', 'B2'], {'ratio': 0.4}, True),
                          (['AA', 'BB'], {'ratio': 0}, False)])
def test_is_toc_content(lines, kwargs, result):
    node = nodes.RemoveContentTable(**kwargs)
    assert node._is_toc_content(lines) == result


def test_find_toc_tables(pages_with_toc_tables):
    node = nodes.RemoveContentTable()

    toc_tables = node._find_toc_tables(pages_with_toc_tables)

    assert toc_tables == [(1, 2), (4, 7)]


def test_remove_content_table(pages_with_toc_tables):
    node = nodes.RemoveContentTable()

    _, _, pages = node("x", "x", pages_with_toc_tables)

    assert len(pages[0]) == 0
    assert len(pages[1]) == 0
    assert len(pages[2]) != 0
    assert len(pages[3]) != 0
    assert len(pages[4]) == 0
    assert len(pages[5]) == 0
    assert len(pages[6]) == 0
    assert len(pages[7]) != 0


def test_remove_content_table_without_toc(pages_with_toc_tables):
    node = nodes.RemoveContentTable()
    pages = [pages_with_toc_tables[i] for i in [0, 2, 3, 7]]

    _, _, pages = node("x", "x", pages)

    for p in pages:
        assert len(p) != 0


@pytest.mark.parametrize("text,result", [('F.2 Title', True), ('F.2. Title', True),
                                         ('2 Title', True), ('2. Title', True),
                                         ('A. Title', True), ('A Title', False),
                                         ('ABC. Title', False), ('Title', False),
                                         ('43.', False), ('43. ', False), ('43', False),
                                         ('2 T', True), ('2. T', True), ('2 m', False),
                                         ('2 m.', False), ('2 .m', False),
                                         ('2 em', True), ('2 me', True), ('2    m', False),
                                         ('2    T', True), ('F.2Title', False),
                                         ('4.0 mm', False), ('4.0 kg', False)])
def test_is_title_like_regex(text, result):
    node = nodes.ExtractFontInfo()
    assert node._is_like_title(text) == result


@pytest.mark.parametrize("text,result", [('F.2 Title', False), ('F.2 Tit.le', True),
                                         ('F.2. Title', False), ('F.2. Tit.le', True),
                                         ('2 Title', False), ('2 Title.', True),
                                         ('2. Title', False), ('2. Title.', True),
                                         ('A. Title', False), ('A. .Title', True),
                                         ('A Title.', False), ('2. m', False),
                                         ('2 m', False), ('2     m', False),
                                         ('2 m.', False), ('2   m.', False),
                                         ('2 .m', False), ('2    .m', False),
                                         ('2 T', False), ('2 T.', True),
                                         ('2 .T', True), ('2   T.', True),
                                         ('2    .T', True), ('2.T', False)])
def test_has_sep_in_title_regex(text, result):
    node = nodes.ExtractFontInfo()
    assert node._has_sep_in_title(text) == result


def test_normalize_title_find_inconsistency_no(page_data_wrong_title_lvl_cant_detect):
    node = nodes.NormalizeTitleLevel()
    wrong_lvl, right_lvl = node._find_inconsistency(page_data_wrong_title_lvl_cant_detect)
    assert wrong_lvl > 9999 and right_lvl is None


def test_normalize_title_find_inconsistency_yes(page_data_wrong_title_lvl):
    node = nodes.NormalizeTitleLevel()
    wrong_lvl, right_lvl = node._find_inconsistency(page_data_wrong_title_lvl)
    assert wrong_lvl == 2 and right_lvl == 1


def test_normalize_title_lvl_no(page_data_wrong_title_lvl_cant_detect):
    node = nodes.NormalizeTitleLevel()
    _, _, page_data = node("x", "x", page_data_wrong_title_lvl_cant_detect)
    assert page_data[0][11].title_level == 2


def test_normalize_title_lvl_yes(page_data_wrong_title_lvl):
    node = nodes.NormalizeTitleLevel()
    _, _, page_data = node("x", "x", page_data_wrong_title_lvl)
    assert page_data[0][11].title_level == 1
    assert page_data[0][15].title_level == 1


@pytest.mark.parametrize("nb_1,nb_m,ratio", [(1, 0, 1), (9, 1, 0.9), (0, 0, 0), (0, 10, 0), (1, 1, 0.5)])
def test_one_liner_ratio(nb_1, nb_m, ratio):
    class MockTxt(LTTextContainer):
        def __init__(self, multi_line=False):
            self.nb_lines = 10 if multi_line else 1

        def __len__(self):
            return self.nb_lines

    page_tree = [[MockTxt() for i in range(nb_1)] + [MockTxt(True) for i in range(nb_m)]]

    node = nodes.Paragraphize()
    assert node._one_liner_ratio(page_tree) == ratio


@pytest.mark.parametrize("x1", [([0, 1, 2, 3]), ([1])])
def test_max_x1(x1):
    class MockTxt(LTTextContainer):
        def __init__(self, i):
            self.x1 = i

    page_tree = [[MockTxt(i) for i in x1]]

    node = nodes.Paragraphize()
    assert node._get_max_x1(page_tree) == max(x1)


@pytest.mark.parametrize("x0,x1,max_x1,kwargs,res", [(0, 250, 255, {}, True),
                                                     (245, 250, 255, {}, False),
                                                     (0, 25, 255, {}, False),
                                                     (0, 25, 255, {'x1_ratio': 0.01}, True)])
def test_is_big_line(x0, x1, max_x1, kwargs, res):
    class Mock():
        def __init__(self, x0=0, x1=1):
            self.x0 = x0
            self.x1 = x1

    node = nodes.Paragraphize(**kwargs)
    assert node._is_big_line(Mock(x0, x1), max_x1) == res


def test_paragraphize_not_enough_one_liners(one_line_par_not_enough_one_liners):
    node = nodes.Paragraphize()
    _, _, pages = node("x", "x", one_line_par_not_enough_one_liners)
    assert pages == one_line_par_not_enough_one_liners


def test_paragraphize_case0(one_line_par_case0):
    node = nodes.Paragraphize()
    _, _, pages = node("x", "x", one_line_par_case0)
    assert len(pages[0]) == len(one_line_par_case0[0])


def test_paragraphize_case1(one_line_par_case1):
    node = nodes.Paragraphize()
    _, _, pages = node("x", "x", one_line_par_case1)
    assert len(pages[0]) == len(one_line_par_case1[0])


def test_paragraphize_case2_1(one_line_par_case2_1):
    node = nodes.Paragraphize()
    _, _, pages = node("x", "x", one_line_par_case2_1)
    assert len(pages[0]) == len(one_line_par_case2_1[0]) - 1


def test_paragraphize_case2_2(one_line_par_case2_2):
    node = nodes.Paragraphize()
    _, _, pages = node("x", "x", one_line_par_case2_2)
    assert len(pages[0]) == len(one_line_par_case2_2[0]) - 1


def test_paragraphize_case3(one_line_par_case3):
    node = nodes.Paragraphize()
    _, _, pages = node("x", "x", one_line_par_case3)
    assert len(pages[0]) == len(one_line_par_case3[0]) - 1


@pytest.mark.parametrize("text, inputs, paragraph", [
    ('Single line', [('Single line', 1)], [('Single line', 1)]),
    ('Single line\n\n', [('Single line', 1)], [('Single line', 1)]),
    ('Single line🟊', [('Single line🟊', 1)], [('Single line🟊', 1)]),
    ('One line\ntest two line.', [('One line\ntest two line.', 1)], [('One line test two line.', 1)]),
    ('Parenthesis (test\n\ntest)', [('Parenthesis (test test)', 1)], [('Parenthesis (test test)', 1)]),
    ('0Text with digit.1', [('0Text with digit.1', 1)], [('0Text with digit.1', 1)]),
    ('  ', [], []),
    ('           Text with space.   ', [('Text with space.', 0)], [('Text with space.', 0)]),
    ('Multi line;\n\nwith semicolon', [('Multi line;\n\nwith semicolon', 0)], [('Multi line; with semicolon', 0)]),
    ('(Line with.\n\nbrackets included.)', [('(Line with.\n\nbrackets included.)', 0)],
        [('(Line with. brackets included.)', 0)]),
    ('[Line with.\n\nsquare bracket.]', [('[Line with.\n\nsquare bracket.]', 1)], [('[Line with. square bracket.]', 1)])
])
def test_make_text_paragraph(text, inputs, paragraph):
    node = nodes.TextParagraphize()
    assert node._make_paragraph(text, inputs) == paragraph


def test_text_paragraphize(text_page_data_text):
    node = nodes.TextParagraphize()
    _, _, pages = node("x", "x", text_page_data_text)
    assert pages[0]._objs[1] == 'test 1 test 2.'
    assert pages[0]._objs[2] == '- bullet 1'
    assert pages[0]._objs[3] == '- bullet 2'
    assert pages[0]._objs[4] == 'Table'
    assert pages[0]._objs[6] == 'between lines. (Sample with inside.)'
    assert pages[1]._objs[0] == 'Test no bullet:'
    assert pages[1]._objs[1] == 'no bullet 1.'
    assert pages[1]._objs[2] == 'no bullet 2.'
    assert pages[1]._objs[3] == '(Second sample for brackets)'
    assert pages[1]._objs[4] == 'Text sample.'
    assert pages[1]._objs[5] == 'Test of two lines of text.'
    assert pages[1]._objs[6] == 'Text sample.'
    assert pages[2]._objs[0] == 'Text with space in front.'


def test_bullet_paragraphize(text_page_data_bullets):
    node = nodes.BulletParagraph()
    _, _, pages = node("x", "x", text_page_data_bullets)
    assert pages[0]._objs[0].get_text() == 'Test sample.'
    assert pages[0]._objs[1].get_text() == 'Test bullets:\n2.2.1 bullet 1\n2.2.2 bullet 2'
    assert pages[0]._objs[3].get_text() == '2.2.3 bullet after table'
    assert pages[0]._objs[4].get_text() == 'Test page:\n\"大 bullet 1\n\"大 bullet 2\n\"大 bullet 3:\n- sub 1\n' \
                                           '- sub 2\n\"大 bullet 4'
    assert pages[1]._objs[0].get_text() == 'Test over.'


def test_bullet_non_paragraphize(text_page_data_bullets):
    node = nodes.BulletParagraph(group=False)
    _, _, pages = node("x", "x", text_page_data_bullets)
    assert pages[0]._objs[0].get_text() == 'Test sample.'
    assert pages[0]._objs[1].get_text() == 'Test bullets:'
    assert pages[0]._objs[2].get_text() == '2.2.1 bullet 1'
    assert pages[0]._objs[3].get_text() == '2.2.2 bullet 2'
    assert pages[0]._objs[5].get_text() == '2.2.3 bullet after table'
    assert pages[0]._objs[6].get_text() == 'Test page:'
    assert pages[0]._objs[7].get_text() == '\"大 bullet 1'
    assert pages[1]._objs[4].get_text() == 'Test over.'


@pytest.mark.parametrize("kwargs,err", [({'margin': [0.1, 0.1, 0.1, 0.1]}, False),
                                        ({'margin': 'x'}, True),
                                        ({'margin': [0.1]}, False),
                                        ({'margin': [0.1, 0.1]}, False),
                                        ({'margin': [0.1, 0.1, 0.1]}, True),
                                        ({'margin': [1, 0]}, True),
                                        ({'margin': [0, 1]}, True),
                                        ({'margin': [0.5, 0.5]}, False)])
def test_remove_headers_constructor(kwargs, err):
    try:
        nodes.RemoveHeaderFooter(**kwargs)
    except ValueError:
        assert err
    else:
        assert not err


@pytest.mark.parametrize("idx", [(0), (1), (2)])
def test_create_headers(headerfooter_mock_data, idx):
    node = nodes.RemoveHeaderFooter()
    pages = headerfooter_mock_data[idx]

    headers = node._create_headers(pages)
    assert len(headers) == len(pages)
    for i, (h, p) in enumerate(zip(headers, pages)):
        assert h.elements == p._objs
        assert i in h.ref and len(h.ref) == 1


@pytest.mark.parametrize("idx,nb", [(0, 2), (1, 0), (2, 0), (3, 1), (4, 2)])
def test_create_headers_strange_pages(headerfooter_mock_data_2, idx, nb):
    node = nodes.RemoveHeaderFooter()
    pages = headerfooter_mock_data_2[idx]

    headers = node._create_headers(pages)
    assert len(headers) == nb


def test_remove_headers_from_page(headerfooter_mock_data):
    node = nodes.RemoveHeaderFooter()
    pages = headerfooter_mock_data[0]

    headers = node._create_headers(pages)
    pages = node._remove_headers(pages, headers)
    assert len(pages[0]) == 0 and len(pages[1]) == 0


def test_remove_partial_headers_from_page(headerfooter_mock_data):
    node = nodes.RemoveHeaderFooter()
    pages = headerfooter_mock_data[0]

    headers = node._create_headers(pages)
    pages = node._remove_headers(pages, [headers[0]])
    assert len(pages[0]) == 0 and len(pages[1]) == 2


def test_group_matching_trio(headers):
    node = nodes.RemoveHeaderFooter()

    remains, merged = node._group_matching_trio(headers)

    assert len(remains) == 4
    assert len(merged.elements) == 1
    assert len(merged.ref) == 4 and set([2, 3, 4, 5]) == set(merged.ref.keys())


def test_group_matching_trio_no_match(headers):
    node = nodes.RemoveHeaderFooter()

    remains, merged = node._group_matching_trio(headers)  # Remove the matching header
    remains, merged = node._group_matching_trio(remains)

    assert len(remains) == 4
    assert merged is None


@pytest.mark.parametrize("i1,i2", [(0, 1), (0, 2)])
def test_gather_similar_headers(mock_texts, i1, i2):
    node = nodes.RemoveHeaderFooter()
    headers = [
        Header(elements=[mock_texts[i1]], p=0, indices=[0]),
        Header(elements=[mock_texts[i2]], p=1, indices=[1]),
    ]

    merged = node._gather_headers(headers)

    assert len(merged) == 1
    assert len(merged[0].elements) == 1
    assert len(merged[0].ref) == 2 and set([0, 1]) == set(merged[0].ref.keys())


def test_gather_overlapping_headers(mock_texts):
    node = nodes.RemoveHeaderFooter()
    headers = [
        Header(elements=[mock_texts[0]], p=0, indices=[0]),
        Header(elements=[mock_texts[3]], p=1, indices=[1]),
    ]

    merged = node._gather_headers(headers)

    assert len(merged) == 1
    assert len(merged[0].elements) == 1
    assert len(merged[0].ref) == 2 and set([0, 1]) == set(merged[0].ref.keys())


def test_gather_different_headers(mock_texts):
    node = nodes.RemoveHeaderFooter()
    headers = [
        Header(elements=[mock_texts[0]], p=0, indices=[0]),
        Header(elements=[MockTxt(x0=101, x1=200, y0=101, y1=200)], p=1, indices=[1]),
    ]

    merged = node._gather_headers(headers)

    assert len(merged) == 2


def test_assign_raw_headers(mock_texts):
    node = nodes.RemoveHeaderFooter()
    headers = [
        Header(elements=[MockTxt(x0=101, x1=200, y0=101, y1=200)], p=0, indices=[1]),
        Header(elements=[mock_texts[0]], p=1, indices=[0]),
        Header(elements=[MockTxt(x0=101, x1=200, y0=101, y1=200)], p=2, indices=[1]),
    ]
    raw_headers = [
        Header(elements=[mock_texts[0]], p=4, indices=[0]),
        Header(elements=[mock_texts[0]], p=5, indices=[0]),
    ]

    node._assign_raw_headers(headers, raw_headers)

    assert len(headers) == 3
    assert 4 not in headers[0].ref.keys() and 4 in headers[1].ref.keys() and 4 not in headers[2].ref.keys()
    assert 5 not in headers[0].ref.keys() and 5 in headers[1].ref.keys() and 5 not in headers[2].ref.keys()


def test_brute_force_raw_headers_positions_match(mock_texts):
    node = nodes.RemoveHeaderFooter()
    raw_headers = [
        Header(elements=[mock_texts[0], mock_texts[0]], p=4, indices=[0, 2]),
        Header(elements=[mock_texts[2], mock_texts[3]], p=5, indices=[0, 1]),
    ]

    headers = node._brute_force_pos_match(raw_headers)

    assert len(headers) == 1
    assert len(headers[0].elements) == 1
    assert 4 in headers[0].ref.keys() and headers[0].ref[4] == [0]
    assert 5 in headers[0].ref.keys() and headers[0].ref[5] == [0]


def test_brute_force_raw_headers_positions_dont_match(mock_texts):
    node = nodes.RemoveHeaderFooter()
    raw_headers = [
        Header(elements=[mock_texts[0]], p=4, indices=[0]),
        Header(elements=[mock_texts[3]], p=5, indices=[0]),
    ]

    headers = node._brute_force_pos_match(raw_headers)

    assert len(headers) == 1
    assert len(headers[0].elements) == 0
    assert 4 in headers[0].ref.keys() and headers[0].ref[4] == []
    assert 5 in headers[0].ref.keys() and headers[0].ref[5] == []


def test_brute_force_raw_headers_positions_single_page(mock_texts):
    node = nodes.RemoveHeaderFooter()
    raw_headers = [
        Header(elements=[mock_texts[0]], p=4, indices=[0]),
    ]

    headers = node._brute_force_pos_match(raw_headers)

    assert len(headers) == 0


def test_remove_headers(pages_with_headers):
    node = nodes.RemoveHeaderFooter()

    _, _, pages = node("x", "x", pages_with_headers)

    assert len(pages) == 13
    assert len(pages[0]) == 0
    for p in pages[1:]:
        assert len(p) == 1  # Headers were removed, only content is left


def test_remove_headers_odd_even(pages_with_headers_odd_even):
    node = nodes.RemoveHeaderFooter()

    _, _, pages = node("x", "x", pages_with_headers_odd_even)

    assert len(pages) == 13
    assert len(pages[0]) == 0
    for p in pages[1:]:
        assert len(p) == 1  # Footers were removed, only content is left


def test_remove_headers_ocr(pages_with_headers_ocr):
    node = nodes.RemoveHeaderFooter()

    _, _, pages = node("x", "x", pages_with_headers_ocr)

    assert len(pages) == 13
    assert len(pages[0]) == 0
    for p in pages[1:]:
        assert len(p) == 1  # Footers were removed, only content is left


def test_remove_headers_brute_force(pages_with_headers_brute_force):
    node = nodes.RemoveHeaderFooter()

    _, _, pages = node("x", "x", pages_with_headers_brute_force)

    assert len(pages) == 3
    assert len(pages[0]) == 0
    for p in pages[1:]:
        assert len(p) == 1  # Headers were removed, only content is left


def test_remove_headers_single_page(pages_with_headers_single_page):
    node = nodes.RemoveHeaderFooter()

    _, _, pages = node("x", "x", pages_with_headers_single_page)

    assert len(pages) == 1
    assert len(pages[0]) == 2  # No header removed, because it's a single page


def test_unique_cache_filename():
    x1 = get_unique_filename("/home/test/path/test/name.pdf")
    x2 = get_unique_filename("/home/test/path2/test/name.pdf")
    assert x1 != x2


def test_normalize_dont_normalize():
    node = nodes.NormalizePdf(normalize=False)
    test_path = "/home/test/path/test/name.pdf"
    path, name = node(test_path)
    assert path == test_path
    assert name == "name"


def test_normalize():
    with tempfile.TemporaryDirectory() as tmpdirname:
        node = nodes.NormalizePdf(cache=tmpdirname)

        pdf_path = os.path.join(os.path.dirname(__file__), 'data/2_pages.pdf')
        path, name = node(pdf_path)

        assert os.path.dirname(path) == tmpdirname
        assert name == "2_pages"


def test_remove_non_searchable_page():
    node = nodes.RemoveNonSearchablePage()

    pages = []
    # simulate non-searchable pages (#0, #1)
    p = LTPage(pageid=0, bbox=(0, 0, 0, 0))
    p.add("page0")
    pages.insert(0, p)

    p = LTPage(pageid=1, bbox=(0, 0, 0, 0))
    p.add("page1")
    pages.insert(1, p)

    # simulate searchable pages (#2)
    p = LTPage(pageid=2, bbox=(0, 0, 0, 0))
    header = LTTextContainer()
    header.add(Txt('text'))
    p.add(header)
    p.add("page2")
    pages.insert(2, p)

    _, _, clean_pages = node("x", "x", pages)

    assert len(clean_pages[0]) == 0
    assert len(clean_pages[1]) == 0
    assert len(clean_pages[2]) != 0


@pytest.mark.parametrize("char_map", [([[False, True, False], [False, True, False]]),
                                      ([[False, True, False], [False, False, False]]),
                                      ([[False, False, False], [False, True, False]]),
                                      ([[False, False, False], [False, False, False]]),
                                      ([[True, True, True], [True, True, True]]),
                                      ([[False, True, False]]), ([[False, False, False]]),
                                      ([[True, True, True]]), ([[True, True, False]]),
                                      ([[False, True, True]]), ([[]]),
                                      ([[False]]), ([[True]])])
def test_remove_math_characters(char_map):
    elem = []
    for line_map in char_map:
        line = []
        for c_is_math in line_map:
            line.append(MockChar(font=("CambriaMath+Italic" if c_is_math else "GDEYF,Arial")))
        elem.append(MockLine(line))
    pages = [MockPage([MockText(elem)])]
    node = nodes.RemoveMathCharacters()

    _, _, pages = node("x", "x", pages)

    clean_elem = pages[0]._objs[0]

    for line, line_map in zip(clean_elem, char_map):
        assert len(line) == len([c for c in line_map if not c])


@pytest.mark.parametrize("key,nb_t", [('no_t', 0), ('empty', 0), ('1_t', 1),
                                      ('2_t_same_page', 2), ('2_t', 1),
                                      ('2_t_diff_col', 2), ('2_t_diff_pos', 2),
                                      ('2_t_nomerge', 2), ('3_t', 1),
                                      ('3_t_nomerge', 2)])
def test_merge_tables_page_split(tables_merge_fixtures, key, nb_t):
    node = nodes.MergeSuccessiveTables()
    pages = tables_merge_fixtures[key]

    _, _, pages = node('x', 'x', pages)

    nb_tables = 0
    for page in pages:
        for elem in page:
            if isinstance(elem, LTTable):
                nb_tables += 1
    assert nb_tables == nb_t


def test_merge_tables_bigger_margin(pages_with_2_tables_diff_pos):
    node = nodes.MergeSuccessiveTables(margin=10)

    _, _, pages = node('x', 'x', pages_with_2_tables_diff_pos)

    nb_tables = 0
    for page in pages:
        for elem in page:
            if isinstance(elem, LTTable):
                nb_tables += 1
    assert nb_tables == 1


@pytest.mark.parametrize("kwargs,pos,res", [({}, (10, 990), [False, False, True]),
                                            ({}, (10, 400), [True, False, False]),
                                            ({}, (600, 990), [False, True, False]),
                                            ({}, (10, 450), [True, False, False]),
                                            ({}, (10, 550), [True, False, False]),
                                            ({}, (450, 990), [False, True, False]),
                                            ({}, (550, 990), [False, True, False]),
                                            ({}, (10, 551), [False, False, True]),
                                            ({}, (449, 990), [False, False, True]),
                                            ({'middle_margin': 0.1}, (10, 551), [True, False, False]),
                                            ({'middle_margin': 0.1}, (449, 990), [False, True, False]),
                                            ({}, (460, 470), [False, False, True]),
                                            ({}, (520, 530), [False, False, True]),
                                            ({}, (460, 530), [False, False, True])])
def test_assign_area(kwargs, pos, res):
    node = nodes.ReorderElements(**kwargs)
    p = MockPage([MockTxt(x0=pos[0], x1=pos[1])])

    lrc = node.assign_area(p)
    results = [len(liste) > 0 for liste in lrc]

    assert results == res


def test_reorder_empty(empty_pages_without_tables):
    node = nodes.ReorderElements()
    _, _, _ = node('x', 'x', empty_pages_without_tables)
    assert True         # Nothing to verify, just ensure it does not crash


@pytest.mark.parametrize("key", ['normal', '2_col', '2_col+common', 'common+2_col'])
def test_reorder_elements(columned_pages, key):
    node = nodes.ReorderElements()
    pages = columned_pages[key]

    _, _, pages = node('x', 'x', pages)

    full_str = ""
    for page in pages:
        for elem in page:
            full_str += elem.get_text()
    assert full_str == "1234"


@pytest.mark.parametrize("key,nb_l", [('2_col', 2), ('1_liner', 1), ('1_linel', 1),
                                      ('diff_height', 2), ('multimatch', 1),
                                      ('multimatch_2l', 2), ('m2_col', 5),
                                      ('m1_liner', 4), ('m1_linel', 4),
                                      ('mdiff_height', 5), ('mmultimatch', 4),
                                      ('mmultimatch_2l', 6)])
def test_linify(lined_pages, key, nb_l):
    node = nodes.Linify()
    pages = lined_pages[key]

    _, _, pages = node('x', 'x', pages)

    nb_lines = 0
    for page in pages:
        for elem in page:
            nb_lines += len(elem)
    assert nb_lines == nb_l


def test_linify_pos():
    node = nodes.Linify()
    pages = [MockPage([MockText([MockLine([MockChar(x0=0, x1=250)], x0=0, x1=250)]),
                       MockText([MockLine([MockChar(x0=350, x1=1000)], x0=350, x1=1000)])])]

    _, _, pages = node('x', 'x', pages)

    assert len(pages[0]._objs[0]) == 1
    assert pages[0]._objs[0]._objs[0].x0 == 0
    assert pages[0]._objs[0]._objs[0].x1 == 1000


@pytest.mark.parametrize("lines,nb_t,nb_l", [(['x'], 1, 1), ([' '], 0, 0), (['\n'], 0, 0), (['✅'], 1, 1),
                                             (['x '], 1, 1), ([' x'], 1, 1), ([' \n'], 0, 0),
                                             (['x', 'x'], 1, 2), (['x', '\n'], 1, 1),
                                             ([' ', 'x'], 1, 1), ([' ', '\n'], 0, 0)])
def test_remove_empty_lines(lines, nb_t, nb_l):
    node = nodes.RemoveEmptyLines()
    pages = [MockPage([MockText([MockLine([LTAnno(c) for c in line]) for line in lines])])]

    _, _, pages = node("x", "x", pages)

    nb_text = 0
    nb_lines = 0
    for page in pages:
        for elem in page:
            nb_text += 1
            nb_lines += len(elem)
    assert nb_text == nb_t
    assert nb_lines == nb_l


def test_remove_landscape_page():
    node = nodes.RemoveLandscapePages()
    pages = [
        MockPage([MockTxt()]),
        MockPage([MockTxt()]),
        MockPage([MockTxt()], width=500, height=500),
        MockPage([MockTxt()]),
        MockPage([MockTxt()]),
    ]

    _, _, pages = node("x", "x", pages)

    assert [len(p) for p in pages] == [1, 1, 0, 1, 1]


def test_remove_landscape_page_reverse():
    node = nodes.RemoveLandscapePages()
    pages = [
        MockPage([MockTxt()], width=500, height=500),
        MockPage([MockTxt()], width=500, height=500),
        MockPage([MockTxt()]),
        MockPage([MockTxt()], width=500, height=500),
        MockPage([MockTxt()], width=500, height=500),
    ]

    _, _, pages = node("x", "x", pages)

    assert [len(p) for p in pages] == [1, 1, 0, 1, 1]


@pytest.mark.parametrize("kwargs,result", [({}, 5), ({'dist_margin': 0}, 3)])
def test_remove_landscape_page_flexible(kwargs, result):
    node = nodes.RemoveLandscapePages(**kwargs)
    pages = [
        MockPage([MockTxt()], width=495, height=495),
        MockPage([MockTxt()], width=500, height=500),
        MockPage([MockTxt()], width=500, height=500),
        MockPage([MockTxt()], width=495, height=495),
        MockPage([MockTxt()], width=500, height=500),
    ]

    _, _, pages = node("x", "x", pages)

    assert sum(len(p) for p in pages) == result


def test_assign_camelot_table_same_number():
    t1 = LTTable()
    t1.set_bbox((0, 0, 100, 100))
    t2 = LTTable()
    t2.set_bbox((0, 90, 100, 190))

    ct1 = MockTable2((0, 0, 100, 100))
    ct2 = MockTable2((0, 90, 100, 190))

    node = nodes.CleanTables()
    node._assign_camelot_tables([t1, t2], [ct1, ct2])

    assert t1.camelot_table is ct1
    assert t2.camelot_table is ct2


def test_assign_camelot_table_approx():
    t1 = LTTable()
    t1.set_bbox((0, 0, 100, 100))
    t2 = LTTable()
    t2.set_bbox((0, 90, 100, 190))

    ct1 = MockTable2((20, 0, 100, 100))
    ct2 = MockTable2((0, 85, 100, 195))

    node = nodes.CleanTables()
    node._assign_camelot_tables([t1, t2], [ct1, ct2])

    assert t1.camelot_table is ct1
    assert t2.camelot_table is ct2


def test_assign_camelot_table_less():
    t1 = LTTable()
    t1.set_bbox((0, 0, 100, 100))
    t2 = LTTable()
    t2.set_bbox((0, 90, 100, 190))

    ct1 = MockTable2((0, 0, 100, 100))

    node = nodes.CleanTables()
    node._assign_camelot_tables([t1, t2], [ct1])

    assert t1.camelot_table is ct1
    assert t2.camelot_table is None


def test_assign_camelot_table_more():
    node = nodes.CleanTables()
    with pytest.raises(AssertionError):
        node._assign_camelot_tables([1], [1, 2])
