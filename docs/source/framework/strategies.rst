.. _strategies:

Strategies
==========

.. note::
  Most terms utilized in this page are described under :ref:`modules`. Please refer to it before proceeding.

This page explains the internal mechanisms of **restio**, and describes some of the design decisions made during implementation. In general, most of the items below are managed by **Session** instances separately:

- :ref:`model_uniqueness`
- :ref:`caching`
- :ref:`model_state_management`
- :ref:`commit_rollback`


.. _model_uniqueness:

Model uniqueness
----------------

In **restio**, a :code:`Model` instance (from now on referred as :code:`model` for simplicity) represents one object (to be) persisted in a remote data store through a REST API. To keep track of models representing the same data on the remote, **restio** identifies each of them uniquely by their *primary keys* and *internal UUID*.

The fields that represent the *primary keys* are statically defined by providing the :code:`Field` descriptor with :code:`pk=True` when declaring model classes (see :ref:`primary_keys`), and are loaded when retrieving the models from the remote server. In general, most models will have their primary key fields populated when retrieving data from the remote server.

It is up to the developer to choose the *primary keys* that will identify a model.

Depending on the remote REST API, some primary keys cannot be defined by the client and will be generated by the server when creating the model. In the meantime, the models will be identified in the cache exclusively by their *internal UUID*. This happens whenever one or more primary keys have the value :code:`None` in the instance. In this case, it is up to the DAO to propagate this value back to the model whenever it is available.

The *internal UUID* is automatically generated when instantiating the model, and should never be modified externally.

.. code-block:: python

    session = Session()

    # retrieving a model registers the model in the cache by its primary key
    model_retrieved = await session.get(Model, key=5)  # key is 5, _internal_id is ddc59b7e-9ad9-48cc-9361-fcd2b901e657

    # creating a model with empty primary key registers it in the cache by its internal uuid
    new_model = Model(key=None)   # key is None, _internal_id is cad0d71c-dc4d-4722-adf1-712d798bdfdb
    session.add(new_model)    # model is registered to the cache based on its _internal_id

    # persists to the server
    await session.comit()

    # now both models are registered in the cache by their primary keys
    model_retrieved  # key is 5, _internal_id is ddc59b7e-9ad9-48cc-9361-fcd2b901e657
    new_model        # key is 1234 (generated by the server), _internal_id is cad0d71c-dc4d-4722-adf1-712d798bdfdb

    # model is retrieved from the cache
    new_model_retrieve = await session.get(Model, key=1234)  # key is 1234, _internal_id is cad0d71c-dc4d-4722-adf1-712d798bdfdb

    assert new_model == new_model_retrieve  # True

Other things to keep in mind:

- Primary keys will be organized in order of declaration in the model class. In case of class inheritance, the field ordering will be in reverse MRO (parent first).
- Changing a model's primary key will have immediate effect to the instances, but will only be propagated into the session's cache after the session is commited (see :code:`commit_rollback` below for more details). You can force this behavior earlier by calling :code:`Session.update_cache()`.

When calling :code:`Session.get(ModelType, key1=primary_key1, key2=primary_key2, ...)`, session instances will propagate the request to DAOs for retrieving models from the remote if they don't exist in cache yet. The values in the :code:`primary_keys` tuple will dictate the search in cache that happens before this call, so keep this in mind when choosing the fields that will truly behave as identifiers (see :ref:`caching` for more details).

.. _caching:

Caching
-------

Every **Session** contains its own internal cache. The cache is composed by two in-memory data stores:

- Model Cache
- Query Cache

The **Model Cache** is the ultimate source of truth for storing values in the :code:`Session`. Every model retrieved from :code:`Session.get` and :code:`Session.query`, or passed to :code:`Session.add` is registered in the **Model Cache** (if it is not there yet). A model can be identified in the **Model Cache** by either its *primary keys* or its *internal UUID*.

On the other hand, the **Query Cache** is a secondary mechanism to optimize the interaction with the remote API that would in most cases happen via multiple calls to :code:`Session.get`. Cached queries always hold references to models registered in the **Model Cache** and don't depend on the involved primary keys. Queries are identified by their instance types and the parameters provided.

The session cache is valid while the session instance exists. To eliminate the cache, the developer can either dispose from it and start a new session, or call :code:`Session.reset()`. Sessions with lots of cached models tend to be slower when retrieving new data due to the internal search mechanism that prevents duplication.

Possible inconsistencies between values retrieved from the remote and the local cache will cause the session to ignore the incoming data and favor the locally stored models. This is done to guarantee atomicity of operations within the session scope. **It is up to the developer to define the consistency boundaries of the application and create a workflow that will reduce the chance of overriding data on the remote server**.

.. _model_state_management:

Model State Management
----------------------

Each model in a session contains an internal state. When calling :code:`Session.commit()` or :code:`Session.rollback()`, the session uses the state of the models to decide how to propagate data to the remote server.

Below, a list of possible states a model can hold:

+-----------+--------------------------------------------------------------------------------------------------+
| State     | Description                                                                                      |
+===========+==================================================================================================+
| UNBOUND   | The model has been instantiated locally but is not bound to any session.                         |
+-----------+--------------------------------------------------------------------------------------------------+
| CLEAN     | The model has been retrieved from the remote and has not been modified locally.                  |
+-----------+--------------------------------------------------------------------------------------------------+
| NEW       | The model has been instantiated locally and marked in the session to be added during commit.     |
+-----------+--------------------------------------------------------------------------------------------------+
| DIRTY     | The model has been retrieved from the remote and has been modified locally.                      |
+-----------+--------------------------------------------------------------------------------------------------+
| DELETED   | The model has been retrieved from the remote and has been marked for deletion.                   |
+-----------+--------------------------------------------------------------------------------------------------+
| DISCARDED | The model has been registered in the internal cache and marked to be discarded.                  |
+-----------+--------------------------------------------------------------------------------------------------+

