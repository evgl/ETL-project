import logging

from bonobo.config import Configurable, Option
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextContainer

from prospector.document import Title, Paragraph, Table, Document
from prospector.miner import LTTable


class ExtractPages(Configurable):
    """ Transformation reading the file at the given path and extracting pages
    using `pdfminer.six`.

    Arguments:
        boxes_flow (float): `pdfminer` parameter. See
            [documentation](https://pdfminersix.readthedocs.io/en/latest/reference/composable.html#laparams).
        detect_vertical (bool): `pdfminer` parameter. See
            [documentation](https://pdfminersix.readthedocs.io/en/latest/reference/composable.html#laparams).
        char_margin (float): `pdfminer` parameter. See
            [documentation](https://pdfminersix.readthedocs.io/en/latest/reference/composable.html#laparams).
        line_margin (float): `pdfminer` parameter. See
            [documentation](https://pdfminersix.readthedocs.io/en/latest/reference/composable.html#laparams).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logging.getLogger('pdfminer').setLevel(logging.ERROR)

    boxes_flow = Option(float, default=0.5, required=False, __doc__="`pdfminer` parameter")
    detect_vertical = Option(bool, default=False, required=False, __doc__="`pdfminer` parameter")
    char_margin = Option(float, default=3, required=False, __doc__="`pdfminer` parameter")
    line_margin = Option(float, default=0.45, required=False, __doc__="`pdfminer` parameter")

    def __call__(self, path, name):
        """ Extract pages from the file at the given path using `pdfminer.six`.
        Return the resulting object.

        Arguments:
            path (str): Path of the file to extract.
            name (str): Original name of the file to extract.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: List of PDF pages extracted from the file.
        """
        pages = list(extract_pages(path, laparams=LAParams(boxes_flow=self.boxes_flow,
                                                           detect_vertical=self.detect_vertical,
                                                           char_margin=self.char_margin,
                                                           line_margin=self.line_margin)))
        return path, name, pages


class CreateDocument(Configurable):
    """ Node creating the Document object and filling it with the data. """

    def __call__(self, doc_path, doc_name, pages):
        """ Create the Document object, from the parsed pages (from
        `pdfminer.six`) and the fonts of title.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            Document: Document object, representing the data.
        """
        elements = self._parse_elements(pages)
        return Document(name=doc_name, content=elements)

    def _parse_elements(self, pages):
        """ Go through every elements of every pages of the PDF and create
        an Element for each. Return this list of elements.

        Arguments:
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            list of Element: List of Elements parsed from the PDF.
        """
        elements = []
        for p, page in enumerate(pages):
            for elem in page:
                # Just look at table and text. Other things are ignored
                if isinstance(elem, LTTextContainer):       # Text
                    # Don't add empty stuff !
                    content = elem.get_text().strip()
                    if content == "":
                        continue

                    # Add the element
                    if elem.title_level is None:
                        elements.append(Paragraph(page=p, text=content))
                    else:
                        elements.append(Title(page=p, text=content,
                                              level=elem.title_level))
                elif isinstance(elem, LTTable):             # Table
                    elements.append(Table(page=p, camelot=elem.camelot_table))

        return elements
