import copy

import pytest
import pandas as pd
from pdfminer.layout import LTRect, LTTextContainer, LTText, LTLine, LTPage, LTChar, LTTextLine
from prospector.nodes import Font, TableFont
from prospector.document import Document, Title, Paragraph, Table
from prospector.miner import LTTable, LTParagraph
from prospector.nodes.headers import Header


@pytest.fixture
def font_reference():
    return Font(size=10, bold=False, italic=False, underline=False, caps=False,
                title_like=False, sep_in_title=False, alignement=189)


@pytest.fixture
def modified_fonts():
    # Return a list of font, where each font have a difference with the reference font
    return [
        Font(size=11, bold=False, italic=False, caps=False, underline=False,
             title_like=False, sep_in_title=False, alignement=189),
        Font(size=10, bold=True, italic=False, caps=False, underline=False,
             title_like=False, sep_in_title=False, alignement=189),
        Font(size=10, bold=False, italic=False, caps=True, underline=False,
             title_like=False, sep_in_title=False, alignement=189),
        Font(size=10, bold=False, italic=False, caps=False, underline=True,
             title_like=False, sep_in_title=False, alignement=189),
        Font(size=10, bold=False, italic=False, caps=False, underline=False,
             title_like=True, sep_in_title=False, alignement=189),
        Font(size=10, bold=False, italic=True, caps=False, underline=False,
             title_like=False, sep_in_title=False, alignement=189),
        Font(size=10, bold=False, italic=False, caps=False, underline=False,
             title_like=False, sep_in_title=True, alignement=189),
        Font(size=10, bold=False, italic=False, caps=False, underline=False,
             title_like=False, sep_in_title=False, alignement=200),
        Font(size=9, bold=True, italic=True, caps=True, underline=True,
             title_like=True, sep_in_title=True, alignement=10),
    ]


class MockPage():
    def __init__(self, x, width=1000, height=1000):
        self._objs = x
        self.width = width
        self.height = height
        self.pageid = 0
        self.bbox = (0, 0, 1000, 1000)
        self.rotate = False

    def __len__(self):
        return self._objs.__len__()

    def __iter__(self):
        return self._objs.__iter__()


class Txt(LTText):    # A fake class for easier access to text
    def __init__(self, text="", x0=0, x1=1, y0=0, y1=1):
        self.text = text
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.width, self.height = x1 - x0, y1 - y0

    def get_text(self):
        return self.text


class Mock():
    def __init__(self, font):
        self.font = font


@pytest.fixture
def font_data():
    # Define font
    header_1 = Font(size=14, bold=False, italic=False, caps=True, underline=False,
                    title_like=True, sep_in_title=False, alignement=189)
    header_2 = Font(size=11, bold=False, italic=False, caps=False, underline=False,
                    title_like=True, sep_in_title=False, alignement=416)
    text = Font(size=10, bold=False, italic=False, caps=False, underline=False,
                title_like=False, sep_in_title=False, alignement=116)
    weird_text = Font(size=10, bold=True, italic=True, caps=True, underline=False,
                      title_like=False, sep_in_title=False, alignement=116)
    solo_last = Font(size=8, bold=True, italic=False, caps=True, underline=False,
                     title_like=False, sep_in_title=False, alignement=116)
    tf = TableFont()

    class EmptyMock():
        pass

    # Create some tree (with only 1 page)
    return [MockPage([
        Mock(None),
        Mock(copy.copy(header_1)),
        Mock(copy.copy(header_2)),
        EmptyMock(),
        Mock(copy.copy(text)),
        Mock(None),
        Mock(copy.copy(text)),
        Mock(copy.copy(text)),
        Mock(copy.copy(header_2)),
        Mock(copy.copy(text)),
        None,
        Mock(copy.copy(header_2)),
        Mock(copy.copy(weird_text)),
        Mock(copy.copy(weird_text)),
        Mock(copy.copy(header_1)),
        Mock(copy.copy(header_2)),
        Mock(copy.copy(tf)),
        Mock(copy.copy(header_1)),
        Mock(copy.copy(solo_last)),
    ])], (header_1, header_2, text, weird_text, solo_last, tf)


@pytest.fixture
def font_data_more_text(font_data):
    ft_data, fonts = font_data

    for _ in range(10):
        ft_data[0]._objs.insert(4, Mock(copy.copy(fonts[2])))

    return ft_data, fonts


@pytest.fixture
def page_data():
    # Simulate some PDF content, matching `font_data`

    header_1 = LTTextContainer()
    header_1.add(Txt('H1'))
    header_1.title_level = 0
    header_2 = LTTextContainer()
    header_2.add(Txt('H2'))
    header_2.title_level = 1
    text = LTTextContainer()
    text.add(Txt('text'))
    text.title_level = None
    weird_text = LTTextContainer()
    weird_text.add(Txt(''))
    weird_text.title_level = None
    weird_text_not_empty = LTTextContainer()
    weird_text_not_empty.add(Txt('x'))
    weird_text_not_empty.title_level = None

    # Simulate a tree with only 1 page
    return [[
        LTRect(1, (0, 0, 0, 0)),
        copy.copy(header_1),
        copy.copy(header_2),
        LTRect(1, (1, 0, 0, 0)),
        copy.copy(text),
        LTRect(1, (2, 0, 0, 0)),
        copy.copy(text),
        copy.copy(text),
        copy.copy(header_2),
        copy.copy(text),
        LTRect(1, (3, 0, 0, 0)),
        copy.copy(header_2),
        copy.copy(weird_text_not_empty),
        copy.copy(weird_text),
        copy.copy(header_1),
        copy.copy(header_2),
        LTTable(),
        copy.copy(header_1),
        copy.copy(text),
    ]]


