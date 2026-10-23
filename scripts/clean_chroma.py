#!/usr/bin/env python3
"""Conservative magenta despill for already-extracted RGBA frames.

No frame is generated, duplicated, resized, translated, or warped. The original
files are never overwritten. This is a repair candidate, not visual acceptance.

The local model is C=t*F+(1-t)*K with K=(255,0,255). F is estimated from nearby
opaque non-magenta pixels; least-squares projection estimates t. The output uses
unmixed RGB and old_alpha*t. A transparent-region boundary band bounds the operation.
This underdetermined inverse cannot recover missing pixels or guarantee exact
color. Thin structures without an interior sample use a reported conservative
despill fallback. Legitimate magenta edge details would be altered; do not use
this tool for characters whose design contains magenta. Review the source and
output over light and dark backgrounds before acceptance.
Interior key pixels are protected by default. The explicit include_interior_key
option is only for visually confirmed contamination in artwork without genuine
magenta; it does not infer whether a color belongs to the character design.
"""
import argparse
from collections import deque
import json
from pathlib import Path

from PIL import Image
from petlib import digest, reject_symlink_chain, write_json

KEY = (255, 0, 255)


def magenta(pixel, excess=35):
    r, g, b, a = pixel
    return a > 0 and r-g > excess and b-g > excess and min(r, b) > 60


def rgba_pixels(image):
    # Pillow 13 renamed getdata; retain compatibility with the minimum 10.4.
    return image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata()


def visible_key_count(image):
    return sum(a > 16 and r-g > 50 and b-g > 50 and r > 80 and b > 80 for r, g, b, a in rgba_pixels(image))


def cool_residue(pixel):
    r, g, b, a = pixel
    return a > 16 and b > 40 and b > min(r, g)+12


def exterior_band(pixels, width, height, depth):
    """Return distance into foreground from connected transparent regions.

    Enclosed transparent gaps between hair locks are also true matte boundaries.
    Opaque inner pixels beyond the requested band remain untouched.
    """
    distance = [-1] * (width*height)
    pending = deque()
    def enqueue(x, y):
        index = y*width+x
        if distance[index] < 0 and pixels[index][3] <= 16:
            distance[index] = 0
            pending.append(index)
    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height-1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width-1, y)
    # Include enclosed transparent hair/lace gaps as their own components.
    for index, pixel in enumerate(pixels):
        if pixel[3] <= 16 and distance[index] < 0:
            distance[index] = 0
            pending.append(index)
    # Establish connected transparent regions, including fine gaps.
    while pending:
        index = pending.popleft()
        x, y = index % width, index // width
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < width and 0 <= ny < height:
                enqueue(nx, ny)
    pending = deque(index for index, value in enumerate(distance) if value == 0)
    while pending:
        index = pending.popleft()
        level = distance[index]
        if level >= depth:
            continue
        x, y = index % width, index // width
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < width and 0 <= ny < height:
                other = ny*width+nx
                if distance[other] < 0:
                    distance[other] = level+1
                    pending.append(other)
    return distance