The session is resposible for coordinating the state of each model in its cache. Each model is by default marked as **UNBOUND** when instantiated. When binding to a session, the model will have its state set to:

- **CLEAN**, when retrieved from the remote server through :code:`Session.get` or :code:`Session.query`.
- **NEW**, when marked for adding through :code:`Session.add` for the first time.

Subsequent operations to the model will either cause its state to change to:

- **DIRTY**, when the value of at least one model field changes when compared to persistent values.
- **DELETED**, when marked for deletion through :code:`Session.remove`.
- **DISCARDED**, when marked for deletion after adding, when deleted during :code:`Session.commit`, or when disposed via :code:`Session.reset()`.

.. warning::
    Models with fields containing mutable collections (lists, sets or dicts) will not automatically be marked as **DIRTY** if items get added, removed or reordered. **restio** does not provide such fields out-of-the-box for this reason, and you should use immutable collections instead (e.g. :code:`TupleField`, :code:`FrozenSetField`, etc).


Model data
^^^^^^^^^^

Each model instance stores two dictionaries of data internally.

- The first set contains the actual values of the models. These values can be retrieved and modified normally by accessing the fields of the instance.
- The second set stores the persistent values for each modified field, so it is possible to evaluate the overall state of a model after each change. This also makes it possible to rollback models to their previous persistent state.

When dealing with data, the developer will most likely only need to access the regular fields of the models. However, in :code:`DAO.update` it might be handy to check which fields changed by accessing the :code:`model._persistent_values` attribute. By doing that, the developer is able to:

- Efficiently select fewer endpoints for modifying each model based on the changed fields.
- Reduce the chance of data inconsistency when persisting changes to the remote API.


.. _commit_rollback:

Commit and Rollback
-------------------

Commit and Rollback rely on the state of each model for decision making. Below, a description of how they work.

Commit
^^^^^^

Models are persisted to the remote data store during :code:`commit`. The :code:`Session` will try to schedule as many :code:`asyncio` tasks as possible to optimize the calls to the remote server - this is done to reduce the total time to commit all models.

The logic for deciding the order in which models are persisted is the following:

1. Models are distributed in three groups, according to their state (:code:`NEW`, :code:`DIRTY` and :code:`DELETED`).

2. The models in any of the groups are inspected to make sure there is one DAO associated to each model. The DAO methods are also checked, and if one of them is missing, the commit is interrupted immediately before any task runs.

3. Models on the :code:`DELETED` group are inspected one-by-one. If any of these models contain at least one cached parent pointing to it that will still be persisted on the remote data store (in other words, parents that will not be deleted), then the commit is interrupted immediately before any task runs.

4. Three dependency graphs are drawn. The first graph includes only models with state :code:`NEW`, the second only models with state :code:`DIRTY` and the third only models with state :code:`DELETED`. On all graphs, the parents of a model are the models referring to it in the same group, while the children are the models referred by it.

5. The graphs are processed in order. The trees in :code:`NEW` and :code:`DIRTY` graphs are traversed from top to bottom (parents to children), while in the :code:`DELETED` graph the trees are traversed from bottom to top (children to parents). All operations from one graph need to be finalized so the next graph can be processed. Operations within each graph are optimized as follows:

  - All trees in a graph are processed in parallel in the :code:`asyncio` event loop.
  - Each group of nodes are scheduled in parallel in the :code:`asyncio` event loop.
  - As soon as a node is processed, the next node(s) is (are) scheduled to be persisted if the tree structure allows (that means, if all children of a particular node have been processed, that node can be processed). Otherwise, the processor awaits until a new node is finished, and the inspection for a new node restarts.
  - If an error occurs, the processing will be conditioned to the :code:`PersistencyStrategy` defined for the session. This should be set per session scope and the choice might vary according to the use case:

    - :code:`INTERRUPT_ON_ERROR` will cause the commit to interrupt the scheduling of new nodes and will wait until current processes finalize.
    - :code:`CONTINUE_ON_ERROR` will cause the commit to ignore the error messages and continue processing all available nodes.

  - Models that have been persisted on the remote will be also persisted on the local cache, while models not processed or processed with error are not persisted on cache. This behavior does not depend on the :code:`PersistencyStrategy`. Models that have been deleted will be discarded from cache, and models that changed primary keys will be re-registered after the commit is done.

6. All processed actions performed by the DAOs are returned by the :code:`commit` in the form of a list of :code:`DAOTask`. Each :code:`DAOTask` can then be awaited after the commit. Tasks that raised an :code:`Exception` during the commit will then raise it once more upon awaiting.

Rollback
^^^^^^^^

Rollbacks do not affect the data on the remote data store. The term here is used for rolling back changes on the internal cache that have not yet been persisted on the remote. This is particularly useful if a certain business rule is violated but the developer still wants to utilize the values from the cache without requesting for the whole data again.

Rolling back will behave as follows:

- Models marked as :code:`NEW` and :code:`DELETED` will be marked as :code:`DISCARDED`.
- Models marked as :code:`DIRTY` will be reverted to :code:`CLEAN` and the persistent internal values recovered.
- All :code:`DISCARDED` models are removed from the cache.
