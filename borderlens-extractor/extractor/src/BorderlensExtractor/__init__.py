"""Manual raw catalogue extraction for Borderlands GOTY Enhanced."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
import platform
import sys
import time

import mods_base
import unrealsdk
from mods_base import (SETTINGS_DIR, ButtonOption, SpinnerOption, build_mod,
                       get_pc, get_ordered_mod_list, hook, keybind)
from unrealsdk import logging
from unrealsdk.hooks import Type

from .job import Job
from .policy import FORMAT_VERSION, LIMITS, validate_plan
from .storage import atomic, encoded, utc

SETTINGS = Path(SETTINGS_DIR) / 'BorderlensExtractor'
SETTINGS.mkdir(parents=True, exist_ok=True)
EXPORTS = SETTINGS / 'exports'
LABEL = '[Borderlens Extractor]'
__version__: str
__version_info__: tuple[int, ...]
job = None
world_token = None
last_status = 0.0
last_log = 0.0

scope = SpinnerOption('Export scope', value='Catalogue packages',
    choices=['Catalogue packages', 'Loaded data only'], wrap_enabled=True,
    description='Catalogue packages loads the bundled data-package plan. Loaded data only is a smaller snapshot. Start a fresh export after changing this.')


def report(message, error=False):
    (logging.error if error else logging.info)(f'{LABEL} {message}')


def safe(callback):
    @wraps(callback)
    def wrapped(*args, **kwargs):
        global job
        try:
            return callback(*args, **kwargs)
        except Exception as exc:
            if job is not None:
                try:job.close()
                except Exception:pass
                job.state = 'failed'
            report(f'{callback.__name__} failed: {type(exc).__name__}: {exc}. Existing export chunks are retained.', True)
            return None
    return wrapped


def context():
    pc = get_pc()
    if pc is None or pc.Pawn is None or pc.WorldInfo is None:
        raise ValueError('Load a character and wait until the HUD appears first.')
    world = pc.WorldInfo
    if int(world.NetMode) == 3:
        raise ValueError('Run the extractor in a solo game, not as a co-op client.')
    # Paths and raw profile fields only; never call pawn/item stat functions.
    map_name = world._path_name().split('.', 1)[0]
    profile = getattr(pc, 'LastLoadedProfile', None)
    # Enhanced keeps a persistent Loader world; record streamed levels as
    # additional provenance instead of treating 'Loader' as the playable map.
    streaming = []
    try:
        for entry in world.StreamingLevels:
            loaded_level = getattr(entry, 'LoadedLevel', None)
            streaming.append({'package':str(entry.PackageName),
                              'loaded_level':loaded_level._path_name() if loaded_level is not None else None})
        streaming_error = None
    except Exception as exc:
        streaming_error = repr(exc)[:500]
    data = {'started_utc':utc(), 'map':map_name,
            'streaming_levels':streaming, 'streaming_levels_error':streaming_error,
            'character_class':pc.Pawn.Class._path_name(),
            'profile_level':getattr(profile, 'ExpLevel', None),
            'sdk_version':str(getattr(unrealsdk, '__version__', 'unknown')),
            'mods_base_version':str(getattr(mods_base, '__version__', 'unknown')),
            'python':platform.python_version(), 'architecture':platform.machine(),
            'platform':sys.platform, 'executable':Path(sys.executable).name,
            'game':'BL1E', 'game_build':'not independently verified',
            'vanilla_status':'unverified; restart after disabling gameplay mods',
            'mods':[{'name':str(m.name), 'version':str(m.version),
                     'enabled':bool(m.is_enabled), 'type':str(m.mod_type)}
                    for m in get_ordered_mod_list()]}
    return data, (map_name, world._get_address(), pc.Pawn._get_address())


def metadata(session):
    raw = files(__package__).joinpath('package-plan.json').read_bytes()
    packages = validate_plan(json.loads(raw))
    config = {'scope':'catalogue' if scope.value == 'Catalogue packages' else 'loaded',
              'package_plan_sha256':sha256(raw).hexdigest(), 'limits':LIMITS}
    return {'format_version':FORMAT_VERSION, 'extractor_version':__version__,
            'configuration':config, 'session':session}, packages


def publish():
    if job is None:return
    status = job.progress()
    if job.state == 'complete':status['archive'] = str(job.bundle.output)
    atomic(SETTINGS/'status.json', encoded(status))


def previous_export():
    pointer = SETTINGS/'latest.json'
    try:
        name = json.loads(pointer.read_text(encoding='utf-8'))['directory']
    except FileNotFoundError:return None
    if not isinstance(name,str) or Path(name).name != name or name in ('.','..'):
        raise ValueError('Invalid latest-export pointer')
    directory = EXPORTS/name
    if not directory.resolve().is_relative_to(EXPORTS.resolve()):
        raise ValueError('Export pointer escapes exports folder')
    try:
        manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    except FileNotFoundError:
        report('Previous export folder or manifest is missing; starting a fresh capture.')
        return None
    if manifest.get('extractor_version') != __version__:
        report('Previous export uses another extractor version; starting a fresh capture.')
        return None
    return directory if manifest.get('status') != 'complete' or not directory.with_suffix('.zip').exists() else None


@safe
def start(fresh=False):
    global job, world_token, last_status, last_log
    session, token = context()
    meta, packages = metadata(session)
    directory = None if fresh else previous_export()
    if job is not None:job.close()
    if directory is None:
        directory = EXPORTS/('borderlens-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    job = Job(unrealsdk, directory, meta, packages, resume=directory.exists())
    world_token = token
    atomic(SETTINGS/'latest.json', encoded({'directory':directory.name}))
    last_status = last_log = time.monotonic()
    publish()
    report(f'Export started: {directory}. Stay on this map. F9 pauses/resumes; progress is in status.json.')


@keybind('Start / pause / resume raw export', 'F9')
@safe
def export_key():
    global job
    if job is None or job.state in ('complete','failed'):
        start()
    elif job.state == 'running':
        job.pause()
        publish()
        report('Paused. F9 resumes.')
    else:
        _, token = context()
        if token != world_token:
            raise ValueError('World changed; use Start fresh export in the mod menu.')
        job.resume()
        publish()
        report('Resumed.')


@safe
def fresh_export(_option=None):
    start(fresh=True)


@safe
def show_status(_option=None):
    if job is None:
        report(f'No active job. Load a character, close menus, then press F9. Output: {EXPORTS}')
    else:
        publish()
        report(json.dumps(job.progress(), ensure_ascii=False))


@safe
def finish_early(_option=None):
    if job is not None and job.state in ('running','paused'):
        job.finish('User ended capture early; remaining work was not scanned.')
        publish()
        report('Finishing partial export ZIP; close menus and wait for completion.')


@hook('Engine.GameViewportClient:PostRender', Type.POST)
@safe
def on_render(_obj, _args, _ret, _func):
    global last_status, last_log, job
    if job is None or job.state != 'running':return
    now = time.monotonic()
    if now-last_status >= 1:
        _, token = context()
        if token != world_token:
            stop_for_travel()
            return
        publish()
        last_status = now
    before = job.state
    job.tick()
    if job.state != before:
        publish()
        if job.state == 'complete':report(f'Export ZIP ready: {job.bundle.output}')
        elif job.state == 'failed':report(f'Export failed; see {job.dataset.directory}/manifest.json', True)
    elif now-last_log >= 10:
        report(f'{job.phase}: {sum(job.dataset.counts.values())} records; {job.package_index}/{len(job.packages)} packages. {job.note}')
        last_log = now


@safe
def stop_for_travel():
    global job, world_token
    if job is None:return
    if job.state != 'complete':
        job.pause('Stopped for world change; F9 will resume from committed chunks.', release=True)
        job.close()
        report('Export stopped for world change. Load a map and press F9 to resume, or start fresh.')
    job = None
    world_token = None


@hook('WillowGame.WillowGameInfo:PreCommitMapChange')
def on_travel(_obj, _args, _ret, _func):
    stop_for_travel()


@safe
def on_disable():
    stop_for_travel()


build_mod(options=[scope,
                   ButtonOption('Show export status (SDK log)', on_press=show_status),
                   ButtonOption('Start fresh export', on_press=fresh_export),
                   ButtonOption('Finish partial export now', on_press=finish_early)],
          keybinds=[export_key], hooks=[on_render, on_travel],
          on_disable=on_disable, settings_file=SETTINGS/'mod.json')
report(f'Loaded {__version__}. Load a solo character, then F9 to export.')
