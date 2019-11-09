import setuptools
import restio

with open("README.md", "r") as fh:
    long_description = fh.read()

read_the_docs_url = "https://restio.readthedocs.io/en/latest"
git_url = "https://github.com/eduardostarling/restio.git"

setuptools.setup(
    name=restio.__name__,
    version=restio.__version__,
    author="Eduardo Starling",
    author_email="edmstar@gmail.com",
    description="restio Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=git_url,
    packages=['restio'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Documentation": read_the_docs_url,
        "Source Code": git_url,
    }
)
