from pdfminer.layout import LTTextContainer, LTPage
from bonobo.config import Option

from prospector.nodes.utils import ConfigurableModificator
from prospector.miner import merge_with_previous, LTParagraph, LTTable
import re


class Paragraphize(ConfigurableModificator):
    """ In some document, the format is weird and difficult for `pdfminer` to
    divide text into paragraph. This node tries to create better separation
    between paragraph, based on the text position.

    Attributes:
        ol_ratio (float, optional): One-liner ratio, which is the maximum ratio
            of paragraphs having a single line before considering that the
            document is wrongly separated by `pdfminer`.
        x1_ratio (float, optional): Ratio used to determine if an element
            reached the end of the line in a page. For example :

            |    Title                                                |
            |    Text starts here, and take the full width of page    |

            Here the title does not take the full width, but the text line does.
        apx_ratio (float, optional): Ratio used to check if 2 lines starts
            approximately at the same position.
    """

    ol_ratio = Option(float, default=0.9, required=False, __doc__="One-liner ratio")
    x1_ratio = Option(float, default=0.95, required=False, __doc__="Width ratio for elements")
    apx_ratio = Option(float, default=1.0, required=False, __doc__="Ratio for checking if the 2 lines starts approx "
                                                                   "at the same position")

    def __call__(self, doc_path, doc_name, pages):
        """ If most of the paragraph are a single line, it means the paragraph
        division sucks. So we apply this node to try to get better division
        between paragraphs.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages extracted from a PDF file, with
                better separation between paragraphs.
        """
        if self._one_liner_ratio(pages) < self.ol_ratio:
            return doc_path, doc_name, pages      # Ratio is fine, skip this node

        pages = self.cp(pages)
        max_x1 = self._get_max_x1(pages)
        for p, page in enumerate(pages):
            prev_elem = None
            to_merge = []
            for e, elem in enumerate(page):
                max_x1 = max(max_x1, elem.x1)
                if prev_elem is not None:
                    if isinstance(elem, LTTextContainer) and isinstance(prev_elem, LTTextContainer):
                        diff_x0 = abs(elem.x0 - prev_elem.x0)

                        # Case 0 :
                        # ---
                        # ---------
                        if not self._is_big_line(prev_elem, max_x1):
                            pass

                        # Case 1 :
                        #    -----------
                        # --------------
                        elif diff_x0 >= self.apx_ratio and elem.x0 - prev_elem.x0 < 0:
                            pass

                        # Case 2 :
                        # --------------   or    --------------
                        # --------------         ---------
                        elif diff_x0 <= self.apx_ratio and self._is_big_line(prev_elem, max_x1):
                            to_merge.append(e)

                        # Case 3 :
                        # --------------
                        #    -----------
                        elif diff_x0 >= self.apx_ratio and elem.x0 - prev_elem.x0 > 0 and self._is_big_line(prev_elem, max_x1):
                            to_merge.append(e)

                        else:
                            raise RuntimeError("Unknown case !\n{}\n{}".format(prev_elem.get_text().strip(),
                                                                               elem.get_text().strip()))

                prev_elem = elem

            page = merge_with_previous(page, to_merge)
        return doc_path, doc_name, pages

    def _one_liner_ratio(self, pages):
        """ Compute the ratio of 1-liner paragraphs in this document.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            float: Ratio of 1-liner paragraphs.
        """
        lines = [len(elem) for page in pages for elem in page if isinstance(elem, LTTextContainer)]
        return 0 if len(lines) == 0 else lines.count(1) / len(lines)

    def _get_max_x1(self, pages):
        """ Compute the maximum position of text on the right size of the page.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            float: Position of the most-right x1 coordinate for text.
        """
        x1 = [elem.x1 for page in pages for elem in page if isinstance(elem, LTTextContainer)]
        return max(x1)

    def _is_big_line(self, elem, max_x1):
        """ Method checking if an element is wide enough :
        * Starting from left part of the page
        * Stretching to at least X% of the width of the max x1page

        Arguments:
            elem (pdfminer.LTElement): Element to check.
            width (float): Page's width.

        Returns:
            bool: `True` if the element is considered big enough, `False`
                otherwise.
        """
        return elem.x0 < max_x1 / 2 and elem.x1 > max_x1 * self.x1_ratio


