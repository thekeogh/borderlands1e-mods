"""Read-only installed package inventory and English localisation crawl seeds.

Never loads a package. Unknown binary formats stay diagnostics. Localisation
sections are locators, not assumed fully-qualified Unreal object paths.
"""

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import struct
import sys

from .catalogue import category, name_field, origin, usable_name, localisation_identities

PACKAGE_EXTENSIONS = frozenset(('.upk', '.umap', '.udk', '.u', '.xxx'))
ENGLISH_EXTENSIONS = frozenset(('.int', '.eng'))
ASSIGNMENT = re.compile(r'([A-Za-z_][\w.\[\]()-]*)\s*=\s*("(?:\\.|[^"\\])*"|[^,()\r\n]+)')
TOP_ASSIGNMENT = re.compile(r'^([A-Za-z_][\w.\[\]()-]*)\s*=\s*(.*)$')
QUOTED = re.compile(r'^"(?:\\.|[^"\\])*"')


def game_root():
    for start in (Path(sys.executable).parent, Path.cwd()):
        try:
            start = start.resolve()
            for candidate in (start, *list(start.parents)[:6]):
                if (candidate/'WillowGame').is_dir():return candidate
        except OSError:continue
    return None


def header_info(raw):
    """Bounded standard UE3 summary prefix, only where its layout is known."""
    result = {'signature_hex':raw[:8].hex(), 'summary_status':'unrecognized'}
    if len(raw) < 12:return result
    endian = {b'\xc1\x83\x2a\x9e':'<', b'\x9e\x2a\x83\xc1':'>'}.get(raw[:4])
    if endian is None:return result
    packed_version = struct.unpack_from(endian+'I', raw, 4)[0]
    version, licensee = packed_version & 0xffff, packed_version >> 16
    result.update(file_version=version, licensee_version=licensee,
                  summary_status='version_only')
    # Other versions/licensee layouts need explicit support; do not guess offsets.
    if not 512 <= version <= 900 or licensee > 100:return result
    size = struct.unpack_from(endian+'i', raw, 12)[0] if len(raw) >= 16 else 0
    if not -1024 <= size <= 1024:return result
    offset = 16 + (size if size >= 0 else -size*2)
    if offset+28 > len(raw):return result
    flags, names, name_offset, exports, export_offset, imports, import_offset = struct.unpack_from(endian+'7I', raw, offset)
    if max(names, exports, imports) > 2000000:return result
    result.update(summary_status='standard_prefix_candidate', package_flags=hex(flags),
                  contains_map=bool(flags & 0x20000), name_count=names,
                  export_count=exports, import_count=imports,
                  name_offset=name_offset, export_offset=export_offset, import_offset=import_offset)
    return result


def decode_text(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):return raw.decode('utf-16'), 'utf-16'
    if b'\x00' in raw[:256]:
        return raw.decode('utf-16-le'), 'utf-16-le'
    try:return raw.decode('utf-8-sig'), 'utf-8'
    except UnicodeDecodeError:return raw.decode('cp1252'), 'cp1252'


def unquote(value):
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        # JSON's small escape vocabulary overlaps Unreal's. Preserve unknown
        # escapes verbatim instead of corrupting text with unicode_escape.
        try:return json.loads(value)
        except ValueError:
            return re.sub(r'\\([\\"])', r'\1', value[1:-1])
    return value


def localisation_sections(text, max_names=16384, max_line=131072):
    section, names, omitted = None, [], 0
    for number, line in enumerate(text.splitlines(), 1):
        if number % 128 == 0:yield None  # Even prose-only files yield frame work.
        line = line.strip()
        if not line or line.startswith((';', '#', '//')):continue
        if line.startswith('[') and ']' in line:
            if len(line) > max_line:raise ValueError('Localisation section exceeds string limit at line '+str(number))
            if section is not None and (names or omitted):yield section, names, omitted
            section, names, omitted = line[1:line.index(']')].strip(), [], 0
            continue
        if section is None:continue
        if len(line) > max_line:
            omitted += 1
            continue
        top = TOP_ASSIGNMENT.match(line)
        if top is None:continue
        field, value = top.groups()
        if value.startswith('('):
            assignments = (match.groups() for match in ASSIGNMENT.finditer(value))
        else:
            # Ordinary unquoted INI names can contain commas and parentheses.
            # Only struct tuples need tokenization.
            quoted = QUOTED.match(value) if value.startswith('"') else None
            assignments = [(field, quoted[0] if quoted is not None else value)]
        for field, value in assignments:
            if name_field(field):
                value = unquote(value)
                if usable_name(value):
                    if len(names) < max_names:names.append({'name':value.strip(), 'field':field, 'line':number})
                    else:omitted += 1
    if section is not None and (names or omitted):yield section, names, omitted


