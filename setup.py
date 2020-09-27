import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as fr:
    reqs = fr.read().strip().split('\n')


setuptools.setup(
    name="prospector",
    version="0.1",
    author="42Maru",
    author_email="dev@42maru.com",
    description="Extract document data from PDF, DOCX, ...",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/42maru-ai/prospector",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=reqs,
)
