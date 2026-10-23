#!/usr/bin/env python3
"""Render nine actual atlas rows as GIFs at official Codex v1 timing."""
import argparse
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
from petlib import COUNTS, DURATIONS, STATES, atomic_write, reject_package_output, reject_symlink_chain, validate, write_json


def gif_bytes(frames, durations):
    """The canonical project GIF renderer, also used to bind decoded QA to its atlas."""
    palette_frames = []
    for frame in frames:
        pal = frame.convert('RGB').quantize(colors=255)
        mask = frame.getchannel('A').point(lambda v: 255 if v < 128 else 0)
        pal.paste(255, mask=mask)
        pal.info['transparency'] = 255
        palette_frames.append(pal)
    output = BytesIO()
    palette_frames[0].save(output, format='GIF', save_all=True, append_images=palette_frames[1:],
                           duration=list(durations), loop=0, disposal=2, transparency=255, optimize=False)
    return output.getvalue()


def preview(package, output_dir):
    report = validate(package)
    if not report['ok']:
        raise ValueError('; '.join(report['errors']))
    package, output_dir = Path(package), Path(output_dir)
    # Never overwrite the source package with generated media.
    reject_package_output(package, output_dir)
    # Check all destinations before writing anything, including late contact/report files.
    reject_symlink_chain(output_dir)
    for name in [*(f'{state}.gif' for state in STATES), 'contact-sheet.png',
                 'contact-sheet-dark.png', 'preview-report.json']:
        reject_symlink_chain(output_dir / name)
        if (output_dir / name).exists() and not (output_dir / name).is_file():
            raise ValueError(f'preview output is not a regular file: {name}')
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(package / 'spritesheet.webp') as src:
        atlas = src.convert('RGBA')
    sheet = Image.new('RGB', (1536, 9*240), '#e9edf2')
    dark_sheet = Image.new('RGB', sheet.size, '#202632')
    draw = ImageDraw.Draw(sheet)
    dark_draw = ImageDraw.Draw(dark_sheet)
    gifs = []
    for row, (state, count) in enumerate(zip(STATES, COUNTS)):
        frames = []
        for col in range(count):
            frame = atlas.crop((col*192, row*208, (col+1)*192, (row+1)*208))
            frames.append(frame)
            sheet.paste(frame, (col*192, row*240+28), frame)
            dark_sheet.paste(frame, (col*192, row*240+28), frame)
        draw.text((6, row*240+6), state, fill='#182533')
        dark_draw.text((6, row*240+6), state, fill='#e9edf2')
        target = output_dir / f'{state}.gif'
        atomic_write(target, gif_bytes(frames, DURATIONS[row]))
        with Image.open(target) as check:
            if check.n_frames != count:
                raise ValueError(f'{state}: GIF encoder collapsed frames; output needs repair')
            actual = []
            for index in range(check.n_frames):
                check.seek(index)
                actual.append(check.info['duration'])
            if actual != list(DURATIONS[row]):
                raise ValueError(f'{state}: GIF timing mismatch')
        gifs.append({'state': state, 'path': str(target), 'frames': count, 'durations_ms': actual})
    for image, name in [(sheet, 'contact-sheet.png'), (dark_sheet, 'contact-sheet-dark.png')]:
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        atomic_write(output_dir / name, buffer.getvalue())
    result = {'ok': True, 'spritesheet_sha256': report['spritesheet_sha256'], 'previews': gifs, 'visual_qa': 'NOT_EXECUTED', 'note': 'GIF alpha is binary; inspect original WebP separately for alpha edges.'}
    write_json(output_dir / 'preview-report.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    try:
        result = preview(args.package, args.output_dir)
        print(f"Generated {len(result['previews'])} verified GIF containers; visual review still required.")
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