@pytest.fixture
def expected_elements():
    return [
        Title(page=0, text='H1', level=0),
        Title(page=0, text='H2', level=1),
        Paragraph(page=0, text='text'),
        Paragraph(page=0, text='text'),
        Paragraph(page=0, text='text'),
        Title(page=0, text='H2', level=1),
        Paragraph(page=0, text='text'),
        Title(page=0, text='H2', level=1),
        Paragraph(page=0, text='x'),
        Title(page=0, text='H1', level=0),
        Title(page=0, text='H2', level=1),
        Table(page=0, camelot=None),
        Title(page=0, text='H1', level=0),
        Paragraph(page=0, text='text'),
    ]


@pytest.fixture
def document():
    return Document(
        name="test",
        content=[
            Title(page=0, text="H1", level=0),
            Paragraph(page=0, text="paragraph 1"),
            Title(page=0, text="H2", level=1),
            Paragraph(page=0, text="paragraph 2"),
            Paragraph(page=1, text="paragraph 3"),
            Title(page=1, text="H2", level=1),
            Paragraph(page=1, text="paragraph 4"),
        ]
    )


@pytest.fixture
def all_crossing_lines():
    h = set([LTRect(1, (0, i * 10, 200, i * 10 + 0.5)) for i in range(4)])
    v = set([LTRect(1, (i * 10, 0, i * 10 + 0.5, 200)) for i in range(4)])
    return h, v


@pytest.fixture
def all_crossing_lines_other_type():
    h = set([LTLine(1, (0, i * 10), (200, i * 10 + 0.5)) for i in range(4)])
    v = set([LTLine(1, (i * 10, 0), (i * 10 + 0.5, 200)) for i in range(4)])
    return h, v


@pytest.fixture
def all_crossing_lines_mixed_type():
    h = set([LTLine(1, (0, i * 10), (200, i * 10 + 0.5)) for i in range(4)])
    v = set([LTRect(1, (i * 10, 0, i * 10 + 0.5, 200)) for i in range(4)])
    return h, v


@pytest.fixture
def empty_lines():
    #          Just one line for the pop
    return set([LTRect(1, (0, 0, 0, 0))]), set()


@pytest.fixture
def touching_and_crossing_lines():
    h = set([
        LTLine(1, (0, 0), (100, 0)),
        LTLine(1, (100, 0), (200, 0)),
    ])
    v = set([
        LTLine(1, (50, -100), (50, 100)),
        LTLine(1, (150, -100), (150, 100)),
    ])
    return h, v


@pytest.fixture
def touching_not_crossing_lines():
    h = set([
        LTLine(1, (0, 0), (100, 0)),
        LTLine(1, (100, 0), (200, 0)),
    ])
    v = set([
        LTLine(1, (50, 50), (50, 100)),
        LTLine(1, (150, 50), (150, 100)),
    ])
    return h, v


@pytest.fixture
def none_crossing_lines():
    h = set([LTRect(1, (0, i * 10, 200, i * 10 + 0.5)) for i in range(4)])
    v = set([LTRect(1, (i * 10, 50, i * 10 + 0.5, 200)) for i in range(4)])
    return h, v


@pytest.fixture
def some_crossing_lines():
    h = set([LTRect(1, (0, i * 10, 200, i * 10 + 0.5)) for i in range(4)])
    v = set([LTRect(1, (i * 10, i * 20, i * 10 + 0.5, 200)) for i in range(4)])
    return h, v


@pytest.fixture
def almost_crossing_lines():
    h = set([LTRect(1, (0.9, 0, 200, 0.5))])    # Starts from almost 0
    v = set([LTRect(1, (0, 0, 0.5, 200))])
    return h, v


@pytest.fixture
def lines(all_crossing_lines, none_crossing_lines, some_crossing_lines,
          almost_crossing_lines, all_crossing_lines_other_type,
          all_crossing_lines_mixed_type, empty_lines,
          touching_and_crossing_lines, touching_not_crossing_lines):
    return {
        'all': all_crossing_lines,
        'none': none_crossing_lines,
        'some': some_crossing_lines,
        'almost': almost_crossing_lines,
        'all_type': all_crossing_lines_other_type,
        'all_mixed': all_crossing_lines_mixed_type,
        'empty': empty_lines,
        'touching': touching_and_crossing_lines,
        'only_touching': touching_not_crossing_lines,
    }


def _get_table(h=10, v=10):
    t = LTTable()
    h = [LTRect(1, (0, i * 10, 200, i * 10 + 0.5)) for i in range(h)]
    v = [LTRect(1, (i * 10, 0, i * 10 + 0.5, 200)) for i in range(v)]
    t._objs.extend(h)
    t._objs.extend(v)
    return t


