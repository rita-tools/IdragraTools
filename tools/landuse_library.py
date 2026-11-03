"""Land-use class assignments and whole-library crop imports."""

import math
import os
import re
import sqlite3
from contextlib import closing
from collections import Counter


def connect_database(path):
    if not os.path.isfile(path):
        raise ValueError('The project database does not exist.')
    return sqlite3.connect(path)


def positive_id(value):
    try:
        number = float(value)
        if not math.isfinite(number) or not number.is_integer() or not 1 <= number <= 2147483647:
            raise ValueError()
        return int(number)
    except (TypeError, ValueError):
        raise ValueError('Class IDs must be positive integers: %s.' % value)


def crop_id(value):
    try:
        number = float(value)
        if not math.isfinite(number) or not number.is_integer() or not 0 <= number <= 2147483647:
            raise ValueError()
        return int(number)
    except (TypeError, ValueError):
        raise ValueError('Crop IDs must be non-negative integers: %s.' % value)


def read_library(path):
    with closing(connect_database(path)) as connection:
        classes = {}
        for class_id, name, description, sequence in connection.execute(
                'SELECT id, name, descr, croplist FROM idr_soiluses ORDER BY id'):
            if class_id in classes:
                raise ValueError('Duplicate land-use class ID %s in Soil uses. Resolve it before configuring classes.' % class_id)
            classes[class_id] = {'name': name, 'description': description,
                                 'crops': [crop_id(value) for value in (sequence or '').split()]}
        crops = dict(connection.execute('SELECT id, name FROM idr_crop_types ORDER BY name'))
    return classes, crops


def resolve_classes(values, existing, map_classes=(), use_names=False):
    """Return one (class ID, name) per source polygon; reuse name IDs on append."""
    names_by_id = {key: record['name'] for key, record in existing.items()}
    names_to_ids = {}
    for key, name in list(names_by_id.items()) + list(map_classes):
        if name:
            name = str(name).strip()
            names_to_ids.setdefault(name, set()).add(key)
            names_by_id.setdefault(key, name)
    used = set(existing) | {key for key, _ in map_classes}
    next_id = max(used | {0}) + 1
    resolved = []
    source_names = {}
    for value, label in values:
        if use_names:
            name = '' if value is None else str(value).strip()
            if not name:
                raise ValueError('Every imported polygon needs a land-use class name.')
            matches = names_to_ids.get(name, set())
            if len(matches) > 1:
                raise ValueError('Class name "%s" belongs to several IDs; import using IDs instead.' % name)
            if matches:
                class_id = next(iter(matches))
            else:
                class_id = positive_id(next_id)
                next_id += 1
                names_to_ids[name] = {class_id}
        else:
            class_id = positive_id(value)
            name = str(label).strip() if label is not None else ''
            if name:
                if class_id in source_names and source_names[class_id] != name:
                    raise ValueError('Conflicting names for map class %s.' % class_id)
                source_names[class_id] = name
        resolved.append((class_id, name))
    # Apply a supplied name consistently even if some polygons had a blank label.
    return [(key, name or source_names.get(key) or names_by_id.get(key) or 'Land use %s' % key)
            for key, name in resolved]


def save_assignments(path, assignments):
    """Update only the listed map classes; preserve descriptions and unused classes."""
    with closing(connect_database(path)) as connection:
        try:
            connection.execute('BEGIN IMMEDIATE')
            crop_ids = {row[0] for row in connection.execute('SELECT id FROM idr_crop_types')}
            for class_id, record in assignments.items():
                positive_id(class_id)
                sequence = record['crops']
                if not record['name'].strip() or not 1 <= len(sequence) <= 2:
                    raise ValueError('Give class %s a name and one or two crops.' % class_id)
                if any(crop not in crop_ids for crop in sequence):
                    raise ValueError('Class %s references a crop that is not in the project.' % class_id)
                count = connection.execute('SELECT COUNT(*) FROM idr_soiluses WHERE id=?', (class_id,)).fetchone()[0]
                if count > 1:
                    raise ValueError('Duplicate land-use class ID %s.' % class_id)
                text = ' '.join(map(str, sequence))
                if count:
                    connection.execute('UPDATE idr_soiluses SET name=?, croplist=? WHERE id=?',
                                       (record['name'].strip(), text, class_id))
                else:
                    connection.execute('INSERT INTO idr_soiluses (id, name, descr, croplist) VALUES (?, ?, ?, ?)',
                                       (class_id, record['name'].strip(), '', text))
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def raster_class_ids(sources):
    """Collect exact class values in blocks, excluding each raster's mask/nodata."""
    import numpy as np
    from osgeo import gdal
    ids = set()
    for source in sources:
        dataset = gdal.Open(source)
        if dataset is None:
            raise ValueError('Unable to open land-use raster: %s.' % source)
        try:
            band = dataset.GetRasterBand(1)
            mask = band.GetMaskBand()
            for y in range(0, dataset.RasterYSize, 256):
                height = min(256, dataset.RasterYSize - y)
                data = band.ReadAsArray(0, y, dataset.RasterXSize, height)
                valid = mask.ReadAsArray(0, y, dataset.RasterXSize, height) != 0
                ids.update(positive_id(value) for value in np.unique(data[valid & np.isfinite(data)]))
        finally:
            band = mask = dataset = None
    return ids


