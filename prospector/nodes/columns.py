from bonobo.config import Option

from pdfminer.layout import LTTextContainer

from prospector.nodes.utils import ConfigurableModificator
from prospector.utils import is_same_bbox
from prospector.miner import rm, merge_lines, get, update_bbox


class ConfigurableMiddle(ConfigurableModificator):
    """ A Configurable with an option for detecting the middle of the page.

    We can't just separate the page in the exact middle, because some page are
    scanned and therefore might not be perfectly aligned with the page layout.

    So instead, we consider some margin, relative to the page width.

    Attributes:
        middle_margin (float): The margin ratio relative to the page width.
    """

    middle_margin = Option(float, default=0.05, required=False, __doc__="Middle margin from exact middle.")

    def assign_area(self, page, width=None):
        """ Method that assign each elements of a page into a specific area of
        the page : left column, right column, or common (taking the whole
        width). Based on the coordinates of each element.

        Arguments:
            page (pdfminer.LTPage): Elements (in the form of a page, or a list)
                to assign.
            width (float, optional): Width of the page. If `None`, use the page
                width. Defaults to `None`.

        Returns:
            list: Elements belonging to the left part of the page.
            list: Elements belonging to the right part of the page.
            list: Elements belonging to the common part of the page.
        """
        left, right, common = [], [], []

        w = width if width is not None else page.width
        middle = w / 2
        middle_up = middle + w * self.middle_margin
        middle_low = middle - w * self.middle_margin

        for elem in page:
            if elem.x0 < middle_low and elem.x1 <= middle_up:
                left.append(elem)
            elif elem.x0 >= middle_low and elem.x1 > middle_up:
                right.append(elem)
            else:
                common.append(elem)

        return left, right, common