@pytest.fixture(params=[0, 1, 2])
def single_cell_table(request):
    return _get_table(h=request.param)


@pytest.fixture(params=[3, 10])
def multi_cell_table(request):
    return _get_table(h=request.param)


@pytest.fixture
def page_data_wrong_title_lvl_cant_detect(page_data):
    page_data[0][11].title_level = 2
    return page_data


@pytest.fixture
def page_data_wrong_title_lvl(page_data_wrong_title_lvl_cant_detect):
    page_data_wrong_title_lvl_cant_detect[0][15].title_level = 2
    return page_data_wrong_title_lvl_cant_detect


@pytest.fixture
def text_page_data():
    # Simulate some PDF content, with some paragraph that is wrongly divided

    header_1 = LTTextContainer()
    header_1.add(LTParagraph('H1'))
    header_1.title_level = 0
    header_2 = LTTextContainer()
    header_2.add(LTParagraph('H2'))
    header_2.title_level = 1

    page = LTPage(pageid=0, bbox=(0, 0, 0, 0))
    page.add(LTRect(1, (0, 0, 0, 0)))
    page.add(copy.copy(header_1))
    page.add(copy.copy(header_2))
    page.add(LTRect(1, (1, 0, 0, 0)))
    page.add(LTParagraph("This is the first line,\n"))
    page.add(LTRect(1, (2, 0, 0, 0)))
    page.add(LTParagraph("this is the end of the line.\n"))
    page.add(LTParagraph("This is the second p!\n"))
    page.add(LTParagraph("This is the third one (but \n"))
    page.add(LTParagraph("with parenthesis).\n"))
    page.add(LTParagraph("This is the fourth one (but \n"))
    page.add(copy.copy(header_2))
    page.add(LTParagraph("cut)\n"))
    page.add(LTRect(1, (3, 0, 0, 0)))
    page.add(copy.copy(header_2))
    page.add(LTParagraph("This is the fifth one (but \n"))
    page.add(LTTable())
    page.add(LTParagraph("cut)\n"))
    page.add(LTParagraph("This is the sixth one (but \n"))

    page2 = LTPage(pageid=1, bbox=(0, 0, 0, 0))
    page2.add(LTParagraph("cut)"))

    return [page, page2]


@pytest.fixture
def text_page_data_text():
    page = LTPage(pageid=0, bbox=(0, 0, 0, 0))
    page.add(LTTable())
    text1 = LTTextContainer()
    text1.add(Txt('test 1\n\ntest 2.\n\n'))
    page.add(text1)
    text2 = LTTextContainer()
    text2.add(Txt('- bullet 1\n\n- bullet 2\n\nTable\n\n'))
    page.add(text2)
    page.add(LTTable())
    text3 = LTTextContainer()
    text3.add(Txt('between lines. (Sample with\n\n'))
    page.add(text3)
    page2 = LTPage(pageid=1, bbox=(0, 0, 0, 0))
    text4 = LTTextContainer()
    text4.add(Txt('inside.)\n\nTest no bullet:\n\nno bullet 1.\n\nno bullet 2.'))
    text5 = LTTextContainer()
    text5.add(Txt('\n\n(Second sample\n\nfor brackets)\n\n  Text sample.'))
    text6 = LTTextContainer()
    text6.add(Txt('\n\nTest of two\nlines of text.\n\n'))
    page2.add(text4)
    page2.add(text5)
    page2.add(text6)
    page3 = LTPage(pageid=2, bbox=(0, 0, 0, 0))
    text7 = LTTextContainer()
    text7.add(Txt('Text sample.\n\n   Text with space in front.\n\n'))
    page3.add(text7)
    return [page, page2, page3]


@pytest.fixture
def text_page_data_bullets():
    page = LTPage(pageid=0, bbox=(0, 0, 0, 0))
    page.add('Test sample.')
    page.add('Test bullets:')
    page.add('2.2.1 bullet 1')
    page.add('2.2.2 bullet 2')
    page.add(LTTable())
    page.add('2.2.3 bullet after table')
    page.add('Test page:')
    page.add('\"大 bullet 1')
    page.add('\"大 bullet 2')
    page2 = LTPage(pageid=1, bbox=(0, 0, 0, 0))
    page2.add('\"大 bullet 3:')
    page2.add('- sub 1')
    page2.add('- sub 2')
    page2.add('\"大 bullet 4')
    page2.add('Test over.')
    return [page, page2]


class MockTxt(LTTextContainer):
    def __init__(self, x0=0, x1=1, y0=0, y1=1, multi_line=False, txt="x"):
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1
        self.bbox = (x0, y0, x1, y1)
        self._objs = [Txt(txt) for _ in range(10 if multi_line else 1)]

    def __len__(self):
        return len(self._objs)


@pytest.fixture
def one_line_par_not_enough_one_liners():
    return [MockPage([MockTxt(x1=100), MockTxt(x1=200, multi_line=True)])]


@pytest.fixture
def one_line_par_case0():
    return [MockPage([MockTxt(x1=100), MockTxt(x1=200)])]


