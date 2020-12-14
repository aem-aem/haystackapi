"""
Model to inject a another graphene model, to manage the haystack layer.
See the blueprint_graphql to see how to integrate this part of global GraphQL model.
"""
import logging
from datetime import datetime, date, time
from typing import Optional, List, Any, Dict, Union

import graphene
from graphql import ResolveInfo
from graphql.language import ast

import haystackapi
from haystackapi import Ref, Uri, Coordinate, parse_hs_date_format
from haystackapi.providers.haystack_interface import get_singleton_provider, parse_date_range
from haystackapi.zincdumper import dump_hs_date_time, dump_hs_time, dump_hs_date

BOTO3_AVAILABLE = False
try:
    import boto3
    from botocore.client import BaseClient

    BOTO3_AVAILABLE = True
except ImportError:
    pass

log = logging.getLogger("haystackapi")


# PPR: see the batch approach
# WARNING: At this time only public endpoints are supported by AWS AppSync

class HSScalar(graphene.Scalar):
    """Haystack Scalar"""

    class Meta:
        name = "AWSJSON" if BOTO3_AVAILABLE else "JSONString"

    @staticmethod
    def serialize(hs_scalar):
        return haystackapi.dump_scalar(hs_scalar, haystackapi.MODE_JSON, version=haystackapi.VER_3_0)

    @staticmethod
    # Parse from AST See https://tinyurl.com/y3fr76a4
    def parse_literal(node):
        if isinstance(node, ast.StringValue):  # FIXME: parse_literal in GraphQL API
            return f"node={node}"

    @staticmethod
    # Parse form json
    def parse_value(value):
        return f"parse_value={value}"  # FIXME: parse_value in GraphQL API


class HSDateTime(graphene.String):
    # class Meta:
    #     name = "String"
    @staticmethod
    def serialize(dt):
        assert isinstance(
            dt, (datetime, date)
        ), 'Received not compatible datetime "{}"'.format(repr(dt))
        return dump_hs_date_time(dt)

    @classmethod
    def parse_literal(cls, node):
        if isinstance(node, ast.StringValue):
            return cls.parse_value(node.value)

    @staticmethod
    def parse_value(value: str) -> Optional[datetime]:
        try:
            if isinstance(value, datetime):
                return value
            elif isinstance(value, str):
                return parse_hs_date_format(value)
        except ValueError:
            return None


class HSDate(graphene.String):
    # class Meta:
    #     name = "AWSDateTime" if BOTO3_AVAILABLE else "DateTime"
    @staticmethod
    def serialize(dt):
        assert isinstance(
            dt, (datetime, date)
        ), 'Received not compatible date "{}"'.format(repr(dt))
        return dump_hs_date(dt)

    @classmethod
    def parse_literal(cls, node):
        if isinstance(node, ast.StringValue):
            return cls.parse_value(node.value)

    @staticmethod
    def parse_value(value: str) -> Optional[date]:
        try:
            if isinstance(value, date):
                return value
            elif isinstance(value, str):
                return parse_hs_date_format(value)
        except ValueError:
            return None


class HSTime(graphene.String):
    # class Meta:
    #     name = "String"
    @staticmethod
    def serialize(dt):
        assert isinstance(
            dt, (datetime, time)
        ), 'Received not compatible time "{}"'.format(repr(dt))
        return dump_hs_time(dt)

    @classmethod
    def parse_literal(cls, node):
        if isinstance(node, ast.StringValue):
            return cls.parse_value(node.value)

    @staticmethod
    def parse_value(value: str) -> Optional[date]:
        try:
            if isinstance(value, time):
                return value
            elif isinstance(value, str):
                return parse_hs_date_format(value)
        except ValueError:
            return None


class HSUri(graphene.String):
    class Meta:
        name = "AWSURL" if BOTO3_AVAILABLE else "HSURL"


class HSAbout(graphene.ObjectType):
    """Result of 'about' haystack operation"""
    haystackVersion = graphene.String(required=True,
                                      description="Haystack version implemented")
    tz = graphene.String(required=True,
                         description="Server time zone")
    serverName = graphene.String(required=True,
                                 description="Server name")
    serverTime = graphene.Field(graphene.NonNull(HSDateTime),
                                description="Server current time")
    serverBootTime = graphene.Field(graphene.NonNull(HSDateTime),
                                    description="Server boot time")
    productName = graphene.String(required=True,
                                  description="Server Product name")
    productUri = graphene.Field(graphene.NonNull(HSUri),
                                description="Server URL")
    productVersion = graphene.String(required=True,
                                     description="Product version")
    moduleName = graphene.String(required=True,
                                 description="Module name")
    moduleVersion = graphene.String(required=True,
                                    description="Module version")


