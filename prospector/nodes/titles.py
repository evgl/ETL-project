import re
from collections import namedtuple, Counter

from bonobo.config import Option
from pdfminer.layout import LTTextContainer, LTChar, LTRect, LTLine

from prospector.miner import LTTable, get
from prospector.nodes.utils import ConfigurableModificator


UNITS = ['m', 'cm', 'km', 'mm', 'nm', 'kg', 'cm', '°C', '°K', '°F']


CharFont = namedtuple('CharFont', ['size', 'bold', 'italic'])
Font = namedtuple('Font', ['size', 'bold', 'italic', 'underline', 'caps', 'title_like', 'sep_in_title', 'alignement'])
TableFont = namedtuple('TableFont', [])


class ExtractFontInfo(ConfigurableModificator):
    """ Node that extract the font information from `pdfminer` object.

    Attributes:
        margin (float, optional): Only consider the horizontal lines with a
            height less than this margin for checking underlined text. Also
            used for the maximum space allowed between text and the line.
            Defaults to `1`.
    """

    margin = Option(float, default=1.5, required=False, __doc__="Maximum height for lines.")

    def __call__(self, doc_path, doc_name, pages):
        """ Extract information for each text group of the document.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages extracted from a PDF file, with text
                element having font information.
        """
        pages = self.cp(pages)

        for page in pages:
            hlines = []
            for element in page:
                if isinstance(element, LTTable):                # Special case : Table
                    element.font = TableFont()
                elif (isinstance(element, LTRect) or isinstance(element, LTLine)) and element.height <= self.margin:
                    hlines.append(element)      # Keep track of lines, to detect underlined text
                if not isinstance(element, LTTextContainer):    # Ignore everything that is not text
                    continue

                # Each character have their own font...
                char_fonts = []
                for line in element:
                    for character in line:
                        if isinstance(character, LTChar) and character.get_text().isalnum():
                            char_fonts.append(CharFont(
                                size=round(character.size),
                                bold=("Bold" in character.fontname),
                                italic=("Italic" in character.fontname),
                            ))

                if len(char_fonts) == 0:           # Only non-alphanumerical characters
                    element.font = None
                    continue
                else:
                    # Always take the first appearing font as the main font
                    ft = char_fonts[0]

                # Get info from the whole text box
                elem_text = element.get_text().strip()

                caps = elem_text.replace("'s", "").isupper()        # In some caps titles, only "'s" is not caps...
                title_like = self._is_like_title(elem_text)
                sep_in_title = self._has_sep_in_title(elem_text)
                alignement = round(element.x0)

                element.font = Font(size=ft.size, bold=ft.bold, italic=ft.italic,
                                    underline=False, caps=caps, title_like=title_like,
                                    sep_in_title=sep_in_title, alignement=alignement)

            # All elements were assigned a font, with `underline` set to `False`
            # by default. But if we have some lines in the page, try to find
            # the associated text and update the font accordingly
            self._underline_elements(page, hlines)

        return doc_path, doc_name, pages

    def _is_like_title(self, text):
        """ Detect if text starts like a title.

        Arguments:
            text (str): Text to detect.

        Returns:
            bool: `True` if it starts like a title, `False` otherwise.
        """
        units = "|".join([re.escape(u) for u in UNITS])
        # Regex explanation :
        # Pattern 1 : Digits or uppercase letter (1 or 2), separated by separator
        #             (only dot for now). Can have several repetition, but at
        #             least one. Can end up with a separator or not only if it's
        #             a digit. Then spaces and something. Ensure that something
        #             is not `m` or `mm` with negative lookahead (`(?!)`),
        #             because we don't want to match meters and millimeters.
        # Pattern 2 : Same as pattern 1, but force the separator (for the case
        #             with upper letter).
        # Pattern 3 : Same as pattern 1, but allow the first number to be 3
        #             digits long.
        pattern = re.compile(r"^([0-9A-Z]{1,2}\.)*[0-9]{1,2}\.?\s+(?!\.*(" + units + r")\.*(\n.+)?$)\S.*$|"
                             r"^([0-9A-Z]{1,2}\.)+\s+(?!\.*(" + units + r")\.*(\n.+)?$)\S.*$|"
                             r"^[0-9]{1,3}(\.[0-9A-Z]{1,2})*\.?\s+(?!\.*(" + units + r")\.*(\n.+)?$)\S.*$",
                             re.DOTALL)
        return bool(re.search(pattern, text))

    def _has_sep_in_title(self, text):
        """ Detect if the title had separator in it.

        First we check if the text is a title, and if it is, we check if there
        is separator or not (after the first space).
        If the title contain som separator (like dot), it might not be a title.

        Arguments:
            text (str): Text to detect.

        Returns:
            bool: `True` if it has separator in title, `False` otherwise.
        """
        # Regex explanation : See `_is_like_title()` method.
        # Same patterns, but also checking if the title does not contain any dot.
        pattern = re.compile(r"^\S+\s+[^\.]+$", re.DOTALL)
        return self._is_like_title(text) and not bool(re.match(pattern, text))

    def _underline_elements(self, page, hlines):
        """ For each given horizontal line, find if there is a text element
        close enough to be considered as underline. If it's the case, update
        the font of that element.

        Note : This function does not handle all the edge cases. For example it
            can't handle multilines where only part of the line is underlined.

        Arguments:
            page (pdfminer.LTPage): Page with all elements inside.
            hlines (list of pdfminer.LTRect or pdfminer.LTLine): List of
                horizontal lines to possibly match with a text element.
        """
        for hline in hlines:
            found = False
            for element in page:
                if not isinstance(element, LTTextContainer) or element.font is None:
                    continue        # Skip non-text

                for tline in element:
                    if tline.get_text().strip() == "":
                        continue

                    if tline.is_hoverlap(hline) and tline.vdistance(hline) <= self.margin:
                        ft = element.font
                        element.font = Font(size=ft.size, bold=ft.bold,
                                            italic=ft.italic, underline=True,
                                            caps=ft.caps, title_like=ft.title_like,
                                            sep_in_title=ft.sep_in_title,
                                            alignement=ft.alignement)
                        found = True
                        break

                if found:
                    break