@pytest.fixture
def one_line_par_case1():
    return [MockPage([MockTxt(x0=20, x1=100), MockTxt(x1=100)])]


@pytest.fixture
def one_line_par_case2_1():
    return [MockPage([MockTxt(x1=100), MockTxt(x1=100)])]


@pytest.fixture
def one_line_par_case2_2():
    return [MockPage([MockTxt(x1=200), MockTxt(x1=100)])]


@pytest.fixture
def one_line_par_case3():
    return [MockPage([MockTxt(x1=100), MockTxt(x0=20, x1=100)])]


@pytest.fixture
def multi_page_without_headerfooter():
    return [
        MockPage([MockTxt(x0=1, x1=2), MockTxt(x0=20, x1=100)]),
        MockPage([MockTxt(x0=3, x1=4), MockTxt(x0=30, x1=60)]),
    ]


@pytest.fixture
def multi_page_with_headerfooter():
    return [
        MockPage([MockTxt(x1=100), MockTxt(x0=20, x1=100)]),
        MockPage([MockTxt(x1=100), MockTxt(x0=30, x1=60)]),
    ]


@pytest.fixture
def multi_page_with_headerfooter_different_x1():
    return [
        MockPage([MockTxt(x1=100), MockTxt(x0=20, x1=100)]),
        MockPage([MockTxt(x1=200), MockTxt(x0=30, x1=60)]),
    ]


@pytest.fixture
def multi_page_with_headerfooter_empty_page_beginning():
    return [
        MockPage([]),
        MockPage([MockTxt(x1=100), MockTxt(x0=20, x1=100)]),
        MockPage([MockTxt(x1=100), MockTxt(x0=30, x1=60)]),
    ]


@pytest.fixture
def multi_page_with_headerfooter_empty_page_middle():
    return [
        MockPage([MockTxt(x1=100), MockTxt(x0=20, x1=100)]),
        MockPage([]),
        MockPage([MockTxt(x1=100), MockTxt(x0=30, x1=60)]),
    ]


@pytest.fixture
def multi_page_with_headerfooter_all_empty():
    return [
        MockPage([]),
        MockPage([]),
    ]


@pytest.fixture
def multi_page_with_middle_elements():
    return [MockPage([MockTxt(x0=500, x1=510, y0=500, y1=510)])]


@pytest.fixture
def multi_page_with_middle_elements_and_other():
    return [MockPage([MockTxt(x0=500, x1=510, y0=500, y1=510), MockTxt(x1=100)])]


@pytest.fixture
def headerfooter_mock_data(multi_page_without_headerfooter,
                           multi_page_with_headerfooter,
                           multi_page_with_headerfooter_different_x1,):
    return [
        multi_page_without_headerfooter,
        multi_page_with_headerfooter,
        multi_page_with_headerfooter_different_x1,
    ]


@pytest.fixture
def headerfooter_mock_data_2(multi_page_with_headerfooter_empty_page_middle,
                             multi_page_with_headerfooter_all_empty,
                             multi_page_with_middle_elements,
                             multi_page_with_middle_elements_and_other,
                             multi_page_with_headerfooter_empty_page_beginning,):
    return [
        multi_page_with_headerfooter_empty_page_middle,
        multi_page_with_headerfooter_all_empty,
        multi_page_with_middle_elements,
        multi_page_with_middle_elements_and_other,
        multi_page_with_headerfooter_empty_page_beginning,
    ]


@pytest.fixture
def mock_texts():
    return [
        MockTxt(x1=100, y1=100, txt="Test"),
        MockTxt(x1=100, y1=100, txt="Test"),
        MockTxt(x1=200, y1=200, txt="Test"),
        MockTxt(x0=50, x1=200, y0=50, y1=100, txt="Test"),
        MockTxt(x1=100, y1=100, txt="Test-1"),
        MockTxt(x1=100, y1=100, txt="Test-2"),
        MockTxt(x1=100, y1=100, txt="Test-33"),
        MockTxt(x1=100, y1=100, txt="Te st"),
        MockTxt(x1=100, y1=100, txt="Te   st"),
        MockTxt(x1=100, y1=100, txt="Test ViI1"),
        MockTxt(x1=100, y1=100, txt="Test V1Ll"),
        MockTxt(x1=100, y1=100, txt="Test VXXX"),
        MockTxt(x1=100, y1=100, txt="Test V222"),
    ]


@pytest.fixture
def headers(mock_texts):
    return [
        Header(elements=[mock_texts[0], mock_texts[0]], p=0, indices=[0, 1]),
        Header(elements=[mock_texts[0], mock_texts[3]], p=1, indices=[1, 2]),
        Header(elements=[mock_texts[0], mock_texts[0]], p=0, indices=[0, 1]),
        Header(elements=[mock_texts[4]], p=2, indices=[3]),
        Header(elements=[mock_texts[5]], p=3, indices=[3]),
        Header(elements=[mock_texts[4]], p=4, indices=[3]),
        Header(elements=[mock_texts[5]], p=5, indices=[3]),
        Header(elements=[mock_texts[0], mock_texts[0]], p=0, indices=[0, 1]),
    ]


