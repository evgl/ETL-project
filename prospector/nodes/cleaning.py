import re
from collections import Counter

from bonobo.config import Option
from pdfminer.layout import LTTextContainer, LTPage, LTChar, LTAnno

from prospector.nodes.utils import ConfigurableModificator
from prospector.miner import rm, merge_with_previous, get


class FixIndentationSeparatedText(ConfigurableModificator):
    """ Node that merge back some text, when it was in the same paragraph but
    with a different indentation.

    Some text, when going to a new line, are indented differently. Because of
    this, `pdfminer` separate the text into 2 differents paragraph, just
    because of this indentation. But the text should be a single paragraph.

    This node simply check if the line difference between 2 paragraphs is
    smaller than a margin (see `line_margin` in `pdfminer` documentation). If
    it's the case and if the text is otherwise in the same bounding box, it
    merges the 2 paragraphs back together.

    Attributes:
        line_margin (float): `pdfminer` parameter. See
            [documentation](https://pdfminersix.readthedocs.io/en/latest/reference/composable.html#laparams).
        end_area_ratio (float): From where we consider the end area is.
    """

    line_margin = Option(float, default=0.75, required=False, __doc__="`pdfminer` parameter")
    end_area_ratio = Option(float, default=0.75, required=False, __doc__="End area ratio")

    def __call__(self, doc_path, doc_name, pages):
        """ Iterate pages and ensure there is no separated paragraphs that
        should not be separated. If there is, merge them.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: List of PDF pages extracted from the file.
        """
        pages = self.cp(pages)

        for p, page in enumerate(pages):
            prev_elem = None
            to_merge = []
            max_x1 = 0
            for e, elem in enumerate(page):
                if prev_elem is not None and self._is_close(prev_elem, elem):
                    if self._is_indented_item(prev_elem, elem, max_x1) or \
                            self._is_middle_text(prev_elem, elem):
                        to_merge.append(e)
                prev_elem = elem
                max_x1 = max(max_x1, elem.x1)

            merge_with_previous(page, to_merge)

        return doc_path, doc_name, pages

    def _is_close(self, elem1, elem2):
        """ Check if the 2 elements are close enough together to be considered
        the same text or not.

        Refer to shorturl.at/cvO15

        Arguments:
            elem1 (pdfminer Element): Element of the page.
            elem2 (pdfminer Element): Successive element of the page.

        Returns:
            bool: `True` if the 2 elements are close enough, `False` otherwise.
        """
        if not isinstance(elem1, LTTextContainer) or not isinstance(elem2, LTTextContainer) or \
                len(elem1) == 0 or len(elem2) == 0:
            return False
        last_line_e1 = get(elem1, -1)
        first_line_e2 = get(elem2, 0)
        l1 = last_line_e1.y1 - first_line_e2.y1
        l2 = last_line_e1.y0 - first_line_e2.y0
        alm = (last_line_e1.height + first_line_e2.height) * self.line_margin
        return l1 < alm and l2 < alm

    def _is_indented_item(self, elem1, elem2, max_x1):
        """ Given 2 elements, check if they are an "indented item" together.
        An indented item look like :

        •    This is a line with a bullet point at the
             beginning and this text continue, but with some
             indentation.

        Because the bullet point is considered part of the text, the bbox of
        each line is different, so `pdfminer` consider it as 2 different
        paragraphs. But we should consider it as a single paragraph.

        Arguments:
            elem1 (pdfminer Element): Element of the page.
            elem2 (pdfminer Element): Successive element of the page.
            max_x1 (float): The maximum end x-coordinate for elements so far
                in the page. Used to ensure the first line is reaching around
                the end of the page.

        Returns:
            bool: `True` if the 2 elements represent an indented item, `False`
                otherwise.
        """
        if len(elem1) != 1:     # The first element should be a single line
            return False

        # Ensure the line 1 is reaching the end of the area. If it's not, then
        # it's not a multi line...
        if elem1.x1 < self.end_area_ratio * max_x1:
            return False

        if elem2.x1 > elem1.x1:
            # End position of text is not matching. Maybe due to word size ?
            # Try to see if it's due to the next word size.
            char_width = []
            for char in get(elem2, 0):
                if char.get_text().isspace():
                    break
                if isinstance(char, LTAnno):
                    continue
                char_width.append(char.width)
            w = sum(char_width[:-1])
            return elem2.x0 - elem1.x0 > 1 and elem2.x1 <= elem1.x1 + w
        else:
            return elem2.x0 - elem1.x0 > 1

    def _is_middle_text(self, elem1, elem2):
        """ Given 2 elements, check if they are a "middle text" together.
        An middle text look like :

                        This is
               the beginning of the line
                  and this is the end

        Because each line starts from a different point, `pdfminer` consider it
        as different paragraphs. But we should consider it as a single
        paragraph.

        Arguments:
            elem1 (pdfminer Element): Element of the page.
            elem2 (pdfminer Element): Successive element of the page.

        Returns:
            bool: `True` if the 2 elements represent an middle text, `False`
                otherwise.
        """
        middle_x = [round(l1.x0 + (l1.x1 - l1.x0) / 2) for l1 in elem1]
        middle_x.extend([round(l2.x0 + (l2.x1 - l2.x0) / 2) for l2 in elem2])
        return all(m_pos == middle_x[0] for m_pos in middle_x)


