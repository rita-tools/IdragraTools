import csv
import os
import sqlite3
from collections import defaultdict
from datetime import datetime


SUPPORTED_TABLES = {
    'ws_tmin', 'ws_tmax', 'ws_ptot', 'ws_umin', 'ws_umax',
    'ws_vmed', 'ws_rgcorr', 'ws_co2', 'node_act_disc', 'node_disc'
}


class TimeSeriesImportError(Exception):
    pass


def normalized_separator(separator):
    if separator == r'\t':
        return '\t'
    if len(separator) != 1:
        raise TimeSeriesImportError('The column separator must be a single character.')
    return separator


def read_header(filename, separator, rows_before_header=0):
    separator = normalized_separator(separator)
    try:
        with open(filename, 'r', encoding='utf-8-sig', newline='') as source:
            reader = csv.reader(source, delimiter=separator)
            for _ in range(rows_before_header):
                next(reader)
            header = next(reader)
    except (OSError, StopIteration, csv.Error) as error:
        raise TimeSeriesImportError('Unable to read the header from %s: %s' % (filename, error)) from error

    columns = [column.strip() for column in header]
    if not columns or not any(columns):
        raise TimeSeriesImportError('No column names were found in %s.' % filename)
    if len(columns) != len(set(columns)):
        raise TimeSeriesImportError('Duplicate column names were found in %s.' % filename)
    return columns


def csv_files_in_folder(folder):
    try:
        filenames = sorted(os.listdir(folder))
    except OSError as error:
        raise TimeSeriesImportError('Unable to read folder %s: %s' % (folder, error)) from error
    return [os.path.join(folder, name) for name in filenames if name.lower().endswith('.csv')]


def station_id_from_filename(filename, available_station_ids):
    stem = os.path.splitext(os.path.basename(filename))[0]
    available = {str(station_id): station_id for station_id in available_station_ids}
    if stem in available:
        return available[stem]

    try:
        normalized_stem = str(int(stem))
    except ValueError as error:
        raise TimeSeriesImportError(
            'Filename %s does not contain a numeric station ID.' % os.path.basename(filename)
        ) from error

    if normalized_stem not in available:
        raise TimeSeriesImportError(
            'No measuring point with ID %s exists for file %s.' % (stem, os.path.basename(filename))
        )
    return available[normalized_stem]


def _parse_file(job, records_by_table, skipped_empty):
    filename = job['filename']
    separator = normalized_separator(job['separator'])
    rows_before_header = job['rows_before_header']
    timestamp_column = job['timestamp_column']
    mappings = job['mappings']
    time_format = job['time_format']
    station_id = job['station_id']

    columns = read_header(filename, separator, rows_before_header)
    column_indexes = {column: index for index, column in enumerate(columns)}
    required_columns = [timestamp_column] + list(mappings.values())
    missing = [column for column in required_columns if column not in column_indexes]
    if missing:
        raise TimeSeriesImportError(
            'Missing columns in %s: %s' % (os.path.basename(filename), ', '.join(missing))
        )

    try:
        with open(filename, 'r', encoding='utf-8-sig', newline='') as source:
            reader = csv.reader(source, delimiter=separator)
            for _ in range(rows_before_header + 1):
                next(reader)

            for row_number, row in enumerate(reader, start=rows_before_header + 2):
                if not row or not any(value.strip() for value in row):
                    continue
                try:
                    raw_timestamp = row[column_indexes[timestamp_column]].strip()
                    timestamp = datetime.strptime(raw_timestamp, time_format).strftime('%Y-%m-%d')
                except (IndexError, ValueError) as error:
                    raise TimeSeriesImportError(
                        'Invalid timestamp in %s at row %s: %s' %
                        (os.path.basename(filename), row_number, error)
                    ) from error

                for table_name, source_column in mappings.items():
                    try:
                        raw_value = row[column_indexes[source_column]].strip()
                    except IndexError as error:
                        raise TimeSeriesImportError(
                            'Missing value in %s at row %s, column %s.' %
                            (os.path.basename(filename), row_number, source_column)
                        ) from error
                    if raw_value == '':
                        skipped_empty[table_name] += 1
                        continue
                    try:
                        value = float(raw_value)
                    except ValueError as error:
                        raise TimeSeriesImportError(
                            'Invalid number in %s at row %s, column %s: %s' %
                            (os.path.basename(filename), row_number, source_column, raw_value)
                        ) from error
                    records_by_table[table_name].append((timestamp, station_id, value))
    except (OSError, StopIteration, csv.Error) as error:
        raise TimeSeriesImportError('Unable to read %s: %s' % (filename, error)) from error


