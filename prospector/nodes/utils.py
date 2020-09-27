import os
import copy

import fitz
from bonobo.config import Configurable, Option
from pdfminer.layout import LTTextContainer, LTContainer, LTImage

from prospector.utils import PROSPECTOR_CACHE, get_unique_filename


class OneByOne(Configurable):
    """ Simple extractor that can handle both single element and list of
    element. Elements are yielded one by one.

    Arguments:
        x (object): Object that needs to be yielded element by element.
    """

    x = Option(required=True, positional=True,
               __doc__="Object that needs to be yielded element by element")

    def __call__(self):
        if isinstance(self.x, list):
            for elem in self.x:
                yield elem
        else:
            yield self.x


class NormalizePdf(Configurable):
    """ Node normalizing PDF. Sometimes the PDF file does not respect perfect
    format. `pdfminer` can read such file, but other libraries like `camelot`
    throws error. So we need to normalize the format of the PDF.

    This node should be called before extracting data from the PDF file with
    `pdfminer`.

    Arguments:
        normalize (bool): Wether to normalize the PDF file or not.
        cache (str): Path of the cache folder to use where we will save the
            normalized PDF file.
    """

    normalize = Option(bool, default=True, required=False, __doc__="Normalize PDF or not")
    cache = Option(str, default=PROSPECTOR_CACHE, required=False, __doc__="Cache folder")

    def __call__(self, doc_path):
        """ Normalize the given PDF, saving it to the cache. PDF are normalized
        using MuPDF library, because it's fast.

        Arguments:
            doc_path (str): Path of the file to normalize.

        Returns:
            str: Path of the file.
            str: Original name of the file.
        """
        doc_name = os.path.splitext(os.path.basename(doc_path))[0]
        if not self.normalize:
            return doc_path, doc_name

        # Create cache directory if not existing
        cache = os.path.expanduser(self.cache)
        os.makedirs(cache, exist_ok=True)

        # Create unique path in cache for saving normalized PDF
        filename = get_unique_filename(doc_name) + ".pdf"
        normal_path = os.path.join(cache, filename)

        # Normalize PDF
        pdf = fitz.open(doc_path)
        pdf.save(normal_path)

        return normal_path, doc_name


class SaveAs(Configurable):
    """ End-Node that save the Document object to a specific format.

    Arguments:
        directory (str, optional): Directory where to save the document.
            Defaults to current working directory.
        formt (str, optional): Format for saving the document. Defaults to
            `html`.
        flatten (bool, optional): Whether to flatten the document
            representation or not. Defaults to `False`.
    """

    directory = Option(str, default='./', required=False, __doc__="Directory where to save the document")
    formt = Option(str, default='html', required=False, __doc__="Format for saving the document")

    def __call__(self, document):
        """ Save the given document to the specified format.

        Arguments:
            document (Document): Document to save.
        """
        formt = self.formt.lower()
        if formt == 'html':
            content = document.to_html()
        elif formt == 'json':
            content = document.to_json()
        else:
            raise ValueError("Unknown format : {}".format(formt))

        with open("{}.{}".format(os.path.join(self.directory, document.name), formt), 'w') as f:
            f.write(content)


class ConfigurableModificator(Configurable):
    """ A Configurable with an option for deep-copying objects that needs to be
    deep-copied.

    If the graph where the Node belong is **linear** and return only 1 output
    for each input, then we don't need to care of side-effects, and therefore
    no need to deep-copy.

    But otherwise, if we don't deep copy the object, it might have side-effects
    on other threads. This is a great source of bugs, so by default we always
    deep-copy.

    We disable deep-copy when we know what we are doing and when we are looking
    for performances.

    Arguments:
        linear_graph (bool): Do we deep-copy or not.
    """

    linear_graph = Option(bool, default=False, required=False, __doc__="Do we deep-copy or not.")

    def cp(self, o):
        """ Function for copying an object. The object is deep-copied if we are
        not in a linear graph. If we are in a linear graph, then we don't need
        to care of side-effects and we can just return the object like this.

        Arguments:
            o (obj): Object to copy.

        Returns:
            o (obj): Object, deep-copied or not, ensuring there will be no
                side-effects.
        """
        if self.linear_graph:
            return o
        else:
            return self._deep_copy(o)

    def _deep_copy(self, obj):
        """ Deep-copy a given object. To ensure it works well with any
        `pdfminer` object, we need to redefine how they are copied (specially
        `LTImage`, because they contain a stream).

        This method is recursive.

        Arguments:
            obj (Object): Object to be deep-copied.

        Returns:
            Object: Deep-copied object.
        """
        if type(obj) == LTImage:
            # Image can't be deep-copied because of the stream. Shallow copy is
            # enough (unlikely that we will modify the stream...)
            return LTImage(name=obj.name, stream=obj.stream, bbox=obj.bbox)
        elif isinstance(obj, LTContainer):
            # We have a `pdfminer` object ! Deep-copy every childs through this
            # method and shallow copy the rest
            obj_cp = copy.copy(obj)
            obj_cp._objs = self._deep_copy(obj._objs)
            return obj_cp
        elif isinstance(obj, list):
            # Ensure every element of the list use this method
            return [self._deep_copy(o) for o in obj]
        else:
            return copy.deepcopy(obj)


