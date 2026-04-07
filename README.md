# Anime Library

Local Windows-first anime library browser with:

- folder-name scanning for title extraction
- metadata cross-checking across MyAnimeList, TMDB, and Bangumi
- a local web UI with poster gallery, filters, detail pages, and episode playback
- native folder picking on first run and in Settings

## Run

From this folder on Windows:

```powershell
py -m anime_library
```

Or double-click [launch_anime_library.bat](/D:/Developing/Media%20Library/launch_anime_library.bat).

The app starts a local server and opens the browser automatically.

## First-Time Setup

1. Choose one or more library root folders.
2. The app scans the child folders under each root.
3. Each child folder becomes a library item, and video files inside it become playable episodes.

## Metadata Notes

- `Bangumi` works without extra credentials.
- `TMDB` needs either an API key or a read access token for full support.
- `MyAnimeList` can use a client ID. Without one, the app falls back to Jikan-backed MAL data so the library still works.

## Storage

The app stores its local config, poster cache, and catalog under:

`%APPDATA%\AnimeLibraryExpressive`

## Current Heuristics

- Folder names are cleaned by stripping common release-group and encode tags.
- Compound titles such as `凉宫春日的忧郁&消失 [CASO&MAI] [Ma10p_2160p]` expand into search candidates like:
  - `凉宫春日的忧郁`
  - `凉宫春日的消失`
  - `凉宫春日的忧郁&消失`
- Existing metadata is reused on rescans unless the folder name changes or you trigger a refresh scan from Settings.

### Code of this project is purly written by AI. I just did the debugging on my computer.
Prompt will be put on shortly after I finish tidying-up.
