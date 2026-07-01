# EmbyCon — French edition · `kodi-addon-emby`

[Français](README.md) · **English**

Kodi add-on to browse and play the media library of an **[Emby](https://emby.media)** server (movies, TV shows, music) directly from the Kodi interface.

> [!NOTE]
> This repository is a **French-enhanced fork** of [**EmbyCon**](https://github.com/faush01/plugin.video.embycon) by **faush01 (Team B)**, distributed under the **GPL-2.0** license. The add-on ID remains `plugin.video.embycon` to keep existing installs and settings compatible. All credit for the original add-on goes to its authors; this fork adds a French interface and several features described below.

---

## ✨ What this fork adds

- **Full French interface** — complete translation (`resource.language.fr_fr`), auto-detected from Kodi's language.
- **Hide watched items** — on both lists *and* home widgets, with reliable refreshing: cache is purged on marking, and a reload token (`&reload`) is injected into widget paths so widgets update automatically after a watched/unwatched action.
- **Server-side sorting** — configurable default sort per content type (movies, box sets, series, seasons, episodes) with ascending/descending order.
- **Automatic playback quality** — background network-speed measurement (never during playback) that sets the maximum bitrate automatically; manual mode still available.
- **Skip intro & skip credits** — based on the server-detected markers (`IntroStart`/`IntroEnd`/`CreditsStart`), in *Button* or *Automatic* mode, with a **fixed-duration fallback** (skip the first X seconds / offer the credits skip X seconds before the end) when the server has no markers.
- **Intelligent subtitles** — automatically enables a preferred-language subtitle when the audio is not in your preferred language (like the Emby web app).
- **Play next episode** — configurable dialog (enable, trigger threshold, percentage).
- **Refresh after playback** — the current list updates shortly after playback ends.
- **Reorganized settings** — 6 clear categories grouped by intent (Server & account, Quality & playback, Automations, Display & lists, Services, Advanced).

---

## 📦 Installation

### Via the TheWorms repository (recommended, automatic updates)

1. In Kodi: **Settings → System → Add-ons** and enable **Unknown sources**.
2. Install the TheWorms repository from this URL (File manager → *Add source*, or install the zip directly):
   ```
   https://raw.githubusercontent.com/TheWorms/kodi-repo/main/zips/repository.theworms/repository.theworms.zip
   ```
3. **Add-ons → Install from repository → TheWorms Repository → Video add-ons → EmbyCon**.

### From a zip

Download the latest archive from the [Releases](https://github.com/TheWorms/kodi-addon-emby/releases) page, then in Kodi: **Add-ons → Install from zip file**.

---

## ⚙️ Configuration

1. Open the add-on settings.
2. **Server & account**: enter your Emby server address and port (or use auto-detection), then your credentials.
3. Browse your library from Kodi's **EmbyCon** entry, or add **widgets** to your home screen.

> For watched items to disappear from lists and widgets, enable **Display & lists → Organization → Hide watched items**.

---

## 🖥️ Compatibility

- **Kodi 21 (Omega)** and Python 3-compatible versions.
- Tested on CoreELEC (ODROID-N2+).
- Automatic widget refresh requires a skin that evaluates `$INFO[...]` tokens in widget paths (e.g. Arctic Zephyr-derived skins).

---

## 🙏 Credits & license

- Original add-on: **[EmbyCon](https://github.com/faush01/plugin.video.embycon)** by **faush01 / Team B**.
- French fork and additional features: **[TheWorms](https://github.com/TheWorms)**.
- License: **[GPL-2.0](LICENSE.txt)** — full source code is available in this repository, as required by the license.

Emby is a trademark of Emby LLC. This project is not affiliated with Emby LLC or the Kodi/XBMC Foundation.

---

## 🤝 Contributing

Bug reports and suggestions are welcome via [issues](https://github.com/TheWorms/kodi-addon-emby/issues). Please include your Kodi version, your skin, and the relevant log lines.
