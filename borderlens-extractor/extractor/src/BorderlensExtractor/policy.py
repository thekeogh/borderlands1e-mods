"""Conservative data-only discovery and explicit raw-export limits."""

import re

FORMAT_VERSION = 1
ROOT_SET = 0x4000
SKIP_FIELDS = frozenset((
    'Class','Outer','Name','ObjectFlags','InternalIndex','VfTableObject','HashNext',
    'HashOuterNext','StateFrame','Linker','LinkerIndex','ObjectInternalInteger','NetIndex',
))
BINDING_TERMS = ('definition','balance','inventory','itempool','loot','drop','weapon',
                 'allegiance','behavior','population','spawn','displayname','charactername','location')
WORLD_CLASSES = ('WillowInteractiveObject','WillowAIPawn','PopulationOpportunityDen')
LIMITS = {'depth': 14, 'array': 16384, 'string': 131072, 'nodes': 60000,
          'objects': 40000, 'bindings': 1000, 'references': 200000,
          'chunk_records': 128, 'chunk_bytes': 4 * 1024 * 1024,
          'frame_ms': 4.0, 'frame_records': 3}


def data_class(name):
    value = name.lower()
    return (value.endswith(('definition','resolver','lookup','curve','partlistcollection','datatable'))
            or 'behavior' in value
            or value.startswith(('seqact_', 'seqcond_', 'populationfactory',
                                 'expressiontree', 'expressionnode', 'attributeexpression'))
            or value.endswith('expressionevaluator')
            or value == 'gearboxaifactory')


def binding_field(name):
    return any(term in name.lower() for term in BINDING_TERMS)


def valid_package(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,95}',name):
        return False
    value = name.lower()
    if value.endswith(('_p','_dynamic','_vista','_art','_env')):
        return False
    return (value.startswith('gd_') or re.match(r'dlc[1-4]_(gd_|packagedefinition$)',value) is not None
            or re.fullmatch(r'[a-z][0-9]_missions',value) is not None
            or re.fullmatch(r'[a-z][0-9]_missiondata',value) is not None)


def validate_plan(data):
    if data.get('format_version') != FORMAT_VERSION or not isinstance(data.get('packages'),list):
        raise ValueError('Unsupported package plan format')
    result, seen = [], set()
    for row in data['packages']:
        if not isinstance(row, dict):raise ValueError('Package plan entries must be objects')
        name = row.get('name')
        if not valid_package(name):
            raise ValueError('Refusing non-data/unreviewed package name: '+repr(name))
        if name.casefold() in seen:
            raise ValueError('Duplicate package: '+name)
        seen.add(name.casefold())
        result.append({'name':name,'group':str(row.get('group','unclassified')),
                       'evidence':str(row.get('evidence','candidate'))})
    return result
