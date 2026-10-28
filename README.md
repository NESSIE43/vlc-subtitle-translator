# VLC Subtitle Translator

**English** · [Türkçe](README.tr.md)

A small helper for learning languages while watching subtitled videos in VLC (Windows and Linux).

- **Hover a word → see its translation.** Other meanings of the word may appear too, and you can translate the whole sentence.
- **Any language to any language:** you choose the subtitle language (the one you're learning) and the translation language, for example English → Turkish, German → English, Spanish → French.
- **Color-code words:** 🟢 Known / 🟡 Learning / 🔴 Unknown. The color you pick shows up every time the word appears.
- **★ Favorites.** Favorite words are underlined. The "My words / Favorites" window lets you browse, search, edit translations and export everything as CSV (Excel).
- The video pauses automatically while you hover a word and resumes when you move away (can be turned off).
- The interface is available in **English and Turkish**. It follows your system language and can be changed from the selector at the top of the window.

## How does it work?

VLC's extension system can't detect mouse movement over the video. So this program runs next to
VLC: it reads the current playback time from VLC, reads the subtitle file itself and draws the
subtitles as an overlay on top of the VLC window. VLC's own subtitles are turned off
automatically, so you don't see them twice.

## Requirements

**Windows 10 / 11**
- [Python 3.10+](https://www.python.org/downloads/). Tick "Add python.exe to PATH" while installing. No extra packages are needed.
- [VLC 3](https://www.videolan.org/vlc/)

**Linux** (X11 desktop recommended)
- Python 3.10+ with Tk:
  - Debian / Ubuntu: `sudo apt install python3 python3-tk`
  - Fedora: `sudo dnf install python3 python3-tkinter`
  - Arch: `sudo pacman -S python tk`
- VLC 3 (distribution package, Flatpak or Snap)

**Both**
- Optional: [ffmpeg](https://ffmpeg.org/) on PATH. Only needed to read subtitles **embedded inside** the video.
- Your own translation API key (see below).

## Installation

1. Download this repository (**Code → Download ZIP**) and extract it, or `git clone` it.
2. Start the program:
   - Windows: double-click **`start.bat`**
   - Linux: run **`./start.sh`** (or `python3 vlc_subtitle_translator.py`)
3. On first launch the program asks whether to set up VLC automatically. Choose **Yes**
   (you'll be asked to close VLC first if it's open). This turns on VLC's web interface,
   **reachable only from this computer and protected by a random password**. Your previous VLC
   settings are backed up next to the VLC settings file as `vlcrc.vlc-subtitle-translator.bak`.
4. On the **Translation** tab choose your languages and enter your own API key (next section).

## Translation service and API key

This project **contains no API keys** and does not go through the developer's server or account.
Your computer sends translation requests **with your own key** directly to the service you
choose. Your key is stored only on your computer, in `data/ayarlar.json`. Don't share that file.

The program only translates the word you hover (and the sentence when you click "Translate
sentence"), and caches the result. The same word is never translated twice, so the free quotas
are more than enough for normal use.

### Option 1: DeepL API Free (recommended)

500,000 characters per month for free.

1. Sign up for **DeepL API Free** at <https://www.deepl.com/pro-api>.
   (A card may be requested for verification; the Free plan is not charged.)
2. Copy your key from **API Keys** in your account. Free keys end with `:fx`.
3. In the program, on the **Translation** tab, choose **DeepL API**, paste the key and press **Test**.

If you pick a language pair DeepL doesn't support, you'll see an error in the translation popup.
Use Google Cloud in that case.

### Option 2: Google Cloud Translation API

500,000 characters per month for free, paid after that. Supports more languages.

1. Create a project at <https://console.cloud.google.com/>. You need to link a billing account.
2. Enable **Cloud Translation API** under **APIs & Services → Library**.
3. Create a key under **APIs & Services → Credentials → Create credentials → API key**.
   For safety, restrict the key to *Cloud Translation API* only with **API restrictions**.
4. To avoid surprise bills, set a low budget alert under **Billing → Budgets & alerts**.
5. In the program choose **Google Cloud Translation API**, paste the key and press **Test**.

Check current prices and quotas on the services' own pages.

### No-key mode (for trying out only)

If you want to try the program without a key, the **No key** option uses Google Translate's
public, **unofficial** endpoint (falling back to MyMemory). This endpoint is undocumented, may
temporarily block IP addresses that send many requests, and may stop working at any time. For
regular use, choose DeepL or Google Cloud with your own key.

## Usage

1. Start the program and keep it open.
2. Open your video in VLC as usual.
3. Subtitles are found automatically:
   - A `.srt / .vtt / .ass` file next to the video (e.g. `movie.srt`, `movie.en.srt`, a `Subs` folder).
     Files named with your subtitle language are preferred; files in your translation language are skipped.
   - Otherwise the subtitles embedded in the video (mkv/mp4, extracted with ffmpeg).
   - Otherwise use **"Choose subtitle file…"** on the panel.
4. Hover the words and start learning.

The subtitles are visible while the VLC window is in front and hidden when you switch to another
window. Fullscreen works too, and the subtitles stay above VLC's playback bar. If you change the
subtitle delay in VLC (H / G keys), the program follows it.

## Appearance

On the **Appearance** tab you can adjust the subtitles with a live preview: font, size, bold, text
color, black outline, background color and opacity, rounded corners, distance from the bottom and
maximum width.

## Known limitations

- On Linux the subtitle background is always an opaque box (Tk has no per-pixel transparency on
  X11), so the opacity setting has no effect there. Under Wayland the program works through
  XWayland; keeping the window on top depends on your desktop.
- Words are split on spaces. In languages that don't use spaces (Chinese, Japanese, Thai) a whole
  line behaves like one word.
- Right-to-left languages (Arabic, Hebrew, Persian) may not display correctly.
- Your word list is a single list; words spelled the same in different languages share one entry.

## Files

| File | Purpose |
|---|---|
| `vlc_subtitle_translator.py` | Main program and control panel |
| `overlay.py` | Subtitle overlay on VLC and the word popup |
| `translator.py` | Translation services (DeepL, Google Cloud, no key) |
| `languages.py` | Supported languages |
| `i18n.py` | Interface language (Turkish / English) |
| `words_window.py` | My words / Favorites window |
| `subtitles.py` | Reading and finding subtitles |
| `storage.py` | Words, settings and translation cache |
| `theme.py` | Dark UI theme |
| `vlc_client.py` | Talking to VLC's web interface |
| `vlc_setup.py` | Editing VLC's settings file |
| `osutil.py`, `winutil.py`, `x11util.py` | Following the VLC window (Windows / Linux) |

Personal data lives in the `data/` folder and is not added to git:
`ayarlar.json` (VLC password, API keys), `kelimeler.json` (colors, favorites; copy this file to
back up your words), `ceviri_onbellek.json`, `cache/`.

## Troubleshooting

- **"VLC not found"**: Is VLC running? If so, close VLC, press "Set up VLC automatically" on the panel, then reopen VLC.
- **"Wrong password"**: Run "Set up VLC automatically" again to rewrite the password.
- **"Translation failed: … key is invalid"**: Check the key on the Translation tab and press **Test**.
- **Subtitles slightly early/late**: Adjust the subtitle delay in VLC with `H` / `G`.
- Errors are written to `data/hata.log`.

## License

[MIT](LICENSE)
