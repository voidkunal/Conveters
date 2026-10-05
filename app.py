import streamlit as st
import yt_dlp
import os
import requests
import urllib.parse
import shutil
import tempfile
import re
import imageio_ffmpeg

# Get the internal path to the bundled FFmpeg to bypass Streamlit's system limitations
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# --- 1. Page Config & Session State ---
st.set_page_config(page_title="Void Tech Converter", page_icon="💀", layout="wide")

if 'app_step' not in st.session_state:
    st.session_state.app_step = 'input'

if 'temp_dir' not in st.session_state:
    os.makedirs('downloads', exist_ok=True)
    st.session_state.temp_dir = 'downloads'

for key in ['file_path', 'media_title', 'thumbnail_url', 'direct_url', 'detected_type', 'target_url', 'profile_entries', 'ig_bio']:
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
    for key in ['file_path', 'media_title', 'thumbnail_url', 'direct_url', 'detected_type', 'target_url', 'profile_entries', 'ig_bio']:
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
    dark_mode = st.toggle("", value=False, key="dark_mode_toggle")

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
def get_base_opts(flat=False):
    opts = {
        'quiet': True, 
        'nocheckcertificate': True,
        'no_warnings': True,
        'source_address': '0.0.0.0', 
        'rm_cachedir': True,
        'ffmpeg_location': FFMPEG_PATH, # Uses the built-in Python FFmpeg
        'extractor_args': {
            'youtube': {'player_client': ['ios']}
        }
    }
    if flat:
        opts['extract_flat'] = 'in_playlist'
    return opts

# --- 4. Processing Logic ---
def process_single_download(target_url, format_str, is_audio=False):
    with st.spinner("Downloading media to server buffer..."):
        opts = get_base_opts()
        opts['outtmpl'] = os.path.join(st.session_state.temp_dir, '%(title)s.%(ext)s')
        
        if is_audio:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            opts['format'] = format_str
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target_url, download=True)
                expected_filename = ydl.prepare_filename(info)
                
                if is_audio:
                    base, _ = os.path.splitext(expected_filename)
                    expected_filename = base + '.mp3'
                    
                st.session_state.file_path = expected_filename
                st.session_state.app_step = 'ready'
                st.rerun()
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg or "Sign in" in error_msg:
                st.error(f"❌ **Platform Blocked Request:** YouTube is temporarily blocking the cloud server. \n\n*Technical Details:* `{error_msg}`")
            else:
                st.error(f"❌ **Extraction Error:** \n\n`{error_msg}`")