def crop_identity(filename):
    """Read the ID prefix, including reserved bare-soil ID 0."""
    stem = os.path.splitext(os.path.basename(filename))[0].strip()
    match = re.fullmatch(r'([+-]?\d+)_(.*)', stem)
    if match:
        identifier = crop_id(match.group(1))
        name = match.group(2).strip()
        if not name:
            raise ValueError('Crop filename must include a name after the ID: %s.' % filename)
        return identifier, name
    return None, stem


def crop_display_name(name):
    """Also clean names left by the previous importer, e.g. '1_wheat'."""
    return re.sub(r'^\d+_', '', str(name).strip()).strip()


def crop_filename(crop_id, name):
    """Use the database ID exactly once in exported filenames (including fallback 0)."""
    name = crop_display_name(name)
    name = re.sub(r'[\s<>:"/\\|?*]+', '_', name).strip('_.') or 'crop'
    return '%s_%s.tab' % (int(crop_id), name)


def read_crop_file(filename):
    # Keep the existing parser's support for IdrAgra .tab files and inline demo parameters.
    from .parse_par_file import parseParFile
    parameters = {key.lower(): value for key, value in parseParFile(filename).items()}
    table = parameters.pop('table', None)
    if table:
        table = {key.lower(): values for key, values in table.items()}
        for field in ('gdd', 'kcb', 'lai', 'hc', 'sr'):
            if field not in table or not table[field]:
                raise ValueError('%s: missing crop curve %s.' % (os.path.basename(filename), field))
            parameters[field] = ' '.join(table[field])
    if filename.lower().endswith('.tab'):
        crop_id, name = crop_identity(filename)
        parameters.pop('id', None)  # The model takes the ID from the filename, not file contents.
        if crop_id is not None:
            parameters['id'] = crop_id
        parameters['name'] = name
    else:
        # Bundled .txt presets already declare their original IDs and names.
        parameters['name'] = str(parameters.get('name') or os.path.splitext(os.path.basename(filename))[0]).strip()
    return parameters


def import_crops(path, parameters_list):
    """Replace the crop library and clear all class assignments in one transaction."""
    parameters_list = list(parameters_list)
    if not parameters_list:
        raise ValueError('Select at least one crop file. The existing library was not changed.')
    with closing(connect_database(path)) as connection:
        try:
            connection.execute('BEGIN IMMEDIATE')
            schema = {row[1].lower(): (row[1], row[2].lower())
                      for row in connection.execute('PRAGMA table_info(idr_crop_types)')}
            explicit_ids = [crop_id(record['id']) for record in parameters_list if record.get('id') is not None]
            if len(set(explicit_ids)) != len(explicit_ids):
                raise ValueError('Several selected crop files declare the same crop ID. Select only one file per ID.')
            selected_names = [crop_display_name(record['name']).casefold() for record in parameters_list]
            name_counts = Counter(selected_names)
            used_names = set(selected_names)
            suffixes = Counter()
            # Reserve explicit IDs before allocating any ID-less crops.
            next_id = max([0, *explicit_ids]) + 1
            connection.execute('DELETE FROM idr_crop_types')
            connection.execute("UPDATE idr_soiluses SET croplist = ''")
            for parameters in parameters_list:
                name = crop_display_name(parameters['name'])
                if not name:
                    raise ValueError('Crop name cannot be empty.')
                key = name.casefold()
                if name_counts[key] > 1:
                    suffixes[key] += 1
                    candidate = '%s_%s' % (name, suffixes[key])
                    while candidate.casefold() in used_names:
                        suffixes[key] += 1
                        candidate = '%s_%s' % (name, suffixes[key])
                    name = candidate
                    used_names.add(name.casefold())
                requested_id = crop_id(parameters['id']) if parameters.get('id') is not None else None
                identifier = requested_id if requested_id is not None else positive_id(next_id)
                if requested_id is None:
                    next_id += 1
                values = {}
                for field, (column, datatype) in schema.items():
                    if field in ('fid', 'id', 'adv_opts'):
                        continue
                    if field not in parameters:
                        raise ValueError('%s: missing parameter %s.' % (name, field))
                    value = parameters[field]
                    if field in ('gdd', 'kcb', 'lai', 'hc', 'sr'):
                        tokens = str(value).split()
                        if not tokens:
                            raise ValueError('%s: empty crop curve %s.' % (name, field))
                        for token in tokens:
                            if token != '*' and not math.isfinite(float(token)):
                                raise ValueError('%s: invalid crop curve %s.' % (name, field))
                    elif 'int' in datatype or 'double' in datatype or 'real' in datatype:
                        value = float(value)
                        if not math.isfinite(value) or ('int' in datatype and not value.is_integer()):
                            raise ValueError('%s: invalid parameter %s.' % (name, field))
                        value = int(value) if 'int' in datatype else value
                    values[column] = value
                values['name'] = name
                lengths = [len(str(parameters[field]).split()) for field in ('gdd', 'kcb', 'lai', 'hc', 'sr')]
                if len(set(lengths)) != 1:
                    raise ValueError('%s: crop curves must have the same number of points.' % name)
                unknown = ['%s = %s' % (key, value) for key, value in parameters.items()
                           if key not in schema and key != 'table']
                values['adv_opts'] = '\n'.join(filter(None, [parameters.get('adv_opts', ''), *unknown]))
                values['id'] = identifier
                columns = list(values)
                connection.execute('INSERT INTO idr_crop_types (%s) VALUES (%s)' %
                                   (', '.join('"%s"' % col for col in columns), ', '.join('?' for _ in columns)),
                                   [values[col] for col in columns])
            connection.commit()
            return {'imported': len(parameters_list)}
        except Exception:
            connection.rollback()
            raise
