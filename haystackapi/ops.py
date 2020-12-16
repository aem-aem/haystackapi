""" Haystack API implemented with HTTP generic layer.

    The environment variable `HAYSTACK_PROVIDER` is use to
    route the HTTP request to the specified provider.

    Upper of this API, you can find a Flask, AWS Lambda, etc.
"""
from __future__ import annotations

import base64
import codecs
import gzip
import logging
import os
import re
import traceback
from ast import literal_eval
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Any, Match, List, cast
from typing import Tuple, Dict

from accept_types import AcceptableType, get_best_match

from .datatypes import Ref, Quantity, MARKER
from .dumper import dump
from .grid import Grid, VER_3_0
from .grid_filter import parse_hs_date_format
from .parser import MODE_ZINC, MODE_CSV, MODE_JSON, parse_scalar, parse, mode_to_suffix
from .providers.haystack_interface import (
    EmptyGrid,
    HttpError, get_singleton_provider, parse_date_range,
)

_DEFAULT_VERSION = VER_3_0
DEFAULT_MIME_TYPE: str = MODE_CSV
_DEFAULT_MIME_TYPE_WITH_METADATA = MODE_ZINC

log = logging.getLogger("haystackapi")


@dataclass
class HaystackHttpRequest:
    """
    A wrapper between http request and Haystack API provider.
    """

    body: str = ""
    args: Dict[str, str] = field(default_factory=lambda: ({}))
    is_base64: bool = False
    headers: Dict[str, str] = field(
        default_factory=lambda: (
            {"Host": "localhost", "Content-Type": "text/text", "Accept": "*/*"}
        )
    )


@dataclass
class HaystackHttpResponse:
    """
    A wrapper between http response and Haystack API provider.
    """

    status_code: int = 200
    status: str = "OK"
    headers: Dict[str, str] = field(
        default_factory=lambda: ({"Content-Type": "text/text"})
    )
    body: str = ""


_COMPRESS_TYPE_STR = r"[a-zA-Z0-9._-]+"

# Matches either '*', 'image/*', or 'image/png'
_valid_encoding_type = re.compile(r"^(?:[a-zA-Z-]+)$")

# Matches the 'q=1.23' from the parameters of a Accept mime types
_q_match = re.compile(r"(?:^|;)\s*q=([0-9.-]+)(?:$|;)")


class _AcceptableEncoding:
    encoding_type = None
    weight = Decimal(1)
    pattern = None

    def __init__(self, raw_encoding_type):
        bits = raw_encoding_type.split(";", 1)

        encoding_type = bits[0]
        if not _valid_encoding_type.match(encoding_type):
            raise ValueError(f'"{encoding_type}" is not a valid encoding type')

        tail = ""
        if len(bits) > 1:
            tail = bits[1]

        self.encoding_type = encoding_type
        self.weight = _get_weight(tail)
        self.pattern = re.compile("^" + re.escape(encoding_type) + "$")

    def matches(self, encoding_type: str) -> Optional[Match[Any]]:
        """
        Return true if encoding_type match the pattern
        """
        return self.pattern.match(encoding_type)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        display = self.encoding_type
        if self.weight != Decimal(1):
            display += "; q=%0.2f" % self.weight

        return display

    def __repr__(self):
        return "<AcceptableType {0}>".format(self)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, _AcceptableEncoding):
            return False
        return (self.encoding_type, self.weight) == (other.encoding_type, other.weight)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, _AcceptableEncoding):
            raise ValueError("Parameter invalid")
        return self.weight < other.weight


def get_best_encoding_match(
        header: str, available_encoding: List[str]
) -> Optional[str]:
    """
    Return best encoding match.
    """
    acceptable_types = _parse_header(header)

    for acceptable_type in acceptable_types:
        for available_type in available_encoding:
            if acceptable_type.matches(available_type):
                return available_type

    return None


def _parse_header(header: str) -> List[AcceptableType]:
    """Parse an ``Accept`` header into a sorted list of :class:`AcceptableType`
    instances.
    """
    raw_encoding_types = header.split(",")
    encoding_types = []
    for raw_encoding_type in raw_encoding_types:
        try:
            encoding_types.append(_AcceptableEncoding(raw_encoding_type.strip()))
        except ValueError:
            pass

    return sorted(encoding_types, reverse=True)