@pytest.fixture
def pages_with_headers():
    type1 = MockPage([MockTxt(x0=10, x1=100, y0=10, y1=100),        # Header element
                      MockTxt(x0=50, x1=100, y0=50, y1=100),        # Header element
                      MockTxt(x0=500, x1=510, y0=500, y1=510)])     # Content element
    type2 = MockPage([MockTxt(x0=20, x1=100, y0=20, y1=100),        # Header element
                      MockTxt(x0=500, x1=510, y0=500, y1=510)])     # Content element
    type3 = MockPage([MockTxt(x0=90, x1=100, y0=90, y1=100),        # Header element
                      MockTxt(x0=500, x1=510, y0=500, y1=510)])     # Content element

    return [
        MockPage([]),
        copy.deepcopy(type1),
        copy.deepcopy(type2),
        copy.deepcopy(type1),
        copy.deepcopy(type2),
        copy.deepcopy(type2),
        copy.deepcopy(type2),
        copy.deepcopy(type2),
        copy.deepcopy(type1),
        copy.deepcopy(type3),
        copy.deepcopy(type3),
        copy.deepcopy(type3),
        copy.deepcopy(type1),
    ]


@pytest.fixture
def pages_with_headers_odd_even():
    type1_a = MockPage([MockTxt(x0=20, x1=100, y0=20, y1=100),        # Content
                        MockTxt(x0=0, x1=10, y0=0, y1=10)])           # Footer
    type1_b = MockPage([MockTxt(x0=50, x1=70, y0=50, y1=70),          # Content
                        MockTxt(x0=0, x1=10, y0=0, y1=10)])           # Footer
    type2_a = MockPage([MockTxt(x0=40, x1=45, y0=40, y1=45),        # Content
                        MockTxt(x0=90, x1=100, y0=0, y1=10)])           # Footer
    type2_b = MockPage([MockTxt(x0=30, x1=35, y0=30, y1=35),          # Content
                        MockTxt(x0=90, x1=100, y0=0, y1=10)])           # Footer

    return [
        MockPage([]),
        copy.deepcopy(type1_a),
        copy.deepcopy(type2_a),
        copy.deepcopy(type1_b),
        copy.deepcopy(type2_b),
        copy.deepcopy(type1_a),
        copy.deepcopy(type2_a),
        copy.deepcopy(type1_b),
        copy.deepcopy(type2_b),
        copy.deepcopy(type1_a),
        copy.deepcopy(type2_a),
        copy.deepcopy(type1_b),
        copy.deepcopy(type2_b),
    ]


@pytest.fixture
def pages_with_headers_ocr():
    type1, type2, type3 = [], [], []
    for i in range(5):
        p1 = MockPage([MockTxt(x0=10 + 0.1 * i, x1=100 + 0.1 * i, y0=10 + 0.1 * i, y1=100 + 0.1 * i),        # Header element
                       MockTxt(x0=50, x1=100, y0=50, y1=100),        # Header element
                       MockTxt(x0=500, x1=510, y0=500, y1=510)])     # Content element
        p2 = MockPage([MockTxt(x0=20 + 0.1 * i, x1=100 + 0.1 * i, y0=20 + 0.1 * i, y1=100 + 0.1 * i),        # Header element
                       MockTxt(x0=500, x1=510, y0=500, y1=510)])     # Content element
        p3 = MockPage([MockTxt(x0=90 + 0.1 * i, x1=100 + 0.1 * i, y0=90 + 0.1 * i, y1=100 + 0.1 * i),        # Header element
                       MockTxt(x0=500, x1=510, y0=500, y1=510)])     # Content element
        type1.append(p1)
        type2.append(p2)
        type3.append(p3)

    return [
        MockPage([]),
        type1[0],
        type2[0],
        type1[1],
        type2[1],
        type2[2],
        type2[3],
        type2[4],
        type1[2],
        type3[0],
        type3[1],
        type3[2],
        type1[3],
    ]


@pytest.fixture
def pages_with_headers_brute_force():
    type2 = MockPage([MockTxt(x0=20, x1=100, y0=20, y1=100),        # Header element
                      MockTxt(x0=500, x1=510, y0=500, y1=510)])     # Content element

    return [
        MockPage([]),
        copy.deepcopy(type2),
        copy.deepcopy(type2),
    ]


@pytest.fixture
def pages_with_headers_single_page():
    return [MockPage([MockTxt(x0=20, x1=100, y0=20, y1=100), MockTxt(x0=500, x1=510, y0=500, y1=510)])]


class MockText(LTTextContainer):
    def __init__(self, x, x0=0):
        self._objs = x
        self.x0 = x0
        if self.x0 == 0 and x != []:
            self.x0 = min([y.x0 for y in x])
            self.x1 = max([y.x1 for y in x])
            self.y0 = min([y.y0 for y in x])
            self.y1 = max([y.y1 for y in x])
            self.bbox = (self.x0, self.y0, self.x1, self.y1)

    def __len__(self):
        return self._objs.__len__()

    def __iter__(self):
        return self._objs.__iter__()


