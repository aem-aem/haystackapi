#!/usr/bin/python
# -*- coding: utf-8 -*-
# Zinc data types
# (C) 2016 VRT Systems
#
# vim: set ts=4 sts=4 et tw=78 sw=4 si:

import six

from . import PINT_AVAILABLE

if PINT_AVAILABLE:
    from . import ureg
    from .pint import to_pint

from abc import ABCMeta

STR_SUB  = [
    ('\b',  '\\b'),
    ('\f',  '\\f'),
    ('\n',  '\\n'),
    ('\r',  '\\r'),
    ('\t',  '\\t'),
]

# Will keep in memory the way we want Quantity being created
MODE_PINT = False
def use_pint(val = True):
    global MODE_PINT
    if val:
        #print('Switching to Pint')
        if PINT_AVAILABLE:
            MODE_PINT = True
        else:
            raise ImportError('Pint not installed. Use pip install pint if needed')
    else:
        #print('Back to default Quantity')
        MODE_PINT = False

class Quantity(metaclass=ABCMeta):
    def __new__(self, value, unit = None):
        if MODE_PINT:
            return Quantity_Pint(value, unit)
        else:
            return Quantity_Default(value, unit)
            
class Qty(object):
    '''
    A quantity is a scalar value (floating point) with a unit.
    '''
    def __init__(self, value, unit):
        self.value = value
        self.unit = unit     

class Quantity_Default(Qty):
    '''
    Default class to be used to define Quantity.
    
    '''
    def __init__(self, value, unit):
        super(Quantity_Default, self).__init__(value, unit)
        

    def __repr__(self):
        return '%s(%r, %r)' % (
                self.__class__.__name__, self.value, self.unit
        )

    def __str__(self):
        return '%s %s' % (
                self.value, self.unit
        )

    def __index__(self):
        return self.value.__index__()

    def __oct__(self):
        return oct(self.value)

    def __hex__(self):
        return hex(self.value)

    def __int__(self):
        return int(self.value)

    def __long__(self):
        return long(self.value)

    def __complex__(self):
        return complex(self.value)

    def __float__(self):
        return float(self.value)

    def __neg__(self):
        return -self.value

    def __pos__(self):
        return +self.value

    def __abs__(self):
        return abs(self.value)

    def __invert__(self):
        return ~self.value

    def __add__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value + other

    def __sub__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value - other

    def __mul__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value * other

    def __div__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value / other

    def __truediv__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value / other

    def __floordiv__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value // other

    def __mod__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value % other

    def __divmod__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return divmod(self.value, other)

    def __pow__(self, other, modulo=None):
        if isinstance(other, Quantity_Default):
            other = other.value
        return pow(self.value, other, modulo)

    def __lshift__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value << other

    def __rshift__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value >> other

    def __and__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value & other

    def __xor__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value ^ other

    def __or__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return self.value | other

    def __radd__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other + self.value

    def __rsub__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other - self.value

    def __rmul__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other * self.value

    def __rdiv__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other / self.value

    def __rtruediv__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other / self.value

    def __rfloordiv__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other // self.value

    def __rmod__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other % self.value

    def __rdivmod__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return divmod(other, self.value)

    def __rpow__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return pow(other, self.value)

    def __rlshift__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other << self.value

    def __rrshift__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other >> self.value

    def __rand__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other & self.value

    def __rxor__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other ^ self.value

    def __ror__(self, other):
        if isinstance(other, Qty):
            other = other.value
        return other | self.value

    def _cmp_op(self, other, op):
        if isinstance(other, Qty):
            if other.unit != self.unit:
                raise TypeError('Quantity units differ: %s vs %s' \
                        % (self.unit, other.unit))
            return op(self.value, other.value)
        return op(self.value, other)

    def __lt__(self, other):
        return self._cmp_op(other, lambda x, y : x < y)

    def __le__(self, other):
        return self._cmp_op(other, lambda x, y : x <= y)

    def __eq__(self, other):
        return self._cmp_op(other, lambda x, y : x == y)

    def __ge__(self, other):
        return self._cmp_op(other, lambda x, y : x >= y)

    def __gt__(self, other):
        return self._cmp_op(other, lambda x, y : x > y)

    def __ne__(self, other):
        return self._cmp_op(other, lambda x, y : x != y)

    def __cmp__(self, other):
        if self == other:
            return 0
        elif self < other:
            return -1
        else:
            return 1

    def __hash__(self):
        return hash((self.value, self.unit))