class BulletParagraph(ConfigurableModificator):
    """ Group bullets after : into one paragraph
    and change the paragraph strings to LTParagraph objects.

    Arguments:
        group ('bool', optional): Whether to group bullets after : or not.
            Defaults to `True`.
    """
    group = Option(bool, default=True, required=False, __doc__="Group bullets or not")

    def __call__(self, doc_path, doc_name, pages):
        """ If pages and doc_name is input, it makes a list of tuples in the
        format of (element, page number) and puts the list into _make_paragraph function,
        which will group the bullets and return the pages to return.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str) : Name of the file.
            pages (List of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            doc_path (str): Path of the file.
            doc_name (str) : Name of the file.
            pages (List of pdfminer.LTPage): pages after paragraphing bullet texts.

        """
        pages = self.cp(pages)
        if not self.group:
            return doc_path, doc_name, self._not_grouped_paragraph(pages)
        elem_list = []
        for p, page in enumerate(pages):
            for elem in page:
                elem_list.append((elem, p))

        new_pages = self._make_paragraph(elem_list, pages)

        return doc_path, doc_name, new_pages

    def _not_grouped_paragraph(self, pages):
        """ If the bullets after ':' shouldn't be grouped to a single paragraph, this
        function is called. For the paragraphs in string type, it is put into LTParagraph
        object and then into LTPage objects. If they are titles, tables etc, they are just
        put into LTPage objects.

        Arguments:
            pages (List of pdfminer.LTPage): Pages extracted from a PDF file.
        Returns:
            pages (List of pdfminer.LTPage): Pages that includes LTParagraphs, LTTables etc.
        """
        new_pages = [LTPage(pageid=p.pageid, bbox=p.bbox, rotate=p.rotate) for p in pages]
        for p, page in enumerate(pages):
            for elem in page:
                if type(elem) is str:
                    new_pages[p].add(LTParagraph(text=elem))
                else:
                    new_pages[p].add(elem)
        return new_pages

    def _make_paragraph(self, elem_list, pages):
        """ Make the elements to paragraphs. First check if the elements
        are str or not. If not, just add them to the paragraphs(pages).
        If it is, check if there is bullets to group, make paragraphs from
        it, and return LTPages.

        Arguments:
            elem_list (List) : List of tuples of elements and page nums.
            pages (List of pdfminer.LTPage) : LTPages from the previous node

        """

        paragraphs, strings, is_paragraphed = [], [], False
        for elem in elem_list:
            # If the element is not part of paragraph(tables, titles etc)
            if type(elem[0]) is not str:
                # If there were strings with type str right in front
                if strings:
                    # Check if there are bullets to group.
                    paragraphs.extend(self._bullet_paragraph(strings))
                    strings = []
                paragraphs.append(elem)
                is_paragraphed = False
            # If there was no : right in front of the paragraph
            elif not is_paragraphed:
                if strings:
                    paragraphs.extend(self._bullet_paragraph(strings))
                    strings = []
                # Start a new list of paragraphs
                strings.append(elem)
                is_paragraphed = True
            else:
                strings.append(elem)
        # For the leftover paragraphs with bullets
        if strings:
            paragraphs.extend(self._bullet_paragraph(strings))
        # Reformat it to LTPages with LTParagraphs
        new_pages = self._paragraphs_to_pages(paragraphs, pages)

        return new_pages

    def _bullet_paragraph(self, strings):
        """ When it gets strings that includes bullets and text without bullets,
        if first determines if it includes bullets. If it does, group them together.
        After this, it returns the list of tuples to return.

        Arguments:
            strings (List of strings) : List of strings(paragraphs).

        Returns:
            paragraphs_list (List of tuples) : List of tuples in the form of (text, page num).
        """

        is_bullet, paragraphs, temp_paragraph, pattern, patterns = False, [], [], '', []
        # Get rid of null string from the input list of strings
        strings = self._list_preprocess(strings)

        for n, string in enumerate(strings):
            # If the last letter of the string is : and at least one string is at the back,
            # check if its first word bullet pattern is different from the next string bullet pattern.
            # If all of these are satisfied, regard them as bullets to group.
            if string[0][-1] == ':' and n < len(strings) - 1:
                pattern = self._pattern_str(strings[n + 1][0])
                if self._pattern_str(string[0]) != pattern and pattern != '':
                    temp_paragraph.append(string)
                    patterns.append(re.compile(pattern))
                    patterns = list(set(patterns))
                    is_bullet = True
                elif temp_paragraph:
                    temp_paragraph.append(string)
                    patterns.append(re.compile(pattern))
                    patterns = list(set(patterns))
                else:
                    paragraphs.append(string)

            # If there was : in front, check if the string also satisfies the bullet pattern.
            # If it does satisfy, add it to the group and if not, make it a separate paragraph.
            elif is_bullet:
                is_matched = False
                for re_com in patterns:
                    if re_com.match(string[0]) is not None:
                        temp_paragraph.append(string)
                        is_matched = True
                if not is_matched:
                    paragraphs.append(temp_paragraph)
                    temp_paragraph = []
                    paragraphs.append(string)
                    is_bullet, patterns = False, []
            else:
                paragraphs.append(string)
        # If there was : in front and there is a group of bullets, add them to paragraphs
        if is_bullet and temp_paragraph:
            paragraphs.append(temp_paragraph)

        # Bind the paragraphs
        return self._paragraphs_to_lists(paragraphs)

    def _list_preprocess(self, lines):
        """ Get rid of empty strings in the input list

        Arguments:
            lines (List of string)

        Returns:
            List of string without empty ones.

        """
        new_lines = []
        for line in lines:
            if line[0].strip() != '':
                new_lines.append((line[0].strip(), line[1]))
        return new_lines

    def _pattern_str(self, line):
        """ Find the pattern of bullets in a paragraph. If there are no bullets,
        return ''. If it has bullets, return regular expressions of the bullets.

        Arguments:
            line (str) : A paragraph to find patterns of bullets.

        Returns:
            string of regular expression of bullet pattern.
        """

        if line.strip() == '':
            return ''
        f_token = line.strip().split()[0]
        if f_token[0] in ['(', '[', '{'] and f_token[1:].isalnum():
            return ''
        first_token = line.strip().split()[0]
        is_bullet_pattern = False

        # Make a regular expression of the bullet
        pattern_list, is_bullet_pattern = self._str_regex(first_token, is_bullet_pattern)

        if is_bullet_pattern:
            return ''.join(pattern_list).strip()

        # Regard string without punctuations as string without bullets and return ''
        else:
            return ''

    def _str_regex(self, first_token, is_bullet_pattern):
        """ Return regex pattern strings from the input word. Also
        return whether it is a bullet or not - not a bullet if the
        word contains no punctuations.

        Arguments:
            first_token (str) : Word to get the pattern of regex.
            is_bullet_pattern (bool) : whether it is a bullet or not.

        Returns:
            pattern_list (list of str) : List of strings of regex of each word.
            is_bullet_pattern (bool) : whether it is a bullet or not.
        """
        pattern_list = []
        for char in first_token:
            if not char.isalnum():
                for c in ['\'', '\"', '\\']:
                    if c == char:
                        char = '\\' + c
                pattern_list.append('[' + char + ']')
                is_bullet_pattern = True
            elif char.isalnum():
                if len(pattern_list) == 0 or pattern_list[-1] != '[a-zA-Z0-9가-힣ㅏ-ㅣㄱ-ㅎ\u4e00-\u9fff]+':
                    pattern_list.append('[a-zA-Z0-9가-힣ㅏ-ㅣㄱ-ㅎ\u4e00-\u9fff]+')
        return pattern_list, is_bullet_pattern

    def _paragraphs_to_lists(self, paragraphs):
        """ If it gets the list of paragraphs including lists of paragraphs with bullets and
        the paragraphs without bullets, it returns the paragraph list which only contains
        tuples of text and page numbers.

        Arguments:
            paragraphs (List of lists and str) : List of lists of paragraphs with bullets and
                strings that are not part of the bullet groups.

        Returns:
            paragraphs_list (List of tuples) : List of tuples in the form of (text, page num).

        """

        paragraphs_list = []
        for paragraph in paragraphs:
            # If it is not in the group of bullets
            if type(paragraph[0]) is str:
                paragraphs_list.append(paragraph)
            # If it is a list of elements in the group of bullets
            else:
                str_bullet = ''
                for line in paragraph:
                    str_bullet += '\n' + line[0]
                paragraphs_list.append((str_bullet.strip(), paragraph[0][1]))

        return paragraphs_list

    def _paragraphs_to_pages(self, paragraphs, pages):
        """ Make list of paragraphs to LTPages with LTParagraphs.
        If the element's type is str, add them to LTParagraphs and put them into LTPages.
        If its type is not str, just add them to LTPages.

        Arguments:
            paragraphs (List of elements) : List of LTTables, titles, string of paragraphs etc
            pages (List of pdfminer.LTPage) : LTPages from the previous node

        Returns:
            LTPages that include LTTables, titles, LTParagraphs etc.
        """

        new_pages = [LTPage(pageid=p.pageid, bbox=p.bbox, rotate=p.rotate) for p in pages]
        for paragraph in paragraphs:
            if type(paragraph[0]) is str:
                new_pages[paragraph[1]].add(LTParagraph(text=paragraph[0]))
            else:
                new_pages[paragraph[1]].add(paragraph[0])
        return new_pages


