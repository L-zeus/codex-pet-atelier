#!/usr/bin/env python3
"""Extract already-generated poses with one independent companion per body.

Explicit x-order pairing repairs nearest-center assignment when wings extend
toward the next pose. This does not generate, mirror or change any pose. It
requires the official hatch-pet extraction module and subsequent visual QA.
"""
import argparse
import importlib.util
from pathlib import Path

from PIL import Image

from petlib import COUNTS, STATES, digest, reject_symlink_chain, write_json


def pair_companions(components, count):
    ranked = sorted(components, key=lambda item: item['area'], reverse=True)
    if len(ranked) < count*2:
        raise ValueError('need one separate body and companion per frame')
    bodies, companions, noise = ranked[:count], ranked[count:count*2], ranked[count*2:]
    if min(item['area'] for item in bodies) < 10*max(item['area'] for item in companions):
        raise ValueError('body/companion area separation ambiguous; inspect source')
    smallest = min(item['area'] for item in companions)
    if max(item['area'] for item in companions) > smallest*2:
        raise ValueError('companion size varies too much for safe rank pairing')
    for item in companions:
        x0, y0, x1, y1 = item['bbox']
        if not 0.5 <= (x1-x0)/max(1, y1-y0) <= 2:
            raise ValueError('companion shape ambiguous; inspect source')
    if any(item['area'] >= smallest/4 for item in noise):
        raise ValueError('additional substantial component; inspect source')
    bodies.sort(key=lambda item: item['center_x'])
    companions.sort(key=lambda item: item['center_x'])
    return [[body, companion] for body, companion in zip(bodies, companions)], noise


def extract(strip_path, output, state, hatch_tools):
    strip_path, output = Path(strip_path).absolute(), Path(output).absolute()
    for path in (strip_path, output):
        reject_symlink_chain(path)
    if output.exists():
        raise ValueError('output exists; source and prior candidates are never overwritten')
    module_path = Path(hatch_tools) / 'scripts/extract_strip_frames.py'
    spec = importlib.util.spec_from_file_location('hatch_extract', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Image.open(strip_path) as source:
        strip = module.remove_chroma_background(source, (255, 0, 255), 96)
    count = COUNTS[STATES.index(state)]
    groups, noise = pair_companions(module.connected_components(strip), count)
    boxes = [module.component_bounds(group) for group in groups]
    padding = 4
    top = max(0, min(box[1] for box in boxes)-padding)
    bottom = min(strip.height, max(box[3] for box in boxes)+padding)
    width = max(box[2]-box[0] for box in boxes)+2*padding
    target = output / state
    target.mkdir(parents=True)
    frames = []
    pairing = []
    for index, (group, box) in enumerate(zip(groups, boxes)):
        component = module.component_group_image(strip, group, padding=padding)
        viewport = Image.new('RGBA', (width, bottom-top))
        viewport.alpha_composite(component, ((width-component.width)//2, max(0, box[1]-padding)-top))
        frame = module.fit_viewport_to_cell(viewport)
        path = target / f'{index:02d}.png'
        frame.save(path)
        frames.append(str(path.resolve()))
        pairing.append({'frame': index, 'body_bbox': group[0]['bbox'], 'body_area': group[0]['area'],
                        'companion_bbox': group[1]['bbox'], 'companion_area': group[1]['area'],
                        'frame_sha256': digest(path)})
    receipt = {'source': str(strip_path), 'source_sha256': digest(strip_path),
               'algorithm': 'x-order-one-body-one-companion-v1', 'pairing': pairing,
               'dropped_small_components': [{'area': item['area'], 'bbox': item['bbox']} for item in noise],
               'official_extractor_sha256': digest(module_path), 'script_sha256': digest(__file__),
               'visual_qa': 'NOT_EXECUTED', 'note': 'Small disconnected noise removed; body and cloud pixels grouped without repainting. Rank association requires visual review.'}
    write_json(output / 'pairing-receipt.json', receipt)
    write_json(output / 'frames-manifest.json', {'ok': True, 'chroma_key': {'hex': '#FF00FF', 'rgb': [255,0,255], 'threshold': 96},
               'rows': [{'state': state, 'frames': frames, 'method': 'stable-slots',
                         'component_pairing': receipt['algorithm'], 'pairing_receipt': str(output / 'pairing-receipt.json')}]})
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('strip')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--state', choices=STATES, required=True)
    parser.add_argument('--hatch-tools', required=True)
    args = parser.parse_args()
    try:
        receipt = extract(args.strip, args.output_dir, args.state, args.hatch_tools)
        print(f"Extracted {len(receipt['pairing'])} real body/companion pairs; visual review required.")
        return 0
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
