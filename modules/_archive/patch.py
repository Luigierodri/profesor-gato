import pathlib

f = pathlib.Path('modules/video_assembler.py')
lines = f.read_text(encoding='utf-8').splitlines()

# Corregir indentacion de lineas 124 en adelante hasta el proximo metodo
fixed = []
in_bad_block = False
for i, line in enumerate(lines):
    if i == 123:  # linea 124 (0-indexed)
        in_bad_block = True
    if in_bad_block and line.startswith('        def ') and i > 123:
        in_bad_block = False
    if in_bad_block and line.startswith('        '):
        line = line[4:]  # quitar 4 espacios extra
    fixed.append(line)

f.write_text('\n'.join(fixed), encoding='utf-8')
print('OK indentacion corregida')