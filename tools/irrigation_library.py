"""Import an irrigation-method library without changing map assignments."""

import math
import os
import re
from collections import Counter
from contextlib import closing

from .landuse_library import connect_database, crop_display_name, positive_id
from .parse_par_file import parseParFile


def read_irrigation_file(filename):
    parameters = {key.lower(): value for key, value in parseParFile(filename).items()}
    # Exported method files use different labels from the inline bundled presets.
    for source, target in [('a', 'losses_a'), ('b', 'losses_b'), ('c', 'losses_c'),
                           ('interceptionflag', 'f_interception')]:
        if source in parameters:
            parameters[target] = parameters.pop(source)
    try:
        with open(filename, encoding='utf-8-sig') as source:
            text = source.read()
    except UnicodeDecodeError:
        with open(filename, encoding='cp1252') as source:
            text = source.read()
    for field, label in [('name', 'Irrigation method'), ('irr_eff', 'Irrigation efficiency')]:
        if field not in parameters:
            match = re.search(r'^\s*#\s*' + label + r':\s*(.*?)\s*$', text, re.I | re.M)
            if match:
                parameters[field] = match.group(1)
    parameters['name'] = str(parameters.get('name') or
        crop_display_name(os.path.splitext(os.path.basename(filename))[0])).strip()
    parameters['id'] = positive_id(parameters.get('id'))
    hours = [str(hour) for hour in range(1, 25)]
    if 'irr_time' not in parameters and all(hour in parameters for hour in hours):
        parameters['irr_time'] = ' '.join(hours)
        parameters['irr_fraction'] = ' '.join(parameters.pop(hour) for hour in hours)
    flag = str(parameters.get('f_interception', '')).lower()
    if flag in ('t', 'true', 'f', 'false'):
        parameters['f_interception'] = int(flag in ('t', 'true'))
    return parameters


def map_irrigation_methods(records, assignments):
    """Copy selected parameters under the map's IDs; do not edit the source maps."""
    mapped = []
    for map_id, source_index in sorted(assignments.items()):
        identifier = positive_id(map_id)
        if source_index is None or not 0 <= source_index < len(records):
            raise ValueError('Select irrigation parameters for map ID %s.' % identifier)
        mapped.append(dict(records[source_index], id=identifier))
    # Several map classes can use the same preset, but the database needs unique names.
    counts = Counter(record['name'].strip().casefold() for record in mapped)
    reserved = {record['name'].strip().casefold() for record in mapped}
    suffixes = Counter()
    for record in mapped:
        name = record['name'].strip()
        key = name.casefold()
        if counts[key] > 1:
            suffixes[key] += 1
            candidate = '%s_%s' % (name, suffixes[key])
            while candidate.casefold() in reserved:
                suffixes[key] += 1
                candidate = '%s_%s' % (name, suffixes[key])
            name = candidate
            reserved.add(name.casefold())
        record['name'] = name
    return mapped


def import_irrigation_methods(path, records, required_ids=()):
    records = list(records)
    if not records:
        raise ValueError('Select at least one irrigation method. The existing library was not changed.')
    ids = [positive_id(record.get('id')) for record in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Several selected files declare the same irrigation method ID.')
    missing = set(required_ids) - set(ids) - {0}
    if missing:
        raise ValueError('The maps use irrigation method IDs missing from this library: %s. '
                         'Include these methods or change the map assignments first.' %
                         ', '.join(map(str, sorted(missing))))
    with closing(connect_database(path)) as connection:
        try:
            connection.execute('BEGIN IMMEDIATE')
            schema = {row[1].lower(): (row[1], row[2].lower())
                      for row in connection.execute('PRAGMA table_info(idr_irrmet_types)')}
            connection.execute('DELETE FROM idr_irrmet_types')
            names = set()
            for identifier, record in zip(ids, records):
                values = {'id': identifier}
                for key, (column, datatype) in schema.items():
                    if key in ('fid', 'id', 'adv_opts'):
                        continue
                    if key not in record:
                        raise ValueError('Method %s: missing parameter %s.' % (identifier, key))
                    value = record[key]
                    if key == 'name':
                        value = str(value).strip()
                        if not value or value.casefold() in names:
                            raise ValueError('Irrigation method names must be nonempty and unique: %s.' % value)
                        names.add(value.casefold())
                    elif 'double' in datatype or 'real' in datatype or 'int' in datatype:
                        value = float(value)
                        if not math.isfinite(value) or ('int' in datatype and not value.is_integer()):
                            raise ValueError('Method %s: invalid parameter %s.' % (identifier, key))
                        value = int(value) if 'int' in datatype else value
                    values[column] = value
                for key in ('fw', 'irr_eff'):
                    if not 0 <= values[key] <= 1:
                        raise ValueError('Method %s: %s must be between 0 and 1.' % (identifier, key))
                if values['f_interception'] not in (0, 1):
                    raise ValueError('Method %s: interception flag must be 0 or 1.' % identifier)
                for key in ('qadaq', 'k_stress', 'k_stresswells'):
                    if values[key] < 0:
                        raise ValueError('Method %s: %s cannot be negative.' % (identifier, key))
                if str(values['irr_time']).split() != [str(hour) for hour in range(1, 25)]:
                    raise ValueError('Method %s: irrigation hours must run from 1 to 24.' % identifier)
                fractions = str(values['irr_fraction']).split()
                if len(fractions) != 24:
                    raise ValueError('Method %s: supply 24 irrigation fractions.' % identifier)
                numeric = [float(value) for value in fractions if value != '*']
                if any(not math.isfinite(value) or not 0 <= value <= 1 for value in numeric) or sum(numeric) > 1.000001:
                    raise ValueError('Method %s: invalid irrigation fractions (total exceeds 1).' % identifier)
                unknown = ['%s = %s' % (key, value) for key, value in record.items()
                           if key not in schema and key != 'table']
                values['adv_opts'] = ';'.join(filter(None, [record.get('adv_opts', ''), *unknown]))
                columns = list(values)
                connection.execute('INSERT INTO idr_irrmet_types (%s) VALUES (%s)' %
                    (', '.join('"%s"' % column for column in columns), ', '.join('?' for _ in columns)),
                    [values[column] for column in columns])
            connection.commit()
            return len(records)
        except Exception:
            connection.rollback()
            raise