class FindTitles(ConfigurableModificator):
    """ Transformation that try to find titles. Because every document is
    different and there is not 1 rule that works for every document, we need a
    heuristic algorithm.

    In our case, we use information about the font, and choose the normal
    text font as the font that appear the most. Then we simply find titles
    based on their font if they respect the following condition :
        * A title SHOULD contain text downward
    Once we find all first level of titles, we add this font as text, so we can
    find the next title level. And we repeat until the end.
    """

    def __call__(self, doc_path, doc_name, pages):
        """ Find titles level by level from font information.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages extracted from a PDF file, with text
                element having an attribute indicating the title level. If the
                title level is None, it's just regular text.
        """
        pages = self.cp(pages)

        # Find the text font by taking the font that have most content
        ft_count = Counter([elem.font for page in pages for elem in page
                            if hasattr(elem, 'font') and elem.font is not None])
        text_ft = ft_count.most_common(1)[0][0]

        # Find similar text fonts
        other_fts = list(ft_count.keys())       # From python 3.6, Counter keep order
        text_fts, other_fts = self._find_similar_text_font(other_fts, text_ft)

        # Table is always considered to be content
        text_fts.append(TableFont())

        # From here we have a set of text fonts and other fonts.
        # Find which fonts divides the documents with text underneath
        title_fts = []
        while len(other_fts) != 0:
            ft, other_fts, is_title = self._find_next_title_font(pages, other_fts, text_fts)
            if is_title:
                title_fts.extend(ft)
            text_fts.extend(ft)
        title_fts.reverse()

        # Update our pages object by setting title level for each element
        for page in pages:
            for element in page:
                if hasattr(element, 'font'):
                    try:
                        element.title_level = title_fts.index(element.font)
                    except ValueError:
                        element.title_level = None
        return doc_path, doc_name, pages

    def _is_similar_text_font(self, ft, ft_ref):
        """ The actual comparison method between 2 text fonts, deciding if they
        are similar or not.

        Arguments:
            ft (Font): Font #1.
            ft_ref (Font): Font #2.

        Returns:
            bool: `True` if the 2 fonts are similar, `False` otherwise.
        """
        if type(ft) != type(ft_ref):
            return False
        if ft == ft_ref:        # For cases like TableFont
            return True
        # Here we supposedly have only Font objects
        must_match = ['size', 'bold', 'caps', 'underline', 'title_like']
        for at in must_match:
            if getattr(ft, at) != getattr(ft_ref, at):
                return False
        return True

    def _is_smaller_font(self, ft, ft_ref):
        """ Method checking if the given font is smaller than the reference.

        Arguments:
            ft (Font): Font #1.
            ft_ref (Font): Font #2.

        Returns:
            bool: `True` if Font #1 is smaller than Font #2.
        """
        if isinstance(ft, TableFont) or isinstance(ft_ref, TableFont):
            # TableFont don't have size
            return False

        return ft.size < ft_ref.size

    def _find_similar_text_font(self, fonts, text_font):
        """ Because fonts objects are very detailed, some fonts are considered
        different even though they are actually the same. This method just
        return a list of similar fonts to the given text font.

        Also, smaller font are never title, so they are always considered as
        text font.

        Arguments:
            fonts (list of Font): All existing fonts of the document.
            text_font (Font): The text font that we want to find similar fonts.

        Returns:
            list of Font: Similar fonts as `text_font`.
            list of Font: Remaining fonts.
        """
        similar_ft = []
        other_ft = []
        for ft in fonts:
            if self._is_similar_text_font(ft, text_font) or self._is_smaller_font(ft, text_font):
                similar_ft.append(ft)
            else:
                other_ft.append(ft)
        return similar_ft, other_ft

    def _get_next_font(self, page, idx):
        """ Method to iterate the page until an element with a valid Font is
        found, starting from element idx + 1.

        Arguments:
            page (pdfminer.LTPage): PDF page.
            idx (int): Index from where to start the search.

        Returns:
            int: Index of the element with the valid Font.
            Font: The next Font, or None if nothing could be found.
        """
        i = 0
        next_ft = None
        while idx + i + 1 < len(page) and next_ft is None:
            i += 1
            next_elem = get(page, idx + i)
            if hasattr(next_elem, 'font'):
                next_ft = next_elem.font
        return idx + i, next_ft

    def _has_text_between(self, page, idx, text_fonts):
        """ Method checking if there is text between the element and the next
        element that have the same Font.

        Arguments:
            page (pdfminer.LTPage): PDF page.
            idx (int): Index from where to start the search.

        Returns:
            bool: If there is text between the 2 element with same font or not.
        """
        curr_font = get(page, idx).font
        next_font = None
        i = idx
        while next_font != curr_font:
            i, next_font = self._get_next_font(page, i)
            if next_font is None or next_font in text_fonts:
                break
        return next_font in text_fonts

    def _find_next_title_font(self, pages, fonts, text_fonts):
        """ Identify title font from a list of possible fonts for title and a
        list of fonts for text, given the fonts of each components.

        It works by checking if the content coming after a possible title is
        formated as text. A title without content does not exist.
        If no font that is a title can be found, it means some text data is not
        considered as text. So find the font that have the least amount of valid
        as title and consider it as text.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.
            fonts (list of Font): Possible fonts for title.
            text_fonts (list of Font): Fonts for text.

        Returns:
            list of Font: Choosen font.
            list of Font: Remaining fonts.
            bool: If the choosen fonts should be considered as title or text.
        """
        encounter = Counter({ft: 0 for ft in fonts})
        valid_encounter = Counter({ft: 0 for ft in fonts})
        will_be_encounter = Counter({ft: 0 for ft in fonts})
        for page in pages:
            for e, elem in enumerate(page):
                # We are looking only at the title fonts
                if not hasattr(elem, 'font') or elem.font is None or elem.font in text_fonts:
                    continue

                # Retrieve the next font
                _, next_ft = self._get_next_font(page, e)

                # Check if it's a text font or another font
                if next_ft is not None:
                    encounter.update({elem.font: 1})
                    if next_ft in text_fonts:
                        # If it's a text font, then it's valid
                        valid_encounter.update({elem.font: 1})
                    else:
                        # Try to find text in the things between this title and
                        # the next one
                        if self._has_text_between(page, e, text_fonts):
                            will_be_encounter.update({elem.font: 1})

        # EDGE CASE : A font was never met
        # It's the case where a page end up with a font, and that font appear
        # only at that place. It might be the case of table for example.
        if encounter.most_common()[-1][-1] == 0:
            # In that case, consider it as text
            not_title_ft = [ft for ft, c in encounter.items() if c == 0]
            remaining = [ft for ft in fonts if ft not in not_title_ft]
            return not_title_ft, remaining, False

        # Get the next title font, if any is valid
        best_font_idx = self._get_valid_title_idx(encounter, valid_encounter, fonts)
        if best_font_idx is not None:       # Return it
            ft = fonts.pop(best_font_idx)
            return [ft], fonts, True

        # Here we didn't find any good title. Then it means some text have some
        # weird font and needs to be considered as text. Take the one with the
        # least amount of valid encounter, and the least amount of will_be
        _, min_count = valid_encounter.most_common()[-1]

        not_title_ft = [ft for ft, c in valid_encounter.items() if c == min_count]
        min_will_be = min(will_be_encounter[ft] for ft in not_title_ft)
        not_title_ft = [ft for ft in not_title_ft if will_be_encounter[ft] == min_will_be]

        remaining = [ft for ft in fonts if ft not in not_title_ft]
        return not_title_ft, remaining, False

    def _get_valid_title_idx(self, counter, valid_counter, fonts):
        """ Method to retrieve the index of the next title font, based on the
        number of occurence of that font and number of valid occurence.

        A font is considered as next title if it's valid everytime it's
        encountered.

        If there is a tie (2 fonts are both valid), we choose the one with the
        less occurences (more likely to be a smaller title).

        If no font is valid, `None` is returned.

        Arguments:
            counter (Counter): Counter of the number of occurence for each font.
            valid_counter (Counter): Counter of the number of valid occurence
                for each font.

        Returns:
            int: Index of the font choosen for the next title.
        """
        best_font_idx = None
        best_font_count = float("inf")
        for f, font in enumerate(fonts):
            assert counter[font] > 0 and counter[font] >= valid_counter[font]
            if counter[font] == valid_counter[font] < best_font_count:
                best_font_idx = f
                best_font_count = counter[font]
        return best_font_idx


