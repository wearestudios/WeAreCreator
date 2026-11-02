# Self-hosted fonts

Served from this folder and declared in `src/index.css`. All three families are
licensed under the **SIL Open Font License 1.1** (`OFL.txt` beside this file),
which permits embedding and redistribution with the licence attached.

| File | Family | Axes / weight | Source |
| --- | --- | --- | --- |
| `fraunces-latin-normal.woff2` | Fraunces | opsz 9–144, wght 400–700, WONK | Google Fonts, `family=Fraunces:ital,opsz,wght,WONK@0,9..144,400..700,0..1;1,9..144,400..700,0..1`, latin subset |
| `fraunces-latin-italic.woff2` | Fraunces italic | opsz 9–144, wght 400–700, WONK | same request, italic latin file |
| `inter-tight-latin.woff2` | Inter Tight | wght 400–600 | `@fontsource-variable/inter-tight` 5.3.0, `files/inter-tight-latin-wght-normal.woff2` |
| `jetbrains-mono-latin-400.woff2` | JetBrains Mono | 400 (static) | `@fontsource/jetbrains-mono` 5.3.0, `files/jetbrains-mono-latin-400-normal.woff2` |

**Why Fraunces comes from Google and not fontsource:** no
`@fontsource-variable/fraunces` file carries exactly the axes the site uses.
`wonk` has WONK but no opsz; `opsz`/`standard` have opsz but no WONK; `full` has
all of them plus SOFT, which the site deliberately does not load. Google's
CSS API subsets axes to the request, so asking for `ital,opsz,wght,WONK`
returns files with no SOFT axis at all.

`scripts/build-fonts.py` narrows each weight axis to the range the site uses
(lossless inside it) and prints the metric overrides for the fallback faces in
`index.css`. Re-run it if a file here changes:

    python3 scripts/build-fonts.py <folder of the source files> frontend/public/fonts
