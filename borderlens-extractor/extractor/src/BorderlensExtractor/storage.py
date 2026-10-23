"""Atomic JSON chunks, validated checkpoints, and incremental ZIP creation."""

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def utc():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode('utf-8')


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    with tmp.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


class Dataset:
    def __init__(self, directory, metadata, max_records=128, max_bytes=4194304, resume=False):
        self.directory = Path(directory)
        self.max_records, self.max_bytes = max_records, max_bytes
        self.ids, self.buffer, self.buffer_bytes = set(), [], 0
        self.counts = {}
        self.capture_complete = False
        if resume:
            self.manifest = json.loads((self.directory/'manifest.json').read_text(encoding='utf-8'))
            if self.manifest.get('format_version') != metadata['format_version']:
                raise ValueError('Cannot resume a different raw format version')
            if self.manifest.get('extractor_version') != metadata.get('extractor_version'):
                raise ValueError('Extractor version changed; start a new export')
            self.capture_complete = self.manifest.get('status') == 'complete'
            if self.manifest.get('configuration') != metadata.get('configuration'):
                raise ValueError('Export settings changed; start a new export')
            for chunk in self.manifest.get('chunks',[]):
                relative = Path(chunk['file'])
                if relative.is_absolute() or '..' in relative.parts or relative.parts[:1] != ('data',):
                    raise ValueError('Unsafe checkpoint chunk path')
                path = self.directory/relative
                if not path.resolve().is_relative_to(self.directory.resolve()):
                    raise ValueError('Checkpoint chunk escapes export folder')
                raw = path.read_bytes()
                if sha256(raw).hexdigest() != chunk['sha256']:
                    raise ValueError('Corrupt checkpoint chunk: '+chunk['file'])
                records = json.loads(raw)
                if not isinstance(records,list) or len(records)!=chunk['records']:
                    raise ValueError('Invalid checkpoint record count')
                for row in records:
                    key = row['id']
                    if not isinstance(key,str) or key in self.ids:
                        raise ValueError('Duplicate/invalid raw record ID')
                    self.ids.add(key)
                    kind = row['record_type']
                    self.counts[kind] = self.counts.get(kind,0)+1
            previous = self.manifest.get('sessions', [])
            if previous and previous[-1].get('mods') != metadata['session'].get('mods'):
                self.manifest['coverage']['limitations'].append('Enabled mod snapshot changed between sessions; data provenance is mixed.')
            self.manifest.setdefault('sessions',[]).append(metadata['session'])
            self.manifest['status'] = 'running'
            self.manifest['coverage']['resumed'] = True
        else:
            self.directory.mkdir(parents=True,exist_ok=False)
            (self.directory/'data').mkdir()
            self.manifest = {**metadata,'status':'running','created_utc':utc(),'updated_utc':utc(),
                'sessions':[metadata['session']],'chunks':[],'counts':{},
                'coverage':{'catalogue_complete':False,'resumed':False,
                            'limitations':['Loaded/curated data packages only; not every map/script source.',
                                           'Raw definitions/formulas only; no generated stat extrema or final family JSON.']}}
        self.manifest['counts'] = dict(self.counts)
        self.checkpoint()

    def add(self, row):
        if row['id'] in self.ids:
            return False
        raw_size = len(encoded(row))
        if self.buffer and self.buffer_bytes+raw_size>self.max_bytes:
            self.flush()
        self.ids.add(row['id'])
        self.buffer.append(row)
        self.buffer_bytes += raw_size
        kind = row['record_type']
        self.counts[kind] = self.counts.get(kind,0)+1
        if len(self.buffer)>=self.max_records:
            self.flush()
        return True

    def flush(self):
        if not self.buffer:return
        number = len(self.manifest['chunks'])+1
        name = 'data/records-'+str(number).zfill(5)+'.json'
        raw = encoded(self.buffer)
        atomic(self.directory/name,raw)
        self.manifest['chunks'].append({'file':name,'records':len(self.buffer),'bytes':len(raw),
                                        'sha256':sha256(raw).hexdigest()})
        self.buffer, self.buffer_bytes = [], 0
        self.checkpoint(flush=False)

    def checkpoint(self, flush=True, **updates):
        if flush:self.flush()
        self.manifest.update(updates)
        self.manifest['counts'] = dict(self.counts)
        self.manifest['updated_utc'] = utc()
        atomic(self.directory/'manifest.json',encoded(self.manifest))


class Bundle:
    """One 64-KiB block per step; never touches Unreal objects."""
    def __init__(self, dataset):
        self.root = dataset.directory
        self.output = self.root.with_suffix('.zip')
        self.temp = self.root.with_suffix('.zip.partial')
        self.files = [self.root/c['file'] for c in dataset.manifest['chunks']]+[self.root/'manifest.json']
        self.zip = ZipFile(self.temp,'w',ZIP_DEFLATED,compresslevel=5)
        self.source = self.target = None
        self.done = False
        self.bytes = 0
        self.index = 0

    def step(self):
        if self.done:return True
        if self.source is None:
            if self.index>=len(self.files):
                self.zip.close()
                self.temp.replace(self.output)
                self.done = True
                return True
            path = self.files[self.index]
            self.index += 1
            self.source = path.open('rb')
            self.target = self.zip.open(self.root.name+'/'+str(path.relative_to(self.root)).replace('\\','/'),'w',force_zip64=True)
        block = self.source.read(65536)
        if block:
            self.target.write(block)
            self.bytes += len(block)
        else:
            self.source.close();self.target.close()
            self.source = self.target = None
        return False

    def close(self):
        if self.source is not None:self.source.close()
        if self.target is not None:self.target.close()
        self.source = self.target = None
        if not self.done:self.zip.close()