class RemoveContentTable(ConfigurableModificator):
    """ Node that finds the content table(s), and remove it, as well as all the
    content appearing before the first content table. Usually this is some
    useless content, the document really starts after the content table.

    Content table are found by matching string for the title, and ensuring most
    lines of the TOC end with a number (page number).

    Attributes:
        ratio (float): Ratio of number of lines that should finish by a digit
            for the page to be considered as part of the content table.
    """

    ratio = Option(float, default=0.6, required=False)

    def __call__(self, doc_path, doc_name, pages):
        """ Find the first page that look like a TOC and empty it, as
        well as previous pages. We should empty it and not remove it completely
        because we still need to know the page number.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: List of PDF pages extracted from the file,
                with empty pages instead of content table.
        """
        pages = self.cp(pages)

        tocs = self._find_toc_tables(pages)
        if len(tocs) > 0:
            tocs[0] = (0, tocs[0][1])      # Remove all content before the first TOC

        # Empty TOC pages
        for toc in tocs:
            for idx in range(toc[0], toc[1]):
                # Make an new, empty LTPage
                pages[idx] = LTPage(pageid=pages[idx].pageid, bbox=pages[idx].bbox, rotate=pages[idx].rotate)

        return doc_path, doc_name, pages

    def _find_toc_tables(self, pages):
        """ Method finding which pages are TOC.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            list of tuple of int: List containing the start and end pages of
                each TOC.
        """
        tocs = []
        toc_title_p = None              # Keep in memory the TOC start page
        for p, page in enumerate(pages):
            lines = {}                  # (y0, y1) -> str       Lines content
            lines_x = {}                # (y0, y1) -> int       Lines end position
            for elem in page:
                if isinstance(elem, LTTextContainer):
                    text = elem.get_text().strip()
                    if toc_title_p is None and self._is_toc_title(text):
                        toc_title_p = p

                    if toc_title_p is not None and len(elem) > 0:
                        for line in elem:
                            y_coord = (round(line.y0), round(line.y1))

                            if y_coord not in lines_x or line.x1 > lines_x[y_coord]:
                                lines[y_coord] = line.get_text().strip()
                                lines_x[y_coord] = line.x1

            if toc_title_p is not None and not self._is_toc_content(lines.values()):
                # Look like we found the end of the TOC
                tocs.append((toc_title_p, p))
                toc_title_p = None

        if toc_title_p is not None:
            tocs.append((toc_title_p, toc_title_p + 1))
        return tocs

    def _is_toc_title(self, text):
        """ Check if the given text is a title for a TOC.

        Arguments:
            text (str): String to check.

        Returns:
            bool: `True` if the text is the title of a TOC, `False` otherwise.
        """
        def normalize(x):
            return re.sub(r"[\W_]+", '', x).strip().lower()
        toc_titles = ['content', 'contents', 'tableofcontent', 'tableofcontents']
        return any(normalize(line) in toc_titles for line in text.split("\n") if line != "")

    def _is_toc_content(self, lines):
        """ Check if the lines are the content of a TOC. It's TOC content if
        most lines ends with a page number.

        Arguments:
            lines (list of str): Lines to check.

        Returns:
            bool: `True` if the lines are the content of a TOC, `False`
                otherwise.
        """
        lines = [line for line in lines if line != ""]
        if len(lines) == 0:
            return False

        nb_digit_line = 0
        for line in lines:
            if re.search(r"\d\s*$", line):
                nb_digit_line += 1
        return nb_digit_line / len(lines) > self.ratio


