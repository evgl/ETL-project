from itertools import combinations

from bonobo.config import Option
from pdfminer.layout import LTComponent

from prospector.nodes.utils import ConfigurableModificator
from prospector.utils import is_similar_element
from prospector.miner import rm, get


class Header():
    """ A class representing a Header, which is just a list of LTElements from
    a parsed PDF, and the reference of these elements for each page.

    Attributes:
        elem (list of LTElements): Elements of the Header.
        ref (dict of int): For each page concerned, the indice where the
            elements appear, in order.
    """
    def __init__(self, elements, p, indices):
        """ Constructor """
        self.elements = elements
        self.ref = {p: indices}

    def match(self, header, strict=True):
        """ Method to compute the match between elements of 2 headers.
        It gives a list of tuple, where each tuple contain the indice of first
        header element matching to indice of second header element.

        If `strict` is set, we match the content of each element. Because the
        matching is more strict, there is less chance of False Positive
        happening, so we tolerate more difference in positions. This is
        necessary for OCR document, where the position does not exactly match.

        Arguments:
            header (Header): The header to compare.
            strict (bool, optional): Wether to match strictly or only based on
                position (not content). Defaults to `True`.

        Returns:
            dict: The position of each matching element.
        """
        match = {}
        for e1, elem1 in enumerate(self.elements):
            for e2, elem2 in enumerate(header.elements):
                if e2 in match.values():
                    continue        # Already assigned element, skip it

                atol = 3 if strict else 0.1     # See docstring for details
                match_strict, match_pos = is_similar_element(elem1, elem2, abs_tol=atol)

                if (strict and match_strict) or (not strict and match_pos):
                    match[e1] = e2
        return match

    def ov_match(self, header):
        """ Method to compute the overlapping match between elements of 2
        headers. It gives a dictionary, linking indices of header #1 elements
        to matching indices of header #2 elements.

        Note : the `match()` function return match where each element is
            strictly the same (position + content), or somewhat the same (same
            starting position). This function, just try to match element by
            looking at how much they overlap.

        Arguments:
            header (Header): The header to compare.

        Returns:
            dict: The position of each matching element.
        """
        match = {}
        for e1, elem1 in enumerate(self.elements):
            best = 0
            best_id = None
            for e2, elem2 in enumerate(header.elements):
                if e2 not in match.values():
                    ov = elem1.hoverlap(elem2) * elem1.voverlap(elem2)
                    if ov > best:
                        best = ov
                        best_id = e2

            if best != 0:
                match[e1] = best_id
        return match

    def merge(self, header, match):
        """ Merge the given header with this header. Only common elements are
        kept.

        Arguments:
            header (Header): The header to merge.
            match (dict): The position of each matching element.
        """
        common_elem = []
        new_ref = {p: [] for p in self.ref}
        new_ref.update({p: [] for p in header.ref})
        for e1, e2 in match.items():
            # Save only common elements
            common_elem.append(self.elements[e1])

            # Update the bbox of the saved element
            common_elem[-1].set_bbox((
                min(self.elements[e1].x0, header.elements[e2].x0),
                min(self.elements[e1].y0, header.elements[e2].y0),
                max(self.elements[e1].x1, header.elements[e2].x1),
                max(self.elements[e1].y1, header.elements[e2].y1)
            ))

            # Save existing ref
            for p, r in self.ref.items():
                new_ref[p].append(r[e1])

            # Save existing ref from the other header
            for p, r in header.ref.items():
                new_ref[p].append(r[e2])
        self.elements = common_elem
        self.ref = new_ref

    def assign(self, header, match):
        """ Similar to merge, but all elements of current header are kept, only
        references for the page are updated.

        Arguments:
            header (Header): The header to merge.
            match (dict): The position of each matching element.
        """
        new_ref = {p: [] for p in header.ref}
        for e1, e2 in match.items():
            for p, r in header.ref.items():
                while len(new_ref[p]) < e1:
                    new_ref[p].append(None)
                new_ref[p].append(r[e2])
        self.ref.update(new_ref)

    def __repr__(self):
        """ Used for displaying a Header class, for easier debugging. """
        return "<Header ({} elements) p[{}]>".format(len(self.elements), self.ref.keys())