class MockLine(LTTextLine):
    def __init__(self, x=[], x0=0, x1=1, y0=0, y1=1):
        self._objs = x
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1
        self.bbox = (x0, y0, x1, y1)
        self.height = y1 - y0
        self.width = x1 - x0

    def __len__(self):
        return self._objs.__len__()

    def __iter__(self):
        return self._objs.__iter__()


class MockChar(LTChar):
    def __init__(self, font=None, txt="x", x0=0, y0=0, x1=1, y1=1, size=10):
        self.fontname = font
        self.size = size
        self._text = txt
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.width = x1 - x0


class MockTable():
    def __init__(self, df):
        self.df = df


@pytest.fixture
def pages_without_tables():
    return [MockPage([Txt("1"), Txt("2"), Txt("3")]),
            MockPage([Txt("4"), Txt("5"), Txt("6")])]


@pytest.fixture
def empty_pages_without_tables():
    return [MockPage([]), MockPage([])]


@pytest.fixture
def pages_with_single_table():
    t = LTTable()
    t.camelot_table = MockTable(pd.DataFrame([[1, 2, 3], [4, 5, 6]]))
    return [MockPage([Txt("1"), t, Txt("3")]),
            MockPage([Txt("4"), Txt("5"), Txt("6")])]


@pytest.fixture
def pages_with_2_tables_same_page():
    t1, t2 = LTTable(), LTTable()
    t1.camelot_table = MockTable(pd.DataFrame([[1, 2, 3], [4, 5, 6]]))
    t2.camelot_table = MockTable(pd.DataFrame([[3, 3, 3], [4, 2, 0]]))
    return [MockPage([Txt("1"), t1, t2]),
            MockPage([Txt("4"), Txt("5"), Txt("6")])]


@pytest.fixture
def pages_with_2_tables():
    t1, t2 = LTTable(), LTTable()
    t1.camelot_table = MockTable(pd.DataFrame([[1, 2, 3], [4, 5, 6]]))
    t2.camelot_table = MockTable(pd.DataFrame([[3, 3, 3], [4, 2, 0]]))
    return [MockPage([Txt("1"), t1]),
            MockPage([t2, Txt("5")])]


@pytest.fixture
def pages_with_2_tables_diff_col():
    t1, t2 = LTTable(), LTTable()
    t1.camelot_table = MockTable(pd.DataFrame([[1, 2, 3], [4, 5, 6]]))
    t2.camelot_table = MockTable(pd.DataFrame([[3, 3], [4, 2]]))
    return [MockPage([Txt("1"), t1]),
            MockPage([t2, Txt("5")])]


@pytest.fixture
def pages_with_2_tables_diff_pos():
    t1, t2 = LTTable(), LTTable()
    t1.camelot_table = MockTable(pd.DataFrame([[1, 2, 3], [4, 5, 6]]))
    t2.camelot_table = MockTable(pd.DataFrame([[3, 3, 3], [4, 2, 0]]))
    t1.x0, t1.x1 = 0, 0
    t2.x0, t2.x1 = 5, 5
    return [MockPage([Txt("1"), t1]),
            MockPage([t2, Txt("5")])]


@pytest.fixture
def pages_with_2_tables_with_something():
    t1, t2 = LTTable(), LTTable()
    t1.camelot_table = MockTable(pd.DataFrame([[1, 2, 3], [4, 5, 6]]))
    t2.camelot_table = MockTable(pd.DataFrame([[3, 3, 3], [4, 2, 0]]))
    return [MockPage([Txt("1"), t1]),
            MockPage([Txt("4"), t2, Txt("5")])]


@pytest.fixture
def pages_with_3_tables():
    t1, t2, t3 = LTTable(), LTTable(), LTTable()
    t1.camelot_table = MockTable(pd.DataFrame([[1, 2, 3], [4, 5, 6]]))
    t2.camelot_table = MockTable(pd.DataFrame([[3, 3, 3], [4, 2, 0], [4, 2, 0]]))
    t3.camelot_table = MockTable(pd.DataFrame([[0, 3, 0]]))
    return [MockPage([Txt("1"), t1]),
            MockPage([t2]),
            MockPage([t3, Txt("4")])]


@pytest.fixture
def pages_with_3_tables_with_something():
    t1, t2, t3, t4 = LTTable(), LTTable(), LTTable(), LTTable()
    t1.camelot_table = MockTable(pd.DataFrame([[1, 2, 3], [4, 5, 6]]))
    t2.camelot_table = MockTable(pd.DataFrame([[3, 3, 3], [4, 2, 0], [4, 2, 0]]))
    t3.camelot_table = MockTable(pd.DataFrame([[0, 3, 0]]))
    t4.camelot_table = MockTable(pd.DataFrame([[3, 5, 3], [4, 2, 0], [4, 2, 0]]))
    return [MockPage([Txt("1"), t1]),
            MockPage([t2, Txt("4"), t4]),
            MockPage([t3])]


