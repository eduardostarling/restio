import setuptools

import restio

with open("README.md", "r") as fh:
    long_description = fh.read()

git_url = "https://github.com/eduardostarling/restio.git"

setuptools.setup(
    name=restio.__name__,
    version=restio.__version__,
    author=restio.__author__,
    author_email=restio.__email__,
    description="restio Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["restio"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    url=git_url,
    project_urls={
        "Source Code": git_url,
        "Documentation": "https://restio.readthedocs.io/en/latest/",
    },
    python_requires=">=3.7",
)
