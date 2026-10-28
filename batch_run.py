"""Process every JPG/PNG in one folder, with independent result folders.

Usage: py batch_run.py "C:\\My Photos" --output-dir "batch_results"
"""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description='Batch analyze tray photographs')
    p.add_argument('folder', help='Folder containing JPG/PNG images')
    p.add_argument('--output-dir', default='batch_results')
    p.add_argument('--cell-pitch-in', type=float, default=None)
    p.add_argument('--max-dimension', type=int, default=2200)
    args = p.parse_args()
    folder = Path(args.folder)
    if not folder.is_dir():
        p.error(f'Not a directory: {folder}')
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() in ('.jpg','.jpeg','.png'))
    if not files:
        p.error(f'No JPG/PNG files found in {folder}')
    failures = []
    for i, f in enumerate(files, 1):
        print(f'\n[{i}/{len(files)}] {f.name}',flush=True)
        cmd = [sys.executable, str(Path(__file__).with_name('main.py')),
               str(f), '--output-dir', str(Path(args.output_dir)/f.stem),
               '--max-dimension',str(args.max_dimension)]
        if args.cell_pitch_in is not None:
            cmd += ['--cell-pitch-in',str(args.cell_pitch_in)]
        if subprocess.run(cmd).returncode != 0:
            failures.append(f.name)
    print(f'\nFinished: {len(files)-len(failures)}/{len(files)} photos analyzed.')
    if failures:
        print('Needs review / perspective selection: ' + ', '.join(failures))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
