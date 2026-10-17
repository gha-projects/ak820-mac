# Contributing

Thanks for helping! You can write issues and pull requests in English or Spanish.
*Puedes escribir en inglés o en español.*

## Your keyboard

The most useful thing is a report from a keyboard that isn't the tested one: use the
**My keyboard** issue template and paste what `python3 ak820.py buscar` prints. Even "it
isn't detected" helps, because the output lists the USB IDs your Mac sees.

## Translations

The texts are written in Spanish inside the code, wrapped in `tr("…")` (Python) or
`tr("…")` / `data-t` (the page in `editor/`). Each language is a file
`idiomas/<code>.json` that maps every Spanish phrase to its translation, keeping the
`{placeholders}`. To add one, copy `idiomas/en.json`, translate the values, and check that
nothing is missing:

```sh
.venv/bin/python idiomas/frases.py fr        # lists missing and leftover phrases
AK820_IDIOMA=fr .venv/bin/python ak820.py --help
```

## Code

- No framework: `ak820.py` is the protocol and the command line, `ak820_editor.py` serves
  the window's page, `ak820_app.py` is the menu-bar app. The formats are in
  [docs/PROTOCOL.md](docs/PROTOCOL.md).
- Run the tests (they use a fake keyboard) before sending a change:
  `.venv/bin/python -m unittest discover -s tests`
- Anything that writes to the keyboard should be tested on a real one, and should be
  undoable: the keyboard can't be read back, so the app keeps what it sent in
  `~/Library/Application Support/ak820-mac/`.