def _get_weight(tail):
    """Given the tail of a mime type header (the bit after the first ``;``),
    find the ``q`` (weight, or quality) parameter.

    If no valid ``q`` parameter is found, default to ``1``, as per the spec.
    """
    match = re.search(_q_match, tail)
    if match:
        try:
            return Decimal(match.group(1))
        except ValueError:
            pass

    # Default weight is 1
    return Decimal(1)


def _parse_body(request: HaystackHttpRequest) -> Grid:
    if "Content-Encoding" in request.headers and request.is_base64:
        content_encoding = request.headers["Content-Encoding"]
        if content_encoding != "gzip":
            raise ValueError(f"Content-Encoding '{content_encoding}' not supported")
        body = codecs.decode(str.encode(request.body), "unicode-escape")
        log.debug("decode body=%s", body)
        request.body = gzip.decompress(base64.b64decode(body)).decode("utf-8")
        request.isBase64Encoded = False
    if "Content-Type" not in request.headers:
        grid = parse(request.body, mode=DEFAULT_MIME_TYPE)
    else:
        content_type = request.headers["Content-Type"]
        if mode_to_suffix(content_type):
            grid = parse(request.body, mode=content_type)
        elif request.body:
            raise HttpError(406, f"Content-Type '{content_type}' not supported")
        else:
            grid = Grid(version=VER_3_0)
    if grid is None:
        grid = EmptyGrid
    return grid


def _format_response(
        headers: Dict[str, str],
        grid_response: Grid,
        status_code: int,
        status_msg: str,
        default=None,
) -> HaystackHttpResponse:
    hs_response = _dump_response(
        headers.get("Accept", DEFAULT_MIME_TYPE), grid_response, default=default
    )

    response = HaystackHttpResponse(
        status_code=status_code, status=status_msg, body=hs_response[1]
    )
    response.headers["Content-Type"] = hs_response[0]
    return response


def _dump_response(
        accept: str, grid: Grid, default: Optional[str] = None
) -> Tuple[str, str]:
    accept_type = get_best_match(
        accept, ["*/*", MODE_CSV, MODE_ZINC, MODE_JSON]
    )
    if accept_type:
        if accept_type in (DEFAULT_MIME_TYPE, "*/*"):
            return (
                DEFAULT_MIME_TYPE + "; charset=utf-8",
                dump(grid, mode=DEFAULT_MIME_TYPE),
            )
        if accept_type == MODE_ZINC:
            return (
                MODE_ZINC + "; charset=utf-8",
                dump(grid, mode=MODE_ZINC),
            )
        if accept_type == MODE_JSON:
            return (
                MODE_JSON + "; charset=utf-8",
                dump(grid, mode=MODE_JSON),
            )
        if accept_type == MODE_CSV:
            return (
                MODE_CSV + "; charset=utf-8",
                dump(grid, mode=MODE_CSV),
            )
    if default:
        return (
            default + "; charset=utf-8",
            dump(grid, mode=default),
        )  # Return HTTP 403 ?

    raise HttpError(406, f"Accept '{accept}' not supported")


def _manage_exception(
        headers: Dict[str, str], ex: Exception, stage: str
) -> HaystackHttpResponse:
    log.error(traceback.format_exc())
    error_grid = Grid(
        version=_DEFAULT_VERSION,
        metadata={
            "err": MARKER,
            "id": "badId",
            "errTrace": traceback.format_exc() if stage == "dev" else "",
        },
        columns=[("id", [("meta", None)])],
    )
    status_code = 400
    status_msg = "ERROR"
    if isinstance(ex, HttpError):
        ex_http = cast(HttpError, ex)
        status_code = ex_http.error
        status_msg = ex_http.msg
    return _format_response(
        headers,
        error_grid,
        status_code,
        status_msg,
        default=_DEFAULT_MIME_TYPE_WITH_METADATA,
    )


