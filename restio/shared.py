from typing import Dict, Type

# Stores the names for a model class type
# this object stays here and is globaly declared so that it can be
# accessed by both BaseModelMeta and Field instances
# In case we need to do any further business with this object,
# then implement a Singleton class to handle the object in a more
# structured way
MODEL_TYPE_REGISTRY: Dict[str, Type] = {}
