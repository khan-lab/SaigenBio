# SaigenBio logo and favicon

The chosen mark reads as **再**, the first character of 再現 (reproduction), with a DNA double helix forming the central stroke. Paired strands in the surrounding strokes retain the compact grid of the character. The design was developed from the maintainer's sketch.

## Assets and usage

| Asset | Use |
| --- | --- |
| [Editable logo SVG](../ui/assets/logo.svg) | Documentation, presentations, and other larger displays; preferred scalable source |
| [512 px PNG](../ui/assets/logo-512.png) / [1024 px PNG](../ui/assets/logo-1024.png) | Repository artwork and software that needs a raster image; transparent background |
| [Favicon SVG](../ui/assets/favicon.svg) | Application browser tab; simplified strands and a warm ivory background |
| [Favicon ICO](../ui/assets/favicon.ico) | Browser fallback, containing 16, 32, and 48 px images |
| [16 px](../ui/assets/favicon-16.png) / [32 px](../ui/assets/favicon-32.png) / [48 px](../ui/assets/favicon-48.png) | Fixed-size favicon exports |

Use the detailed logo at 64 px or larger. Use the simplified favicon at smaller sizes. The application declares the SVG and PNG icons and serves `/favicon.ico` for browsers that request it directly. These assets are included in installed packages.

The mark is deep green (`#294E43`). Place the transparent logo on white or warm ivory (`#F7F6EF`); on a dark surface, give it a light background rather than allowing the green strokes to disappear. Keep its square aspect ratio and preserve the whitespace in the SVG canvas. Do not stretch, crop, add effects, or substitute an ordinary text glyph for the drawing. Use “SaigenBio” as adjacent plain text when the product name is needed.

The repository README uses the detailed mark. Other guides may use the same mark where a product identity is helpful; it need not be repeated on every page. The favicon is an intentionally simpler drawing, not a replacement for the larger logo.

## Editing and exporting

The SVG files are the editable sources. They contain vector paths, no external images or font dependencies. Edit them in a vector editor, then regenerate raster exports. No image tools are required to install or run SaigenBio.

For contributors using ImageMagick with an SVG renderer such as Inkscape:

```sh
magick -background none ui/assets/logo.svg -resize 1024x1024 ui/assets/logo-1024.png
magick ui/assets/logo-1024.png -resize 512x512 ui/assets/logo-512.png
magick -density 1536 -background none ui/assets/favicon.svg -resize 16x16 ui/assets/favicon-16.png
magick -density 1536 -background none ui/assets/favicon.svg -resize 32x32 ui/assets/favicon-32.png
magick -density 1536 -background none ui/assets/favicon.svg -resize 48x48 ui/assets/favicon-48.png
magick ui/assets/favicon-16.png ui/assets/favicon-32.png ui/assets/favicon-48.png ui/assets/favicon.ico
```

Inspect the favicon at actual size on light and dark browser chrome after changing it. Keep the inner openings distinguishable and verify the installed viewer serves the assets using `scripts/check_installation.py`.
