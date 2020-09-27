<h1 align="center">Prospector</h1>
<p align="center">Short description of the package : TODO.</p>

<p align="center"><a href="https://github.com/42maru-ai/prospector/actions"><img src="https://github.com/42maru-ai/prospector/workflows/tests/badge.svg" alt="test status" /></a></p>

<h2 align="center">Description</h2>

TODO

<h2 align="center">Install</h2>

### OS dependencies

These dependencies are required for `camelot` to work.

Run :

```console
sudo apt install python3-tk ghostscript
```

### Python dependencies

Simply run :

```console
pip install git+https://github.com/42maru-ai/prospector.git
```

<h2 align="center">Usage</h2>

There is 2 ways to use the library :
* ETL pipeline
* Sequential execution

Use the **Sequential execution** if you have a single PDF file to treat, or if you need to access the Python object after extraction.

Instead, use the **ETL pipeline** if you need to treat a lot of PDF files. It will likely be faster as it is multi-threaded.  
But the ETL pipeline cannot return a Python object. Objects will be saved in the format of your choice (like `HTML`).

### Sequential execution

Run :

```python
from prospector import dig

doc = dig('doc1.pdf')
```

---

You can then use the `Document` object, or save it to `HTML` for example:

```python
with open('doc1.html', 'w') as f:
    f.write(doc.to_html())
```

### ETL pipeline

Run :

```python
from prospector import pumpjack

pumpjack(['doc1.pdf', 'doc2.pdf'])
```

### Other uses

`prospector` also allow you to detect if a PDF is searchable or not :

```python
from prospector import is_searchable

is_searchable('doc1.pdf')
```

<h2 align="center">Dependencies</h2>

#### [pdfminer.six](https://pdfminersix.readthedocs.io/en/latest/index.html)
Library offering low-level informations about PDF elements, and text extraction utilities.  
This is the community-maintained fork of `pdfminer`.

#### [bonobo](https://www.bonobo-project.org/)
`bonobo` is a python ETL framework.  
Unlike others (Airflow, Luigi), it's a very simple library and does not require to learn a new API, plain python is enough.

#### [camelot](https://camelot-py.readthedocs.io/en/master/index.html#)
`camelot` is a python library for extracting tables from PDF files.  
It relies on `Tkinter` and `ghostscript`.

#### [pymupdf](https://pymupdf.readthedocs.io/en/latest/index.html)
`pymupdf` is a Python binding for [MuPDF](https://www.mupdf.com/), a library for viewing PDF and other formats. We use this library to normalize PDF.

<h2 align="center">Contribute</h2>

Ensure tests are passing :

```console
pip install pytest

python -m pytest -W ignore::DeprecationWarning
```

---

Check if code is well-formated :

```console
pip install flake8

flake8 . --count --max-complexity=10 --max-line-length=127 --statistics --per-file-ignores="__init__.py:F401"
```

---

Run benchmark to ensure there is no regression :

```console
python benchmark/run_benchmark.py
```

---

Generate documentation with :

```console
pip install sphinx
pip install sphinx_rtd_theme

cd docs
make html

cd docs/_build/html/
python3 -m http.server 9999
```