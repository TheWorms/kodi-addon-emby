<!-- logo:start -->
<p align="center"><img src="plugin.video.embycon/icon.png" alt="Logo" width="160"></p>
<!-- logo:end -->

# EmbyCon — French edition · `kodi-addon-emby`

<!-- version:auto -->
**Version : 1.22.5**
<!-- /version:auto -->

[Français](README.md) · **English**

Kodi add-on to browse and play the media library of an **[Emby](https://emby.media)** server (movies, TV shows, music) directly from the Kodi interface.

> [!NOTE]
> This repository is a **French-enhanced fork** of [**EmbyCon**](https://github.com/faush01/plugin.video.embycon) by **faush01 (Team B)**, distributed under the **GPL-2.0** license. The add-on ID remains `plugin.video.embycon` to keep existing installs and settings compatible. All credit for the original add-on goes to its authors; this fork adds a French interface and several features described below.

---

## What this fork adds

- **Full French interface** — complete translation (`resource.language.fr_fr`), auto-detected from Kodi's language.
- **Hide watched items** — on both lists *and* home widgets, with reliable refreshing: cache is purged on marking, and a reload token (`&reload`) is injected into widget paths so widgets update automatically after a watched/unwatched action.
- **Per-list sorting** — movies, series, collections, movies in a collection, seasons and episodes: criterion and direction fit in a single setting (« Release date, oldest → newest »…).
- **Automatic playback quality** — background network-speed measurement (never during playback) that sets the maximum bitrate automatically; manual mode still available.
- **Skip intro & skip credits** — based on the server-detected markers (`IntroStart`/`IntroEnd`/`CreditsStart`), in *Button* or *Automatic* mode, with a **fixed-duration fallback** (skip the first X seconds / offer the credits skip X seconds before the end) when the server has no markers.
- **Intelligent subtitles** — automatically enables a preferred-language subtitle when the audio is not in your preferred language (like the Emby web app).
- **Next episode and next movie** — a window offers what comes next before the end, then plays it, or playback chains without asking.
- **Refresh after playback** — the current list updates shortly after playback ends.
- **Reorganized settings** — 7 menus (Playback, Skips and up next, Lists and sorting, Titles and details, Random movie, Server and account, Advanced), with a help sentence for each setting.

---

## Changelog

### 1.22 · current version

**Playback**

- **Automatic tracks for reduced playback** — when the video is transcoded (connection or hardware), audio and subtitles are picked from your languages, with the same rules as direct playback. Setting *Playback → Audio and subtitles → Tracks of a reduced playback*: *Automatic, from my languages* or *Ask me*.
- **Track menu in the right-click style** — the automatic choice is already selected and marked *AUTO*; Back keeps it.
- **Automatic quality diagnostics** — the Kodi log shows, for each playback, the video, the bitrate limit and the server's decision; a notification warns when the server transcodes too slowly.

**Lists**

- **Hide watched collections** — option *Lists and sorting → Content → Hide watched collections in widgets*.

**Fixes**

- Kodi no longer freezes when coming back from a movie started from a search: results come back without reopening the keyboard, and Back no longer leads to the file browser.

<details>
<summary><b>1.21</b> · random movie, Skip button, new icon, coming back from a movie</summary>

- **Random movie** — back to the home screen on stop, at the end and from full screen; continuous playback that chains another random movie; a natural end counts as fully watched.
- **« Skip » button** (intro and credits) — disappears after the configured delay; label translated.
- **New icon** — the mascot, also in the add-on's notifications and windows.
- **Instant return from a movie** — the list comes back immediately instead of an empty Videos window; Back to a parent list is instant; no more progress box over the home screen.

</details>

<details>
<summary><b>1.20</b> · settings in 7 menus, collection order</summary>

- **Settings reorganized into 7 menus** — renamed, with a help sentence for each setting: 93 settings instead of 110, duplicates merged, readable values (« Off », « No limit »). Existing settings are converted automatically on update.
- **Collections widget** — keeps EmbyCon's order, whatever the skin's sort direction.
- **Movies of a collection** — oldest to newest, to follow a saga year after year.
- **Next episode** — works like movies: offer then play, or play without asking.

</details>

<details>
<summary><b>1.15</b> · random movie, collections, forced subtitles, sorting and views, list cache</summary>

- **Random movie** — full-screen card over the movie's fanart with *Play*, *Next*, *Previous* and *Cancel*; « unwatched only » and maximum length filters. Opening the « Movies - Random » widget starts the draw directly.
- **Movie collections** — *Play all* for a collection, and chaining to the **next movie**: offered when the credits start (or a few minutes before the end), then started automatically.
- **Collection dates** — Emby does not date collections: EmbyCon computes their release date from their movies, in parallel, with a disk cache prepared by the service. Date sorting therefore works on collections too, and EmbyCon's sort direction drives Arctic's Collections widget.
- **Forced subtitles** — shown automatically in your language (foreign dialogue, signs).
- **Sorting and views** — a default sort for each kind of list, a « Collections - Recently added » widget, and the chosen view (list, posters, thumbnails…) kept for each category.
- **Simplified settings** — sub-settings shown only when relevant, duplicates merged; more reliable automatic quality.
- **SQLite list cache + ETag** — browsing costs a few KB instead of tens of MB; large list pagination, network robustness (retries, stabilized websocket, 401 authentication guard) and CI checks (`ruff` + tests) on every push.

</details>

---

## Installation

### Via the TheWorms repository (automatic updates)

1. In Kodi: **Settings → System → Add-ons** and enable **Unknown sources**.
2. Install the TheWorms repository from this URL (File manager → *Add source*, or install the zip directly):
   ```
   https://raw.githubusercontent.com/TheWorms/kodi-repo/main/zips/repository.theworms/repository.theworms.zip
   ```
3. **Add-ons → Install from repository → TheWorms Repository → Video add-ons → EmbyCon**.

---

## Configuration

1. Open the add-on settings.
2. **Server and account**: enter your Emby server address and port (or use auto-detection), then your credentials.
3. Browse your library from Kodi's **EmbyCon** entry, or add **widgets** to your home screen.

> For watched items to disappear from lists and widgets, enable **Lists and sorting → Content → Hide what I have already watched**.

---

## Compatibility

- **Kodi 21 (Omega)** and Python 3-compatible versions.
- Tested on CoreELEC (ODROID-N2+).
- Automatic widget refresh requires a skin that evaluates `$INFO[...]` tokens in widget paths (e.g. Arctic Zephyr-derived skins).

---

## Credits & license

- Original add-on: **[EmbyCon](https://github.com/faush01/plugin.video.embycon)** by **faush01 / Team B**.
- French fork and additional features: **[TheWorms](https://github.com/TheWorms)**.
- License: **[GPL-2.0](LICENSE.txt)** — full source code is available in this repository, as required by the license.

Emby is a trademark of Emby LLC. This project is not affiliated with Emby LLC or the Kodi/XBMC Foundation.

---

## Contributing

Bug reports and suggestions are welcome via [issues](https://github.com/TheWorms/kodi-addon-emby/issues). Please include your Kodi version, your skin, and the relevant log lines.
