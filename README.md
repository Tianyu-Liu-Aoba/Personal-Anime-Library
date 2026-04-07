# Anime Library

Local Windows-first anime library browser with:

- folder-name scanning for title extraction
- metadata cross-checking across MyAnimeList, TMDB, and Bangumi
- a local web UI with poster gallery, filters, detail pages, and episode playback
- native folder picking on first run and in Settings

## Deployment

Download "Media Library" folder to your computer and store it in the desired location.

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

## Usage of AI
Code of this project was purly written by AI (ChatGPT Codex and GitHub Co-Pilot). I just debugged the program on my computer.
Prompt will be put on shortly after I finish tidying-up.

### First Prompt Used
```
I am building my media, specifically anime library. Please write a program that runs on Windows 10 (and later) that does the following job:
1. Scan the names of the folders in a specific path. Use the name of the folders (not the name of the files) as the title of the anime. Scanning should skip system folders. You may need to extract the name of the anime from the folder name. For example, a folder maybe named as following: "凉宫春日的忧郁&消失 \[CASO&MAI] \[Ma10p_2160p]" This folder contains "凉宫春日的忧郁" and "凉宫春日的消失".
2. Fetch the data of the anime, including cover, year, producers, director, tags, brief introduction etc. from the following sources and do the cross-check:
	1. https://myanimelist.net/
	2. https://www.themoviedb.org/
	3. https://bangumi.tv/
3. Create a browser-based user interface, following Google's material 3 expressive guidance (https://design.google/library/expressive-material-design-google-research). The feature of the library are described as follows:
	0. On the first time set up, guide the user to choose the paths that contains the movies/anime.
	1. On boot shows a gallery-like interface, the user can scroll to find the content they want. The poster of each anime should be no smaller than 2\*2.5cm on the screen. 
	2. On the left -hand side bar, the user can filter the contents by tags and years. Tags are placed in a foldable sections The side-bar could be hidden.
	3. When the user clicks on one poster, he/she will enter the details page. This page shows the details of the anime fetched from the internet, and episode chooser.
	4. When clicking on the anime, it opens a new layer on top of the library instead of showing the anime at the very bottom.
	5. When the user clicks on one episode, the web-ui opens the default video player to play the anime.
	6. There is a settings button on the top-right corner. On click, it opens a new window, allowing the user to adjust appearance and add new paths for movies. When adding new paths, the program shall scan all paths added by the user.
	7. Add user-added "known as" name. The application can then use the "known as" name to search for information as well.
	8. Allow the user to modify the information such as title, producers, directors, year, cover etc. And use the modified data to search.
	9. Allow the user to manually enter a bangumi.tv url and fetch the data in the details page.
	10. Allow partial matches in searches and let the user to decide which entry to use.
	11. Once the user manually edited one entry, the entry will not be updated upon following scans.
	12. When updating the library, only update folders that have been modified since last scan.
	13. If it is a multi-season anime, separate episodes by seasons; also, number the episodes from the information (file name) from the files.
		1. (SPs, NCOP, NCED, Promotion Videos etc. are put in a separate folder.)
	14. There are transition animation when opening the side bar, entering the details page, etc.
 ```
After the model have generated the program, test it and report the bugs/flaws in clear and instructive way, such as:
```
We still have problems with dark mode, I think the problem is as follows:
The box contaning the text have a fixed light colour. Therefore, no matter how people adjust background colour, the bright-coloured text appears on a bright background. And here is my solution：
1. Allow the user to custom color shemes for both dark and light modes.
2. When toggling the dark mode, the text-containing becomes dark as well. (Optional: I want to add gausssian blur effect on the textbox as well.)

After this is a UI problem.
1. In details page, "Quick Facts" and "Cover" block are too tall in height, and the bottom alinged with the tabs on the right. I need the "Quick Facts" block placed immediately below the cover the photo, and "modifying cover block" appears only in "Modify" Tab.
2. In the main page, the tags panel should stop moving once it hit the top of the screen.
3. In "modify" section, blocks are stuck together.
```
