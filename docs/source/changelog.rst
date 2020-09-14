Changelog
=========

1.0.0b2
-------

- Fixed bug that failed to properly check trees of models with deleted state.
- Fixed bug that would maintain an incorrect persistent state of models when a model was unbound from a transaction.
- Added support for Field Setters with the :code:`Field.setter` decorator in models.
- Added support for the built-in python :code:`@property` in models.
- Added restriction in which it is not possible anymore to register a model after it has been discarded. Also, during a :code:`Transaction.reset()` all models are now marked as discarded.
- Added check that rejects model attribute updates when the provided values depend on models that are not yet in the transaction cache.
- Added a static method :code:`Transaction.raise_for_status(tasks)` that raises a :code:`TransactionException` with all the :code:`tasks` that failed and all that succeeded during a :code:`Transaction.commit()`.
- **BREAKING CHANGE**: Changed the behavior of :code:`Transaction.commit()` to automatically call :code:`Transaction.raise_for_status()` whenever :code:`raise_for_status=True` (default).
- Improved performance when registering objects to the transaction cache. Registering a new object to a transaction that already contains many models registered will now be faster. Also, applies when queries retrieve multiple objects at once.
- **BREAKING CHANGE**: :code:`BaseModel.get_children()` now returns a :code:`Set` instead of a :code:`List`. This also applies to the input argument :code:`children`.


1.0.0b1
-------

.. warning::
    Several important breaking changes were introduced in this version.

- Main modules cannot be imported directly from top-level :code:`restio` module anymore. You will now need to import from the submodules directly (e.g. what used to be :code:`from restio import BaseModel` should now be :code:`from restio.model import BaseModel`, and so on).
- Added support for descriptors using the base type :code:`Field` (:code:`restio.fields.Field`). The following types of Fields are natively available (please visit :ref:`fields` for all details):

    - IntField
    - StrField
    - BoolField
    - TupleField
    - FrozenSetField
    - ModelField
    - TupleModelField
    - FrozenSetModelField

- Behavior of :code:`BaseModel` has been refactored to support :code:`Field`. The side effect is that **dataclasses are no longer supported**, and classes **should use the descriptor protocol** to define fields that must be tracked by **restio**. As part of that:

    - :code:`PrimaryKey` and :code:`ValueKey` have been removed, in favor of :code:`Field(pk=True)`.
    - :code:`mdataclass` has been removed.
    - :code:`BaseModel.pre_setup_model` and :code:`BaseModel.post_setup_model` have been removed.
    - Model dependencies are now tracked via fields with :code:`depends_on=True`.
    - :code:`BaseModel.get_keys()` method has been replaced for the property :code:`BaseModel.primary_keys`, which now returns a dictionary.
    - A new model state :code:`UNBOUND` has been introduced. All new instances of a model will by default have this state until it is added to a transaction.

- :code:`BaseDAO` now contains an internal attribute :code:`transaction` of type :code:`Transaction`. This field will always contain the instance of the transaction to which the DAO instance is bound.
- :code:`Transaction.get` now requires keyword-only arguments to be provided when passing primary keys. Calls with missing primary keys will fail immediately.
- :code:`Transaction.get` will no longer return :code:`None` when no models are found by the DAO or in the cache. Instead, a :code:`RuntimeError` will be raised.
- :code:`Transaction.get` and :code:`Transaction.query` will no longer automatically register model dependencies (children). This is done to encourage the use of the :code:`Transaction` from within the DAOs or queries when retrieving multiple models at the same time.
- In queries, the use of the :code:`self` keyword (that received the injected :code:`Transaction` instance) has been replaced by an optional keyword-only argument :code:`transaction`.
- :code:`Transaction.query` will now always return :code:`tuple` as a result, regardless of the return type of the query.
- :code:`@query`-annotated functions should now return any Iterable type. The order of the results is preserved in the :code:`tuple` returned by :code:`Transaction.query`.
- Type-hinting should now work better than before.
- The old concept of **mutability** (indicating if a field can change or not within the premises of **restio**) has been droped from the framework. From now on, when we refer to :code:`mutable` attributes/fields we literally mean the `general concept of mutability <https://en.wikipedia.org/wiki/Immutable_object>`_.
- Documentation have been completely refactored to include latest changes and more practical examples. The old examples have been removed.
- A number of bugs have been fixed.


0.3.0 & older
-------------

<not available>
