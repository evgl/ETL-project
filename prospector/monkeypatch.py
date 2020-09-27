from types import GeneratorType
import logging
import os

from bonobo.execution.contexts import base
from bonobo.execution.contexts import NodeExecutionContext

from prospector.document import Document


def error(self, exc_info, *, level=logging.ERROR):
    if not hasattr(self.parent, 'errors'):
        setattr(self.parent, 'errors', [])
    if hasattr(self.input, 'curr'):
        self.parent.errors.append(self.input.curr)
    logging.getLogger(__name__).log(level, repr(self), exc_info=exc_info)


def _extract_filename_from_(input_bag):
    """ Utils function to extract the filename from a node input. Node input
    can be one of the following :

    * str: The file path
    * tuple(str, str): The normalized file path and the original file name.
    * tuple(str, str, pdfminer object): The normalized file path, the original
        file name, and the extracted object using `pdfminer`.
    * Document: The created Document object.

    Arguments:
        input_bag: Node input.

    Returns:
        str: The file name that provoked the error.
    """
    if len(input_bag) == 1 and isinstance(input_bag[0], str):
        return os.path.split(input_bag[0])[1]
    elif len(input_bag) == 1 and isinstance(input_bag[0], Document):
        return input_bag[0].name + ".pdf"
    elif len(input_bag) > 1 and isinstance(input_bag[1], str):
        return input_bag[1] + ".pdf"
    else:
        return ""


def step(self):
    # Pull and check data
    input_bag = self._get()

    setattr(self.input, 'curr', _extract_filename_from_(input_bag))

    # Sent through the stack
    results = self._stack(input_bag)

    # self._exec_time += timer.duration
    # Put data onto output channels

    if isinstance(results, GeneratorType):
        while True:
            try:
                # if kill flag was step, stop iterating.
                if self._killed:
                    break
                result = next(results)
            except StopIteration:
                # That's not an error, we're just done.
                break
            else:
                # Push data (in case of an iterator)
                self._send(self._cast(input_bag, result))
    elif results:
        # Push data (returned value)
        self._send(self._cast(input_bag, results))
    else:
        # case with no result, an execution went through anyway, use for stats.
        # self._exec_count += 1
        pass


base.Lifecycle.error = error
NodeExecutionContext.step = step