class RemoveHeaderFooter(ConfigurableModificator):
    """ Node finding Headers and Footers in the document, and removing it.

    Attributes:
        margin (list of float, optional): Margins (relative to height and width
            of the page) where headers and footers can be located. Can be given
            as (top, right, bottom, left) or (vertical, horizontal) or (all).
            Defaults to `[0.3, 0.2, 0.2, 0.2]`.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not (isinstance(self.margin, list) or isinstance(self.margin, float)):
            raise ValueError("{} is an invalid margin. Should be a list of ratio or a ratio.".format(self.margin))
        elif isinstance(self.margin, float):
            self.margin = [self.margin] * 4
        else:
            if len(self.margin) == 1:
                self.margin *= 4
            elif len(self.margin) == 2:
                self.margin *= 2
            elif len(self.margin) == 4:
                pass
            else:
                raise ValueError("Invalid number of margin provided (1, 2, or 4) : {}".format(len(self.margin)))
        if self.margin[0] + self.margin[2] > 1:
            raise ValueError("Margin should be a ratio (<= 1) : {} / {}".format(self.margin[0], self.margin[2]))
        if self.margin[1] + self.margin[3] > 1:
            raise ValueError("Margin should be a ratio (<= 1) : {} / {}".format(self.margin[1], self.margin[3]))

    margin = Option(default=[0.25, 0.2, 0.2, 0.2], required=False, __doc__="Relative margins")

    def __call__(self, doc_path, doc_name, pages):
        """ Find Headers and Footers by :
        * Creating a raw header for each page of the document. This raw header
            contains elements on the edge of the page, with the given margins.
        * Finding all trio-matching pages : 3-pages neighborhood that have the
            same common elements. We need 3-pages comparison to ensure we
            don't pick accidental common elements between pages.
        * Assigning remaining pages to one of the Header we found.
        * Removing the Header elements from the pages.

        Note : Because some pages have different odd/even pages, we need to
            compute headers 3 times : one time for all pages together, one time
            for only odd pages, and one time for only even pages. Then we pick
            the choice where we found the most headers.

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

        # Create 1 header per page at first (respecting the boundaries)
        raw_headers = self._create_headers(pages)
        even_raw_headers = [h for h in self._create_headers(pages) if next(iter(h.ref.keys())) % 2 == 0]
        odd_raw_headers = [h for h in self._create_headers(pages) if next(iter(h.ref.keys())) % 2 == 1]

        # Match headers with their neighbors
        headers, raw_headers = self._get_headers(raw_headers)
        even_headers, even_raw_headers = self._get_headers(even_raw_headers)
        odd_headers, odd_raw_headers = self._get_headers(odd_raw_headers)

        # Gather similar headers together
        headers = self._gather_headers(headers)
        even_headers = self._gather_headers(even_headers)
        odd_headers = self._gather_headers(odd_headers)

        # Take the best choice between : all pages - odd/even pages separated
        if len(even_raw_headers) + len(odd_raw_headers) < len(raw_headers):
            headers = self._gather_headers(even_headers + odd_headers)
            raw_headers = even_raw_headers + odd_raw_headers

        if len(headers) != 0:
            # We found some general headers ! Just compare the raw headers and
            # associate each of them to the closest matching headers
            self._assign_raw_headers(headers, raw_headers)
        else:
            # Couldn't detect general headers, or the file is too short... As a
            # last resort, try to match every raw headers based on position
            headers = self._brute_force_pos_match(raw_headers)

        # Then remove headers content from the pages
        pages = self._remove_headers(pages, headers)
        return doc_path, doc_name, pages

    def _create_headers(self, pages):
        """ Create the initial list of Headers : simply create one possible
        header for each page. Only elements located at the edge of the page are
        kept.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            list of Headers: List of Headers.
        """
        headers = []
        for p, page in enumerate(pages):
            if len(page) == 0:
                continue        # Skip empty pages

            p_y1 = page.height - page.height * self.margin[0]
            p_y0 = page.height * self.margin[2]
            p_x1 = page.width - page.width * self.margin[1]
            p_x0 = page.width * self.margin[3]

            header_material = []
            header_material_id = []
            for e, elem in enumerate(page):
                if elem.x1 < p_x0 or elem.x0 > p_x1 or elem.y1 < p_y0 or elem.y0 > p_y1:
                    header_material.append(elem)
                    header_material_id.append(e)

            if len(header_material) != 0:
                headers.append(Header(elements=header_material, p=p, indices=header_material_id))
        return headers

    def _get_headers(self, raw_headers):
        """ From a list of raw headers, try to group neighbors that have the
        same content.

        Arguments:
            raw_headers (list of Header): List of raw headers extracted from
                the page.

        Returns:
            list of Header: Header that could be matched with their neighbors.
            list of Header: Remaining raw headers, that couldn't be matched.
        """
        headers = []
        while True:
            # First step : Group neighbors that have the exact same header
            raw_headers, matching_header = self._group_matching_trio(raw_headers)

            if matching_header is None:
                # No new matching headers, leave this loop
                break
            else:
                headers.append(matching_header)
        return headers, raw_headers

    def _remove_headers(self, pages, headers):
        """ Remove headers content from the pages.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.
            headers (list of Headers): List of headers.

        Returns:
            list of pdfminer.LTPage: Pages without header.
        """
        def _is_within(x, zone):
            return x.x0 > zone.x0 and x.x1 < zone.x1 and x.y0 > zone.y0 and x.y1 < zone.y1

        for header in headers:
            for p, indices in header.ref.items():
                green_zone = self._compute_green_zone(pages[p], indices)
                rm(pages[p], to_rm=lambda x: not _is_within(x, green_zone))
        return pages

    def _compute_green_zone(self, page, indices):
        """ Compute the green zone of a page based on the indices of the
        elements to exclude. It creates an area on the middle of the page
        including all elements to be kept.

        Arguments:
            page (pdfminer.LTPage): Page for which to compute the deadzone.
            indices (list of int): List of indices of the elements of the page
                to remove.

        Returns:
            pdfminer.LTComponent: A LTComponent, representing the green zone.
        """
        top, right, bottom, left = 0, 0, 0, 0

        # Compute green zone based on text of Headers
        for idx in indices:
            if idx is None:
                continue

            element = get(page, idx)

            top_impact = sum([bool(elem.y1 >= element.y0) for e, elem in enumerate(page) if e not in indices])
            right_impact = sum([bool(elem.x1 >= element.x0) for e, elem in enumerate(page) if e not in indices])
            bottom_impact = sum([bool(elem.y0 <= element.y1) for e, elem in enumerate(page) if e not in indices])
            left_impact = sum([bool(elem.x0 <= element.x1) for e, elem in enumerate(page) if e not in indices])
            min_impact = min(top_impact, right_impact, bottom_impact, left_impact)

            if min_impact == top_impact:
                top = max(top, page.height - element.y0)
            elif min_impact == bottom_impact:
                bottom = max(bottom, element.y1)
            elif min_impact == left_impact:
                left = max(left, element.x1)
            else:
                right = max(right, page.width - element.x0)

        return LTComponent((left, bottom, page.width - right, page.height - top))

    def _group_matching_trio(self, raw_headers):
        """ Try to match neighbors (strictly), and if 3 successive headers have
        the same match, then group it.

        Arguments:
            raw_headers (list of Header): List of raw headers to match.

        Returns:
            list of Header: List of remaining raw headers.
            Header: The merged Header.
        """
        to_merge = []
        merge_scores = []
        pc_match, cn_match, pn_match = None, None, None
        in_match = False
        idx = 0

        # Detect matching trio
        for prev_h, curr_h, next_h in zip(raw_headers[:-2], raw_headers[1:-1], raw_headers[2:]):
            if pc_match is None:
                pc_match = prev_h.match(curr_h)
            cn_match = curr_h.match(next_h)

            # Check 2 things :
            # * We have same number of strictly matching and position matching.
            #       If we don't, it means the content is different.
            # * Check if the same elements match between prev/curr and curr/next
            if set(pc_match.values()) == set(cn_match.keys()):
                # They match ! Now check if prev and next match as well
                pn_match = prev_h.match(next_h)

                # Check strictly matching                 and match same elements between prev/next
                if set(pc_match.keys()) == set(pn_match.keys()):
                    # The 3 are matching ! Append their idx to the list of idx to merge
                    if in_match:
                        to_merge[-1].append(idx + 2)
                    else:
                        to_merge.append([idx, idx + 1, idx + 2])
                        merge_scores.append(len(pn_match))
                    in_match = True
                else:
                    in_match = False
            else:
                in_match = False

            # Don't recompute pc_match, we already have it. Update for next iter
            pc_match = cn_match
            idx += 1

        if len(merge_scores) == 0:
            return raw_headers, None      # Can't find any trio !

        # Just merge together the group with the best score
        best_idx = max(range(len(merge_scores)), key=lambda x: merge_scores[x])

        # Merge them
        header = None
        for i in reversed(to_merge[best_idx]):
            if header is None:
                header = raw_headers.pop(i)
                continue
            h = raw_headers.pop(i)
            header.merge(h, header.match(h))
        return raw_headers, header

    def _gather_headers(self, headers):
        """ Given a list of Headers, this method try to gather similar headers
        together. Headers are similar if they match in position (not content),
        with the exact same amount of elements.

        Arguments:
            headers (list of Header): List of headers to gather.

        Returns:
            list of Header: List of merged headers.
        """
        to_gather = []
        # Find matching headers
        for i1, i2 in combinations(range(len(headers)), 2):
            if len(headers[i1].ov_match(headers[i2])) == len(headers[i1].elements):
                g = None
                for group_nb, group in enumerate(to_gather):
                    if i1 in group or i2 in group:
                        g = group_nb
                        break

                if g is not None:
                    to_gather[g].add(i1)
                    to_gather[g].add(i2)
                else:
                    to_gather.append(set([i1, i2]))

        # Gather them
        gathered_headers = []
        for idxs in to_gather:
            header_1 = None
            for idx in idxs:
                if header_1 is None:
                    header_1 = headers[idx]
                    continue

                header_1.assign(headers[idx], header_1.ov_match(headers[idx]))
            gathered_headers.append(header_1)

        # Don't forget headers that didn't have similar one
        remaining = [head for h, head in enumerate(headers) if h not in set().union(*to_gather)]
        gathered_headers.extend(remaining)
        return gathered_headers

    def _assign_raw_headers(self, headers, raw_headers):
        """ Assign raw headers to the best matching header.

        Arguments:
            headers (list of Header): List of good, strong headers.
            raw_headers (list of Header): List of raw headers, that we need to
                assign to a good headers.
        """
        for raw in raw_headers:
            # Argmax based on the score with this raw header
            best_idx = max(range(len(headers)), key=lambda x: len(raw.ov_match(headers[x])))

            headers[best_idx].assign(raw, headers[best_idx].ov_match(raw))

    def _brute_force_pos_match(self, raw_headers):
        """ Try to match all given headers based on position. This is a last
        resort solution, as it assumes all pages have the same type of headers,
        which may not be true.

        Arguments:
            raw_headers (list of Header): List of raw headers, to match in a
                single header.

        Returns:
            list of Header: List of 1 header, common to all given raw headers,
                or empty list if we couldn't find any.
        """
        if len(raw_headers) <= 1:
            # Nothing to compare, it's just a single page... Assume no header
            return []

        header = raw_headers.pop(0)
        for rh in raw_headers:
            header.merge(rh, header.match(rh, strict=False))

        return [header]