class HSOps(graphene.ObjectType):
    """Result of 'ops' haystack operation"""

    name = graphene.String(description="Name of operation (see https://project-haystack.org/doc/Ops)")
    summary = graphene.String(description="Summary of operation")


class HSCoordinate(graphene.ObjectType):
    lat = graphene.Float(description="Latitude")  # FIXME: require
    long = graphene.Float(description="Longitude")


class HSTS(graphene.ObjectType):
    """Result of 'hisRead' haystack operation"""
    ts = graphene.Field(HSDateTime, description="Date time of event")
    val = graphene.Field(HSScalar, description="Haystack JSON format of value")

    int = graphene.Int(required=False, description="Integer version of the value")
    float = graphene.Float(required=False, description="Float version of the value")
    str = graphene.String(required=False, description="Float version of the value")
    bool = graphene.Boolean(required=False, description="Boolean version of the value")
    uri = graphene.String(required=False, description="URI version of the value")
    ref = graphene.String(required=False, description="Reference version of the value")
    date = HSDate(required=False, description="Date version of the value")
    time = HSTime(required=False, description="Time version of the value")
    datetime = HSDateTime(required=False, description="Date time version of the value")
    coord = graphene.Field(HSCoordinate,
                           description="Geographic Coordinate")


class HSPointWrite(graphene.ObjectType):
    """Result of 'pointWrite' haystack operation"""
    level = graphene.Int(description="Current level")
    levelDis = graphene.String(description="Description of level")
    val = graphene.Field(HSScalar, description="Value")
    who = graphene.String(description="Who has updated the value")


