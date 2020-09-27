import json

from dominate.tags import html, body, head, title, h1, h2, h3, h4, h5, h6, \
                          p, table, tr, td


H_X = [h1, h2, h3, h4, h5, h6]


class Document():
    """ Object representing a whole document. It contain the structured data
    of the document. It can be saved.

    Attributes:
        name (str): The name of the document.
        content (list): The content of the document, as a list of Elements.
    """
    def __init__(self, name, content):
        self.name = name
        self.content = content

    def __repr__(self):
        return "<Document {} [{}]>".format(self.name, len(self.content))

    def __eq__(self, x):
        if type(x) != Document:
            return False
        return self.name == x.name and self.content == x.content

    def to_html(self, pretty=True):
        """ Method returning the HTML representation of the document.

        Arguments:
            pretty (bool, optional): Wether to render pretty HTML or not.
                Defaults to `True`.

        Returns:
            str: String containing the HTML representation of the Document.
        """
        html_content = [c.to_html() for c in self.content]
        return html(head(title(self.name)),
                    body(html_content)).render(pretty=pretty)

    def to_json(self, pretty=True):
        """ Method returning the JSON representation of the document.

        Arguments:
            pretty (bool, optional): Wether to render JSON with indent or not.
                Defaults to `True`.

        Returns:
            str: String containing the JSON representation of the Document.
        """
        json_content = [c.to_json() for c in self.content]
        return json.dumps({'title': self.name, 'content': json_content},
                          indent=(4 if pretty else None))


class Element():
    """ Base class for any data structure. Every structure should have
    at least the page where it's located in the original document.

    Attributes:
        page (int): Page in the original document (0-based).
    """
    def __init__(self, page):
        self.page = page

    def __eq__(self, x):
        if not isinstance(x, Element):
            return False
        return self.page == x.page

    def to_html(self):
        raise NotImplementedError()

    def to_json(self):
        raise NotImplementedError()


class Title(Element):
    """ Class for representing a Title. Title are just text, and a level (for
    title hierarchy).

    Attributes:
        text (str): Content of the title.
        level (int): Level in the hierarchy of titles. Smaller level means more
            important title (0-based).
    """
    def __init__(self, page, text, level=0):
        super().__init__(page)
        self.text = text
        self.level = level

    def __repr__(self):
        smol = self.text if len(self.text) <= 13 else "{}...".format(self.text[:10])
        return "<Title {} p{} (#{})>".format(smol, self.page, self.level)

    def __eq__(self, x):
        if type(x) != Title:
            return False
        return super().__eq__(x) and self.text == x.text and self.level == x.level

    def to_html(self):
        """ Method returning the HTML representation of the Title.

        Returns:
            dominate.tag: HTML representation of the Title.
        """
        if self.level < len(H_X):
            return H_X[self.level](self.text, data_page=self.page)
        else:
            return p(self.text, data_page=self.page, data_level=self.level + 1)

    def to_json(self):
        """ Method returning the JSON representation of the Title.

        Returns:
            dict: JSON representation of the Title.
        """
        return {'title': self.text, 'level': self.level, 'page': self.page}


class Paragraph(Element):
    """ Class for representing a paragraph.

    Attributes:
        text (str): Content of the paragraph.
    """
    def __init__(self, page, text):
        super().__init__(page)
        self.text = text

    def __repr__(self):
        smol = self.text if len(self.text) <= 13 else "{}...".format(self.text[:10])
        return "<Paragraph {} p{}>".format(smol, self.page)

    def __eq__(self, x):
        if type(x) != Paragraph:
            return False
        return super().__eq__(x) and self.text == x.text

    def to_html(self):
        """ Method returning the HTML representation of the Paragraph.

        Returns:
            dominate.tag: HTML representation of the Paragraph.
        """
        return p(self.text, data_page=self.page)

    def to_json(self):
        """ Method returning the JSON representation of the Paragraph.

        Returns:
            dict: JSON representation of the Paragraph.
        """
        return {'paragraph': self.text, 'page': self.page}


class Table(Element):
    """ Class for representing a table.

    Attributes:
        camelot (camelot.Table): The table itself. Can be `None` if
            camelot is not used.
    """
    def __init__(self, page, camelot):
        super().__init__(page)
        self.camelot = camelot

    def __repr__(self):
        if self.camelot is None:
            return "<Table>"
        else:
            return self.camelot.__repr__()

    def __eq__(self, x):
        if type(x) != Table:
            return False
        return super().__eq__(x) and self.camelot == x.camelot

    def to_html(self):
        """ Method returning the HTML representation of the Table.

        Returns:
            dominate.tag: HTML representation of the Table.
        """
        if self.camelot is None:
            return table(tr(td("📁Table")), border=1, cellspacing=0, data_page=self.page)
        else:
            t = table(border=1, cellspacing=0, data_page=self.page)
            for _, row in self.camelot.df.iterrows():
                r = tr()
                for e in row.to_list():
                    r += td(e)
                t += r
            return t

    def to_json(self):
        """ Method returning the JSON representation of the Table.

        Returns:
            dict: JSON representation of the Table.
        """
        html_table = self.to_html().render(pretty=False)
        return {'table': html_table, 'page': self.page}
