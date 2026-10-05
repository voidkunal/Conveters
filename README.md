# Conveters
Make ez to daily life downloads.

## YouTube downloads

Install dependencies from `requirements.txt` to use the current yt-dlp release,
its YouTube JavaScript components, the Deno runtime needed to process current
YouTube streams, and the bundled FFmpeg binary used to combine separate video
and audio streams.

If YouTube still returns HTTP 403 on a hosted deployment, the host's IP may be
blocked by YouTube. Try running the app from another network. For content your
account is authorized to access, yt-dlp can also use a `cookies.txt` file placed
beside `app.py`. Treat that file like a password: do not commit or share it.
