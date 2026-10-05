from contextlib import contextmanager
import streamlit as st
import yt_dlp
import imageio_ffmpeg
import os
import requests
import urllib.parse
import shutil
import tempfile
import re
import subprocess

# --- 1. Page Config & Session State ---
st.set_page_config(page_title="Void Tech Converter", page_icon="💀", layout="wide")

if 'app_step' not in st.session_state:
    st.session_state.app_step = 'input'

if 'temp_dir' not in st.session_state:
    os.makedirs('downloads', exist_ok=True)
    st.session_state.temp_dir = 'downloads'

for key in ['file_path', 'media_title', 'thumbnail_url', 'direct_url', 'detected_type', 'target_url', 'profile_entries', 'ig_bio', 'has_video', 'has_audio', 'download_is_audio']:
    if key not in st.session_state:
        st.session_state[key] = None

def full_cleanup():
    if st.session_state.file_path and os.path.exists(st.session_state.file_path):
        try:
            if os.path.isdir(st.session_state.file_path):
                shutil.rmtree(st.session_state.file_path)
            else:
                os.remove(st.session_state.file_path)
        except Exception:
            pass
    st.session_state.app_step = 'input'
    for key in ['file_path', 'media_title', 'thumbnail_url', 'direct_url', 'detected_type', 'target_url', 'profile_entries', 'ig_bio', 'has_video', 'has_audio', 'download_is_audio']:
        st.session_state[key] = None

# --- 2. Navigation & Theme ---
col_logo, col_links, col_toggle = st.columns([1.5, 2.5, 0.5])
with col_logo:
    st.markdown("<h3 style='margin-top:0px; padding:0;'>💀 Void Tech Converter</h3>", unsafe_allow_html=True)
with col_links:
    st.markdown("""
        <div style="display: flex; gap: 2rem; color: #8B949E; font-weight: 500; justify-content: center; margin-top: 5px;">
            <span style="cursor:pointer;">Home</span>
            <span style="cursor:pointer;">FAQ</span>
            <span style="cursor:pointer;">Changelog</span>
            <span style="cursor:pointer;">Contact</span>
        </div>
    """, unsafe_allow_html=True)
with col_toggle:
    dark_mode = st.toggle("Dark mode", value=False, key="dark_mode_toggle", label_visibility="collapsed")

theme_css = """
    :root {
        --bg-color: #0E1117; --text-color: #F8F9FA; --input-bg: #1A1F26;
        --border-color: #30363D; --subtext: #8B949E;
    }
""" if dark_mode else """
    :root {
        --bg-color: #F8F9FA; --text-color: #212529; --input-bg: #FFFFFF;
        --border-color: #CED4DA; --subtext: #6C757D;
    }
"""

