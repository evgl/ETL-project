import math

import camelot
from bonobo.config import Option
from pdfminer.layout import LTRect, LTLine, LTTextContainer

from prospector.miner import LTTable, rm, get, append, insert, update_bbox, update_pos
from prospector.nodes.utils import ConfigurableModificator


class CleanTables(ConfigurableModificator):
    """ Node that find tables in the PDF, remove all the content within the
    table, and replace it with a Custom object.

    Attributes:
        pre_detect (bool, optional): Wether to use `pdfminer` object to
            pre-detect tables, in order to run `camelot` only on specific
            pages. Setting this to `True` will make the code faster, but there
            might be discrepancies between what we detect and what `camelot`
            detects. Defaults to `True`.
        camelot (bool, optional): Wether to annotate tables content with
            Camelot or not. In some case Camelot does not detect tables (for
            example headers), so we might want to skip it. Also Camelot is very
            slow. Defaults to `True`.
        margin (float, optional): Sometimes PDFMiner detect lines as
            LTRect. In this case, we should be able to detect if it's a line.
            It's a line if the width or height of the element is not bigger
            than this margin. Used only if `pre_detect` is set to `True`.
            Defaults to `1`.
        line_scale (int, optional): Camelot's option. Refer to
            https://camelot-py.readthedocs.io/en/master/user/advanced.html#detect-short-lines
            and https://camelot-py.readthedocs.io/en/master/api.html#main-interface.
            The default for Camelot is `15`, but here we use a bit bigger scale
            to detect small tables. Defaults to `45`.
    """

    pre_detect = Option(bool, default=True, required=False, __doc__="Whether to pre-detect tables using pdfminer object.")
    camelot = Option(bool, default=True, required=False, __doc__="Whether to use Camelot to annotate tables or not.")
    margin = Option(float, default=1, required=False, __doc__="Width for considering LTRect as a line.")
    line_scale = Option(int, default=45, required=False, __doc__="Line scale option for camelot.")

    def __call__(self, doc_path, doc_name, pages):
        """ Find tables within pages and delete it, replacing it with custom
        object.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages with clean table object.
        """
        pages = self.cp(pages)

        if self.pre_detect:
            tables = self._find_tables(pages)
        else:
            tables = [[] for _ in pages]

        if self.camelot and not self.pre_detect:
            # We didn't pre-detect tables => run camelot on the whole file
            camelot_tables = camelot.read_pdf(doc_path, pages="1-end",
                                              suppress_stdout=True,
                                              line_scale=self.line_scale)
            for ct in camelot_tables:
                tab = LTTable()
                x0, y0, x1, y1 = ct._bbox
                tab.set_bbox((math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)))
                tab.camelot_table = ct
                tables[ct.page - 1].append(tab)
        elif self.camelot and self.pre_detect:
            # Parse tables with camelot and assign it to the right table
            for p, tab in enumerate(tables):
                if len(tab) == 0:
                    continue        # Skip pages without tables

                # Reorder table following position on the page
                tab = sorted(tab, key=lambda t: -t.y0)
                tab_areas = ["{},{},{},{}".format(math.floor(t.x0), math.ceil(t.y1),
                                                  math.ceil(t.x1), math.floor(t.y0))
                             for t in tab]

                camelot_tables = camelot.read_pdf(doc_path,
                                                  pages="{}".format(p + 1),
                                                  suppress_stdout=True,
                                                  line_scale=self.line_scale,
                                                  table_areas=tab_areas)

                self._assign_camelot_tables(tab, camelot_tables)

        pages = self._replace_tables_content(pages, tables)

        return doc_path, doc_name, pages

    def _find_tables(self, pages):
        """ For each page, find the perimeter of tables if there is any.

        We find the table perimeter by extracting all lines in the table, and
        if a horizontal and vertical line cross, then it's likely a table.
        Then we gather all overlapping lines and consider the box englobing all
        these lines as the perimeter of the table.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            list of list of LTTable: For each page, return a list of table
                object which contain the perimeter of the table.
        """
        tables = []
        # First, find all lines and put it in 2 lists : Horizontal and Vertical
        for p, page in enumerate(pages):
            h = set()
            v = set()
            for elem in page:
                if isinstance(elem, LTRect) or isinstance(elem, LTLine):
                    if elem.width <= self.margin and elem.height <= self.margin:
                        # WTF ? Is it a dot ?
                        continue
                    elif elem.width <= self.margin:
                        v.add(elem)
                    elif elem.height <= self.margin:
                        h.add(elem)

            tables_lines = []
            while len(h) > 0 and len(v) > 0:        # Not empty, we can still have crossing lines !
                # Find crossing lines
                line = h.pop()
                crossing_lines = self._find_crossing(line, v, h)

                if len(crossing_lines) != 0:
                    # Update h and v to remove crossing lines
                    h = h - crossing_lines
                    v = v - crossing_lines

                    crossing_lines.add(line)

                    # Add crossing lines as an entry of tables
                    tables_lines.append(crossing_lines)

            # Create an object that englobe all lines in each table
            tables.append(self._convert_to_lttable(tables_lines))
        return tables

    def _convert_to_lttable(self, tables_lines):
        """ Method to convert a list of lines (`pdfminer.LTRect` or
        `pdfminer.LTLine`) into a custom object `LTTable`. This way we can
        later access the bounding box of the table easily.

        Arguments:
            tables_lines (list of list of pdfminer.LTCurve): Several tables
                where each table is a list of pdfminer.LTCurve, to convert to
                custom object.

        Returns:
            list of LTTable: Converted tables.
        """
        tables_obj = []
        for table_lines in tables_lines:
            t = LTTable()
            for tline in table_lines:
                t.add(tline)
            tables_obj.append(t)
        return tables_obj

    def _is_approx_overlap(self, l1, l2):
        """ Method to find if 2 lines are overlapping, with some margin error.

        Arguments:
            l1 (pdfminer.LTCurve): Line 1 to compare.
            l2 (pdfminer.LTCurve): Line 2 to compare.

        Returns:
            bool: `True` if overlapping, `False` otherwise.
        """
        hoverlap = l1.x0 - self.margin <= l2.x1 and l1.x1 + self.margin >= l2.x0
        voverlap = l1.y0 - self.margin <= l2.y1 and l1.y1 + self.margin >= l2.y0
        return hoverlap and voverlap

    def _is_touching(self, l1, l2):
        """ Method to find if 2 lines are touching. No margin error applied.
        Just check if the ends of the 2 lines are touching.

        Arguments:
            l1 (pdfminer.LTCurve): Line 1 to compare.
            l2 (pdfminer.LTCurve): Line 2 to compare.

        Returns:
            bool: `True` if touching, `False` otherwise.
        """
        if l1.x0 == l2.x0 and l1.x1 == l2.x1:       # Same horizontal position
            return l1.y1 == l2.y0 or l2.y1 == l1.y0
        elif l1.y0 == l2.y0 and l1.y1 == l2.y1:     # Same vertical position
            return l1.x1 == l2.x0 or l2.x1 == l1.x0
        else:           # Not even on the same horizontal/vertical position
            return False

    def _find_crossing(self, line, v, h):
        """ Method to find all lines crossing a given line. It first search all
        directly crossing lines, and for all these lines, search for all
        indirectly matching lines.
        It also search for touching lines if we found some crossing lines.

        Note : this function is recursive. For each crossing line, we find the
        subsequent crossing lines by calling this function again.

        Arguments:
            line (pdfminer.LTCurve): Reference line. Assume this line is
                horizontal.
            v (list of pdfminer.LTCurve): List of lines. Assume these lines are
                vertical.
            h (list of pdfminer.LTCurve): List of lines. Assume these lines are
                horizontal.

        Returns:
            list of pdfminer.LTCurve: List of lines crossing directly or
                indirectly the given line.
        """
        crossing_lines = set()
        direct_crossing_lines = set()

        # First, find the directly crossing lines
        for vline in v:
            if self._is_approx_overlap(line, vline):
                direct_crossing_lines.add(vline)

        # Update v to have only not crossed lines
        v = v - direct_crossing_lines

        # Add crossed lines to our total
        crossing_lines = crossing_lines.union(direct_crossing_lines)

        # Then apply recursion and find the indirect crossing line for each direct crossing line
        for dline in direct_crossing_lines:
            indirect_crossing_lines = self._find_crossing(dline, h, v)

            # Update to have only not crossed lines
            h = h - indirect_crossing_lines
            v = v - indirect_crossing_lines

            # Add crossed lines to our total
            crossing_lines = crossing_lines.union(indirect_crossing_lines)

        # ---------------------------------------------------------------------
        # In some case, a single line is represented by 2 touching lines.
        # So, similarly, we detect these + find recursively the touching lines
        touching_lines = set()

        # First, find the directly touching lines
        for hline in h:
            if self._is_touching(line, hline):
                touching_lines.add(hline)

        # Update h to have only not touching lines
        h = h - touching_lines

        # Then apply recursion and find the indirect crossing line for each touching line
        indirect_touching_lines = set()
        for tline in touching_lines:
            indirect_crossing_lines = self._find_crossing(tline, v, h)

            # Update to have only not crossed lines
            h = h - indirect_crossing_lines
            v = v - indirect_crossing_lines

            # Add crossed lines to our total
            indirect_touching_lines = indirect_touching_lines.union(indirect_crossing_lines)

        if len(indirect_touching_lines) != 0:
            # Add to the total only if we found some crossing lines after touching lines
            crossing_lines = crossing_lines.union(touching_lines)
            crossing_lines = crossing_lines.union(indirect_touching_lines)

        return crossing_lines

    def _assign_camelot_tables(self, tables, camelot_tables):
        """ Given a list of tables and a list of detected tables by camelot,
        assign each camelot table to the right table object.

        Arguments:
            tables (list of LTTable): Pre-detected tables.
            camelot_tables (camelot.TableList): Tables detected by camelot.
        """
        assert len(camelot_tables) <= len(tables)
        for ct in camelot_tables:
            best_dist = float('inf')
            best_idx = None
            for t, tab in enumerate(tables):
                if tab.camelot_table is not None:
                    continue

                dist = self._table_dist(tab, ct)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = t

            tables[best_idx].camelot_table = ct

    def _table_dist(self, t, ct):
        """ Compute the distance between 2 tables (one pre-detected table and
        one camelot table), based on coordinates.

        Arguments:
            t (LTTable): Pre-detected table.
            ct (camelot.Table): Table detected by camelot.

        Returns:
            float: Distance between the 2 tables.
        """
        return sum(abs(c1 - c2) for c1, c2 in zip(t.bbox, ct._bbox))

    def _replace_tables_content(self, pages, tables):
        """ Method that puts all elements of a table inside the Table object,
        and place the table in the page.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.
            tables_perimeter (list of list of LTTable): For each page, list of
                table object, containing its perimeter.

        Returns:
            list of pdfminer.LTPage: Pages cleaned with tables object.
        """
        assert len(pages) == len(tables)
        for page, ptables in zip(pages, tables):
            if len(page) == 0:
                continue    # Skip empty page, we don't want to add table there
            for table in ptables:
                rm(page, to_rm=lambda x: (x.x0 >= table.x0 and x.x1 <= table.x1 and
                                          x.y0 >= table.y0 and x.y1 <= table.y1))

                # Some text element are half into the table, half not in the table
                # So delete the lines that are in the table
                for e, elem in enumerate(page):
                    to_update = []
                    if isinstance(elem, LTTextContainer):
                        to_rm = [i for i, line in enumerate(elem)
                                 if line.x0 >= table.x0 and line.x1 <= table.x1 and
                                 line.y0 >= table.y0 and line.y1 <= table.y1]
                        if to_rm != []:
                            rm(elem, to_rm)
                            update_bbox(elem)
                            to_update.append(e)
                    update_pos(page, to_update)

                # Find the index where to insert the table
                idx = None
                for e, elem in enumerate(page):
                    if elem.y0 < table.y0:
                        idx = e
                        break
                if idx is None:
                    append(page, table)
                else:
                    insert(page, table, idx)
        return pages


