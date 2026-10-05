# Conveters
Make ez to daily life downloads.

## YouTube downloads

Install dependencies from `requirements.txt` to use the current yt-dlp release,
its YouTube JavaScript components, the Deno runtime needed to process current
YouTube streams, and the bundled FFmpeg binary used to combine separate video
and audio streams.

YouTube may deny media requests from cloud-hosting IPs or return empty media
responses. The app reports these as source-access errors; changing MP4/MP3
conversion settings cannot fix a denied response. For content you are
authorized to download, run the app on a network where the source permits
access, or use a direct media file hosted by you. The deployed Streamlit Cloud
instance may not be able to download directly from YouTube.

For local use, yt-dlp can read a `cookies.txt` file placed beside `app.py`.
Treat that file like a password: do not commit or share it.