@pytest.fixture
def tables_merge_fixtures(pages_without_tables, empty_pages_without_tables,
                          pages_with_single_table, pages_with_2_tables_same_page,
                          pages_with_2_tables, pages_with_2_tables_diff_col,
                          pages_with_2_tables_diff_pos,
                          pages_with_2_tables_with_something, pages_with_3_tables,
                          pages_with_3_tables_with_something):
    return {
        'no_t': pages_without_tables,
        'empty': empty_pages_without_tables,
        '1_t': pages_with_single_table,
        '2_t_same_page': pages_with_2_tables_same_page,
        '2_t': pages_with_2_tables,
        '2_t_diff_col': pages_with_2_tables_diff_col,
        '2_t_diff_pos': pages_with_2_tables_diff_pos,
        '2_t_nomerge': pages_with_2_tables_with_something,
        '3_t': pages_with_3_tables,
        '3_t_nomerge': pages_with_3_tables_with_something
    }


@pytest.fixture
def pages_no_columns():
    return [MockPage([MockTxt(y0=60, y1=61, txt="3"),
                      MockTxt(y0=40, y1=41, txt="4"),
                      MockTxt(y0=80, y1=81, txt="2"),
                      MockTxt(y0=100, y1=101, txt="1")])]


@pytest.fixture
def pages_2_columns():
    return [MockPage([MockTxt(y0=100, y1=101, txt="1"),
                      MockTxt(x0=700, x1=701, txt="4"),
                      MockTxt(x0=700, y0=100, x1=701, y1=101, txt="3"),
                      MockTxt(txt="2")])]


@pytest.fixture
def pages_2_columns_and_1_common():
    return [MockPage([MockTxt(y0=80, y1=81, txt="2"),
                      MockTxt(y0=100, y1=101, x1=701, txt="1"),
                      MockTxt(x0=700, x1=701, y0=60, y1=61, txt="4"),
                      MockTxt(x0=700, x1=701, y0=80, y1=81, txt="3")])]


@pytest.fixture
def pages_1_common_and_2_columns():
    return [MockPage([MockTxt(y0=100, y1=101, txt="1"),
                      MockTxt(x0=700, x1=701, y0=80, y1=81, txt="3"),
                      MockTxt(y0=80, y1=81, txt="2"),
                      MockTxt(x1=701, txt="4")])]


@pytest.fixture
def columned_pages(pages_no_columns, pages_2_columns,
                   pages_2_columns_and_1_common, pages_1_common_and_2_columns):
    return {
        'normal': pages_no_columns,
        '2_col': pages_2_columns,
        '2_col+common': pages_2_columns_and_1_common,
        'common+2_col': pages_1_common_and_2_columns
    }


@pytest.fixture
def lined_pages_2_columns():
    return [MockPage([MockText([MockLine(x0=0, x1=450)]),
                      MockText([MockLine(x0=550, x1=1000)])])]


@pytest.fixture
def lined_pages_1_line_left(request):
    return [MockPage([MockText([MockLine(x0=0, x1=250)]),
                      MockText([MockLine(x0=350, x1=1000)])])]


@pytest.fixture
def lined_pages_1_line_right(request):
    return [MockPage([MockText([MockLine(x0=0, x1=750)]),
                      MockText([MockLine(x0=850, x1=1000)])])]


@pytest.fixture
def lined_pages_2_columns_diff_height():
    return [MockPage([MockText([MockLine(x0=0, x1=450)]),
                      MockText([MockLine(x0=550, x1=1000, y0=2, y1=3)])])]


@pytest.fixture
def lined_pages_1_line_multimatch():
    return [MockPage([MockText([MockLine(x0=0, x1=250)]),
                      MockText([MockLine(x0=300, x1=700)]),
                      MockText([MockLine(x0=750, x1=1000)])])]


@pytest.fixture
def lined_pages_2_line_multimatch():
    return [MockPage([MockText([MockLine(x0=0, x1=200)]),
                      MockText([MockLine(x0=250, x1=450)]),
                      MockText([MockLine(x0=550, x1=750)]),
                      MockText([MockLine(x0=800, x1=1000)])])]


@pytest.fixture
def multilined_pages_2_columns():
    return [MockPage([MockText([MockLine(x0=0, x1=950, y0=200, y1=201),
                                MockLine(x0=0, x1=450, y0=100, y1=101),
                                MockLine(x0=0, x1=950)]),
                      MockText([MockLine(x0=50, x1=1000, y0=150, y1=151),
                                MockLine(x0=550, x1=1000, y0=100, y1=101)])])]


@pytest.fixture
def multilined_pages_1_line_left(request):
    return [MockPage([MockText([MockLine(x0=0, x1=950, y0=200, y1=201),
                                MockLine(x0=0, x1=250, y0=100, y1=101),
                                MockLine(x0=0, x1=950)]),
                      MockText([MockLine(x0=50, x1=1000, y0=150, y1=151),
                                MockLine(x0=350, x1=1000, y0=100, y1=101)])])]


@pytest.fixture
def multilined_pages_1_line_right(request):
    return [MockPage([MockText([MockLine(x0=0, x1=950, y0=200, y1=201),
                                MockLine(x0=0, x1=750, y0=100, y1=101),
                                MockLine(x0=0, x1=950)]),
                      MockText([MockLine(x0=50, x1=1000, y0=150, y1=151),
                                MockLine(x0=800, x1=1000, y0=100, y1=101)])])]