# PPR: see the batch approach
class ReadHaystack(graphene.ObjectType):
    """ Ontology conform with Haystack project """

    class Meta:
        name = "Haystack"

    about = graphene.NonNull(HSAbout,
                             description="Versions of api")

    ops = graphene.NonNull(graphene.List(
        graphene.NonNull(HSOps)),
        description="List of operation implemented")

    tag_values = graphene.NonNull(graphene.List(graphene.NonNull(graphene.String),
                                                ),
                                  tag=graphene.String(required=True,
                                                      description="Tag name"),
                                  version=HSDateTime(description="Date of the version "
                                                                 "or nothing for the last version"),
                                  description="All values for a specific tag")

    versions = graphene.NonNull(graphene.List(graphene.NonNull(HSDateTime)),
                                description="All versions of data")

    entities = graphene.List(
        graphene.NonNull(HSScalar),
        ids=graphene.List(graphene.ID,
                          description="List of ids to return (if set, ignore filter and limit)"),
        select=graphene.String(default_value='*',
                               description="List of tags to return"),
        limit=graphene.Int(default_value=0,
                           description="Maximum number of items to return"),
        filter=graphene.String(default_value='',
                               description="Filter or item (see https://project-haystack.org/doc/Filters"),
        version=HSDateTime(description="Date of the version or nothing for the last version"),
        description="Selected entities of ontology"
    )

    histories = graphene.List(graphene.NonNull(graphene.List(graphene.NonNull(HSTS))),
                              ids=graphene.List(graphene.ID,
                                                description="List of ids to return"),
                              dates_range=graphene.String(description="today, yesterday, "
                                                                      "{date}, {date},{date}, "
                                                                      "{datetime}, "
                                                                      "{datetime},{datetime}"
                                                          ),
                              version=HSDateTime(description="Date of the version or nothing for the last version"),
                              description="Selected time series")

    point_write = graphene.List(
        graphene.NonNull(HSPointWrite),
        id=graphene.ID(required=True,
                       description="Id to read (accept @xxx, r:xxx or xxx)"),
        version=HSDateTime(description="Date of the version or nothing for the last version"),
        description="Point write values"
    )

    @staticmethod
    def resolve_about(parent: 'ReadHaystack',
                      info: ResolveInfo):
        log.debug(f"resolve_about(parent,info)")
        grid = get_singleton_provider().about("http://localhost")
        rc = ReadHaystack._conv_entity(HSAbout, grid[0])
        rc.serverTime = grid[0]["serverTime"]
        rc.bootTime = grid[0]["serverBootTime"]
        return rc

    @staticmethod
    def resolve_ops(parent: 'ReadHaystack',
                    info: ResolveInfo):
        log.debug(f"resolve_about(parent,info)")
        grid = get_singleton_provider().ops()
        return ReadHaystack._conv_list_to_object_type(HSOps, grid)

    @staticmethod
    def resolve_tag_values(parent: 'ReadHaystack',
                           info: ResolveInfo,
                           tag: str,
                           version: Optional[HSDateTime] = None):
        log.debug("resolve_values(parent,info,%s)", tag)
        return get_singleton_provider().values_for_tag(tag, version)

    @staticmethod
    def resolve_versions(parent: 'ReadHaystack',
                         info: ResolveInfo):
        log.debug("resolve_versions(parent,info)")
        return get_singleton_provider().versions()

    @staticmethod
    def resolve_entities(parent: 'ReadHaystack',
                         info: ResolveInfo,
                         ids: Optional[List[str]] = None,
                         select: str = '*',
                         filter: str = '',
                         limit: int = 0,
                         version: Optional[HSDateTime] = None):
        log.debug(
            f"resolve_entities(parent,info,ids={ids}, select={select}, filter={filter}, limit={limit}, version={version})")
        if ids:
            ids = [Ref(ReadHaystack._filter_id(entity_id)) for entity_id in ids]
        grid = get_singleton_provider().read(limit, select, ids, filter, version)
        return grid

    @staticmethod
    def resolve_histories(parent: 'ReadHaystack',
                          info: ResolveInfo,
                          ids: Optional[List[str]] = None,
                          dates_range: Optional[str] = None,
                          version: Union[str, datetime, None] = None):
        if version:
            version = HSDateTime.parse_value(version)
        log.debug(f"resolve_histories(parent,info,ids={ids}, range={dates_range}, version={version})")
        provider = get_singleton_provider()
        grid_date_range = parse_date_range(dates_range, provider.get_tz())
        return [ReadHaystack._conv_history(
            provider.his_read(Ref(ReadHaystack._filter_id(entity_id)), grid_date_range, version),
            info
        )
            for entity_id in ids]

    @staticmethod
    def resolve_point_write(parent: 'ReadHaystack', info: ResolveInfo,
                            entity_id: str,
                            version: Union[datetime, str, None] = None):
        if version:
            version = HSDateTime.parse_value(version)
        log.debug(f"resolve_point_write(parent,info, entity_id={entity_id}, version={version})")
        ref = Ref(ReadHaystack._filter_id(entity_id))
        grid = get_singleton_provider().point_write_read(ref, version)
        return ReadHaystack._conv_list_to_object_type(HSPointWrite, grid)

    @staticmethod
    def _conv_value(entity: Dict[str, Any],
                    info: ResolveInfo) -> HSTS:
        selection = info.field_asts[0].selection_set.selections
        cast_value = HSTS()
        value = entity["val"]
        cast_value.ts = entity["ts"]
        cast_value.val = value
        for sel in selection:
            name = sel.name.value
            if name in ['ts', 'val']:
                continue

            if name == 'int' and isinstance(value, (int, float)):
                cast_value.int = int(value)
            elif name == 'float' and isinstance(value, float):
                cast_value.float = value
            elif name == 'str':
                cast_value.str = str(value)
            elif name == 'bool':
                cast_value.bool = bool(value)
            elif name == 'uri' and isinstance(value, Uri):
                cast_value.uri = str(value)
            elif name == 'ref' and isinstance(value, Ref):
                cast_value.ref = '@' + value.name
            elif name == 'date' and isinstance(value, date):
                cast_value.date = value
            elif name == 'date' and isinstance(value, datetime):
                cast_value.date = value.date()
            elif name == 'time' and isinstance(value, time):
                cast_value.time = value
            elif name == 'time' and isinstance(value, datetime):
                cast_value.time = value.time()
            elif name == 'datetime' and isinstance(value, datetime):
                cast_value.datetime = value
            elif name == 'coord' and isinstance(value, Coordinate):
                cast_value.coord = HSCoordinate(value.latitude, value.longitude)
        return cast_value

    @staticmethod
    def _conv_history(entities, info: ResolveInfo):
        return [ReadHaystack._conv_value(entity, info) for entity in entities]

    @staticmethod
    def _filter_id(entity_id: str) -> str:
        if entity_id.startswith("r:"):
            return entity_id[2:]
        if entity_id.startswith('@'):
            return entity_id[1:]
        return entity_id

    @staticmethod
    def _conv_entity(cls, entity):
        entity_result = cls()
        for key, val in entity.items():
            if key in entity:
                entity_result.__setattr__(key, val)
        return entity_result

    @staticmethod
    def _conv_list_to_object_type(cls, grid):
        result = []
        for row in grid:
            result.append(ReadHaystack._conv_entity(cls, row))
        return result
