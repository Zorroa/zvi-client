import functools
import re
import uuid


def is_valid_uuid(val):
    """
    Return true if the given value is a valid UUID.

    Args:
        val (str): a string which might be a UUID.

    Returns:
        bool: True if UUID

    """
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


def as_collection(value):
    """If the given value is not a collection of some type, return
    the value wrapped in a list.

    Args:
        value (:obj:`mixed`):

    Returns:
        :obj:`list` of :obj:`mixed`: The value wrapped in alist.

    """
    if value is None:
        return None
    if isinstance(value, (set, list, tuple, dict)):
        return value
    return [value]


class ObjectView:
    """
    Wraps a dictionary and provides an object based view.

    """
    snake = re.compile(r'(?<!^)(?=[A-Z])')

    def __init__(self, d):
        d = dict([(self.snake.sub('_', k).lower(), v) for k, v in d.items()])
        self.__dict__ = d


def as_id(value):
    """
    If 'value' is an object, return the 'id' property, otherwise return
    the value.  This is useful for when you need an entity's unique Id
    but the user passed in an instance of the entity.

    Args:
        value (mixed): A string o an object with an 'id' property.

    Returns:
        str: The id property.
    """
    return getattr(value, 'id', value)


def as_id_collection(value):
    """If the given value is not a collection of some type, return
    the value wrapped in a list.  Additionally entity instances
    are resolved into their unique id.

    Args:
        value (:obj:`mixed`):

    Returns:
        list: A list of entity unique ids.

    """
    if value is None:
        return None
    if isinstance(value, (set, list, tuple, dict)):
        return [getattr(it, "id", it) for it in value]
    return [getattr(value, "id", value)]


def memoize(func):
    """
    Cache the result of the given function.

    Args:
        func (function): A function to wrap.

    Returns:
        function: a wrapped function
    """
    cache = func.cache = {}

    @functools.wraps(func)
    def memoized_func(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return memoized_func