@pytest.fixture
def multilined_pages_2_columns_diff_height():
    return [MockPage([MockText([MockLine(x0=0, x1=950, y0=200, y1=201),
                                MockLine(x0=0, x1=450, y0=100, y1=101),
                                MockLine(x0=0, x1=950)]),
                      MockText([MockLine(x0=50, x1=1000, y0=150, y1=151),
                                MockLine(x0=550, x1=1000, y0=102, y1=103)])])]


@pytest.fixture
def multilined_pages_1_line_multimatch():
    return [MockPage([MockText([MockLine(x0=0, x1=950, y0=200, y1=201),
                                MockLine(x0=0, x1=250, y0=100, y1=101),
                                MockLine(x0=0, x1=950)]),
                      MockText([MockLine(x0=50, x1=1000, y0=150, y1=151),
                                MockLine(x0=300, x1=700, y0=100, y1=101)]),
                      MockText([MockLine(x0=750, x1=1000, y0=100, y1=101)])])]


@pytest.fixture
def multilined_pages_2_line_multimatch():
    return [MockPage([MockText([MockLine(x0=0, x1=950, y0=200, y1=201),
                                MockLine(x0=0, x1=200),
                                MockLine(x0=0, x1=950, y0=-200, y1=-199)]),
                      MockText([MockLine(x0=250, x1=450),
                                MockLine(x0=0, x1=950, y0=-200, y1=-199)]),
                      MockText([MockLine(x0=550, x1=750)]),
                      MockText([MockLine(x0=0, x1=950, y0=200, y1=201),
                                MockLine(x0=800, x1=1000)])])]


@pytest.fixture
def lined_pages(lined_pages_2_columns, lined_pages_1_line_left, lined_pages_1_line_right,
                lined_pages_2_columns_diff_height, lined_pages_1_line_multimatch,
                lined_pages_2_line_multimatch, multilined_pages_1_line_left,
                multilined_pages_1_line_right, multilined_pages_2_columns_diff_height,
                multilined_pages_1_line_multimatch, multilined_pages_2_columns,
                multilined_pages_2_line_multimatch):
    return {
        '2_col': lined_pages_2_columns,
        '1_liner': lined_pages_1_line_right,
        '1_linel': lined_pages_1_line_left,
        'diff_height': lined_pages_2_columns_diff_height,
        'multimatch': lined_pages_1_line_multimatch,
        'multimatch_2l': lined_pages_2_line_multimatch,
        'm2_col': multilined_pages_2_columns,
        'm1_liner': multilined_pages_1_line_right,
        'm1_linel': multilined_pages_1_line_left,
        'mdiff_height': multilined_pages_2_columns_diff_height,
        'mmultimatch': multilined_pages_1_line_multimatch,
        'mmultimatch_2l': multilined_pages_2_line_multimatch,
    }


@pytest.fixture
def pages_with_toc_tables():
    return [
        MockPage([MockText([MockLine(x=[MockChar(txt="Some text")])])]),
        MockPage([MockText([MockLine(x=[MockChar(txt="Contents")], y0=100, y1=101)]),
                  MockText([MockLine(x=[MockChar(txt="p 3")], y0=80, y1=81)]),
                  MockText([MockLine(x=[MockChar(txt="p 4")], y0=60, y1=61)])]),
        MockPage([MockText([MockLine(x=[MockChar(txt="Some text")])])]),
        MockPage([MockText([MockLine(x=[MockChar(txt="Some text")])])]),
        MockPage([MockText([MockLine(x=[MockChar(txt="Contents")], y0=100, y1=101)]),
                  MockText([MockLine(x=[MockChar(txt="Title")], x1=10, y0=80, y1=81),
                            MockLine(x=[MockChar(txt="Title")], x1=10, y0=60, y1=61)]),
                  MockText([MockLine(x=[MockChar(txt="Title2")], x1=20, y0=80, y1=81),
                            MockLine(x=[MockChar(txt="Title2")], x1=20, y0=60, y1=61)]),
                  MockText([MockLine(x=[MockChar(txt="p 5")], x1=30, y0=80, y1=81),
                            MockLine(x=[MockChar(txt="p 6")], x1=30, y0=60, y1=61)])]),
        MockPage([MockText([MockLine(x=[MockChar(txt="p 8")], y0=100, y1=101)])]),
        MockPage([MockText([MockLine(x=[MockChar(txt="p 19")], y0=100, y1=101)])]),
        MockPage([MockText([MockLine(x=[MockChar(txt="Some text")])])]),
    ]


@pytest.fixture
def pages_with_table(all_crossing_lines):
    h, v = all_crossing_lines
    return [MockPage([
        *h, *v,
        MockText([MockLine(x=[MockChar(txt="a")], x0=0, x1=100, y0=0, y1=100),
                  MockLine(x=[MockChar(txt="b")], x0=600, x1=1000, y0=600, y1=1000)]),
        MockText([MockLine(x=[MockChar(txt="c")], x0=-1000, x1=-500, y0=-1000, y1=-500)]),
        MockText([MockLine(x=[MockChar(txt="d")], x0=0, x1=100, y0=0, y1=100)]),
    ])]


class MockTable2():
    def __init__(self, bbox):
        self._bbox = bbox