Quantity.register(Quantity_Default)

if PINT_AVAILABLE:        
    class Quantity_Pint(Qty, ureg.Quantity):
        '''
        A quantity is a scalar value (floating point) with a unit.
        This object uses Pint feature allowing conversion between units
        for example : 
            a = hszinc.Q_(19, 'degC')
            a.to('degF')
        See https://pint.readthedocs.io for details
        '''
        def __init__(self, value, unit):
            super(Quantity_Pint, self).__init__(value, unit)
    Quantity.register(Quantity_Pint)
else:
    # If things turn really bad...just in case.
    Quantity_Pint = Quantity_Default
    to_pint = lambda unit: unit



            
def quantity(value, unit = None):
    """
    Factory to create Quantity object depending on MODE_PINT
    value can be a Quantity itself, allowing conversion between Pint and Default
    """
    if isinstance(value, Quantity) and MODE_PINT:
        return Quantity_Pint(value.value, to_pint(value.unit))
    elif isinstance(value, Quantity) and not MODE_PINT:
        return Quantity_Default(value.value, to_pint(value.unit))
    
    if float(value) and MODE_PINT:
        return Quantity_Pint(value, to_pint(unit))
    elif float(value) and not MODE_PINT:
        return Quantity_Default(value, unit)

    else:
        raise ValueError('Provide value, unit or quantity as argument')


        
class Coordinate(object):
    '''
    A 2D co-ordinate in degrees latitude and longitude.
    '''
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude

    def __repr__(self):
        return '%s(%r, %r)' % (
                self.__class__.__name__, self.latitude, self.longitude
        )

    def __str__(self):
        return '%f° lat %f° long' % (
                self.latitude, self.longitude
        )

    def __eq__(self, other):
        if not isinstance(other, Coordinate):
            raise TypeError('%r is not a Coordinate or subclass' % other)
        return (self.latitude == other.latitude) and \
                (self.longitude == other.longitude)

    def __neq__(self, other):
        return not (self == other)


class Uri(six.text_type):
    '''
    A convenience class to allow identification of a URI from other string
    types.
    '''
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                        super(Uri, self).__repr__())

    def __eq__(self, other):
        if not isinstance(other, Uri):
            raise TypeError('%r is not a Uri' % other)
        return super(Uri, self).__eq__(other)


class Bin(six.text_type):
    '''
    A convenience class to allow identification of a Bin from other string
    types.
    '''
    # TODO: This seems to be the MIME type, no idea where the data lives.
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                        super(Bin, self).__repr__())

    def __eq__(self, other):
        if not isinstance(other, Bin):
            raise TypeError('%r is not a Bin' % other)
        return super(Bin, self).__eq__(other)

class Singleton(object):
    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

class MarkerType(Singleton):
    '''
    A singleton class representing a Marker.
    '''
    def __repr__(self):
        return 'MARKER'

MARKER = MarkerType()

class RemoveType(Singleton):
    '''
    A singleton class representing a Remove.
    '''
    def __repr__(self):
        return 'REMOVE'

REMOVE = RemoveType()


class Ref(object):
    '''
    A reference to an object in Project Haystack.
    '''
    # TODO: The grammar specifies that it can have a string following a space,
    # but the documentation does not specify what this string encodes.  This is
    # distinct from the reference name itself immediately following the @
    # symbol.  I'm guessing it's some kind of value.
    def __init__(self, name, value=None, has_value=False):
        self.name       = name
        self.value      = value
        self.has_value  = has_value or (value is not None)

    def __repr__(self):
        return '%s(%r, %r, %r)' % (
                self.__class__.__name__, self.name, self.value, self.has_value
        )

    def __str__(self):
        if self.has_value:
            return '@%s %r' % (
                    self.name, self.value
            )
        else:
            return '@%s' % self.name

    def __eq__(self, other):
        if not isinstance(other, Ref):
            raise TypeError('%r is not a Ref or subclass' % other)
        return (self.name == other.name) and \
                (self.has_value == other.has_value) and \
                (self.value == other.value)

    def __neq__(self, other):
        return not (self == other)
