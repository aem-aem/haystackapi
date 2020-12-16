# -*- coding: utf-8 -*-
# CSV Grid Parser
# (C) 2020 Philippe PRADOS
#
# vim: set ts=4 sts=4 et tw=78 sw=4 si:
"""
Parse CSV file conform with the specification describe here (https://www.project-haystack.org/doc/Csv)
and produce a `Grid` instance.
"""
from csv import reader
from io import StringIO

from .datatypes import MARKER, Ref
from .grid import Grid
from .version import VER_3_0
from .zincparser import parse_scalar as zinc_parse_scalar, ZincParseException


def parse_grid(grid_str):
    version = VER_3_0
    # for row in csv.reader(grid_str.splitlines()): print(row)
    csv_reader = reader(StringIO(grid_str))
    i = iter(csv_reader)
    headers = next(i)
    grid = Grid(version=version, columns=((x, {}) for x in headers))
    for row in i:
        a_map = {}
        for idx, val in enumerate(row):
            value = parse_scalar(val, version)
            if value is not _EMPTY:
                if idx >= len(headers):
                    raise ZincParseException('Failed to parse scalar: %s' % value, grid_str, 1, 1)
                if value is not None:
                    a_map[headers[idx]] = value
        grid.append(a_map)
    return grid


_EMPTY = "<empty>"


def parse_scalar(scalar, version):
    if scalar == '':
        return _EMPTY
    if scalar == u'\u2713':
        return MARKER
    if scalar == 'true':
        return True
    if scalar == 'false':
        return False
    if scalar[0] == '@':
        return Ref(*scalar[1:].split(' ', 1))
    try:
        return zinc_parse_scalar(scalar, version)  # Date, Time, ... ?
    except ZincParseException:
        return scalar  # It's a simple string
