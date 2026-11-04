"""Read and validate soil horizons before importing a complete set of profiles."""

import math
import os
import sqlite3

import pandas as pd


PROFILE_FIELDS = (
    'soilid', 'maxdepth', 'ksat', 'theta_fc', 'theta_wp',
    'theta_r', 'theta_sat', 'txtr_code',
)


class SoilProfileImportError(ValueError):
    pass


def read_profile_table(filename, sheet=0, separator=';', rows_before_header=0):
    if os.path.splitext(filename)[1].lower() == '.xlsx':
        frame = pd.read_excel(filename, sheet_name=sheet, skiprows=rows_before_header, dtype=object)
    else:
        separator = '\t' if separator == r'\t' else separator
        if len(separator) != 1:
            raise SoilProfileImportError('Choose a single column separator (or \\t).')
        frame = pd.read_csv(filename, sep=separator, skiprows=rows_before_header,
                            encoding='utf-8-sig', dtype=object)
    return frame.dropna(how='all')


def parse_profiles(frame, mappings, rows_before_header=0, decimal='.'):
    missing = [field for field in PROFILE_FIELDS if mappings.get(field) is None]
    if missing:
        raise SoilProfileImportError('Select a source column for: %s.' % ', '.join(missing))
    selected = [mappings[field] for field in PROFILE_FIELDS]
    if len(set(selected)) != len(selected):
        raise SoilProfileImportError('Each profile field must use a different source column.')
    profiles, names, depths = {}, {}, set()
    for position, (index, row) in enumerate(frame.iterrows()):
        row_number = (int(index) if isinstance(index, int) else position) + rows_before_header + 2
        values = []
        for field in PROFILE_FIELDS:
            raw = row.iloc[mappings[field]]
            try:
                value = float(str(raw).strip().replace(decimal, '.'))
                if not math.isfinite(value):
                    raise ValueError()
            except (TypeError, ValueError):
                raise SoilProfileImportError('Row %s: invalid %s value (%s).' % (row_number, field, raw))
            values.append(value)
        soilid, depth, ksat, fc, wp, residual, saturated, texture = values
        if not soilid.is_integer() or soilid < 1:
            raise SoilProfileImportError('Row %s: Soil type ID must be a positive integer.' % row_number)
        if not texture.is_integer() or not 1 <= texture <= 12:
            raise SoilProfileImportError('Row %s: USDA texture code must be an integer from 1 to 12.' % row_number)
        if depth <= 0 or ksat <= 0:
            raise SoilProfileImportError('Row %s: depth and conductivity must be positive.' % row_number)
        if not 0 <= residual <= wp <= fc <= saturated <= 1:
            raise SoilProfileImportError(
                'Row %s: require 0 <= residual <= wilting point <= field capacity <= saturation <= 1.' % row_number)
        soilid = int(soilid)
        if (soilid, depth) in depths:
            raise SoilProfileImportError('Row %s: duplicate depth %s for soil %s.' % (row_number, depth, soilid))
        depths.add((soilid, depth))
        profiles.setdefault(soilid, []).append((soilid, depth, ksat, fc, wp, residual, saturated, int(texture)))
        name_column = mappings.get('soil_name')
        if name_column is not None:
            raw_name = row.iloc[name_column]
            name = '' if pd.isna(raw_name) else str(raw_name).strip()
            if name:
                if soilid in names and names[soilid] != name:
                    raise SoilProfileImportError('Conflicting names for soil %s.' % soilid)
                names[soilid] = name
    if not profiles:
        raise SoilProfileImportError('There are no soil horizons to import.')
    for horizons in profiles.values():
        horizons.sort(key=lambda horizon: horizon[1])
    return profiles, names


def import_profiles(database_path, profiles, names, replace_existing=False, create_types=True):
    """Commit profiles and new type names together; leave unrelated soil IDs untouched."""
    if not os.path.isfile(database_path):
        raise SoilProfileImportError('The destination database does not exist.')
    connection = sqlite3.connect(database_path)
    try:
        connection.execute('BEGIN IMMEDIATE')
        existing = {row[0] for row in connection.execute('SELECT DISTINCT soilid FROM idr_soil_profiles')}
        types = dict(connection.execute('SELECT id, name FROM idr_soil_types'))
        used_names = set(types.values())
        summary = {'profiles': 0, 'horizons': 0, 'skipped': 0, 'types': 0}
        for soilid, horizons in profiles.items():
            if create_types and soilid not in types:
                name = names.get(soilid, 'Soil %s' % soilid)
                if name in used_names:
                    name = '%s [%s]' % (name, soilid)
                if name in used_names:
                    raise SoilProfileImportError('Soil type name already exists: %s.' % name)
                connection.execute('INSERT INTO idr_soil_types (id, name, descr) VALUES (?, ?, ?)',
                                   (soilid, name, ''))
                used_names.add(name)
                summary['types'] += 1
            if soilid in existing and not replace_existing:
                summary['skipped'] += 1
                continue
            if replace_existing:
                connection.execute('DELETE FROM idr_soil_profiles WHERE soilid = ?', (soilid,))
            connection.executemany(
                'INSERT INTO idr_soil_profiles (%s) VALUES (%s)' %
                (', '.join(PROFILE_FIELDS), ', '.join('?' for _ in PROFILE_FIELDS)), horizons)
            summary['profiles'] += 1
            summary['horizons'] += len(horizons)
        connection.commit()
        return summary
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