class PrintPage(Configurable):
    """ A node used for debugging : simply prints the elements of a pdfminer
    object at a specific page.

    Attributes:
        p (int): The page number to print. Required.
    """

    p = Option(int, positional=True, __doc__="The page number to print")

    def __call__(self, doc_path, doc_name, pages):
        """ Print the specic page's elements.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages extracted from a PDF file.
        """
        for p, page in enumerate(pages):
            if p == self.p:
                print("============ Page {} ============".format(p))
                for elem in page:
                    print(elem)
                print("=================================")
        return doc_path, doc_name, pages


class PlotPage(Configurable):
    """ A node used for debugging : plot and show page with elements of a pdfminer
    object.

    Attributes:
        p (int): The page number to show. Required.
        cache (str): Path of the cache folder to use where we will save the
        generated image file.
        save (bool): Whether to save the Plot or not.
        dpi (int): Resolution in dots per inch.
    """

    p = Option(int, positional=True, __doc__="The page number to plot")
    cache = Option(str, default=PROSPECTOR_CACHE, required=False, __doc__="Cache folder")
    save = Option(bool, default=False, required=False, __doc__="Whether to save the Plot or not.")
    dpi = Option(int, default=400, required=False, __doc__="Resolution in dots per inch.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # dependency for PlotPage node
        from pdf2image import convert_from_path
        from matplotlib import pyplot as plt
        import matplotlib.patches as patches

        self.convert_from_path, self.plt, self.patches = convert_from_path, plt, patches

    def __call__(self, doc_path, doc_name, pages):
        """ Plot and show the specic page.

        Arguments:
            doc_path (str): Path of the file.
            doc_name (str): Name of the file.
            pages (list of pdfminer.LTPage): Pages extracted from a PDF file.

        Returns:
            str: Path of the file.
            str: Name of the file.
            list of pdfminer.LTPage: Pages extracted from a PDF file.
        """
        # Create cache directory if not existing
        cache = os.path.dirname(os.path.expanduser(self.cache))
        os.makedirs(cache, exist_ok=True)

        # convert page to image
        self._pdf2img(doc_path, self.p, cache)
        image = os.path.join(cache, get_unique_filename(doc_path) + ".jpg")

        # iterate pages and find the page where the image from
        for p, page in enumerate(pages):
            if page.pageid == self.p:
                self._plot(image, page, doc_name)
                break

        return doc_path, doc_name, pages

    def _plot(self, image, page, doc_name):
        """ Plot the image with specific page's elements.

        Arguments:
            image (str): image to be plotted.
            page (pdfminer.LTPage): Page extracted from a PDF file.
            doc_name (str): Name of the file.
        """
        img = self.plt.imread(image)

        fx = img.shape[0] / page.height
        fy = img.shape[1] / page.width
        fig, ax = self.plt.subplots(1)
        ax.imshow(img)

        for elem in page:
            if isinstance(elem, LTTextContainer):
                x0, x1, y0, y1 = elem.x0, elem.x1, page.height - elem.y0, page.height - elem.y1
                x0, x1, y0, y1 = x0 * fx, x1 * fx, y0 * fy, y1 * fy
                rect = self.patches.Rectangle((x0, y0), x1-x0, y1-y0, linewidth=1, edgecolor='r', facecolor='none')
                ax.add_patch(rect)

        self.plt.savefig(os.path.join(".", doc_name + ".png"), dpi=self.dpi) if self.save else self.plt.show()

    def _pdf2img(self, doc_path, page, cache):
        """ Convert PDF page to image and save it to cache directory.

        Arguments:
            doc_path (str): Path of the file.
            page (pdfminer.LTPage): Page extracted from a PDF file.
            cache (str): Path of the cache folder to use where we will save the
            generated image file.
        """
        output_file = get_unique_filename(doc_path)
        self.convert_from_path(doc_path,
                               output_folder=cache,
                               first_page=page,
                               last_page=page,
                               output_file=output_file,
                               single_file=True,
                               fmt='jpeg')
