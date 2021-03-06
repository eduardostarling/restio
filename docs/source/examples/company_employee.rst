.. _example_usecase:

Company Employees
=================

The step-by-step implementation of the fictitious REST API client described in this page has been done with and without **restio** (links at :ref:`example_usecase_implementation`)

Description
-----------

Let's consider a fictitious use case in which we are consuming a remote REST API that stores part-time Employees that work for Companies. We assume that an Employee can work for multiple Companies at the same time.

The REST API contains the following endpoints:

- Employees Endpoint: :code:`http://my-remote-rest-api/employees/`. Supports GET. Used to retrieve the list of all Employees registered.

- Employee Endpoint: :code:`http://my-remote-rest-api/employees/{employee_key}`. Supports GET, POST, PUT and DELETE. They allow for reading, creating, updating and deleting an Employee.

- Companies Endpoint: :code:`http://my-remote-rest-api/companies/`. Supports GET. Used to retrieve the list of all Companies registered.

- Company Endpoint: :code:`http://my-remote-rest-api/companies/{company_key}`. Supports GET. Used to retrieve a single company.

- Company Employees Endpoint: :code:`http://my-remote-rest-api/companies/{company_key}/employees`. Supports GET. Allows retrieving all the Company Employees.

- Company Employee Endpoint: :code:`http://my-remote-rest-api/companies/{company_key}/employees/{employee_key}`. Supports PUT and DELETE. Allows for hiring or firing an Employee in a Company.

NOTE: Due to specific rules of the business, it is not possible to create, alter or delete a Company from the API.

Requesting :code:`GET http://my-remote-rest-api/employees/` or :code:`GET http://my-remote-rest-api/companies/{company_key}/employees` returns a list of employees in JSON format:

.. code-block:: json

    [
        {
            "key": 1000,
            "name": "Joseph Tribiani",
            "age": 25,
            "address": "1 Granville St, Vancouver, BC, VXX XXX, Canada"
        },
        {
            "key": 1001,
            "name": "Rachel Green",
            "age": 22,
            "address": "2 Granville St, Vancouver, BC, VXX XXX, Canada"
        }
    ]

If we wish to retrieve the information from a single Employee `1000`, we may simply request :code:`GET http://my-remote-rest-api/employees/1000`. The response is:

.. code-block:: json

    {
        "key": 1000,
        "name": "Joseph Tribiani",
        "age": 25,
        "address": "1 Granville St, Vancouver, BC, VXX XXX, Canada"
    }


It is possible to create or alter an Employee by providing the following data to :code:`PUT/POST http://my-remote-rest-api/employees/1000`. Note that `key` is generated by the server and cannot be modified by the client:

.. code-block:: json

    {
        "name": "Joseph Tribiani",
        "age": 25,
        "address": "1 Granville St, Vancouver, BC, VXX XXX, Canada"
    }

.. note::
    PUT will respond with 201 in case of success, containing the header Location with the link to the newly-created resource.


The same logic applies when requesting :code:`GET http://my-remote-rest-api/companies`, which returns a list of companies in JSON format:

.. code-block:: json

    [
        {
            "key": "COMPANY_A",
            "name": "Amazing Company A"
        },
        {
            "key": "COMPANY_B",
            "name": "Not so cool Company B"
        }
    ]

.. _example_usecase_implementation:

Implementation
--------------

.. toctree::
   :maxdepth: 1

   company_employee_with_restio
   company_employee_without_restio
