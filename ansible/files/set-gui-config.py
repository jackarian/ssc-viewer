"""Imposta alcune chiavi di gui.yaml riga per riga, senza toccare commenti, ordine e altre chiavi.

Gira con il python del venv della sala (serve PyYAML). Legge dall'ambiente:
  GUI_FILE  percorso di gui.yaml
  GUI_SET   JSON {"sezione.chiave": valore}
Stampa solo i nomi delle chiavi cambiate, mai i valori. Se cambia qualcosa salva prima
gui.yaml.bak-<data>; se il risultato non si rilegge con i valori attesi rimette il file originale.
"""
import json
import os
import re
import shutil
import sys
import time

import yaml

SECTION = re.compile(r'^([A-Za-z_][\w-]*):\s*(#.*)?$')
KEY = re.compile(r'^(\s+)([A-Za-z_][\w-]*):(\s*)(.*)$')


def section_range(lines, section):
    start = None
    for i, line in enumerate(lines):
        m = SECTION.match(line.rstrip('\n'))
        if m and start is None and m.group(1) == section:
            start = i
        elif start is not None and line[:1] not in ('', ' ', '\t', '\n', '#'):
            return start, i
    return start, len(lines)


def set_key(lines, section, key, value):
    text = json.dumps(value)
    start, end = section_range(lines, section)
    if start is None:
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        lines += [f'{section}:\n', f'  {key}: {text}\n']
        return
    indent, last = '  ', start
    for i in range(start + 1, end):
        m = KEY.match(lines[i].rstrip('\n'))
        if not m:
            continue
        indent, last = m.group(1), i
        if m.group(2) == key:
            lines[i] = f'{indent}{key}: {text}\n'
            return
    lines.insert(last + 1, f'{indent}{key}: {text}\n')


def main():
    path = os.environ['GUI_FILE']
    updates = json.loads(os.environ['GUI_SET'])
    original = open(path).read()
    current = yaml.safe_load(original) or {}

    lines = original.splitlines(keepends=True)
    changed = []
    for dotted, value in updates.items():
        section, key = dotted.split('.', 1)
        if (current.get(section) or {}).get(key) != value:
            set_key(lines, section, key, value)
            changed.append(dotted)

    if not changed:
        print('gui.yaml già allineato')
        return

    backup = f'{path}.bak-{time.strftime("%Y%m%d%H%M%S")}'
    shutil.copy2(path, backup)
    with open(path, 'w') as f:
        f.writelines(lines)

    result = yaml.safe_load(open(path).read()) or {}
    wrong = [d for d, v in updates.items() if (result.get(d.split('.')[0]) or {}).get(d.split('.', 1)[1]) != v]
    if wrong:
        shutil.copy2(backup, path)
        print(f'gui.yaml non valido dopo la modifica ({", ".join(wrong)}): rimesso l\'originale', file=sys.stderr)
        sys.exit(1)
    print(f'changed: {", ".join(changed)} (backup {os.path.basename(backup)})')


if __name__ == '__main__':
    main()