def import_jobs(database_path, jobs, overwrite_existing=True):
    if not jobs:
        raise TimeSeriesImportError('There are no files to import.')

    records_by_table = defaultdict(list)
    skipped_empty = defaultdict(int)
    for job in jobs:
        invalid_tables = set(job['mappings']) - SUPPORTED_TABLES
        if invalid_tables:
            raise TimeSeriesImportError('Unsupported destination tables: %s' % ', '.join(sorted(invalid_tables)))
        _parse_file(job, records_by_table, skipped_empty)

    if not records_by_table:
        raise TimeSeriesImportError('The selected files contain no values to import.')

    summary = {}
    connection = sqlite3.connect(database_path)
    try:
        connection.execute('BEGIN')
        for table_name, records in records_by_table.items():
            table_columns = {
                row[1] for row in connection.execute('PRAGMA table_info("%s")' % table_name)
            }
            if not {'timestamp', 'wsid', 'recval'}.issubset(table_columns):
                raise TimeSeriesImportError('Destination table %s has an unexpected structure.' % table_name)

            connection.execute('DROP TABLE IF EXISTS temp._idragra_import')
            connection.execute(
                'CREATE TEMP TABLE _idragra_import ('
                'timestamp TEXT, wsid INTEGER, recval REAL, '
                'PRIMARY KEY (timestamp, wsid))'
            )
            connection.executemany(
                'INSERT OR REPLACE INTO temp._idragra_import (timestamp, wsid, recval) VALUES (?, ?, ?)',
                records
            )

            existing = connection.execute(
                'SELECT COUNT(*) FROM temp._idragra_import AS src '
                'WHERE EXISTS ('
                'SELECT 1 FROM "%s" AS dst '
                'WHERE dst.timestamp = src.timestamp AND dst.wsid = src.wsid)' % table_name
            ).fetchone()[0]

            if overwrite_existing:
                connection.execute(
                    'UPDATE "%s" SET recval = ('
                    'SELECT src.recval FROM temp._idragra_import AS src '
                    'WHERE src.timestamp = "%s".timestamp AND src.wsid = "%s".wsid) '
                    'WHERE EXISTS ('
                    'SELECT 1 FROM temp._idragra_import AS src '
                    'WHERE src.timestamp = "%s".timestamp AND src.wsid = "%s".wsid)' %
                    (table_name, table_name, table_name, table_name, table_name)
                )

            connection.execute(
                'INSERT INTO "%s" (timestamp, wsid, recval) '
                'SELECT src.timestamp, src.wsid, src.recval FROM temp._idragra_import AS src '
                'WHERE NOT EXISTS ('
                'SELECT 1 FROM "%s" AS dst '
                'WHERE dst.timestamp = src.timestamp AND dst.wsid = src.wsid)' %
                (table_name, table_name)
            )
            unique_records = connection.execute('SELECT COUNT(*) FROM temp._idragra_import').fetchone()[0]
            summary[table_name] = {
                'inserted': unique_records - existing,
                'updated': existing if overwrite_existing else 0,
                'existing_skipped': 0 if overwrite_existing else existing,
                'empty_skipped': skipped_empty[table_name]
            }

        connection.execute('DROP TABLE IF EXISTS temp._idragra_import')
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return summary