st.markdown(f"""
    <style>
    {theme_css}
    .stApp {{ background-color: var(--bg-color); color: var(--text-color); }}
    header, footer, #MainMenu {{ visibility: hidden; }}
    .main-title {{ text-align: center; font-size: 3.5rem; font-weight: 800; margin-top: 2rem; margin-bottom: 1rem; color: var(--text-color); }}
    .main-title span {{ color: #FF4A6B; }}
    .sub-title {{ text-align: center; font-size: 1.2rem; color: var(--subtext); max-width: 700px; margin: 0 auto 3rem auto; line-height: 1.5; }}
    .stTextInput > div > div > input {{ background-color: var(--input-bg); color: var(--text-color); border: 1px solid var(--border-color); border-radius: 6px; padding: 12px 20px; font-size: 1.1rem; }}
    .block-container {{ max-width: 900px; padding-top: 1rem; }}
    
    .ig-profile-card {{ display: flex; align-items: center; gap: 20px; background-color: var(--input-bg); padding: 20px; border-radius: 12px; border: 1px solid var(--border-color); margin-bottom: 20px; }}
    .ig-profile-card img {{ border-radius: 50%; width: 100px; height: 100px; object-fit: cover; border: 2px solid #FF4A6B; }}
    .ig-stats {{ color: var(--subtext); font-size: 0.95rem; margin-top: 5px; }}
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>Void Tech <span>Converter</span></div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Intelligently auto-detects, previews, and downloads Videos, Audio, Images, and Public Profiles from YouTube, Facebook, and Instagram.</div>", unsafe_allow_html=True)

# --- 3. Stealth yt-dlp Configuration ---
@contextmanager
def youtube_cookie_file():
    local_cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    if os.path.isfile(local_cookie_file):
        yield local_cookie_file
        return

    cookie_data = os.environ.get('YOUTUBE_COOKIES')
    if cookie_data is None:
        try:
            cookie_data = st.secrets.get('YOUTUBE_COOKIES')
        except FileNotFoundError:
            cookie_data = None

    if not cookie_data:
        yield None
        return
    if not isinstance(cookie_data, str):
        raise ValueError("YOUTUBE_COOKIES must contain Netscape-format cookie text.")

    fd, temporary_cookie_file = tempfile.mkstemp(prefix='conveters-youtube-cookies-', suffix='.txt')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as cookie_file:
            cookie_file.write(cookie_data)
        yield temporary_cookie_file
    finally:
        if os.path.exists(temporary_cookie_file):
            os.remove(temporary_cookie_file)


def get_base_opts(flat=False, cookie_file=None):
    opts = {
        'quiet': True, 
        'no_warnings': True,
        'rm_cachedir': True,
        'force_ipv4': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        },
        'extractor_args': {
            'youtube': {'player_client': ['android', 'web']}
        }
    }

    if cookie_file:
        opts['cookiefile'] = cookie_file
        
    if flat:
        opts['extract_flat'] = 'in_playlist'
    return opts


def get_ffmpeg_path():
    return shutil.which('ffmpeg') or imageio_ffmpeg.get_ffmpeg_exe()


def find_downloaded_file(ydl, info):
    candidates = []
    if info.get('filepath'):
        candidates.append(info['filepath'])
    candidates.append(ydl.prepare_filename(info))
    for requested in info.get('requested_downloads') or []:
        if requested.get('filepath'):
            candidates.append(requested['filepath'])

    for candidate in candidates:
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
            return candidate

    for candidate in candidates:
        base, _ = os.path.splitext(candidate)
        for extension in ('.mp4', '.mkv', '.webm', '.mov', '.m4a', '.mp3'):
            path = base + extension
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return path

    if any(os.path.isfile(candidate) for candidate in candidates):
        raise RuntimeError("The media host created an empty download. It did not return media data.")

    raise FileNotFoundError("yt-dlp reported success, but the downloaded media file was not found.")


def get_download_error_message(target_url, error):
    error_text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(error))
    hostname = (urllib.parse.urlparse(target_url).hostname or "").lower()
    is_youtube = (hostname == "youtu.be" or hostname == "youtube.com" or hostname.endswith(".youtube.com"))
    media_rejected = ("403" in error_text or "downloaded file is empty" in error_text.lower() or "empty download" in error_text.lower())

    if is_youtube and media_rejected:
        return (
            "❌ **YouTube did not provide the video data to this server.** "
            "This is a YouTube access restriction blocking the cloud IP, not an MP4 conversion problem. "
            "Changing formats or retrying will not fix this."
            f"\n\n*Technical Details:* `{error_text}`"
        )
    if "requested format is not available" in error_text.lower():
        return (
            "❌ **No compatible format was returned by the media source.** "
            f"\n\n*Technical Details:* `{error_text}`"
        )
    return f"❌ **Extraction Error:**\n\n`{error_text}`"


def convert_video_to_mp4(source_path, ffmpeg_path):
    if not os.path.isfile(source_path) or os.path.getsize(source_path) == 0:
        raise RuntimeError("The downloaded source file is empty; there is no media to convert.")

    output_dir = os.path.dirname(source_path) or '.'
    output_path = os.path.splitext(source_path)[0] + '.mp4'
    fd, temporary_path = tempfile.mkstemp(suffix='.mp4', dir=output_dir)
    os.close(fd)

    try:
        result = subprocess.run(
            [
                ffmpeg_path, '-hide_banner', '-loglevel', 'error', '-y',
                '-i', source_path, '-map', '0:v:0', '-map', '0:a:0?',
                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                '-movflags', '+faststart', temporary_path,
            ],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            details = result.stderr.strip().splitlines()
            raise RuntimeError("MP4 conversion failed: " + (details[-1] if details else "FFmpeg returned an error."))

        if os.path.getsize(temporary_path) == 0:
            raise RuntimeError("FFmpeg produced an empty MP4 file.")
        os.replace(temporary_path, output_path)
        if os.path.abspath(source_path) != os.path.abspath(output_path):
            os.remove(source_path)
        return output_path
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


# --- 4. Processing Logic ---
def process_single_download(target_url, is_audio=False):
    with st.spinner("Downloading media to server buffer..."):
        opts = get_base_opts()
        opts['outtmpl'] = os.path.join(st.session_state.temp_dir, '%(title)s.%(ext)s')
        ffmpeg_path = get_ffmpeg_path()
        opts['ffmpeg_location'] = ffmpeg_path

        if is_audio:
            opts['format'] = 'bestaudio/best'
            if ffmpeg_path:
                opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
            else:
                st.info("FFmpeg is unavailable, audio will download in original format.")
        else:
            opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/bestvideo'
        
        try:
            with youtube_cookie_file() as cookie_file:
                if cookie_file:
                    opts['cookiefile'] = cookie_file

                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(target_url, download=True)
                    downloaded_path = find_downloaded_file(ydl, info)

                    if is_audio:
                        expected_filename = os.path.splitext(downloaded_path)[0] + '.mp3'
                        if not os.path.isfile(expected_filename):
                            raise FileNotFoundError("FFmpeg did not produce the requested MP3 file.")
                    else:
                        expected_filename = convert_video_to_mp4(downloaded_path, ffmpeg_path)
                
                st.session_state.file_path = expected_filename
                st.session_state.download_is_audio = is_audio
                st.session_state.app_step = 'ready'
                st.rerun()
        except Exception as e:
            st.error(get_download_error_message(target_url, e))

def safe_ig_profile_scrape(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=5)
        img_match = re.search(r'<meta property="og:image" content="([^"]+)"', r.text)
        desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', r.text)
        
        if img_match:
            username = url.split('instagram.com/')[1].replace('/', '')
            return {
                'image': img_match.group(1).replace('&amp;', '&'),
                'description': desc_match.group(1).split('- See Instagram')[0].strip() if desc_match else "Instagram Profile",
                'username': f"@{username}"
            }
    except Exception:
        pass
    return None

# --- 5. Step 1: Input ---
if st.session_state.app_step == 'input':
    url = st.text_input("URL", label_visibility="collapsed", placeholder="Search or Insert URL here...")
    
    if st.button("Submit Link", use_container_width=True) and url:
        is_ig_profile = ('instagram.com' in url and not any(x in url for x in ['/p/', '/reel/', '/tv/']))
        
        with st.spinner("Analyzing link content..."):
            if is_ig_profile:
                ig_data = safe_ig_profile_scrape(url)
                if ig_data:
                    st.session_state.detected_type = 'ig_profile_preview'
                    st.session_state.media_title = ig_data['username']
                    st.session_state.thumbnail_url = ig_data['image']
                    st.session_state.ig_bio = ig_data['description']
                    st.session_state.target_url = url
                    st.session_state.app_step = 'preview'
                    st.rerun()
                else:
                    st.error("❌ Meta blocked access to this profile. Please paste an individual post link.")
            else:
                try:
                    with youtube_cookie_file() as cookie_file:
                        with yt_dlp.YoutubeDL(get_base_opts(cookie_file=cookie_file)) as ydl:
                            info = ydl.extract_info(url, download=False)
                        
                        entries = info.get('entries')
                        media_info = entries[0] if entries else info
                            
                        st.session_state.media_title = media_info.get('title') or info.get('title', 'Unknown Media')
                        thumbnails = media_info.get('thumbnails', [])
                        best_thumb = thumbnails[-1]['url'] if thumbnails else media_info.get('thumbnail')
                        
                        st.session_state.thumbnail_url = best_thumb
                        st.session_state.target_url = media_info.get('webpage_url') or info.get('webpage_url', url)
                        
                        formats = media_info.get('formats') or [media_info]
                        has_vid, has_aud = False, False
                        best_direct_url = media_info.get('url')
                        
                        for fmt in formats:
                            vcodec = fmt.get('vcodec')
                            acodec = fmt.get('acodec')
                            ext = fmt.get('ext', '').lower()
                            
                            if vcodec not in (None, 'none', '') or ext in ('mp4', 'webm', 'mov', 'mkv'):
                                has_vid = True
                                if ext == 'mp4' and fmt.get('url'):
                                    best_direct_url = fmt.get('url')
                            
                            if acodec not in (None, 'none', '') or ext in ('m4a', 'mp3', 'ogg', 'wav', 'aac'):
                                has_aud = True
                                
                        if media_info.get('_type') == 'video' or info.get('_type') == 'video':
                            has_vid = True
                            if not media_info.get('formats'):
                                has_aud = True

                        st.session_state.direct_url = best_direct_url
                        st.session_state.has_video = has_vid
                        st.session_state.has_audio = has_aud
                        st.session_state.detected_type = 'video' if has_vid else 'audio' if has_aud else 'image'
                        
                        if st.session_state.detected_type == 'image' and not st.session_state.direct_url:
                            st.session_state.direct_url = best_thumb
                            
                        st.session_state.app_step = 'preview'
                        st.rerun()
                except Exception as e:
                    st.error(get_download_error_message(url, e))

# --- 6. Step 2: Dynamic Preview ---
elif st.session_state.app_step == 'preview':
    st.markdown("<h2 style='text-align:center;'>Search result</h2>", unsafe_allow_html=True)
    
    if st.session_state.detected_type == 'ig_profile_preview':
        st.markdown(f"""
            <div class='ig-profile-card'>
                <img src='{st.session_state.thumbnail_url}'>
                <div>
                    <h3 style='margin:0; padding:0;'>{st.session_state.media_title}</h3>
                    <div class='ig-stats'><strong>{st.session_state.ig_bio}</strong></div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        st.warning("⚠ Meta heavily restricts automated profile downloads. Download from individual post links instead.")

    elif st.session_state.detected_type == 'video':
        target = st.session_state.target_url.lower()
        if 'youtube.com' in target or 'youtu.be' in target:
            st.video(st.session_state.target_url.replace('/shorts/', '/watch?v='))
        elif 'instagram.com' in target or 'facebook.com' in target:
            if st.session_state.direct_url and '.mp4' in st.session_state.direct_url.lower():
                st.video(st.session_state.direct_url)
            elif st.session_state.thumbnail_url:
                st.image(st.session_state.thumbnail_url, use_container_width=True)
                st.info("Live video preview restricted by Meta, but the video can still be downloaded below.")
        else:
            if st.session_state.direct_url:
                st.video(st.session_state.direct_url)
            elif st.session_state.thumbnail_url:
                st.image(st.session_state.thumbnail_url, use_container_width=True)
            
    elif st.session_state.detected_type == 'audio':
        if st.session_state.direct_url or st.session_state.target_url:
            st.audio(st.session_state.direct_url or st.session_state.target_url)
            
    elif st.session_state.detected_type == 'image':
        if st.session_state.thumbnail_url or st.session_state.direct_url:
            st.image(st.session_state.thumbnail_url or st.session_state.direct_url, use_container_width=True)

    if st.session_state.detected_type != 'ig_profile_preview':
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### Available Downloads:")
        if st.session_state.detected_type in ('video', 'audio'):
            if st.session_state.has_video and st.button("Download Video", use_container_width=True):
                process_single_download(st.session_state.target_url)
            if st.session_state.has_audio and st.button("Download Audio" + (" (MP3)" if get_ffmpeg_path() else ""), use_container_width=True):
                process_single_download(st.session_state.target_url, is_audio=True)
                    
        elif st.session_state.detected_type == 'image':
            if st.button("Download Image", use_container_width=True):
                target_img = st.session_state.direct_url or st.session_state.thumbnail_url
                if target_img:
                    try:
                        img_data = requests.get(target_img).content
                        safe_title = "".join(c for c in st.session_state.media_title if c.isalnum()).rstrip() or 'downloaded_image'
                        file_path = os.path.join(st.session_state.temp_dir, f"{safe_title}.jpg")
                        with open(file_path, 'wb') as f:
                            f.write(img_data)
                        st.session_state.file_path = file_path
                        st.session_state.app_step = 'ready'
                        st.rerun()
                    except:
                        st.error("❌ Failed to download the image directly from the server.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Cancel & Go Back", use_container_width=True):
        full_cleanup()
        st.rerun()

# --- 7. Step 3: Final File Delivery ---
elif st.session_state.app_step == 'ready' and st.session_state.file_path:
    st.success("Media is ready!")
    
    with open(st.session_state.file_path, "rb") as file:
        file_ext = os.path.splitext(st.session_state.file_path)[1].lower()
        mime_map = {
            '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.mkv': 'video/x-matroska',
            '.jpg': 'image/jpeg', '.png': 'image/png', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4'
        }
        
        st.download_button(
            label=f"Save {file_ext.upper().replace('.', '')} to Device",
            data=file,
            file_name=os.path.basename(st.session_state.file_path),
            mime=mime_map.get(file_ext, 'application/octet-stream'),
            use_container_width=True,
            type="primary"
        )
    
    st.markdown("<p style='text-align: center; color: #8B949E; margin-top: 15px;'><em>Note: Media is securely wiped from our servers immediately upon download.</em></p>", unsafe_allow_html=True)
    
    if st.button("Process Another Link", use_container_width=True):
        full_cleanup()
        st.rerun()