def about(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """ Implement Haystack 'about' with AWS Lambda """
    headers = request.headers
    log.debug("HAYSTACK_PROVIDER=%s", os.environ.get("HAYSTACK_PROVIDER", None))
    log.debug("HAYSTACK_URL=%s", os.environ.get("HAYSTACK_URL", None))
    try:
        provider = get_singleton_provider()
        if headers["Host"].startswith("localhost:"):
            home = "http://" + headers["Host"] + "/"
        else:
            home = "https://" + headers["Host"] + "/" + stage
        grid_response = provider.about(home)
        assert grid_response is not None
        return _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def ops(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """ Implement Haystack 'ops' with AWS Lambda """
    headers = request.headers
    try:
        provider = get_singleton_provider()
        grid_response = provider.ops()
        assert grid_response is not None
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def formats(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """ Implement Haystack 'formats' with AWS Lambda """
    headers = request.headers
    try:
        provider = get_singleton_provider()
        grid_response = provider.formats()
        if grid_response is None:
            grid_response = Grid(
                version=_DEFAULT_VERSION,
                columns={
                    "mime": {},
                    "receive": {},
                    "send": {},
                },
            )
            grid_response.extend(
                [
                    {
                        "mime": MODE_ZINC,
                        "receive": MARKER,
                        "send": MARKER,
                    },
                    {
                        "mime": MODE_JSON,
                        "receive": MARKER,
                        "send": MARKER,
                    },
                    {
                        "mime": MODE_CSV,
                        "receive": MARKER,
                        "send": MARKER,
                    },
                ]
            )
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def read(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `read` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        read_ids = select = read_filter = date_version = None
        limit = 0
        if grid_request:
            if "id" in grid_request.column:
                read_ids = grid_request
            else:
                if "filter" in grid_request.column:
                    read_filter = grid_request[0].get("filter", "")
                else:
                    read_filter = ""
                if "limit" in grid_request.column:
                    limit = int(grid_request[0].get("limit", 0))
            if "select" in grid_request.column:
                select = grid_request[0].get("select", "*")
            date_version = (
                grid_request[0].get("version", None) if grid_request else None
            )

        # Priority of query string
        if args:
            if "id" in args:
                read_ids = Grid(version=grid_request.version, columns=["id"])
                for i in args["id"].split(","):
                    read_ids.append({"id": Ref(i)})
            else:
                if "filter" in args:
                    read_filter = args["filter"]
                if "limit" in args:
                    limit = int(args["limit"])
            if "select" in args:
                select = args["select"]
            if "version" in args:
                date_version = parse_hs_date_format(args["version"].split(" "))

        if read_ids is None and read_filter is None:
            raise ValueError("'id' or 'filter' must be set")
        log.debug(
            "id=%s select='%s' filter='%s' limit=%s, date_version=%s",
            read_ids,
            select,
            read_filter,
            limit,
            date_version,
        )
        grid_response = provider.read(limit, select, read_ids, read_filter, date_version)
        assert grid_response is not None
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def nav(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `nav` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        nav_id = None
        if grid_request:
            if "navId" in grid_request.column:
                nav_id = grid_request[0]["navId"]
        if args:
            if "navId" in args:
                nav_id = args["navId"]
        grid_response = provider.nav(nav_id=nav_id)
        assert grid_response is not None
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def watch_sub(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `watch_sub` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        watch_dis = watch_id = lease = None
        ids = []
        if grid_request:
            watch_dis = grid_request.metadata["watchDis"]
            watch_id = grid_request.metadata.get("watchId", None)
            if "lease" in grid_request.metadata:
                lease = int(grid_request.metadata["lease"])
            ids = [row["id"] for row in grid_request]

        if args:
            if "watchDis" in args:
                watch_dis = args["watchDis"]
            if "watchId" in args:
                watch_id = args["watchId"]
            if "lease" in args:
                lease = int(args["lease"])
            if "ids" in args:  # Use list of str
                ids = [Ref(x[1:]) for x in literal_eval(args["ids"])]
        if not watch_dis:
            raise ValueError("'watchDis' and 'watchId' must be setted")
        grid_response = provider.watch_sub(watch_dis, watch_id, ids, lease)
        assert grid_response is not None
        assert "watchId" in grid_response.metadata
        assert "lease" in grid_response.metadata
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def watch_unsub(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `watch_unsub` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        close = False
        watch_id = False
        ids = []
        if grid_request:
            if "watchId" in grid_request.metadata:
                watch_id = grid_request.metadata["watchId"]
            if "close" in grid_request.metadata:
                close = bool(grid_request.metadata["close"])
            ids = [row["id"] for row in grid_request]

        if args:
            if "watchId" in args:
                watch_id = args["watchId"]
            if "close" in args:
                close = bool(args["close"])
            if "ids" in args:  # Use list of str
                ids = {Ref(x[1:]) for x in literal_eval(args["ids"])}

        if not watch_id:
            raise ValueError("'watchId' must be set")
        provider.watch_unsub(watch_id, ids, close)
        grid_response = EmptyGrid
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def watch_poll(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `watch_poll` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        watch_id = None
        refresh = False
        if grid_request:
            if "watchId" in grid_request.metadata:
                watch_id = grid_request.metadata["watchId"]
            if "refresh" in grid_request.metadata:
                refresh = True
        if args:
            if "watchId" in args:
                watch_id = args["watchId"]
            if "refresh" in args:
                refresh = True

        grid_response = provider.watch_poll(watch_id, refresh)
        assert grid_response is not None
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def point_write(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `point_write_read` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        date_version = None
        level = 17
        val = who = duration = None
        entity_id = None
        if grid_request:
            entity_id = grid_request[0]["id"]
            date_version = grid_request[0].get("version", None)
            if "level" in grid_request[0]:
                level = int(grid_request[0]["level"])
            val = grid_request[0].get("val")
            who = grid_request[0].get("who")
            duration = grid_request[0].get("duration")  # Must be quantity

        if "id" in args:
            entity_id = Ref(args["id"][1:])
        if "level" in args:
            level = int(args["level"])
        if "val" in args:
            val = parse_scalar(
                args["val"],
                mode=MODE_ZINC,
            )
        if "who" in args:
            val = args["who"]
        if "duration" in args:
            duration = parse_scalar(args["duration"])
            assert isinstance(duration, Quantity)
        if "version" in args:
            date_version = parse_hs_date_format(args["version"].split(" "))
        if entity_id is None:
            raise ValueError("'id' must be set")
        if val is not None:
            provider.point_write_write(
                entity_id, level, val, who, duration, date_version
            )
            grid_response = EmptyGrid
        else:
            grid_response = provider.point_write_read(entity_id, date_version)
            assert grid_response is not None
            assert "level" in grid_response.column
            assert "levelDis" in grid_response.column
            assert "val" in grid_response.column
            assert "who" in grid_response.column
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def his_read(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `his_read` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        entity_id = date_version = None
        date_range = None
        if grid_request:
            if "id" in grid_request.column:
                entity_id = grid_request[0].get("id", "")
            if "range" in grid_request.column:
                date_range = grid_request[0].get("range", "")
            date_version = (
                grid_request[0].get("version", None) if grid_request else None
            )

        # Priority of query string
        if args:
            if "id" in args:
                entity_id = Ref(args["id"][1:])
            if "range" in args:
                date_range = args["range"]
            if "version" in args:
                date_version = parse_hs_date_format(args["version"])

        grid_date_range = parse_date_range(date_range, provider.get_tz())
        log.debug(
            "id=%s range=%s, date_version=%s", entity_id, grid_date_range, date_version
        )
        grid_response = provider.his_read(entity_id, grid_date_range, date_version)
        assert grid_response is not None
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def his_write(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `his_write` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        entity_id = grid_request.metadata.get("id")
        date_version = grid_request.metadata.get("version")
        time_serie_grid = grid_request

        # Priority of query string
        if args:
            if "id" in args:
                entity_id = Ref(args["id"][1:])
            if "ts" in args:  # Array of tuple
                time_serie_grid = Grid(version=VER_3_0, columns=["date", "val"])
                time_serie_grid.extend(
                    [
                        {"date": parse_hs_date_format(d), "val": v}
                        for d, v in literal_eval(args["ts"])
                    ]
                )
        if "version" in args:
            date_version = parse_hs_date_format(args["version"])
        grid_response = provider.his_write(entity_id, time_serie_grid, date_version)
        assert grid_response is not None
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response


def invoke_action(request: HaystackHttpRequest, stage: str) -> HaystackHttpResponse:
    """Implement the haystack `invoke_action` operation"""
    headers, args = (request.headers, request.args)
    try:
        provider = get_singleton_provider()
        grid_request = _parse_body(request)
        entity_id = grid_request.metadata.get("id")
        action = grid_request.metadata.get("action")
        # Priority of query string
        if args:
            if "id" in args:
                entity_id = Ref(args["id"][1:])
            if "action" in args:
                action = args["action"]
        params = grid_request[0] if grid_request else {}
        grid_response = provider.invoke_action(entity_id, action, params)
        assert grid_response is not None
        response = _format_response(headers, grid_response, 200, "OK")
    except Exception as ex:  # pylint: disable=broad-except
        response = _manage_exception(headers, ex, stage)
    return response
