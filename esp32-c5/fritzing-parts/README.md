# Fritzing parts

Parts missing from Fritzing's own library, for starting new sketches with the
fritzing-format skill (`fzz.load_fzpz`). Existing `.fzz` sketches carry their own copy.

- `Seeed Studio XIAO ESP32C5.fzpz`: from
  [Seeed-Studio/fritzing_parts](https://github.com/Seeed-Studio/fritzing_parts)
  (`XIAO Boards/`, committed 2026-01-22). Its breadboard SVG lacks the
  `<g id="breadboard">` layer group; `load_fzpz` adds it.