class NormalizeTitleLevel(ConfigurableModificator):
    """ Node that finds any anomaly in the title levels, and fix it.

    Because Titles are found using a heuristic algorithm based on the font, it
    may detect 2 titles with same level as title with different level.

    So this node simply ensure that level of titles are consistent. If they are
    not, title level are modified.
    """

    def __call__(self, doc_path, doc_name, pages):
        """ If the title level does not correspond to the current nest level,
        then we have an inconsistency.

        Because fixing an inconsistency can lead to more inconsistencies, we
        need to loop several times to ensure all iconsistencies are fixed.

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

        while True:
            wrong_lvl, right_lvl = self._find_inconsistency(pages)

            if right_lvl is None:
                break       # Couldn't find any inconsistency

            pages = self._update_title_level(pages, wrong_lvl, right_lvl)

        return doc_path, doc_name, pages

    def _find_inconsistency(self, pages):
        """ Find the first inconsistency (first in term of title hierarchy)
        found in the pages.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            int: Current level of the inconsistent title. Can be `inf` if no
                inconsistency is found.
            int: Expected level of the inconsistent title. Can be `None` if no
                inconsistency is found.
        """
        nest_lvl = 0
        inc_lvl = float("inf")
        right_lvl = None
        for page in pages:
            for elem in page:
                # Treat only titles
                if hasattr(elem, 'title_level') and elem.title_level is not None:
                    if elem.title_level < inc_lvl and elem.title_level > nest_lvl:
                        # We should first return the biggest title, so keep
                        # track of the biggest title so far
                        inc_lvl = elem.title_level
                        right_lvl = nest_lvl
                    nest_lvl = elem.title_level + 1
        return inc_lvl, right_lvl       # No inconsistency found

    def _update_title_level(self, pages, current_lvl, expected_lvl):
        """ Change all the level of titles with the current level to the given
        expected level.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.
            current_lvl (int): Level of titles to modify.
            expected_lvl (int): The level titles should have.

        Returns:
            list of pdfminer.LTPage: Updated pages.
        """
        for page in pages:
            for elem in page:
                # Treat only titles
                if hasattr(elem, 'title_level') and elem.title_level == current_lvl:
                    elem.title_level = expected_lvl
        return pages
