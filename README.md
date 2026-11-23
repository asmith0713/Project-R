# Private Gallery

A web app that runs on a Raspberry Pi and shows your photos and videos in a browser, laid out like Google Photos. It is protected by one secret key and works only on your home wifi. It fits phones, tablets, laptops and big screens, and follows your device's light or dark mode.

## What it does

- **Photos:** everything in one timeline, newest first, grouped by the day each photo was taken, with a scrubber on the right to jump through the years
- **Albums:** your folders (sub-folders included) with cover pictures
- **Viewer:** swipe between photos, pinch or double-tap to zoom, swipe down to close, and see the date, camera and location
- Plays videos and opens iPhone HEIC and RAW (DNG) photos
- **Favorites:** heart a photo to find it quickly
- **Manage:** select many photos to move, download or delete them. Deleted items wait in **Trash** for 30 days.
- Upload photos and videos from your phone or by dragging them onto the page, and create, rename and delete albums
- Shuffle slideshow of an album or everything
- Add it to your phone's home screen like an app
- Asks for a secret key before showing anything, including thumbnails and videos

## What's in the folder

| Item | What it is |
|---|---|
| `app.py` | Starts the app |
| `gallery/` | The server side (Python) |
| `web/` | The pages you see (Svelte). They have to be built once with `npm`. |
| `requirements.txt` | The Python packages it needs |
| `photos/` | Your photos and videos go here (created on first run) |
| `.auth.json` | Your key, stored as a hash (created by `setpass`) |
| `.favorites.json` | Which photos you hearted |
| `.cache/` | Thumbnails, JPEG copies of HEIC/RAW photos, and the photo index (safe to delete) |
| `photos/.trash/` | Deleted items, kept for 30 days |

## Set it up (once)

You need a Raspberry Pi with Raspberry Pi OS and Python 3. Everything below runs on the Pi, over SSH from your Mac.

**1. Connect to the Pi from your Mac**

```
ssh yourusername@raspberrypi.local
```

**2. Install the tools it needs**

```
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm ffmpeg
```

`ffmpeg` makes the video thumbnails, and `nodejs`/`npm` build the pages.

**3. Copy this folder to the Pi** (run this in a new Terminal window on your Mac)

```
scp -r ~/Downloads/private-gallery yourusername@raspberrypi.local:~/
```

Change the path if you saved the folder somewhere else.

**4. Install the app** (back in the SSH window)

```
cd ~/private-gallery
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd web && npm install && npm run build && cd ..
```

**5. Choose your secret key**

```
python3 app.py setpass
```

Use at least 6 characters. Pick something your family wouldn't guess.

**6. Add your photos**

From your Mac, copy a folder across (sub-folders are kept):

```
rsync -av ~/Desktop/MyPhotos/ yourusername@raspberrypi.local:~/private-gallery/photos/
```

`rsync` can resume if the connection drops. You can run it again later and it only sends what's new.

**7. Start it**

```
python3 app.py
```

The first time, it looks through all your photos to read their dates. That takes about a minute per thousand photos, and the page fills in by itself. To get thumbnails ready ahead of time as well, run `python3 app.py warm` once.

## Open it

On any phone or laptop connected to your home wifi, open:

```
http://raspberrypi.local:8080
```

If that doesn't load, use the Pi's IP address instead. Find it by running `hostname -I` on the Pi, then open `http://192.168.1.50:8080` (with your own number). Bookmark whichever works.

Enter your secret key. Your login lasts 12 hours. Press **Lock** when you're done.

## Using it

