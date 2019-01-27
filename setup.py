import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="restio",
    version="0.0.1",
    author="Eduardo Starling",
    author_email="edmstar@gmail.com",
    description="Rest Integration Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/eduardostarling/restio.git",
    packages=['restio'],
    package_dir={'': 'src'},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'coverage'
    ]
)
