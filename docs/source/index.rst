Introduction
============

**restio** is an asynchronous ORM-like framework that provides a generic approach for consuming remote REST APIs. It offers the following advantages over a regular REST API Client:

- Clear decoupling between models and data access logic.
- Client-side caching of models and queries.
- Improved performance for nearly all operations with native use of `asyncio`.
- Type-checking and data validation.
- Model state management.
- Rich relational models and dependency management.


Step-by-step implementation of fictitious REST API Clients have been implemented. You can access them in the following pages:

- :ref:`example_usecase`


Requirements
============

- Python 3.7+

Pip
---

You can install **restio** as a dependency to your project with pip:

.. code-block:: bash

   pip install restio


Documentation
=============

.. toctree::
   :maxdepth: 2
   :caption: Documentation

   framework/framework

.. toctree::
   :maxdepth: 1

   changelog

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/company_employee

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   framework/api


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
