#!/usr/bin/env python3
"""Measure real atlas transitions and verify GIF containers; never certify visual QA."""
import argparse
import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from petlib import CELL, COUNTS, DURATIONS, STATES, digest, reject_package_output, validate, write_json
from preview_pet import gif_bytes


def decoded_hash(frame):
    rgba = frame.convert('RGBA')
    # Invisible palette RGB is irrelevant; compare all visible colors and alpha.
    rgba.paste((0, 0, 0, 0), mask=rgba.getchannel('A').point(lambda value: 255 if value == 0 else 0))
    return hashlib.sha256(rgba.tobytes()).hexdigest()


def audit(package, preview_dir=None):
    validation = validate(package)
    result = {'ok': False, 'validation': validation, 'rows': [], 'errors': [],
              'visual_qa': 'NOT_EXECUTED',
              'note': 'Pixel differences and bounding boxes are diagnostic measurements. They do not prove pose changes, identity, direction, or smooth playback.'}
    if not validation['ok']:
        result['errors'] = validation['errors']
        return result
    with Image.open(Path(package) / 'spritesheet.webp') as src:
        atlas = src.convert('RGBA')
    result['spritesheet_sha256'] = validation['spritesheet_sha256']
    for row, (state, count) in enumerate(zip(STATES, COUNTS)):
        frames = [atlas.crop((col*192, row*208, (col+1)*192, (row+1)*208)) for col in range(count)]
        boxes = [frame.getchannel('A').getbbox() for frame in frames]
        # Composite on gray so hidden RGB cannot distort measurements.
        composites = []
        for frame in frames:
            background = Image.new('RGBA', frame.size, '#808080')
            composites.append(Image.alpha_composite(background, frame).convert('RGB'))
        changes = []
        for index in range(count):
            other = (index+1) % count
            difference = ImageChops.difference(composites[index], composites[other])
            changes.append({'from': index, 'to': other,
                            'loop_seam': other == 0,
                            'mean_rgb_difference': sum(ImageStat.Stat(difference).mean)/3,
                            'changed_bbox': difference.getbbox()})
        item = {'state': state, 'frames': count, 'bboxes': boxes,
                'baseline_range_px': max(b[3] for b in boxes)-min(b[3] for b in boxes),
                'height_range_px': max(b[3]-b[1] for b in boxes)-min(b[3]-b[1] for b in boxes),
                'transitions': changes, 'gif': {'status': 'NOT_RUN'}}
        if preview_dir is not None:
            gif_path = Path(preview_dir) / f'{state}.gif'
            try:
                with Image.open(gif_path) as gif:
                    timings, hashes = [], []
                    for index in range(gif.n_frames):
                        gif.seek(index)
                        timings.append(gif.info.get('duration'))
                        hashes.append(decoded_hash(gif))
                    with Image.open(BytesIO(gif_bytes(frames, DURATIONS[row]))) as expected:
                        expected_hashes = []
                        for index in range(expected.n_frames):
                            expected.seek(index)
                            expected_hashes.append(decoded_hash(expected))
                    good = (gif.format == 'GIF' and gif.size == CELL and gif.info.get('loop') == 0
                            and gif.n_frames == count and timings == list(DURATIONS[row])
                            and hashes == expected_hashes)
                    item['gif'] = {'status': 'PASS' if good else 'FAIL', 'path': str(gif_path),
                                   'sha256': digest(gif_path), 'frames': gif.n_frames,
                                   'size': list(gif.size), 'loop': gif.info.get('loop'),
                                   'atlas_decoded_frames_match': hashes == expected_hashes,
                                   'durations_ms': timings, 'decoded_frame_sha256': hashes}
                    if not good:
                        result['errors'].append(f'{state}: GIF dimensions, loop, count, timing, or atlas content mismatch')
            except (OSError, ValueError) as exc:
                item['gif'] = {'status': 'FAIL', 'error': str(exc)}
                result['errors'].append(f'{state}: {exc}')
        result['rows'].append(item)
    switches = []
    for source in result['rows']:
        for target in result['rows']:
            if source is target:
                continue
            destination = target['bboxes'][0]
            def measure(box):
                return {'center_dx': ((destination[0]+destination[2])-(box[0]+box[2]))/2,
                        'center_dy': ((destination[1]+destination[3])-(box[1]+box[3]))/2,
                        'bottom_dy': destination[3]-box[3],
                        'bbox_height_ratio': (destination[3]-destination[1])/(box[3]-box[1])}
            samples = [measure(box) for box in source['bboxes']]
            switches.append({'from': source['state'], 'to': target['state'],
                             'last_to_first': samples[-1],
                             'all_source_phases': {key: [min(m[key] for m in samples), max(m[key] for m in samples)] for key in samples[0]},
                             'source_phase_count': len(samples)})
    result['state_switches'] = switches
    result['state_switch_note'] = '72 last-to-first state boundaries and every source phase to each other state first frame. Bounding boxes include hair/wings/tail/cloud and pose projection; changes are diagnostic, not automatic visual failures or GUI evidence.'
    result['ok'] = not result['errors']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('--preview-dir')
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    try:
        reject_package_output(args.package, args.report)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
    result = audit(args.package, args.preview_dir)
    write_json(args.report, result)
    print(f"Motion measurements saved; machine checks {'passed' if result['ok'] else 'failed'}; visual review required.")
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