def clean_frame(image, band=4, radius=6, rgb_mode='unmix', include_interior_key=False, foreground_palette='any'):
    if image.mode != 'RGBA':
        raise ValueError('RGBA input required')
    if not 1 <= band <= 12 or not 1 <= radius <= 16:
        raise ValueError('band must be 1..12 and radius 1..16')
    if rgb_mode not in ('unmix', 'neighbor'):
        raise ValueError('rgb_mode must be unmix or neighbor')
    if foreground_palette not in ('any', 'warm'):
        raise ValueError('foreground_palette must be any or warm')
    original = list(rgba_pixels(image))
    output = original.copy()
    width, height = image.size
    distance = exterior_band(original, width, height, band)
    stats = {'size': list(image.size), 'visible_key_before': visible_key_count(image), 'changed_pixels': 0, 'unmixed_pixels': 0, 'fallback_pixels': 0, 'normalized_transparent_pixels': 0, 'interior_magenta_untouched': 0, 'interior_magenta_processed': 0, 'band_pixels': sum(value >= 0 and value <= band for value in distance)}
    offsets = sorted(((dx*dx+dy*dy, dx, dy) for dy in range(-radius, radius+1) for dx in range(-radius, radius+1) if 0 < dx*dx+dy*dy <= radius*radius))
    for index, pixel in enumerate(original):
        red, green, blue, alpha = pixel
        if alpha == 0:
            if pixel != (0,0,0,0):
                output[index] = (0,0,0,0)
                stats['normalized_transparent_pixels'] += 1
            continue
        if not magenta(pixel) and not (foreground_palette == 'warm' and cool_residue(pixel)):
            continue
        if distance[index] < 0:
            if not include_interior_key:
                stats['interior_magenta_untouched'] += 1
                continue
            stats['interior_magenta_processed'] += 1
        x, y = index % width, index // width
        candidates = []
        nearest_distance = None
        for squared, dx, dy in offsets:
            if nearest_distance is not None and squared > nearest_distance+4:
                break
            nx, ny = x+dx, y+dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            neighbor = original[ny*width+nx]
            if neighbor[3] < 220 or magenta(neighbor, excess=20):
                continue
            if foreground_palette == 'warm' and cool_residue(neighbor):
                continue
            if nearest_distance is None:
                nearest_distance = squared
            vector = tuple(neighbor[channel]-KEY[channel] for channel in range(3))
            observed = tuple(pixel[channel]-KEY[channel] for channel in range(3))
            denominator = sum(v*v for v in vector)
            if denominator == 0:
                continue
            weight = max(0.03, min(1.0, sum(v*c for v,c in zip(vector,observed))/denominator))
            residual = sum((observed[channel]-weight*vector[channel])**2 for channel in range(3))
            candidates.append((residual+4*squared, weight, neighbor))
        if candidates:
            _, weight, foreground = min(candidates, key=lambda entry: entry[0])
            # Ill-conditioned unmixing of white/lavender edges can invent green.
            # Optional neighbor mode uses an observed foreground color while
            # retaining the projected alpha; it remains a visual-QA candidate.
            rgb = foreground[:3] if rgb_mode == 'neighbor' else tuple(round(max(0,min(255,(pixel[channel]-(1-weight)*KEY[channel])/weight))) for channel in range(3))
            # Noise/incorrect interior estimates can leave red spill on blue edges.
            # Bound only that remaining simultaneous red+blue excess.
            if rgb[0]-rgb[1] > 30 and rgb[2]-rgb[1] > 30:
                rgb = (min(rgb[0], rgb[1]+20), rgb[1], rgb[2])
            new_alpha = round(alpha*weight)
            output[index] = (*rgb, new_alpha) if new_alpha else (0,0,0,0)
            stats['unmixed_pixels'] += 1
        else:
            # Thin strand with no reliable interior sample. Retain geometry,
            # reduce red spill and confidence; count this explicitly for QA.
            excess = min(red-green, blue-green)
            weight = max(0.1, min(1.0, 1-excess/255))
            new_alpha = round(alpha*weight)
            output[index] = (min(red, green+20), green, blue, new_alpha) if new_alpha else (0,0,0,0)
            stats['fallback_pixels'] += 1
    stats['changed_pixels'] = sum(a != b for a,b in zip(original,output))
    stats['alpha_nonzero_before'] = sum(p[3] > 0 for p in original)
    stats['alpha_nonzero_after'] = sum(p[3] > 0 for p in output)
    cleaned = Image.new('RGBA', image.size)
    cleaned.putdata(output)
    stats['visible_key_after'] = visible_key_count(cleaned)
    stats['cool_residue_before'] = sum(cool_residue(pixel) for pixel in original)
    stats['cool_residue_after'] = sum(cool_residue(pixel) for pixel in output)
    stats['visual_qa'] = 'NOT_EXECUTED'
    return cleaned, stats