class MergeSuccessiveTables(ConfigurableModificator):
    """ Node that merge successive tables, if they were cut by a new page.

    We check if the tables are successive, if their position match and if their
    number of columns match.

    Attributes:
        margin (float, optional): When checking the position of tables, the
            maximum difference of positions is given by this margin. Defaults
            to `1`.
    """

    margin = Option(float, default=1, required=False, __doc__="Maximum position difference.")

    def __call__(self, doc_path, doc_name, pages):
        """ Merge successive tables if they are separated by a new page.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages with merged table object.
        """
        pages = self.cp(pages)

        start_table = None
        prev = None
        to_rm = []

        # Merge tables
        for p, page in enumerate(pages):
            curr = get(page, 0) if len(page) > 0 else None
            if isinstance(prev, LTTable) and isinstance(curr, LTTable) and \
                    abs(prev.x0 - curr.x0) <= self.margin and \
                    abs(prev.x1 - curr.x1) <= self.margin and \
                    prev.camelot_table is not None and curr.camelot_table is not None and \
                    len(prev.camelot_table.df.columns) == len(curr.camelot_table.df.columns):
                # The 2 tables are indeed from the same table
                if start_table is None:     # Keep in memory the first table
                    start_table = prev

                start_table.merge(curr)
                to_rm.append(p)
            else:
                start_table = None

            prev = get(page, -1) if len(page) > 0 else None    # For next loop

        # Delete merged tables
        for i in sorted(to_rm, reverse=True):
            rm(pages[i], to_rm=[0])

        return doc_path, doc_name, pages
