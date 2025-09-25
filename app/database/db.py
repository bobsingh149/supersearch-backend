from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional, Tuple
from app.database.sql.sql import render_sql, SQLFilePath


class Db:
    """
    Database helper class with static methods for common CRUD operations.
    All methods take a session and required parameters, then render and execute SQL.
    """

    @staticmethod
    async def insert(
        session: AsyncSession,
        tenant: str,
        table_name: str,
        columns: List[str],
        values: Dict[str, Any]
    ) -> Any:
        """
        Insert a single record into a table.

        Args:
            session: Async database session
            tenant: Tenant/schema name
            table_name: Name of the table
            columns: List of column names
            values: Dictionary mapping column names to values

        Returns:
            The inserted record(s)
        """
        sql = render_sql(
            SQLFilePath.GENERIC_INSERT,
            tenant=tenant,
            table_name=table_name,
            columns=columns
        )
        result = await session.execute(text(sql), values)
        return result.fetchall()

    @staticmethod
    async def update(
        session: AsyncSession,
        tenant: str,
        table_name: str,
        updates: Dict[str, Any],
        id_field: str,
        id_value: Any
    ) -> Any:
        """
        Update a record in a table.

        Args:
            session: Async database session
            tenant: Tenant/schema name
            table_name: Name of the table
            updates: Dictionary of column-value pairs to update
            id_field: Name of the ID field
            id_value: Value of the ID field

        Returns:
            The updated record(s)
        """
        sql = render_sql(
            SQLFilePath.GENERIC_UPDATE,
            tenant=tenant,
            table_name=table_name,
            updates=updates,
            id_field=id_field
        )
        params = dict(updates)
        params[id_field] = id_value
        result = await session.execute(text(sql), params)
        return result.fetchall()

    @staticmethod
    async def delete(
        session: AsyncSession,
        tenant: str,
        table_name: str,
        id_field: str,
        id_value: Any
    ) -> Any:
        """
        Delete a record from a table.

        Args:
            session: Async database session
            tenant: Tenant/schema name
            table_name: Name of the table
            id_field: Name of the ID field
            id_value: Value of the ID field

        Returns:
            The deleted record ID(s)
        """
        sql = render_sql(
            SQLFilePath.GENERIC_DELETE,
            tenant=tenant,
            table_name=table_name,
            id_field=id_field
        )
        result = await session.execute(text(sql), {id_field: id_value})
        return result.fetchall()

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        tenant: str,
        table_name: str,
        id_field: str,
        id_value: Any
    ) -> Optional[Any]:
        """
        Get a record by ID from a table.

        Args:
            session: Async database session
            tenant: Tenant/schema name
            table_name: Name of the table
            id_field: Name of the ID field
            id_value: Value of the ID field

        Returns:
            The record if found, None otherwise
        """
        sql = render_sql(
            SQLFilePath.GENERIC_GET_BY_ID,
            tenant=tenant,
            table_name=table_name,
            id_field=id_field
        )
        result = await session.execute(text(sql), {id_field: id_value})
        return result.fetchone()

    @staticmethod
    async def get_all(
        session: AsyncSession,
        tenant: str,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_direction: Optional[str] = "ASC",
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Any]:
        """
        Get all records from a table with optional filtering and pagination.

        Args:
            session: Async database session
            tenant: Tenant/schema name
            table_name: Name of the table
            filters: Optional dictionary of column-value filters
            sort_by: Optional column name to sort by
            sort_direction: Sort direction ('ASC' or 'DESC')
            limit: Optional limit for pagination
            offset: Optional offset for pagination

        Returns:
            List of records
        """
        sql = render_sql(
            SQLFilePath.GENERIC_GET_ALL,
            tenant=tenant,
            table_name=table_name,
            filters=filters or {},
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset
        )
        params = filters or {}
        result = await session.execute(text(sql), params)
        return result.fetchall()

    @staticmethod
    async def count(
        session: AsyncSession,
        tenant: str,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Count records in a table with optional filtering.

        Args:
            session: Async database session
            tenant: Tenant/schema name
            table_name: Name of the table
            filters: Optional dictionary of column-value filters

        Returns:
            Count of records
        """
        sql = render_sql(
            SQLFilePath.GENERIC_COUNT,
            tenant=tenant,
            table_name=table_name,
            filters=filters or {}
        )
        params = filters or {}
        result = await session.execute(text(sql), params)
        row = result.fetchone()
        return row.total if row else 0

    @staticmethod
    async def bulk_insert(
        session: AsyncSession,
        tenant: str,
        table_name: str,
        columns: List[str],
        items: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        Bulk insert multiple records into a table.

        Args:
            session: Async database session
            tenant: Tenant/schema name
            table_name: Name of the table
            columns: List of column names
            items: List of dictionaries mapping column names to values

        Returns:
            The inserted records
        """
        sql = render_sql(
            SQLFilePath.GENERIC_BULK_INSERT,
            tenant=tenant,
            table_name=table_name,
            columns=columns,
            items=items
        )

        # Build parameters dict with indexed column names
        params = {}
        for i, item in enumerate(items, 1):
            for column in columns:
                params[f"{column}_{i}"] = item[column]

        result = await session.execute(text(sql), params)
        return result.fetchall()

    @staticmethod
    async def advanced_filter(
        session: AsyncSession,
        tenant: str,
        table_name: str,
        filters: List[Dict[str, Any]],
        sort_by: Optional[str] = None,
        sort_direction: Optional[str] = "ASC",
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Any]:
        """
        Advanced filtering with complex filter conditions.

        Args:
            session: Async database session
            tenant: Tenant/schema name
            table_name: Name of the table
            filters: List of filter objects with 'field', 'operator', 'value'
            sort_by: Optional column name to sort by
            sort_direction: Sort direction ('ASC' or 'DESC')
            limit: Optional limit for pagination
            offset: Optional offset for pagination

        Returns:
            List of filtered records
        """
        sql = render_sql(
            SQLFilePath.GENERIC_ADVANCED_FILTER,
            tenant=tenant,
            table_name=table_name,
            filters=filters,
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset
        )

        # Build parameters from filters
        params = {}
        for i, filter_obj in enumerate(filters):
            if 'value' in filter_obj:
                operator = filter_obj.get('operator', '=')
                if operator in ['IN', 'NOT IN', 'BETWEEN', 'NOT BETWEEN'] and isinstance(filter_obj['value'], list):
                    for j, val in enumerate(filter_obj['value']):
                        params[f"value_{i}_{j}"] = val
                else:
                    params[f"value_{i}"] = filter_obj['value']

        result = await session.execute(text(sql), params)
        return result.fetchall()