class Linify(ConfigurableMiddle):
    """ Node gathering text lines together. Some document may have different
    columns of text : lines are not gathered. But in other cases, 2 text lines
    being at the same height should be gathered into a single line.

    Attributes:
        abs_tol (float): Absolute tolerance to use when comparing the position
            of 2 lines.
        min_space (float): Minimum spacing between 2 lines to be considered as
            different columns.
    """

    abs_tol = Option(float, default=1, required=False, __doc__="Tolerance for comparing line position.")
    min_space = Option(float, default=13.5, required=False, __doc__="Minimum spacing between columns.")

    def __call__(self, doc_path, doc_name, pages):
        """ Gather lines that should be together. Lines should be gathered if
        they appear at the same height and the `hole` is not in the middle of
        the page.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages extracted from a PDF file, with
                reordered content.
        """
        pages = self.cp(pages)

        for p, page in enumerate(pages):
            idx_to_merge = self._find_lines_idx_to_merge(page)

            # Order by x-coordinate
            def x_coord(idx): return get(get(page, idx[0]), idx[1]).x0
            idx_to_merge = [sorted(list(g), key=x_coord) for g in idx_to_merge]

            # Merge everything in the first line. Merged lines are saved to be removed
            by_page_rm = {}
            for group in idx_to_merge:
                assert len(group) > 1

                idx_l1 = group[0]
                l1 = get(get(page, idx_l1[0]), idx_l1[1])

                for idx_l2 in group[1:]:
                    l2 = get(get(page, idx_l2[0]), idx_l2[1])

                    merge_lines(l1, l2)

                    if idx_l2[0] not in by_page_rm:
                        by_page_rm[idx_l2[0]] = []
                    by_page_rm[idx_l2[0]].append(idx_l2[1])

            # Remove merged lines
            for e, lines_idx in by_page_rm.items():
                rm(get(page, e), lines_idx)

            # Update the bbox of every updated elements
            for e in set([idxs[0] for grp in idx_to_merge for idxs in grp]):
                update_bbox(get(page, e))

            # Ensure all text elements are not empty
            rm(page, to_rm=lambda x: isinstance(x, LTTextContainer) and len(x) == 0)

        return doc_path, doc_name, pages

    def _find_lines_idx_to_merge(self, page):
        """ Method finding all lines that are at the same height and should be
        merged together.

        Arguments:
            page (LTPage): PDF page containing all elements.

        Returns:
            list of set: List of groups that should be merged, where each group
                is a set of tuple (element idx, line idx), describing lines
                that should be merged together.
        """
        groups = []
        # First, iterate each line of the page
        for e1, elem1 in enumerate(page):
            if not isinstance(elem1, LTTextContainer):
                continue

            for i1, l1 in enumerate(elem1):
                other_lines = self._find_same_lines(page, l1)

                if len(other_lines) == 0:
                    continue

                # Get existing group or create a new one
                group_id = self._index_in(groups, (e1, i1))
                if group_id is None:
                    group_id = len(groups)
                    groups.append(set([(e1, i1)]))

                for line in other_lines:
                    group_id_2 = self._index_in(groups, line)

                    if group_id_2 == group_id:
                        pass
                    elif group_id_2 is not None:
                        grp = groups.pop(group_id_2)
                        if group_id > group_id_2:
                            group_id = group_id - 1
                        groups[group_id].update(grp)
                    else:
                        groups[group_id].add(line)
        return groups

    def _index_in(self, groups, x):
        """ Quick function finding the index of x in a list of set, where one
        set might contain x.

        Arguments:
            groups (list of set): List of sets, representing all groups.
            x (object): The object to find in the list of sets.

        Returns:
            int: The index of x among groups. `None` if not found.
        """
        for g, group in enumerate(groups):
            if x in group:
                return g
        return None

    def _find_same_lines(self, page, l1):
        """ Method finding all lines that are at the same height with the given
        line.

        Arguments:
            page (LTPage): PDF page containing all elements.
            l1 (LTTextLine): Line to compare and find all other lines similar
                to this one.

        Returns:
            set: Lines indexes of the lines that are similar to the given line.
        """
        lines = set()
        for e2, elem2 in enumerate(page):
            if not isinstance(elem2, LTTextContainer):
                continue        # Skip non text

            for i2, l2 in enumerate(elem2):
                if l1 is l2:
                    continue        # Skip self

                if is_same_bbox((l1.y0, l1.y1), (l2.y0, l2.y1), abs_tol=self.abs_tol) and l1.x1 <= l2.x0:
                    # Lines have the same heights ! Ensure the space is in the middle
                    left, right, _ = self.assign_area([l1, l2], width=page.width)

                    if len(left) != 1 or len(right) != 1 or l2.x0 - l1.x1 < self.min_space:
                        lines.add((e2, i2))
        return lines


class ReorderElements(ConfigurableMiddle):
    """ Node taking care of reordering detected paragraphs appropriately.
    In some case, `pdfminer` mess with the order of paragraphs in a page,
    especially with 2-columns files. This node reorder appropriately the text
    within a page, based on coordinates.
    """

    def __call__(self, doc_path, doc_name, pages):
        """ Reorder paragraphs. Left part of the document first, then right
        columns.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages extracted from a PDF file, with
                reordered content.
        """
        pages = self.cp(pages)

        for page in pages:
            ordered_elements = []
            left, right, common = self.assign_area(page)

            # Within each group, order by y-coordinate
            def y_coord(x): return x.y1
            left = sorted(left, key=y_coord, reverse=True)
            right = sorted(right, key=y_coord, reverse=True)
            common = sorted(common, key=y_coord, reverse=True)

            # Then for each bunch of elements between 2 common elements, read
            # left column first, then second column
            for c_e in common:
                while len(left) > 0 and left[0].y1 >= c_e.y1:
                    ordered_elements.append(left.pop(0))
                while len(right) > 0 and right[0].y1 >= c_e.y1:
                    ordered_elements.append(right.pop(0))
                ordered_elements.append(c_e)
            ordered_elements.extend(left)
            ordered_elements.extend(right)

            # Update the page content with this new order
            assert len(page._objs) == len(ordered_elements)
            page._objs = ordered_elements       # Dirty, using low-level API

        return doc_path, doc_name, pages
