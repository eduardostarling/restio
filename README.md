# restio

## Introduction

When consuming remote REST APIs, the workflow done on the Business Logic Layer (BLL) of an application differentiates from that done in relational databases. On backend multi-tiered applications, it is common to use transactions to guarantee atomicity when persisting data on these databases. For remote APIs, however, this becomes a more cumbersome job, as the application has no control or knowledge of when things will go wrong on the remote server. Adding to that, each interaction with the remote server can be an expensive operation, which makes the management of the remote requests a challenge on the BLL.

In order to tackle this and other issues, the *restio* framework has been created to facilitate the evolution and maintenance of Python applications that access one or several REST APIs at the same time.

This framework relies on a few building blocks that build on top of already existing REST Client libraries. You can read more about them [here](docs/source/FRAMEWORK.md).

## Installation

### Requirements

- Python 3.7+

### Pip

You can install **restio** as a dependency to your project with pip:

```bash
pip install restio
```