class RemoveNonSearchablePage(ConfigurableModificator):
    """ Node that finds the non-searchable page(s) and removes it. This Node
    will only keep searchable pages. `camelot` doesn't work on pages that only
    contain non-searchable elements (e.g. image)
    """

    def __call__(self, doc_path, doc_name, pages):
        """ Find the non-searchable pages and empty it. We should empty it and
        not remove it completely because we still need to know the page number.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: List of PDF pages extracted from the file,
                with empty pages instead of non-searchable pages.
        """
        pages = self.cp(pages)

        nsps = self._find_non_searchable_pages(pages)

        for idx in nsps:
            pages[idx] = LTPage(pageid=pages[idx].pageid, bbox=pages[idx].bbox, rotate=pages[idx].rotate)

        return doc_path, doc_name, pages

    def _find_non_searchable_pages(self, pages):
        """ Method finding which pages are non-searchable.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            list of int: List of non-searchable pages
        """
        nsps = []
        for idx, page in enumerate(pages):
            if not self.is_searchable_page(page):
                nsps.append(idx)
        return nsps

    def is_searchable_page(self, page):
        """ Check if the given page is searchable

        Arguments:
            page (pdfminer.LTPage): A single page extracted from a PDF file.

        Returns:
            bool: `True` if the page is searchable, `False` otherwise.
        """
        for elem in page:
            if isinstance(elem, LTTextContainer) and elem.get_text().strip() != "":
                return True
        return False


class RemoveMathCharacters(ConfigurableModificator):
    """ Node removing all text with a math font. Because it relies on font
    information, this node should be placed after `ExtractFontInfo`.
    """

    def __call__(self, doc_path, doc_name, pages):
        """ Remove all element with a math font.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: List of PDF pages extracted from the file,
                without math content.
        """
        pages = self.cp(pages)

        for page in pages:
            for elem in page:
                if not isinstance(elem, LTTextContainer):
                    continue

                for line in elem:
                    rm(line, to_rm=lambda x: isinstance(x, LTChar) and "Math" in str(x.fontname))

        return doc_path, doc_name, pages


class RemoveEmptyLines(ConfigurableModificator):
    """ Node removing all lines that are empty (just space). Since these lines
    contains no information, no need to clutter the pdfminer object with these.
    """

    def __call__(self, doc_path, doc_name, pages):
        """ Remove all empty lines.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: List of PDF pages extracted from the file,
                without empty lines.
        """
        pages = self.cp(pages)

        for page in pages:
            for elem in page:
                if isinstance(elem, LTTextContainer):
                    rm(elem, to_rm=lambda x: x.get_text().isspace())

            # Ensure all text elements are not empty
            rm(page, to_rm=lambda x: isinstance(x, LTTextContainer) and len(x) == 0)

        return doc_path, doc_name, pages


class RemoveLandscapePages(ConfigurableModificator):
    """ Node removing all landscape pages of the PDF file. Usually this kind of
    pages contain garbage content (appendix, big table or figure).

    Attributes:
        dist_margin (float): Minimum distance difference between 2 pages to be
            considered of different size.
    """

    dist_margin = Option(float, default=10, required=False, __doc__="Minimum distance difference.")

    def __call__(self, doc_path, doc_name, pages):
        """ Remove all landscape pages. We first find the most common page size
        among the document, and remove outliers.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages extracted from the file, without
                landscape pages.
        """
        pages = self.cp(pages)

        all_sizes = [(round(page.width), round(page.height)) for page in pages]
        normal_size = Counter(all_sizes).most_common()[0][0]

        wrong_sized_p = [i for i, s in enumerate(all_sizes)
                         if self._size_dist(s, normal_size) > self.dist_margin]
        for p in wrong_sized_p:
            pages[p] = LTPage(pageid=pages[p].pageid, bbox=pages[p].bbox, rotate=pages[p].rotate)

        return doc_path, doc_name, pages

    def _size_dist(self, size1, size2):
        """ Compute distance between 2 sizes

        Arguments:
            size1 (tuple of int): First size to compare.
            size2 (tuple of int): Second size to compare.

        Returns:
            float: Distance between the 2 sizes.
        """
        return sum(abs(s1 - s2) for s1, s2 in zip(size1, size2))
