import json
import logging
import textwrap
from datetime import datetime
from typing import Dict, Any, Optional

log = logging.getLogger("sql.Provider")


def _exec_sql_filter(params: Dict[str, Any],
                     cursor,
                     table_name: str,
                     grid_filter: Optional[str],
                     version: datetime,
                     limit: int = 0,
                     customer_id: Optional[str] = None):
    if grid_filter is None or grid_filter == '':
        cursor.execute(params["SELECT_ENTITY"], (version, version, customer_id))
        return

    raise NotImplementedError("Complex request not implemented")


def get_db_parameters(table_name: str) -> Dict[str, Any]:
    return {
        "sql_type_to_json": lambda x: json.loads(x),
        "exec_sql_filter": _exec_sql_filter,
        "CREATE_HAYSTACK_TABLE": textwrap.dedent(f'''
            CREATE TABLE IF NOT EXISTS {table_name}
                (
                id text, 
                customer_id text NOT NULL, 
                start_datetime text NOT NULL, 
                end_datetime text NOT NULL, 
                entity text NOT NULL
                );
            '''),
        "CREATE_HAYSTACK_INDEX_1": textwrap.dedent(f'''
            CREATE INDEX IF NOT EXISTS {table_name}_index ON {table_name}(id)
            '''),
        "CREATE_HAYSTACK_INDEX_2": textwrap.dedent(f'''
            '''),
        "CREATE_METADATA_TABLE": textwrap.dedent(f'''
            CREATE TABLE IF NOT EXISTS {table_name}_meta_datas
               (
                customer_id text NOT NULL, 
                start_datetime text NOT NULL, 
                end_datetime text NOT NULL, 
                metadata text,
                cols text
               );
           '''),
        "PURGE_TABLES_HAYSTACK": textwrap.dedent(f'''
            DELETE FROM {table_name} ;
            '''),
        "PURGE_TABLES_HAYSTACK_META": textwrap.dedent(f'''
            DELETE FROM {table_name}_meta_datas ;
            '''),
        "SELECT_META_DATA": textwrap.dedent(f'''
            SELECT metadata,cols FROM {table_name}_meta_datas
            WHERE ? BETWEEN start_datetime AND end_datetime
            AND customer_id=?
            '''),
        "CLOSE_META_DATA": textwrap.dedent(f'''
            UPDATE {table_name}_meta_datas  SET end_datetime=?
            WHERE ? >= start_datetime AND end_datetime = '9999-12-31T23:59:59'
            AND customer_id=?
            '''),
        "UPDATE_META_DATA": textwrap.dedent(f'''
            INSERT INTO {table_name}_meta_datas VALUES (?,?,'9999-12-31T23:59:59',?,?)
            '''),
        "SELECT_ENTITY": textwrap.dedent(f'''
            SELECT entity FROM {table_name}
            WHERE ? BETWEEN start_datetime AND end_datetime
            AND customer_id = ?
            '''),
        "SELECT_ENTITY_WITH_ID": textwrap.dedent(f'''
            SELECT entity FROM {table_name}
            WHERE ? BETWEEN start_datetime AND end_datetime
            AND customer_id = ?
            AND id IN '''),
        "CLOSE_ENTITY": textwrap.dedent(f'''
            UPDATE {table_name} SET end_datetime=? 
            WHERE ? > start_datetime AND end_datetime = '9999-12-31T23:59:59'
            AND id=? 
            AND customer_id = ?
            '''),
        "INSERT_ENTITY": textwrap.dedent(f'''
            INSERT INTO {table_name} VALUES (?,?,?,null,?)
            '''),
        "DISTINCT_VERSION": textwrap.dedent(f'''
            SELECT DISTINCT start_datetime
            FROM {table_name}
            WHERE customer_id = ?
            ORDER BY start_datetime
            '''),
    }