class TextParagraphize(ConfigurableModificator):
    """ Get plain text without bullets in front of them,
    divide them by paragraphs and return them in string forms.
    They will be returned as LTParagraph objects in the next node
    of BulletParagraphize class.
    """

    def __call__(self, doc_path, doc_name, pages):
        """ If the pages are given, get the tables, titles and text from
        it. If tables or title objects are detected, just put them in the
        page objects to return. If not, divide them by paragraphs and return
        them by str forms. If a single paragraph is divided by seperate pages,
        combine them together as one paragraph that belongs to the previous paragraph.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str) : Name of the file.
            pages (List of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            doc_path (str): Path of the file.
            doc_name (str) : Name of the file.
            pages (List of pdfminer.LTPage) : pages after paragraphing pure texts.
        """
        pages = self.cp(pages)
        new_pages = [LTPage(pageid=p.pageid, bbox=p.bbox, rotate=p.rotate) for p in pages]
        succession_paragraphs = []
        for p, page in enumerate(pages):
            for e, elem in enumerate(page):
                if hasattr(elem, 'title_level') and elem.title_level is not None or \
                        type(elem) is LTTable:
                    # Paragraph separators : Titles or Tables
                    paragraphs_made = self._make_pdfminer_paragraph(succession_paragraphs)
                    for par in paragraphs_made:
                        new_pages[par[1]].add(par[0])

                    succession_paragraphs = []
                    new_pages[p].add(elem)  # Add the separator to the pages
                    continue

                if isinstance(elem, LTTextContainer):  # Text
                    succession_paragraphs.append((elem, p))

        # End of page, we might have some paragraphs not added yet
        paragraphs_made = self._make_pdfminer_paragraph(succession_paragraphs)
        for par in paragraphs_made:
            new_pages[par[1]].add(par[0])

        return doc_path, doc_name, new_pages

    def _make_pdfminer_paragraph(self, paragraphs):
        """ Reform the paragraphs. From a list of text elements divided by
        `pdfminer`, we reform appropriate paragraphs. Then
        we return a list of custom objects, mimicking `pdfminer` object.

        Arguments:
            paragraphs (list of pdfminer.LTTextContainer): Text elements to be
                reformed into paragraphs.

        Returns:
            list of tuples of paragraphs and page nums.
        """
        if len(paragraphs) == 0:
            return []
        # Create the whole text
        text = "\n".join([p[0].get_text() for p in paragraphs])

        paragraphs = [(paragraph[0].get_text(), paragraph[1]) for paragraph in paragraphs]
        # Apply logic to make paragraphs
        p_tuples = self._make_paragraph(text, paragraphs)
        tuples = []
        for p in p_tuples:
            if type(p) is tuple:
                tuples.append(p)
            else:
                tup_string = ''
                p_num = 0
                for n, tup in enumerate(p):
                    if n == 0:
                        p_num = tup[1]
                    tup_string += tup[0].strip() + ' '
                tuples.append((tup_string.strip(), p_num))
        return p_tuples

    def _make_paragraph(self, input_str, paragraphs):
        """ Split given text to paragraphs

        The function gets the text between subtitles or subtitles,
        split the text to paragraphs, and returns it by list forms.

        It first divides the text by empty lines, but this sometimes are
        not accurate as single sentences can also divided by empty lines.
        In that case, we use punctuations such as '.', '(', ':' etc to check
        if the lines belong to the previous paragraph or is a new paragraph.

        Arguments:
            input_str (str) : String to be divided to paragraphs

        Returns:
            List of paragraph strings : List of tuples of text and page nums.
        """

        # split text by empty lines
        text_ls = input_str.split('\n\n')
        p_num, tuple_list = -1, []
        for text in text_ls:
            is_finished = False
            for p in paragraphs:
                if text.strip() in p[0] and p[1] >= p_num and text.strip() != '' \
                        and not is_finished:
                    if p[1] > p_num:
                        p_num = p[1]
                    tuple_list.append((text, p_num))
                    is_finished = True
        tuples = self._check_bullet(tuple_list)
        return_ls = []
        for tup in tuples:
            if type(tup) is tuple:
                return_ls.append((tup[0].replace('\n', ' ').strip(), tup[1]))
            else:
                return_ls.extend(self._plain_text_to_paragraph(tup))
        return return_ls

    def _plain_text_to_paragraph(self, text_ls):
        """ Get a list of text, divide them by paragraphs using
        punctuations and return a list of paragraphs.

        Arguments:
            text_ls (list): List of texts without bullets.

        Returns:
            List of tuples of text and page nums.

        """
        result_ls, is_end, is_bracketed = [], True, False
        text_ls = self._remove_blank_in_list(text_ls)
        for num, text in enumerate(text_ls):
            try:
                if self._is_included(text[0], [')', ']', '}']) and is_bracketed:
                    is_bracketed = False

                # check if '(' or '[' is stated without ')' or ']'
                if self._is_included(text[0], ['(', '[', '{']) and not self._is_included(text[0], [')', ']', '}']):
                    is_bracketed = True
                    is_end, result_ls = self._not_last_line_text(is_end, result_ls, text)

                # check if the sentence ended without period or with , or ;
                elif text[0][-1] in [',', ';'] or text[0][-1].isalpha():
                    is_end, result_ls = self._not_last_line_text(is_end, result_ls, text)

                # check if the line ended with '.!?' without bracket issues before
                elif text[0][-1] in ['.', '!', '?', ':', ')', ']', '}'] and not is_bracketed:
                    is_end, result_ls = self._last_line_text(is_end, result_ls, text)

                else:  # Not matching any case before
                    result_ls.append([text])
                    is_end = False
            # in error cases, print the text
            except IndexError:
                is_end, result_ls = self._last_line_text(is_end, result_ls, text)

        # change list of sentences in a paragraph to single string
        return self._paragraph_to_line(result_ls)

    def _check_bullet(self, text_ls):
        """ Check if the texts in the input list contains
        bullets or not. If it does, just put them in the
        return list. If it does not, add them to list to
        put into paragraphing functions.

        Arguments:
            text_ls (List): List of texts

        Returns:
            texts (List): List of bullets and paragraphs

        """

        plain_tuples, tuples = [], []
        for num, tup in enumerate(text_ls):
            if self._is_pattern(tup[0]):
                if plain_tuples:
                    tuples.extend([plain_tuples, tup])
                    plain_tuples = []
                else:
                    tuples.append(tup)
            else:
                plain_tuples.append(tup)
        if plain_tuples:
            tuples.append(plain_tuples)
        return tuples

    def _is_included(self, line, punc):
        """ Check if a list of punctuations are in a line

        Arguments:
            line (str) : string to check if punctuations are in there
            punc (list) : list of punctuations

        Returns:
            boolean of whether it includes punctuations or not
        """
        for letter in punc:
            if letter in line:
                return True
        return False

    def _is_pattern(self, line):
        """ Check if the line is a bullet or not.

        This is done by checking if the first word in a string is
        in any form of bullets, such as '*', '-', '1.2.1' etc.

        It checks if the first word is in bullet forms by checking if
        it includes punctuations inside, and if it does, returns a
        regular expression of bullets. But if not, returns empty string.

        Arguments:
            line (str) : line that might include bullets

        Returns:
            boolean of whether pattern is found or not
        """

        # If line is null or no punctuations in it, return False
        if line.strip() == '':
            return False

        word = line.strip().split()[0]
        # If the first word does not contain punctuations
        if word.isalnum():
            return False
        # If (, ) etc is included
        if len(word) > 1:
            if word[0] in ['(', '[', '{'] and word[1:].isalnum() or word.strip() == line.strip() and \
                    word[0] in ['(', '[', '{'] and word[-1] in [')', ']', '}'] and word[1:-1].isalnum() or \
                    word.strip() == line.strip() and word[-1] in [')', ']', '}'] and word[:-1].isalnum() or \
                    word.strip() == line.strip() and word[-1] in [')', ']', '}'] and word[-2] in ['.', '!', '?'] and \
                    word[1:-2].isalnum():
                return False
        # If a line with one word ends with .
        if len(word) > 1 and word.strip() == line.strip():
            if word.strip()[-1] == '.' and word[:-1].isalnum():
                return False
        # In other cases, return True
        return True

    def _paragraph_to_line(self, input_list):
        """ Makes a paragraph to a single string.
        A list that includes several lists that includes many strings which
        are originally in a single paragraph is given as a parameter.

        This function integrates strings of a single paragraph to a single
        string, and gets rid of '\n' in the string, and finally returns a
        list that includes strings which each of them is a single paragraph.

        Arguments:
            input_list (List) : list of lists of strings that are in a single paragraph

        Returns:
            list of paragraphs : list of strings which each string is a single paragraph
        """

        return_list = []
        for paragraph in input_list:
            lines = []
            p_num = 0
            # delete '\n' in lines and add the strings of a single paragraph to a single string,
            # and return the list of paragraphs
            for n, tup in enumerate(paragraph):
                lines.extend(tup[0].splitlines())
                if n == 0:
                    p_num = tup[1]
            lines = [' '.join(line.split()).strip() for line in lines]
            return_list.append((' '.join(lines).strip(), p_num))
        return return_list

    def _remove_blank_in_list(self, input_list):
        """ Remove blank string in a list of strings

        Arguments:
            input_list (list) : list of strings

        Returns:
            list of strings : strings without blank

        """
        return [(s[0].strip(), s[1]) for s in input_list if s[0].strip() != ""]

    def _not_last_line_text(self, is_end, result_ls, text):
        """ If the given text is not the last part of a
        paragraph, if there is another text in the same
        paragraph in front, add the text to the previous
        paragraph. If not, create a new one.

        Arguments:
            is_end (bool) : check if this is the last text in
            the paragraph
            result_ls (list) : list of the paragraphs
            text (string) : text to add to the paragraph
        Returns:
            is_end (bool) : check if this is the last text in
            the paragraph
            result_ls (list) : list of the paragraphs
        """

        if is_end:
            result_ls.append([text])
            is_end = False
        else:
            result_ls[-1].append(text)
        return is_end, result_ls

    def _last_letter_terminating_ending(self, is_end, result_ls, text):
        """ Check if the given text ends with terminating
        ending punctuations. If the last letter is one of '.!?]})',
        think that the text is the last part of the paragraph

        Arguments:
            is_end (bool) : check if this is the last text in
            the paragraph
            result_ls (list) : list of the paragraphs
            text (string) : text to add to the paragraph
        Returns:
            is_end (bool) : check if this is the last text in
            the paragraph
            result_ls (list) : list of the paragraphs
        """
        if text[-1] in ['.', '!', '?', ':', ')', ']', '}']:
            result_ls[-1].append(text)
            is_end = True
        else:
            result_ls[-1].append(text)
        return is_end, result_ls

    def _last_line_text(self, is_end, result_ls, text):
        """ if the text is the last part of the paragraph,
        end the paragraph.

        Arguments:
            is_end (bool) : check if this is the last text in
            the paragraph
            result_ls (list) : list of the paragraphs
            text (string) : text to add to the paragraph
        Returns:
            is_end (bool) : check if this is the last text in
            the paragraph
            result_ls (list) : list of the paragraphs

        """

        if is_end:
            result_ls.append([text])
        else:
            result_ls[-1].append(text)
            is_end = True
        return is_end, result_ls
