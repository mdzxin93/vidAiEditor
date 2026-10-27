# OpenMontage Editing Stock Library v1

Original assets: 12 editable SVG designs + PNG previews, 8 original MP4 motion backgrounds, 6 original WAV SFX (26 local assets). 10 editing effect configurations. 1 edit-decision planning tool. These assets are reusable components inspired by the editorial grammar of the supplied reference, not copies of third-party footage.

## Quick start
Run `python scripts/test_library.py` and `python scripts/script_to_edl.py scripts/example_script.txt`. Import `catalog/assets.json` into your existing media asset index. Load `presets/cinematic_explainer.json` in the style router. Use `scripts/script_to_edl.py` as a fallback; real production EDL must use Faster-Whisper word timestamps and semantic model ranking.

## Integrating
1. Register every asset path relative to this folder and compute thumbnail + duration metadata.
2. Build a script alignment service; segment and rank a-roll, images and motion backgrounds.
3. Use EDL as an editable *proposal*. Validate available clip lengths before cutting.
4. Use Remotion components for animated typography, graphic reveals and keyframes; use FFmpeg for muxing, normalization and fallback.
5. Allow user to change stock item, effect duration and B-roll placement from timeline.
6. Train an asset ranker only after collecting user-approved EDLs from multiple different videos. Avoid claiming this pack trained any weights.

## Licensing
All 26 included artwork, video and audio assets were generated programmatically for this package. External stock is NOT included or downloaded: outbound media download is blocked. See catalog/external_stock_sources.json for vetted stock sources and licensing requirements. Pexels/Pixabay typically permit final edits but not redistribution as a stock package. Mixkit has Free and Restricted licenses. LottieFiles prohibits compiling/scraping competing libraries. Review each downloaded item.

## Style
Light subtle grid explainer boards, expressive simple line illustrations, black/red/white contrast, quick meaningful cutbacks to dark talking head, clean white/red captions. This is an editorial *style approximation* to the reference video, not pixel-exact reconstruction.
