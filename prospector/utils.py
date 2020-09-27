import math
import re
from hashlib import sha256

from pdfminer.layout import LTTextContainer


PROSPECTOR_CACHE = "~/.cache/prospector"


def is_same_bbox(bbox1, bbox2, abs_tol=0.01):
    """ Utility function determining if 2 bboxes are at the same position.

    Arguments:
        bbox1 (tuple): First bbox to compare.
        bbox2 (tuple): Second bbox to compare.
        abs_tol (float, optional): Absolute Error Tolerance. Defaults to `0.01`.

    Returns:
        bool: `True` if the 2 bboxes have the same position, `False` otherwise.
    """
    for pos1, pos2 in zip(bbox1, bbox2):
        if not math.isclose(pos1, pos2, abs_tol=abs_tol):
            return False
    return True


def _normalize_str(s):
    """ Utility to normalize text. It does the following :
    * Replace double spaces by single spaces
    * Replace digits chain by a normalized character (`<#>`). Useful to match
        page number.
    * Replace all occurence of `1`, `I`, `i`, `L`, `l` by `1`. This is because
        for OCR'd file, these charaters are often confused.

    Arguments:
        s (str): String to normalize.

    Returns:
        str: Normalized string.
    """
    return " ".join(re.sub(r"\d+", "<#>", re.sub(r"[1IiLl]", "1", s)).split())


def is_similar_element(element1, element2, abs_tol=0.01):
    """ Utility function determining if 2 elements are the same. If strict is
    False, we don't test the content of text, just their position.

    Arguments:
        element1 (pdfminer.LTComponent): First element to compare.
        element2 (pdfminer.LTComponent): Second element to compare.
        abs_tol (float, optional): Absolute Error Tolerance. Defaults to `0.01`.
        strict (bool, optional): Whether to strictly match text content.

    Returns:
        bool: `True` if the 2 elements are strictly similar (same position and
            same content in case of text), `False` otherwise.
        bool: `True` if the 2 elements are somehow similar (same starting
            position), `False` otherwise.
    """
    if type(element1) != type(element2):
        return False, False

    if isinstance(element1, LTTextContainer):
        if is_same_bbox((element1.x0, element1.y0), (element2.x0, element2.y0), abs_tol=abs_tol):
            same_content = False
            if is_same_bbox((element1.x1, element1.y1), (element2.x1, element2.y1), abs_tol=abs_tol):
                same_content = _normalize_str(element1.get_text()) == _normalize_str(element2.get_text())
            return same_content, True
        else:       # Not even matching start position
            return False, False
    else:
        same_pos = is_same_bbox(element1.bbox, element2.bbox, abs_tol=abs_tol)
        return same_pos, same_pos


def get_unique_filename(path):
    """ Create a hashed filename for ensuring we don't overwrite files.

    Arguments:
        path (str): Path to hash.

    Returns:
        str: Hash.
    """
    return sha256(path.encode("utf-8")).hexdigest()


def get_error_from_context(context):
    """ Utils to extract filenames of errors met during the execution of the
    graph, from the returned context.

    Arguments:
        context (bonobo.GraphExecutionContext): Context from the executed graph.

    Returns:
        list of strings: Files where error occurred
    """
    if hasattr(context, 'errors'):
        return list(set(context.errors))
    return []
