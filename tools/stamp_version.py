"""Stamp a build with its version, and describe it for the updater.

Run by CI in two steps:

    python tools/stamp_version.py stamp --version 0.2.2-beta.dev.181
    python tools/stamp_version.py manifest --version 0.2.2-beta.dev.181 \\
        --file dist/AccessibleIDE.exe --out dist/version.json \\
        --url https://github.com/OWNER/REPO/releases/download/latest/AccessibleIDE.exe

Why this is a script and not a line in the workflow
---------------------------------------------------
Two workflows need it, and the version has to be written into the program
and into the manifest in exactly the same form. If those ever disagree the
app compares a version against itself and can offer a downgrade, so the two
steps live next to each other in one file that both workflows call.

The version is written into ``src/accessible_ide/__init__.py`` rather than
kept in a separate data file because that is where the app already looks for
it, and a second copy is a second thing to forget.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
INIT_FILE = REPO_ROOT / "src" / "accessible_ide" / "__init__.py"

VERSION_LINE = re.compile(r'^__version__\s*=\s*["\'][^"\']*["\']\s*$', re.MULTILINE)


class StampError(Exception):
    pass


def stamp_version(path: pathlib.Path, version: str) -> None:
    """Write version into the package, leaving the rest of the file alone.

    Refuses to guess: if the line it expects to replace is not there, the
    build must fail rather than ship with whatever version was there before.
    """
    if not re.fullmatch(r'v?\d+(\.\d+)*([-.][0-9A-Za-z.]+)?', version):
        raise StampError(f'{version!r} does not look like a version number')
    version = version.lstrip('v')
    source = path.read_text(encoding='utf-8')
    if VERSION_LINE.search(source) is None:
        raise StampError(
            f'no __version__ line to replace in {path}. '
            'The stamp would be silently skipped and the build would keep '
            'the old version, so this stops instead.'
        )
    updated = VERSION_LINE.sub(f'__version__ = "{version}"', source, count=1)
    path.write_text(updated, encoding='utf-8')


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(version: str, exe: pathlib.Path, url: str, notes: str,
                   prerelease: bool) -> dict:
    """The file the app downloads to find out whether there is a new build.

    ``sha256`` is what makes the download trustworthy: the app refuses to
    install a build whose contents do not match this number. It protects
    against a corrupted or intercepted download. It does not protect against
    someone who can publish releases here, because they can change both the
    program and this file. Closing that needs code signing.
    """
    if not url.startswith('https://'):
        raise StampError('the download address must be https')
    return {
        'version': version.lstrip('v'),
        'url': url,
        'sha256': sha256_of(exe),
        'size': exe.stat().st_size,
        'notes': notes.strip()[:2000],
        'prerelease': prerelease,
        'published': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)

    stamp = commands.add_parser('stamp', help='write the version into the package')
    stamp.add_argument('--version', required=True)
    stamp.add_argument('--file', default=str(INIT_FILE))

    manifest = commands.add_parser('manifest', help='describe a built exe')
    manifest.add_argument('--version', required=True)
    manifest.add_argument('--file', required=True, help='the built exe')
    manifest.add_argument('--out', required=True)
    manifest.add_argument('--url', required=True, help='where readers download it')
    manifest.add_argument('--notes', default='')
    manifest.add_argument('--stable', action='store_true',
                          help='mark this as a finished release, not a dev build')

    args = parser.parse_args(argv)
    try:
        if args.command == 'stamp':
            stamp_version(pathlib.Path(args.file), args.version)
            print(f'stamped {args.file} with {args.version}')
        else:
            exe = pathlib.Path(args.file)
            if not exe.is_file():
                raise StampError(f'{exe} does not exist, so it cannot be described')
            described = build_manifest(
                args.version, exe, args.url, args.notes,
                prerelease=not args.stable,
            )
            out = pathlib.Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(described, indent=2) + '\n', encoding='utf-8')
            print(f'wrote {out} for version {described["version"]}')
    except StampError as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
