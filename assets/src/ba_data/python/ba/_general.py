# Copyright (c) 2011-2020 Eric Froemling
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -----------------------------------------------------------------------------
"""Utility snippets applying to generic Python code."""
from __future__ import annotations

import types
import weakref
from typing import TYPE_CHECKING, TypeVar

import _ba

if TYPE_CHECKING:
    from typing import Any, Type
    from efro.call import Call

T = TypeVar('T')


def getclass(name: str, subclassof: Type[T]) -> Type[T]:
    """Given a full class name such as foo.bar.MyClass, return the class.

    Category: General Utility Functions

    The class will be checked to make sure it is a subclass of the provided
    'subclassof' class, and a TypeError will be raised if not.
    """
    import importlib
    splits = name.split('.')
    modulename = '.'.join(splits[:-1])
    classname = splits[-1]
    module = importlib.import_module(modulename)
    cls: Type = getattr(module, classname)

    if not issubclass(cls, subclassof):
        raise TypeError(name + ' is not a subclass of ' + str(subclassof))
    return cls


def json_prep(data: Any) -> Any:
    """Return a json-friendly version of the provided data.

    This converts any tuples to lists and any bytes to strings
    (interpreted as utf-8, ignoring errors). Logs errors (just once)
    if any data is modified/discarded/unsupported.
    """

    if isinstance(data, dict):
        return dict((json_prep(key), json_prep(value))
                    for key, value in list(data.items()))
    if isinstance(data, list):
        return [json_prep(element) for element in data]
    if isinstance(data, tuple):
        from ba import _error
        _error.print_error('json_prep encountered tuple', once=True)
        return [json_prep(element) for element in data]
    if isinstance(data, bytes):
        try:
            return data.decode(errors='ignore')
        except Exception:
            from ba import _error
            _error.print_error('json_prep encountered utf-8 decode error',
                               once=True)
            return data.decode(errors='ignore')
    if not isinstance(data, (str, float, bool, type(None), int)):
        from ba import _error
        _error.print_error('got unsupported type in json_prep:' +
                           str(type(data)),
                           once=True)
    return data


def utf8_all(data: Any) -> Any:
    """Convert any unicode data in provided sequence(s)to utf8 bytes."""
    if isinstance(data, dict):
        return dict((utf8_all(key), utf8_all(value))
                    for key, value in list(data.items()))
    if isinstance(data, list):
        return [utf8_all(element) for element in data]
    if isinstance(data, tuple):
        return tuple(utf8_all(element) for element in data)
    if isinstance(data, str):
        return data.encode('utf-8', errors='ignore')
    return data


def print_refs(obj: Any) -> None:
    """Print a list of known live references to an object."""
    import gc

    # Hmmm; I just noticed that calling this on an object
    # seems to keep it alive. Should figure out why.
    print('REFERENCES FOR', obj, ':')
    refs = list(gc.get_referrers(obj))
    i = 1
    for ref in refs:
        print('     ref', i, ':', ref)
        i += 1


def get_type_name(cls: Type) -> str:
    """Return a full type name including module for a class."""
    return cls.__module__ + '.' + cls.__name__


