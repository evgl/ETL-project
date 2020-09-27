import logging
import bonobo

from prospector import nodes
from prospector.utils import get_error_from_context


logger = logging.getLogger("prospector")


def dig(file, **kwargs):
    """ Python function that dig and extract content from the given file.

    Note : This function is pure python, there is no ETL pipeline. Use it
        if you need to access the Document object. If you need to dig a lot of
        PDF files and save it, please use the `pumpjack()` function, which
        offer ETL capabilities (multi-threading, etc...).

    Arguments:
        file (`str`): File from where to dig content.
        kwargs (optional): Additional arguments for `get_digging_nodes()`.

    Returns:
        prospector.Document: A document object with all the useful content of
            the PDF file given.
    """
    digging_nodes = get_digging_nodes(**kwargs)

    inputs = [file]
    for node in digging_nodes:
        logger.info("Running node `{}`...".format(node.__class__.__name__))
        inputs = node(*inputs)
    logger.info("Digging done")

    return inputs


def pumpjack(files, directory='./', formt='html', **kwargs):
    """ Run the full ETL pipeline. It run the pipeline for all given files and
    save them with the given format.

    Note : Because it's an ETL pipeline, there is no outputs. If you need to
        access the output object, please use the `dig()` method.

    Arguments:
        files (`str` or `list of str`): Files from where to dig content.
        directory (`str`, optional): Directory where to save the Documents.
            Defaults to current working directory.
        formt (`str`, optional): Format of how to save Document. Defaults to
            `html`.
        flatten (`bool`, optional): Whether to flatten the document
            representation or not. Defaults to `False`.
        kwargs (optional): Additional arguments for `get_digging_nodes()`.

    Returns:
        int: Number of errors met during the pipeline execution.
    """
    graph = bonobo.Graph()
    digging_nodes = get_digging_nodes(**kwargs)

    graph.add_chain(nodes.OneByOne(files),
                    *digging_nodes,
                    nodes.SaveAs(directory=directory, formt=formt))

    context = bonobo.run(graph, services={})
    return get_error_from_context(context)


def get_digging_nodes(normalize=True, group=True, pre_detect=True, camelot=True):
    """ Method defining the core of the pipeline. It returns a list of callable
    which can be used inside an ETL pipeline, or can simply be chained together
    and called in pure python.

    Note : Because it should possibly be chained together and called in pure
        python, the nodes returns should ALWAYS be functions (with `return`
        keyword), not generators (with `yield` keyword).

    Arguments:
        normalize (`bool`, optional): Wether to normalize the PDF file before
            running the other nodes or not. Defaults to `True`.
        group ('bool', optional): Whether to group bullets after : or not.
            Defaults to `True`.
        pre_detect (`bool`, optional): Wether to pre-detect tables before using
            `camelot` or not. Tables can be pre-detected with the `pdfminer`
            object to, in order to run `camelot` only on specific pages.
            Setting this to `True` will make the code faster, but there
            might be discrepancies between what we detect and what `camelot`
            detects. Defaults to `True`.
        camelot (`bool`, optional): Wether to use `camelot` package to parse
            table content or not. `camelot` is slow, so if you don't need table
            data, just specify `False`. Defaults to `True`.

    Returns:
        list of callable: List of callable, that can be used as nodes inside an
            ETL pipeline, or simply be chained and called from python.
    """
    is_linear = True

    return [
        nodes.NormalizePdf(normalize=normalize),
        nodes.ExtractPages(),
        nodes.RemoveLandscapePages(linear_graph=is_linear),
        nodes.RemoveContentTable(linear_graph=is_linear),
        nodes.RemoveNonSearchablePage(linear_graph=is_linear),
        nodes.RemoveMathCharacters(linear_graph=is_linear),
        nodes.RemoveEmptyLines(linear_graph=is_linear),
        nodes.RemoveHeaderFooter(linear_graph=is_linear),
        nodes.Linify(linear_graph=is_linear),
        nodes.ReorderElements(linear_graph=is_linear),
        nodes.CleanTables(linear_graph=is_linear, pre_detect=pre_detect, camelot=camelot),
        nodes.MergeSuccessiveTables(linear_graph=is_linear),
        nodes.FixIndentationSeparatedText(linear_graph=is_linear),
        nodes.Paragraphize(linear_graph=is_linear),
        nodes.ExtractFontInfo(linear_graph=is_linear),
        nodes.FindTitles(linear_graph=is_linear),
        nodes.NormalizeTitleLevel(linear_graph=is_linear),
        nodes.TextParagraphize(linear_graph=is_linear),
        nodes.BulletParagraph(linear_graph=is_linear, group=group),
        nodes.CreateDocument()
    ]


def is_searchable(pdf_file):
    """ Python function that reads the given PDF file and identify if this
    PDF is searchable or not.

    Arguments:
        pdf_file (`str`): Path of the PDF file.

    Returns:
        bool: `True` if the PDF is searchable (contains text), `False`
            otherwise (if the PDF was scanned, contains only images).
    """
    node = nodes.RemoveNonSearchablePage()
    path, name = nodes.NormalizePdf()(pdf_file)
    _, _, pages = nodes.ExtractPages()(path, name)

    for page in pages:
        if node.is_searchable_page(page):
            return True
    return False
