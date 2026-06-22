# Find any database table and column that contains the value 27 in MesobGrace database
cr = self.env.cr
cr.execute("""
    SELECT table_name, column_name 
    FROM information_schema.columns 
    WHERE data_type IN ('integer', 'bigint', 'numeric');
""")
cols = cr.fetchall()
for table_name, column_name in cols:
    if table_name.startswith('pg_') or table_name.startswith('sql_'):
        continue
    try:
        query = f'SELECT id FROM "{table_name}" WHERE "{column_name}" = 27 LIMIT 1;'
        cr.execute(query)
        res = cr.fetchone()
        if res:
            # Get other fields as well to print info
            cr.execute(f'SELECT * FROM "{table_name}" WHERE "{column_name}" = 27 LIMIT 1;')
            row = cr.dictfetchone()
            print(f"FOUND 27 in table={table_name}, column={column_name}, row_data={row}")
    except Exception as e:
        cr.rollback()
    except Exception as e:
        pass