- **Photos** shows everything by date. Drag the scrubber on the right edge (or scroll) to jump back in time.
- **Albums** shows your folders. Tap one to open it, and use the path at the top to go back.
- **View:** tap a photo or video. Swipe left or right (or use the arrow keys) to move, pinch or double-tap to zoom, and swipe down (or press Esc) to close. The ⓘ button shows the date, file, camera and a map link if the photo has a location.
- **Favorite:** tap the heart in the viewer (or press F). Hearted photos appear under **Favorites**.
- **Select:** on a phone, press and hold a photo, then tap more. On a computer, hover and click the circle, and Shift-click to select a range. The bar at the top lets you favorite, move to an album, download or delete them.
- **Delete:** items go to **Trash**, and you can undo straight away or restore them from Trash for 30 days. After that they're gone for good.
- **Slideshow:** in an album, press **Slideshow** to play everything in it (and its sub-albums) in random order. Photos stay for 5 seconds, and videos play to the end.
- **Upload:** open the album you want, press **Upload** and pick photos or videos. On a computer you can also drag files onto the page. A panel shows progress.
- **Albums:** use **New album** on the Albums page, or the ⋮ menu inside an album to make one inside it, rename it, or delete it (only when it's empty).
- **On your phone's home screen:** on iPhone, open the gallery in Safari, tap Share, then **Add to Home Screen**. It then opens full-screen like an app.

Uploads never overwrite anything. If a file with the same name exists, the new one gets `_1` added to its name.

## Make it start automatically

So you don't have to start it by hand after every reboot, set it up as a service. Replace `yourusername` with your Pi username.

```
sudo nano /etc/systemd/system/gallery.service
```

Paste this in, then save (Ctrl+O, Enter, Ctrl+X):

```
[Unit]
Description=Private gallery
After=network-online.target
Wants=network-online.target

[Service]
User=yourusername
WorkingDirectory=/home/yourusername/private-gallery
ExecStart=/home/yourusername/private-gallery/venv/bin/python app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then turn it on:

```
sudo systemctl daemon-reload
sudo systemctl enable --now gallery
```

Useful commands afterwards:

```
sudo systemctl status gallery     # is it running?
sudo systemctl restart gallery    # restart after an update
journalctl -u gallery -f          # watch the log (Ctrl+C to stop)
```

## Everyday tasks

**Back up your photos.** Photos you upload from your phone exist only on the Pi, and memory cards can fail. Every month or so, run this on your Mac:

```
rsync -av yourusername@raspberrypi.local:~/private-gallery/photos/ ~/Desktop/gallery-backup/
```

**Change your secret key.** Stop the app (or `sudo systemctl stop gallery`), run `python3 app.py setpass` again, then start it. Everyone gets logged out.

**Update the app.** Copy the new files over the old ones, rebuild the pages with `cd web && npm install && npm run build`, then restart it. Your key, favorites and photos stay as they are.

**Added lots of photos with rsync?** Run `python3 app.py warm` (with the venv active) so their thumbnails are ready before you browse. Add `--views` to also prepare full-screen copies of HEIC and RAW photos.

**Use another photo folder or port.** Set these before starting:

```
PHOTO_DIR="/path/to/photos" PORT=9000 python3 app.py
```

For the service, add `Environment="PHOTO_DIR=/path/to/photos"` under `[Service]`.

## Privacy and safety

- Nothing is shown until the key is entered, and five wrong tries lock that device out for five minutes.
- On plain wifi, the key and photos travel unencrypted. That's fine at home. Don't open the port to the internet.
- Anyone who can log in to the Pi itself, or take out its memory card, can read the photos. Set a password on the Pi.
- Your browser history keeps the address. Use a private window if that matters.
- The lockout counter resets if the app restarts.
- Deleted items stay in Trash (a hidden `.trash` folder next to your photos) for 30 days.

## Troubleshooting

**The page says "The app isn't built yet".** In the app folder, run `cd web && npm install && npm run build`, then reload.

**The page won't load.** Check that your phone is on the same wifi as the Pi, that the app is running (`sudo systemctl status gallery`), and that the address is right. Try the IP address if `raspberrypi.local` fails.

**I forgot my key.** Run `python3 app.py setpass` to set a new one. Your photos are not affected.

**HEIC photos show as blank.** The `pillow-heif` package didn't install. In the app folder, run `source venv/bin/activate` then `pip install pillow-heif`, and restart.

**An upload failed.** The message after the upload tells you why. The usual causes are an unsupported file type, a file over 2 GB, or the Pi running low on space (it stops uploads below 500 MB free). Check space with `df -h`.

**A video won't play.** Some iPhone videos use a format that Chrome can't play, though Safari can. Try Safari, or convert the video to H.264 MP4.

**The first look at a folder is slow.** The Pi is making thumbnails. Later visits are fast because they're cached.

**Photos aren't showing up.** The app skips hidden files (names starting with a dot) and anything that isn't a photo or video. Supported types are JPG, PNG, GIF, WebP, HEIC, TIFF, DNG, MP4, MOV, M4V, and WebM. New photos copied onto the drive show up within about 10 seconds of the next page load.
