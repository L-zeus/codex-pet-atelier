"""Deterministic Codex v1 checks; these cannot certify animation semantics or rights."""
import hashlib
import json
import os
import re
from pathlib import Path
import tempfile

from PIL import Image, ImageChops

SIZE = (1536, 1872)
CELL = (192, 208)
STATES = ('idle', 'running-right', 'running-left', 'waving', 'jumping', 'failed', 'waiting', 'running', 'review')
COUNTS = (6, 8, 8, 4, 5, 8, 6, 6, 6)
DURATIONS = ((280, 110, 110, 140, 140, 320), (120,)*7+(220,), (120,)*7+(220,), (140,)*3+(280,), (140,)*4+(280,), (140,)*7+(240,), (150,)*5+(260,), (120,)*5+(220,), (150,)*5+(280,))
ID_RE = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def atomic_write(path, data):
    """Replace an output entry without writing through an existing hard link."""
    path = Path(path)
    reject_symlink_chain(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.atelier-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def reject_package_output(package, output):
    reject_symlink_chain(output)
    package, output = Path(package).resolve(), Path(output).resolve()
    if output == package or package in output.parents:
        raise ValueError('output must be outside package')


def reject_symlink_chain(path):
    for part in (Path(path), *Path(path).parents):
        if part.is_symlink():
            raise ValueError(f'symlink path refused: {part}')


def validate(package):
    package = Path(package).absolute()
    report = {'ok': False, 'package': str(package), 'contract': 'codex-v1-8x9', 'errors': [], 'warnings': [], 'rows': [], 'visual_qa': 'NOT_EXECUTED', 'gui_qa': 'NOT_EXECUTED'}
    errors = report['errors']
    try:
        reject_symlink_chain(package)
        if not package.is_dir():
            raise ValueError('package directory missing')
        for child in package.iterdir():
            if child.is_symlink():
                raise ValueError(f'symlink package entry refused: {child.name}')
        manifest_path = package / 'pet.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            raise ValueError('manifest must be an object')
        for field in ('id', 'displayName', 'description', 'spritesheetPath'):
            if not isinstance(manifest.get(field), str) or not manifest[field].strip():
                errors.append(f'missing or invalid manifest field: {field}')
        pet_id = manifest.get('id', '')
        if not isinstance(pet_id, str) or not ID_RE.fullmatch(pet_id):
            errors.append('invalid id')
        if pet_id != package.name:
            errors.append('id must equal package directory name')
        # A fixed basename closes absolute paths, traversal, Windows paths, and URI escapes.
        if manifest.get('spritesheetPath') != 'spritesheet.webp':
            errors.append('spritesheetPath must be the relative basename spritesheet.webp')
        if errors:
            return report
        sprite_path = package / 'spritesheet.webp'
        reject_symlink_chain(sprite_path)
        report.update(pet_id=pet_id, manifest_sha256=digest(manifest_path), spritesheet_sha256=digest(sprite_path))
        with Image.open(sprite_path) as source:
            if getattr(source, 'n_frames', 1) != 1:
                errors.append('atlas must be a single static image, not an animated WebP')
            source.load()
            report.update(size=list(source.size), mode=source.mode, format=source.format)
            if source.format != 'WEBP':
                errors.append('spritesheet.webp must contain WebP bytes')
            if source.size != SIZE:
                errors.append(f'wrong size: expected {SIZE}, got {source.size}')
            if source.mode != 'RGBA':
                errors.append(f'alpha/RGBA required, got {source.mode}')
            if errors:
                return report
            atlas = source.copy()
        red, green, blue, alpha = atlas.split()
        zero_alpha = alpha.point(lambda v: 255 if v == 0 else 0)
        rgb = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        if ImageChops.multiply(rgb, zero_alpha).getbbox():
            errors.append('fully transparent pixels retain hidden RGB residue')
        if alpha.getextrema()[0] != 0:
            errors.append('transparent background required')
        for row, (state, count) in enumerate(zip(STATES, COUNTS)):
            row_report = {'row': row, 'state': state, 'used_frames': count, 'durations_ms': list(DURATIONS[row]), 'frames': []}
            hashes = []
            cropped_hashes = []
            for col in range(8):
                frame = atlas.crop((col*192, row*208, (col+1)*192, (row+1)*208))
                bbox = frame.getchannel('A').getbbox()
                if col < count:
                    frame_hash = hashlib.sha256(frame.tobytes()).hexdigest()
                    hashes.append(frame_hash)
                    row_report['frames'].append({'column': col, 'bbox': bbox, 'sha256': frame_hash})
                    if bbox is None:
                        errors.append(f'{state}[{col}]: empty effective frame')
                    else:
                        cropped = frame.crop(bbox)
                        cropped_hashes.append((cropped.size, hashlib.sha256(cropped.tobytes()).hexdigest()))
                        if bbox[0] == 0 or bbox[1] == 0 or bbox[2] == 192 or bbox[3] == 208:
                            report['warnings'].append(f'{state}[{col}]: touches cell edge; inspect clipping')
                elif bbox is not None:
                    errors.append(f'{state}[{col}]: unused cell is not transparent')
            row_report['unique_frames'] = len(set(hashes))
            if len(set(hashes)) < 2:
                errors.append(f'{state}: identical frames cannot certify an animation')
            row_report['unique_translation_normalized_frames'] = len(set(cropped_hashes))
            if len(cropped_hashes) == count and len(set(cropped_hashes)) == 1 and len(set(hashes)) > 1:
                errors.append(f'{state}: translation-only copies cannot certify an animation')
            report['rows'].append(row_report)
        report['used_cells'] = sum(COUNTS)
        report['unused_cells'] = 72-sum(COUNTS)
        report['warnings'].append('Distinct pixels do not prove pose changes, identity, directional cadence, or semantic correctness; visual review is required.')
        report['ok'] = not errors
    except (OSError, ValueError, TypeError, Image.DecompressionBombError) as exc:
        errors.append(f'{type(exc).__name__}: {exc}')
    return report