class _WeakCall:
    """Wrap a callable and arguments into a single callable object.

    Category: General Utility Classes

    When passed a bound method as the callable, the instance portion
    of it is weak-referenced, meaning the underlying instance is
    free to die if all other references to it go away. Should this
    occur, calling the WeakCall is simply a no-op.

    Think of this as a handy way to tell an object to do something
    at some point in the future if it happens to still exist.

    # EXAMPLE A: this code will create a FooClass instance and call its
    # bar() method 5 seconds later; it will be kept alive even though
    # we overwrite its variable with None because the bound method
    # we pass as a timer callback (foo.bar) strong-references it
    foo = FooClass()
    ba.timer(5.0, foo.bar)
    foo = None

    # EXAMPLE B: this code will *not* keep our object alive; it will die
    # when we overwrite it with None and the timer will be a no-op when it
    # fires
    foo = FooClass()
    ba.timer(5.0, ba.WeakCall(foo.bar))
    foo = None

    Note: additional args and keywords you provide to the WeakCall()
    constructor are stored as regular strong-references; you'll need
    to wrap them in weakrefs manually if desired.
    """

    def __init__(self, *args: Any, **keywds: Any) -> None:
        """
        Instantiate a WeakCall; pass a callable as the first
        arg, followed by any number of arguments or keywords.

        # Example: wrap a method call with some positional and
        # keyword args:
        myweakcall = ba.WeakCall(myobj.dostuff, argval1, namedarg=argval2)

        # Now we have a single callable to run that whole mess.
        # The same as calling myobj.dostuff(argval1, namedarg=argval2)
        # (provided my_obj still exists; this will do nothing otherwise)
        myweakcall()
        """
        if hasattr(args[0], '__func__'):
            self._call = WeakMethod(args[0])
        else:
            app = _ba.app
            if not app.did_weak_call_warning:
                print(('Warning: callable passed to ba.WeakCall() is not'
                       ' weak-referencable (' + str(args[0]) +
                       '); use ba.Call() instead to avoid this '
                       'warning. Stack-trace:'))
                import traceback
                traceback.print_stack()
                app.did_weak_call_warning = True
            self._call = args[0]
        self._args = args[1:]
        self._keywds = keywds

    def __call__(self, *args_extra: Any) -> Any:
        return self._call(*self._args + args_extra, **self._keywds)

    def __str__(self) -> str:
        return ('<ba.WeakCall object; _call=' + str(self._call) + ' _args=' +
                str(self._args) + ' _keywds=' + str(self._keywds) + '>')


class _Call:
    """Wraps a callable and arguments into a single callable object.

    Category: General Utility Classes

    The callable is strong-referenced so it won't die until this
    object does.

    Note that a bound method (ex: myobj.dosomething) contains a reference
    to 'self' (myobj in that case), so you will be keeping that object
    alive too. Use ba.WeakCall if you want to pass a method to callback
    without keeping its object alive.
    """

    def __init__(self, *args: Any, **keywds: Any):
        """
        Instantiate a Call; pass a callable as the first
        arg, followed by any number of arguments or keywords.

        # Example: wrap a method call with 1 positional and 1 keyword arg:
        mycall = ba.Call(myobj.dostuff, argval1, namedarg=argval2)

        # Now we have a single callable to run that whole mess.
        # ..the same as calling myobj.dostuff(argval1, namedarg=argval2)
        mycall()
        """
        self._call = args[0]
        self._args = args[1:]
        self._keywds = keywds

    def __call__(self, *args_extra: Any) -> Any:
        return self._call(*self._args + args_extra, **self._keywds)

    def __str__(self) -> str:
        return ('<ba.Call object; _call=' + str(self._call) + ' _args=' +
                str(self._args) + ' _keywds=' + str(self._keywds) + '>')


if TYPE_CHECKING:
    WeakCall = Call
    Call = Call
else:
    WeakCall = _WeakCall
    WeakCall.__name__ = 'WeakCall'
    Call = _Call
    Call.__name__ = 'Call'


class WeakMethod:
    """A weak-referenced bound method.

    Wraps a bound method using weak references so that the original is
    free to die. If called with a dead target, is simply a no-op.
    """

    def __init__(self, call: types.MethodType):
        assert isinstance(call, types.MethodType)
        self._func = call.__func__
        self._obj = weakref.ref(call.__self__)

    def __call__(self, *args: Any, **keywds: Any) -> Any:
        obj = self._obj()
        if obj is None:
            return None
        return self._func(*((obj, ) + args), **keywds)

    def __str__(self) -> str:
        return '<ba.WeakMethod object; call=' + str(self._func) + '>'