def safe_ig_profile_scrape(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=5)
        img_match = re.search(r'<meta property="og:image" content="([^"]+)"', r.text)
        desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', r.text)
        
        if img_match:
            username = url.split('instagram.com/')[1].replace('/', '')
            return {
                'image': img_match.group(1),
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
                    st.error("❌ Meta blocked access to this profile. Please paste a link to an individual post or reel instead.")
            else:
                try:
                    with yt_dlp.YoutubeDL(get_base_opts(flat=True)) as ydl:
                        info = ydl.extract_info(url, download=False)
                        st.session_state.media_title = info.get('title', 'Unknown Media')
                        st.session_state.thumbnail_url = info.get('thumbnail')
                        st.session_state.direct_url = info.get('url')
                        st.session_state.target_url = info.get('webpage_url', url)
                        
                        ext = info.get('ext', '').lower()
                        if ext in ['mp4', 'webm', 'mov'] or info.get('vcodec') not in [None, 'none', '']:
                            st.session_state.detected_type = 'video'
                        elif ext in ['m4a', 'mp3', 'wav', 'ogg'] or info.get('acodec') not in [None, 'none', '']:
                            st.session_state.detected_type = 'audio'
                        else:
                            st.session_state.detected_type = 'image'
                            
                        st.session_state.app_step = 'preview'
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Could not locate media. Ensure the link is public and valid. \n\n*Error details:* `{str(e)}`")

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
        st.warning("⚠ **Notice:** Meta heavily restricts automated profile downloads. To download videos/photos, please copy and paste the link to an **individual post**.")

    elif st.session_state.detected_type == 'video':
        target = st.session_state.target_url.lower()
        if 'youtube.com' in target or 'youtu.be' in target:
            st.video(st.session_state.target_url)
        elif 'facebook.com' in target or 'fb.watch' in target:
            clean_url = st.session_state.target_url.split('?')[0] if 'fb.watch' in target else st.session_state.target_url
            encoded_url = urllib.parse.quote(clean_url)
            st.markdown(f'''<div style="display: flex; justify-content: center; margin-bottom: 20px;"><iframe src="https://www.facebook.com/plugins/video.php?href={encoded_url}&show_text=0&width=560" width="560" height="315" style="border:none;overflow:hidden" scrolling="no" frameborder="0" allowfullscreen="true" allow="autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share"></iframe></div>''', unsafe_allow_html=True)
        elif 'instagram.com' in target:
            parsed = urllib.parse.urlparse(st.session_state.target_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if not base_url.endswith('/'): base_url += '/'
            st.markdown(f'''<div style="display: flex; justify-content: center; margin-bottom: 20px;"><iframe src="{base_url}embed" width="400" height="480" frameborder="0" scrolling="no" allowtransparency="true"></iframe></div>''', unsafe_allow_html=True)
        else:
            if st.session_state.thumbnail_url: st.image(st.session_state.thumbnail_url, use_column_width=True)
            
    elif st.session_state.detected_type == 'audio':
        st.audio(st.session_state.direct_url or st.session_state.target_url)
    elif st.session_state.detected_type == 'image':
        st.image(st.session_state.thumbnail_url or st.session_state.direct_url, use_column_width=True)

    if st.session_state.detected_type != 'ig_profile_preview':
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### Available Downloads:")
        if st.session_state.detected_type == 'video':
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Extract High-Quality Video (MP4)", use_container_width=True):
                    process_single_download(st.session_state.target_url, 'b[ext=mp4]/best')
            with col2:
                if st.button("Extract Audio Track Only (MP3)", use_container_width=True):
                    process_single_download(st.session_state.target_url, None, is_audio=True)
                            
        elif st.session_state.detected_type == 'audio':
            if st.button("Download Audio Track (MP3)", use_container_width=True):
                process_single_download(st.session_state.target_url, None, is_audio=True)
                        
        elif st.session_state.detected_type == 'image':
            if st.button("Download High Quality Image", use_container_width=True):
                with st.spinner("Downloading image..."):
                    target_img_url = st.session_state.direct_url or st.session_state.thumbnail_url
                    if target_img_url:
                        img_data = requests.get(target_img_url).content
                        safe_title = "".join([c for c in st.session_state.media_title if c.isalpha() or c.isdigit()]).rstrip()
                        file_path = os.path.join(st.session_state.temp_dir, f"{safe_title if safe_title else 'downloaded_image'}.jpg")
                        with open(file_path, 'wb') as handler:
                            handler.write(img_data)
                        st.session_state.file_path = file_path
                        st.session_state.app_step = 'ready'
                        st.rerun()
    
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
            '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime',
            '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.wav': 'audio/wav',
            '.jpg': 'image/jpeg', '.png': 'image/png'
        }
        mime_type = mime_map.get(file_ext, 'application/octet-stream')
        
        st.download_button(
            label=f"Save {file_ext.upper().replace('.', '')} to Device",
            data=file,
            file_name=os.path.basename(st.session_state.file_path),
            mime=mime_type,
            use_container_width=True,
            type="primary",
            on_click=full_cleanup 
        )
    
    st.markdown("<p style='text-align: center; color: #8B949E; margin-top: 15px;'><em>Note: Media is securely wiped from our servers immediately upon download.</em></p>", unsafe_allow_html=True)
    
    if st.button("Process Another Link", use_container_width=True):
        full_cleanup()
        st.rerun()
