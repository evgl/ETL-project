"""
File containing some custom definitions over the `pdfminer.six` library,
in order to improve the library.
"""
from pdfminer.layout import LTExpandableContainer, LTTextContainer, LTTextLine, LTAnno


class LTTable(LTExpandableContainer):
    """ Custom class for representing a table. Nothing else than that. Also it
    may be annotated later with the tables found by camelot.

    Attributes:
        camelot_table (camelot.Table): Table found from `camelot`. May be None
            if `camelot` is not used.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camelot_table = None

    def merge(self, x):
        """ Merge another LTTable object into this one.

        Arguments:
            x (LTTable): Table to merge with this one.
        """
        self.camelot_table.df = self.camelot_table.df.append(x.camelot_table.df)


class LTParagraph(LTTextContainer):
    """ Custom class for representing a paragraph. Easier to build than the
    existing objects in `pdfminer`, where we have to build text character by
    character...

    Attributes:
        text (str): Text of the paragraph.
    """
    def __init__(self, text="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text = text
        self.title_level = None

    def get_text(self):
        """ Need to overwrite this function for accessing text like any other
        `LTTextContainer`.

        Returns:
            str: Text of the container.
        """
        return self.text


def rm(page, to_rm, _enumerate=False):
    """ Helper function deleting the specified indices from the given pdfminer
    object.

    Arguments:
        page (pdfminer Object): Object from where we should delete some
            elements. It can be another object than `Page`, as long as its
            content is stored in `page._objs`.
        to_rm (list or callable): Elements to delete. Can be given as a list or
            a callable. If a list is given, it should contains the indices to
            remove from the object. If it's a callable, it should return `True`
            or `False` given an element.
        _enumerate (bool, optional): If `to_rm` is a callable, weither to return
            the index of the current element as well or not. Defaults to
            `False`.

    Returns:
        pdfminer Object: Cleaned object, without the element to remove.
    """
    # Get the elements to remove
    if isinstance(to_rm, list):
        idx_to_rm = to_rm
    else:
        idx_to_rm = []
        for e, elem in enumerate(page):
            if _enumerate:
                is_to_rm = to_rm(e, elem)
            else:
                is_to_rm = to_rm(elem)

            if is_to_rm:
                idx_to_rm.append(e)

    # Remove it from the objs
    for i in sorted(idx_to_rm, reverse=True):
        page._objs.pop(i)

    return page


def get(page, idx):
    """ Helper function retrieving the element at the given index.

    Arguments:
        page (pdfminer Object): Object from where we should retrieve some
            element. It can be another object than `Page`, as long as its
            content is stored in `page._objs`.
        idx (int): Index of the element to retrieve.

    Returns:
        pdfminer Object: Element which is at the given position in the given
            object.
    """
    return page._objs[idx]


def merge_with_previous(page, to_merge):
    """ Helper function merging the element at the given index, with the
    element located right before.

    Arguments:
        page (pdfminer Object): Object where we should merge some element. It
            can be another object than `Page`, as long as its content is stored
            in `page._objs`.
        to_merge (list): List of index of the elements to merge.

    Returns:
        pdfminer Object: Cleaned object, with merged elements.
    """
    for i in sorted(to_merge, reverse=True):
        elem = page._objs.pop(i)
        for o in elem._objs:
            page._objs[i - 1].add(o)

    return page


def append(page, x):
    """ Helper function to add an element to the given object.

    Arguments:
        page (pdfminer Object): Object where we should append some elements. It
            can be another object than `Page`, as long as its content is stored
            in `page._objs`.
        x (pdfminer Object): Element to add.
    """
    page._objs.append(x)


def insert(page, x, idx):
    """ Helper function to insert an element to the given object, at the
    specific index.

    Arguments:
        page (pdfminer Object): Object where we should append some elements. It
            can be another object than `Page`, as long as its content is stored
            in `page._objs`.
        x (pdfminer Object): Element to add.
        idx (int): Index where to insert the element.
    """
    page._objs.insert(idx, x)


def merge_lines(l1, l2):
    """ Helper function to merge 2 LTTextLine together.

    Note : The order of arguments matter.

    Arguments:
        l1 (LTTextLine): Line 1.
        l2 (LTTextLine): Line 2 to merge into line 1.
    """
    assert isinstance(l1, LTTextLine) and isinstance(l2, LTTextLine)

    # First of all, clean the end of first line : Remove \n at the end
    for c in reversed(l1._objs):
        if isinstance(c, LTAnno) and c.get_text() == "\n":
            c._text = ""
        else:
            break

    # Then, append the second line
    for char in l2:
        if isinstance(char, LTAnno):
            l1._objs.append(char)
        else:
            l1.add(char)        # Use `add` to update the bbox of the line


def update_bbox(e):
    """ Helper function to update the bbox of an element. Sometimes, we update
    the bbox of objects contained in this element. But because the object
    itself is not changed (only its content), the bbox is not updated. So we
    need to update the bbox of the object to reflect the updated content.

    Arguments:
        e (pdfminer Object): Object which bbox should be updated.
    """
    if len(e._objs) > 0:
        e.set_bbox((min([c.x0 for c in e._objs]), min([c.y0 for c in e._objs]),
                   max([c.x1 for c in e._objs]), max([c.y1 for c in e._objs])))


def update_pos(page, e):
    """ Helper function to update the position of an element, based on its
    y-coordinate.

    Arguments:
        page (pdfminer Object): Object containing the element to update.
        e (list of int): Indexes of the elements which we should update pos.
    """
    # First, retrieve the elements
    elems = [page._objs.pop(idx) for idx in e]

    for elem in elems:
        for p, page_elem in enumerate(page):
            if elem.y1 > page_elem.y1:
                page._objs.insert(p, elem)
                break
        else:
            page._objs.append(elem)
