#!/usr/bin/env python3

from app.database.sql.sql import render_sql, SQLFilePath

def test_sql_templates():
    print("Testing SQL template generation...")

    # Test insert with different data types
    insert_sql = render_sql(
        SQLFilePath.GENERIC_INSERT,
        tenant='test_tenant',
        table_name='test_table',
        columns=['id', 'name', 'age', 'is_active', 'score', 'metadata']
    )

    print('INSERT SQL:')
    print(insert_sql)
    print('INSERT PARAMS would be passed separately to session.execute()')
    print()

    # Test update
    update_sql = render_sql(
        SQLFilePath.GENERIC_UPDATE,
        tenant='test_tenant',
        table_name='test_table',
        id_field='id',
        updates={
            'name': 'Updated User',
            'age': 26,
            'is_active': False,
            'score': 98.0
        }
    )

    print('UPDATE SQL:')
    print(update_sql)
    print('UPDATE PARAMS would be passed separately to session.execute()')
    print()

    # Test bulk insert
    bulk_insert_sql = render_sql(
        SQLFilePath.GENERIC_BULK_INSERT,
        tenant='test_tenant',
        table_name='test_table',
        columns=['id', 'name', 'age'],
        items=[
            {'id': '1', 'name': 'User 1', 'age': 20},
            {'id': '2', 'name': 'User 2', 'age': 30}
        ]
    )

    print('BULK INSERT SQL:')
    print(bulk_insert_sql)
    print('BULK INSERT PARAMS would be passed separately to session.execute()')
    print()

    # Test get_all with filters
    get_all_sql = render_sql(
        SQLFilePath.GENERIC_GET_ALL,
        tenant='test_tenant',
        table_name='test_table',
        filters={'category': 'electronics', 'in_stock': True},
        sort_by='created_at',
        sort_direction='DESC',
        limit=10
    )

    print('GET ALL SQL:')
    print(get_all_sql)
    print('GET ALL PARAMS would be passed separately to session.execute()')
    print()

    # Test advanced filter
    advanced_filter_sql = render_sql(
        SQLFilePath.GENERIC_ADVANCED_FILTER,
        tenant='test_tenant',
        table_name='test_table',
        filters=[
            {
                'column': 'price',
                'operator': '>=',
                'value': 100
            },
            {
                'column': 'category',
                'operator': 'IN',
                'value': ['electronics', 'computers'],
                'logic_operator': 'AND'
            }
        ],
        sort_by='price',
        sort_direction='ASC',
        limit=20
    )

    print('ADVANCED FILTER SQL:')
    print(advanced_filter_sql)
    print('ADVANCED FILTER PARAMS would be passed separately to session.execute()')

if __name__ == '__main__':
    test_sql_templates()
