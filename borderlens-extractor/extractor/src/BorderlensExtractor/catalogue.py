"""Small, evidence-linked crawl seeds; no family merging or boss-name guesses."""

import re
from hashlib import sha256

NAME_FIELDS = frozenset((
    'displayname', 'aipawnname', 'missionname', 'skillname', 'itemname',
    'weaponname', 'partname', 'manufacturername', 'vehiclename', 'stationname',
    'regionname', 'challengename', 'charactername', 'locationname', 'menuname',
    'localizedname', 'titlename', 'travelstationname', 'friendlyname',
    'enemyname', 'bossname', 'npcname', 'pawnname', 'mapname', 'levelname',
    'callername', 'outpostdisplayname', 'stationdisplayname',
))

# These strings identify related entities, not names of the owning mission/list.
# A travel key or package name remains an internal identifier, never display prose.
REFERENCE_FIELDS = {
    'missiongiver':('mission_giver', 'display_label'),
    'targetfasttravelstation':('location', 'travel_key'),
    'turninfasttravelstation':('location', 'travel_key'),
    'outpostname':('location', 'travel_key'),
    'outpostpathname':('location', 'object_path'),
    'pickupmapname':('map', 'package_name'),
    'persistentlevelname':('map', 'package_name'),
    'sublevelname':('map', 'package_name'),
}


def field_key(key):
    return re.split(r'[.\[\](]', key)[-1].casefold()


def name_field(key):
    key = field_key(key)
    return key in NAME_FIELDS or key in REFERENCE_FIELDS


def usable_name(value):
    return (isinstance(value, str) and bool(value.strip())
            and value.strip().casefold() not in ('none', 'null')
            and not re.search(r'%[sn]', value)
            and not re.fullmatch(r'<[^>]+>', value.strip()))


def labels(value, prefix=''):
    """Walk already-serialized JSON only; retain exact field/index provenance."""
    if isinstance(value, dict):
        if '$ref' in value or value.get('$type') in ('read_errors', 'unsupported', 'truncated'):
            return
        if value.get('$type') == 'struct':
            yield from labels(value['fields'], prefix)
        elif value.get('$type') == 'array':
            yield from labels(value['items'], prefix)
        else:
            for key, item in value.items():
                field = prefix+'.'+key if prefix else key
                text = item.get('value') if isinstance(item, dict) and item.get('$type') == 'name' else item
                if name_field(key) and usable_name(text):
                    yield {'name':text.strip(), 'field':field}
                elif isinstance(item, (dict, list)):
                    yield from labels(item, field)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from labels(item, prefix+'['+str(index)+']')


def category(class_path):
    cls = class_path.rsplit('.', 1)[-1].casefold()
    if cls in ('aipawnbalancedefinition', 'willowaipawn'):
        return 'character'
    if cls == 'echocalleriddefinition':return 'contact'
    if cls == 'interactivenpcdefinition':return 'npc'
    if cls in ('teleportoutpostlookupobject', 'emergencyteleportoutpostdefinition'):
        return 'location'
    if cls == 'emergencyteleportoutpostlookup':return 'location_list'
    if cls == 'leveldependencylist':return 'map_list'
    if 'mission' in cls and cls.endswith('definition') and 'objective' not in cls:
        return 'mission'
    if cls in ('playerclassdefinition', 'characterclassdefinition', 'willowcharacterclassdefinition'):
        return 'character_class'
    if cls == 'skilldefinition':return 'skill'
    if cls == 'manufacturerdefinition':return 'manufacturer'
    if cls in ('regiondefinition', 'willowregiondefinition'):return 'region'
    if cls == 'challengedefinition':return 'challenge'
    if 'vehicle' in cls and (cls.endswith('definition') or cls.startswith('willow')):
        return 'vehicle'
    if cls in ('weaponnamepartdefinition', 'itemnamepartdefinition'):
        return 'equipment_name'
    if cls in ('weapondefinition', 'weapontypedefinition'):return 'weapon_type'
    if cls == 'itemdefinition':return 'item'
    if cls in ('inventorybalancedefinition', 'weaponbalancedefinition', 'itembalancedefinition'):
        return 'equipment_balance'
    if cls in ('weaponpartdefinition', 'itempartdefinition'):return 'equipment_part'
    if 'itempool' in cls:return 'loot_pool'
    if cls.startswith('populationfactory'):return 'population_source'
    if cls in ('interactiveobjectdefinition', 'willowinteractiveobject'):
        return 'interactive_object'
    return None