def clean_directory(source, output, band=4, radius=6, rgb_mode='unmix', include_interior_key=False, foreground_palette='any'):
    source, output = Path(source).absolute(), Path(output).absolute()
    reject_symlink_chain(source)
    reject_symlink_chain(output)
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('output must be separate from source')
    if output.exists():
        raise ValueError('output exists; originals and previous trials are never overwritten')
    manifest_path = source / 'frames-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict):
        raise ValueError('frame manifest must be an object')
    chroma_key = manifest.get('chroma_key')
    if not isinstance(chroma_key, dict) or chroma_key.get('rgb') != list(KEY):
        raise ValueError('this conservative tool supports only the documented magenta key')
    rows = manifest.get('rows')
    if not isinstance(rows,list) or not rows:
        raise ValueError('source frame manifest needs rows')
    plans = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('frames'), list) or not row['frames']:
            raise ValueError('every row must list existing frames')
        for entry in row['frames']:
            if not isinstance(entry, str):
                raise ValueError('frame paths must be strings')
            path = Path(entry)
            if not path.is_absolute():
                path = source / path
            reject_symlink_chain(path)
            path = path.resolve()
            if source not in path.parents:
                raise ValueError('manifest frame escapes source directory')
            relative = path.relative_to(source)
            if path.suffix.lower() != '.png' or not path.is_file():
                raise ValueError('manifest must list real PNG frames')
            plans.append((path,relative))
    if len({relative for _,relative in plans}) != len(plans):
        raise ValueError('duplicate frame paths in manifest')
    output.mkdir(parents=True)
    frames = []
    for path,relative in plans:
        before_hash = digest(path)
        with Image.open(path) as image:
            cleaned, stats = clean_frame(image,band,radius,rgb_mode,include_interior_key,foreground_palette)
        target = output / relative
        target.parent.mkdir(parents=True,exist_ok=True)
        cleaned.save(target)
        if digest(path) != before_hash:
            raise ValueError('source changed during repair')
        frames.append({'path': str(relative), 'source_sha256': before_hash, 'output_sha256': digest(target), **stats})
    for row in rows:
        row['frames'] = [str(output / Path(entry).resolve().relative_to(source)) if Path(entry).is_absolute() else str(output / entry) for entry in row['frames']]
    algorithm = 'connected-magenta-neighbor-v1' if rgb_mode == 'neighbor' else 'connected-magenta-unmix-v2'
    manifest['edge_cleanup'] = {'algorithm': algorithm, 'source': str(source), 'band':band, 'radius':radius, 'rgb_mode':rgb_mode, 'include_interior_key':include_interior_key, 'foreground_palette':foreground_palette}
    write_json(output/'frames-manifest.json',manifest)
    report = {'ok':True,'status':'REPAIR_CANDIDATE_REQUIRES_VISUAL_QA','algorithm':algorithm,'source':str(source),'output':str(output),'band':band,'radius':radius,'rgb_mode':rgb_mode,'include_interior_key':include_interior_key,'foreground_palette':foreground_palette,'frame_count_before':len(plans),'frame_count_after':len(frames),'frames':frames,'limitations':__doc__,'script_sha256':digest(__file__),'visual_qa':'NOT_EXECUTED'}
    write_json(output/'chroma-clean-report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--band',type=int,default=4)
    parser.add_argument('--radius',type=int,default=6)
    parser.add_argument('--rgb-mode',choices=('unmix','neighbor'),default='unmix',help='Neighbor uses a sampled foreground RGB to avoid inverse-color overshoot; requires visual QA.')
    parser.add_argument('--include-interior-key',action='store_true',help='Opt in only after visual confirmation of interior key contamination and absence of genuine magenta design.')
    parser.add_argument('--foreground-palette',choices=('any','warm'),default='any',help='Warm is only for confirmed blue/purple contamination in an exclusively warm/neutral source palette; never use for genuine blue/lavender designs.')
    args=parser.parse_args()
    try:
        report=clean_directory(args.source,args.output_dir,args.band,args.radius,args.rgb_mode,args.include_interior_key,args.foreground_palette)
        print(json.dumps({'status':report['status'],'frame_count':report['frame_count_after'],'key_pixels_before':sum(row['visible_key_before'] for row in report['frames']),'key_pixels_after':sum(row['visible_key_after'] for row in report['frames']),'report':str(Path(args.output_dir)/'chroma-clean-report.json')},indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        parser.exit(1,f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