def localisation_category(relative, fields):
    keys = {re.split(r'[.\[\](]', field)[-1].casefold() for field in fields}
    path = relative.casefold()
    if keys.intersection(('aipawnname','enemyname','bossname','npcname','pawnname')) or ('displayname' in keys and any(p in path for p in ('enemies', 'npc', 'bandit', 'boss'))):
        return 'character'
    for key, value in (('missionname','mission'), ('skillname','skill'), ('itemname','item'),
                       ('partname','equipment_name'), ('vehiclename','vehicle'),
                       ('manufacturername','manufacturer'), ('challengename','challenge'),
                       ('regionname','region'), ('stationname','location'), ('locationname','location'),
                       ('mapname','map'), ('levelname','map'), ('callername','contact'),
                       ('outpostdisplayname','location'), ('stationdisplayname','location')):
        if key in keys:return value
    return 'named_localisation'


class InstallationScan:
    def __init__(self, root, limits, session):
        self.root = Path(root).resolve() if root is not None else None
        self.limits, self.session = limits, session
        self.summary = {'session':session, 'status':'pending', 'files':0, 'packages':0,
                        'root_detected':self.root is not None,
                        'localisation_files':0, 'named_sections':0, 'errors':[],
                        'limits_hit':[], 'limit_events':0, 'limit_omissions':0,
                        'error_count':0, 'error_omissions':0, 'skipped_symlinks':0,
                        'limitations':['Package inventory is metadata only; maps are never loaded.',
                                       'English localisation candidates may include unused/developer content.',
                                       'Localisation sections are not verified asset paths; packed text may be absent.']}
        self.iterator = self.run()

    def error(self, path, exc):
        self.summary['error_count'] += 1
        if len(self.summary['errors']) < 200:
            self.summary['errors'].append({'file':path, 'error':repr(exc)[:500]})
        else:self.summary['error_omissions'] += 1

    def limit(self, reason):
        self.summary['limit_events'] += 1
        if len(self.summary['limits_hit']) < 200:self.summary['limits_hit'].append(reason)
        else:self.summary['limit_omissions'] += 1

    def close(self, status='interrupted'):
        self.iterator.close()
        if self.summary['status'] in ('pending','running'):self.summary['status'] = status

    def files(self):
        willow = self.root/'WillowGame'
        if not willow.is_dir():raise ValueError('WillowGame directory not found')
        # Only content/localisation/DLC trees. No saves, SDK settings or config.
        pending = [p for p in sorted(willow.iterdir(), key=lambda p:p.name.casefold())
                   if p.name.casefold().startswith(('cookedpc', 'dlc', 'localization', 'localisation'))]
        directories = 0
        while pending:
            path = pending.pop()
            yield None
            if path.is_symlink():
                self.summary['skipped_symlinks'] += 1
                continue
            if not path.resolve().is_relative_to(willow.resolve()):continue
            if path.is_dir():
                directories += 1
                if directories > self.limits['installation_directories']:
                    self.limit('installation_directories')
                    return
                try:
                    with os.scandir(path) as entries:
                        children = []
                        for entry in entries:
                            children.append(Path(entry.path))
                            if len(children) >= self.limits['installation_files']:
                                self.limit('directory_entries')
                                break
                    pending.extend(sorted(children, key=lambda p:p.name.casefold(), reverse=True))
                except OSError as exc:self.error(str(path.relative_to(self.root)), exc)
            elif path.suffix.casefold() in PACKAGE_EXTENSIONS or path.suffix.casefold() in ENGLISH_EXTENSIONS:
                self.summary['files'] += 1
                if self.summary['files'] > self.limits['installation_files']:
                    self.limit('installation_files')
                    return
                yield path

    def run(self):
        if self.root is None:
            self.summary['status'] = 'unavailable'
            self.error('WillowGame', ValueError('Could not locate game installation from executable/working directory'))
            return
        self.summary['status'] = 'running'
        try:
            for path in self.files():
                if path is None:
                    yield None
                    continue
                relative = path.relative_to(self.root).as_posix()
                key = 'file:'+relative.casefold()+'@'+str(self.session)
                try:
                    size = path.stat().st_size
                    if path.suffix.casefold() in PACKAGE_EXTENSIONS:
                        with path.open('rb') as stream:header = header_info(stream.read(4096))
                        self.summary['packages'] += 1
                        yield {'record_type':'package_file', 'id':key, 'file':relative,
                               'package':path.stem, 'bytes':size, 'header':header,
                               'session':self.session, 'loaded_by_scan':False}
                        continue
                    self.summary['localisation_files'] += 1
                    if size > self.limits['localisation_bytes']:
                        self.limit('localisation_bytes:'+relative)
                        yield {'record_type':'localisation_file', 'id':key, 'file':relative,
                               'bytes':size, 'status':'size_limit', 'session':self.session}
                        continue
                    with path.open('rb') as stream:raw = stream.read(self.limits['localisation_bytes']+1)
                    if len(raw) > self.limits['localisation_bytes']:raise ValueError('Localisation file grew past byte limit')
                    text, encoding = decode_text(raw)
                    digest = sha256(raw).hexdigest()
                    yield {'record_type':'localisation_file', 'id':key, 'file':relative,
                           'bytes':len(raw), 'sha256':digest, 'encoding':encoding,
                           'language':path.suffix[1:].upper(),
                           'status':'read', 'session':self.session}
                    occurrences = {}
                    for section in localisation_sections(text, self.limits['array'], self.limits['string']):
                        if section is None:
                            yield None
                            continue
                        section_name, names, omitted = section
                        occurrences[section_name] = occurrences.get(section_name, 0)+1
                        if omitted:self.limit('localisation_names:'+relative+':'+section_name[:100])
                        self.summary['named_sections'] += 1
                        if self.summary['named_sections'] > self.limits['identities']:
                            self.limit('localisation_identities')
                            self.summary['status'] = 'partial'
                            return
                        locator = relative.casefold()+'\n'+section_name+'\n'+str(occurrences[section_name])
                        locator_id = 'localisation:'+sha256(locator.encode('utf-8')).hexdigest()
                        parts = section_name.rsplit(None, 1)
                        object_name = parts[0]
                        class_hint = parts[1] if len(parts) == 2 else None
                        asset_hint = object_name if object_name.casefold().startswith(path.stem.casefold()+'.') else path.stem+'.'+object_name
                        source = {'record_type':'catalogue_identity', 'id':'identity:'+locator_id+':'+digest,
                               'locator_id':locator_id,
                               'category':category(class_hint or '') or localisation_category(relative, [n['field'] for n in names]),
                               'asset_path':None, 'asset_path_hint':asset_hint,
                               'internal_name':object_name, 'class':None, 'class_hint':class_hint, 'names':names,
                               'identity_status':'localisation_candidate',
                               'source_file':relative, 'source_sha256':digest, 'source_record':key,
                               'section':section_name, 'section_occurrence':occurrences[section_name],
                               'origin_hint':origin(path.stem), 'omitted_name_values':omitted,
                               'character_role':None, 'is_boss':None, 'is_named_enemy':None,
                               'context':{'session':self.session}, 'source_complete':not omitted}
                        yield from localisation_identities(source)
                except (OSError, ValueError, UnicodeError) as exc:
                    self.error(relative, exc)
                    yield {'record_type':'installation_error', 'id':'error:'+key,
                           'file':relative, 'session':self.session, 'error':repr(exc)[:500]}
        except (OSError, ValueError) as exc:
            self.error('WillowGame', exc)
        self.summary['status'] = 'partial' if self.summary['errors'] or self.summary['limits_hit'] else 'complete'
        self.summary['english_names_found'] = bool(self.summary['named_sections'])