def origin(path):
    """DLC namespaces are hints; base-game/mod origin remains unverified."""
    match = re.match(r'dlc([1-4])_', path, re.I)
    return 'dlc'+match[1] if match else None


def identity(record):
    if record.get('is_default') or record.get('name', '').startswith('Default__'):
        return None
    kind = record.get('binding_category') or category(record.get('class', ''))
    names = [n for n in labels(record.get('properties', {})) if field_key(n['field']) not in REFERENCE_FIELDS]
    if kind is None and not names:return None
    path = record['path']
    return {'record_type':'catalogue_identity', 'id':'identity:'+record['id'],
            'category':kind or 'named_definition', 'asset_path':path,
            'class':record.get('class'), 'internal_name':record.get('name'),
            'names':names, 'source_record':record['id'],
            'context':record.get('context'), 'origin_hint':origin(path),
            'identity_status':'asset_evidence', 'character_role':None,
            'is_boss':None, 'is_named_enemy':None,
            'source_complete':record.get('complete', False)}


def field_identity(source, label, localisation=False):
    """A source/field locator; never pretend a string is a resolved actor ID."""
    kind, identifier_kind = REFERENCE_FIELDS[field_key(label['field'])]
    value = label['name']
    seed = {'record_type':'catalogue_identity',
            'id':'identity:field:'+source['id']+':'+sha256(label['field'].encode('utf-8')).hexdigest(),
            'category':kind, 'identity_status':'localisation_field_candidate' if localisation else 'field_candidate',
            'asset_path':None, 'class':None, 'internal_name':value if identifier_kind != 'display_label' else None,
            'names':[dict(label)] if identifier_kind == 'display_label' else [],
            'source_value':value, 'identifier_kind':identifier_kind,
            'internal_identifiers':[] if identifier_kind == 'display_label' else [{'value':value, 'field':label['field'], 'kind':identifier_kind}],
            'source_record':source['source_record'] if localisation else source['id'],
            'source_asset_path':None if localisation else source['path'],
            'source_field':label['field'], 'context':source.get('context'),
            'origin_hint':None, 'source_origin_hint':source.get('origin_hint') if localisation else origin(source['path']),
            'character_role':None, 'is_boss':None, 'is_named_enemy':None,
            'source_complete':source.get('source_complete', False) if localisation else source.get('complete', False)}
    if identifier_kind in ('object_path', 'package_name'):seed['asset_path_hint'] = value
    if localisation:
        seed['source_asset_path_hint'] = source.get('asset_path_hint')
        seed['source_identity'] = source['id']
        for key in ('source_file', 'source_sha256', 'section', 'section_occurrence'):
            seed[key] = source[key]
        if 'line' in label:seed['source_line'] = label['line']
    return seed


def identities(record):
    if record.get('is_default') or record.get('name', '').startswith('Default__'):return
    seed = identity(record)
    if seed is not None:yield seed
    for label in labels(record.get('properties', {})):
        if field_key(label['field']) in REFERENCE_FIELDS:
            yield field_identity(record, label)


def localisation_identities(source):
    """Split reference labels without mixing people/map keys into mission names."""
    primary = dict(source)
    all_labels = source['names']+source.get('related_fields', [])
    primary['names'] = [n for n in all_labels if field_key(n['field']) not in REFERENCE_FIELDS]
    primary['related_fields'] = [n for n in all_labels if field_key(n['field']) in REFERENCE_FIELDS]
    yield primary
    # Tuple members can repeat a field on one source line. Distinguish each
    # occurrence so none is silently lost, retaining the original field too.
    occurrences = {}
    for label in primary['related_fields']:
        if field_key(label['field']) not in REFERENCE_FIELDS:continue
        key = label['field']
        occurrences[key] = occurrences.get(key, 0)+1
        seed = field_identity(source, label, localisation=True)
        seed['id'] += ':'+str(occurrences[key])
        yield seed
