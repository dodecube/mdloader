# msg.py - Fixed Symbol Corruption in Filenames
import sys
import json
import struct
import subprocess
import os
import time
import re
import traceback
import glob
from urllib.parse import urlparse
from PIL import Image

# Configuration
DOWNLOAD_DIR = 'E:/home/music-shazam'
YT_DLP_PATH = 'E:/home/music-shazam/deps/yt-dlp.exe'
FFMPEG_PATH = 'E:/home/music-shazam/deps/ffmpeg/bin'
COOKIES_PATH = 'E:/home/music-shazam/deps/cookies.txt'

def read_message():
    """Read a message from stdin using native messaging protocol"""
    try:
        raw_length = sys.stdin.buffer.read(4)
        if len(raw_length) == 0:
            return None
        message_length = struct.unpack('@I', raw_length)[0]
        message = sys.stdin.buffer.read(message_length).decode('utf-8')
        return json.loads(message)
    except Exception as e:
        debug_print(f"Error reading message: {e}")
        return None

def send_message(message):
    """Send a message to stdout using native messaging protocol"""
    try:
        encoded_message = json.dumps(message, ensure_ascii=False).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('@I', len(encoded_message)))
        sys.stdout.buffer.write(encoded_message)
        sys.stdout.buffer.flush()
    except Exception as e:
        debug_print(f"Error sending message: {e}")

def debug_print(message):
    """Print debug information to stderr"""
    print(f"DEBUG: {message}", file=sys.stderr)

def validate_url(url):
    """Validate and normalize the URL, allow ytsearch:"""
    try:
        if url.startswith('ytsearch:'):
            return True, url
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "❌ Invalid URL format"
        # Convert YouTube Music URLs to regular YouTube
        return True, url
    except Exception as e:
        return False, f"❌ URL validation error: {str(e)}"

def check_dependencies():
    """Check if all required dependencies are available"""
    dependencies = {
        'yt-dlp': YT_DLP_PATH,
        'ffmpeg': os.path.join(FFMPEG_PATH, 'ffmpeg.exe'),
        'download_dir': DOWNLOAD_DIR
    }
    
    missing = []
    for name, path in dependencies.items():
        if not os.path.exists(path):
            missing.append(f"{name} not found at: {path}")
        else:
            debug_print(f"✅ {name} found: {path}")
    
    # Cookies are optional but recommended
    if os.path.exists(COOKIES_PATH):
        debug_print(f"✅ Cookies found: {COOKIES_PATH}")
    else:
        debug_print("⚠️ Cookies file not found - some videos may not download")
    
    return missing

def test_yt_dlp():
    """Test if yt-dlp is working properly"""
    try:
        # Test version command
        result = subprocess.run(
            [YT_DLP_PATH, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return False, f"❌ yt-dlp test failed: {result.stderr}"
        
        version = result.stdout.strip()
        debug_print(f"✅ yt-dlp version: {version}")
        return True, version
        
    except subprocess.TimeoutExpired:
        return False, "❌ yt-dlp version check timed out"
    except Exception as e:
        return False, f"❌ yt-dlp test error: {str(e)}"

def get_video_info(url):
    """Get video information before downloading"""
    try:
        # Use --ignore-config and --no-warnings to prevent extra output
        cmd = [YT_DLP_PATH, '--ignore-config', '--no-warnings', '--dump-json', url]
        debug_print(f"Getting video info: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8'
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if "Video unavailable" in error_msg:
                return False, "❌ Video is unavailable or removed"
            elif "Private video" in error_msg:
                return False, "❌ Video is private"
            elif "is not a valid URL" in error_msg:
                return False, "❌ Invalid YouTube URL"
            else:
                return False, f"❌ Failed to get video info: {error_msg}"
        
        # The JSON output is always the last line of stdout (even with warnings)
        output_lines = result.stdout.strip().split('\n')
        if not output_lines or output_lines[-1] == '':
            debug_print("No output from yt-dlp")
            return False, "❌ No data received from yt-dlp"
        
        json_line = output_lines[-1]
        try:
            info = json.loads(json_line)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 'Unknown')
            debug_print(f"✅ Video: {title} ({duration}s)")
            return True, f"Found: {title}"
            
        except json.JSONDecodeError as e:
            debug_print("❌ JSON decode failed. Last line was:")
            debug_print(json_line)
            debug_print("Full stdout:")
            debug_print(result.stdout)
            debug_print("Full stderr:")
            debug_print(result.stderr)
            return False, "❌ Failed to parse video information"
            
    except subprocess.TimeoutExpired:
        return False, "❌ Video info request timed out"
    except Exception as e:
        return False, f"❌ Video info error: {str(e)}"
    
def download_with_progress(url, download_dir, use_cookies=False):
    """Download with progress tracking and detailed error handling"""
    try:
        # Build the download command - use title only to avoid artist issues
        JUNK_WORDS = [
            'official', 'lyrics', 'video', 'audio', 'hd', '4k', 
            'official video', 'official audio', 'lyric video', 
            'remastered', 'high res', 'full video'
        ]
        junk_pattern = "|".join(re.escape(word) for word in JUNK_WORDS)
        final_regex = rf' (?i)[(\[]({junk_pattern})[)\]]'
        cmd = [
            YT_DLP_PATH,
            '-f', 'bestaudio[ext=m4a]/bestaudio/best',  # <--- ADD THIS: Select best audio format, fallback to best overall
            '-x',                     # --extract-audio (convert to audio)
            '--audio-format', 'mp3',
            '--audio-quality', '192K',
            '--embed-metadata',
            '--add-metadata',
            '--write-thumbnail',
            '--convert-thumbnails', 'jpg',
            '--newline',
            '--progress',
            '--replace-in-metadata', 'title', final_regex, '',
            '-o', f'{download_dir}/%(title)s.%(ext)s',
            '--ffmpeg-location', FFMPEG_PATH,
        ]
        
        # Объединяем stdout и stderr, чтобы читать всё в одном цикле
        
        if use_cookies and os.path.exists(COOKIES_PATH):
            cmd.extend(['--cookies', COOKIES_PATH])
            debug_print("Using cookies for authentication")
        elif use_cookies:
            debug_print("Cookies requested but file not found")

        
        
        cmd.append(url)
        
        debug_print(f"Download command: {' '.join(cmd)}")
        
        # Start the download process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, 
            universal_newlines=True,
            encoding='utf-8', # Явно указываем кодировку
            errors='replace',
            bufsize=1,
            cwd=download_dir
        )
        
        full_output = []

        debug_print("Download process started")
        
        # Monitor process output
        if process.stdout:
            for line in process.stdout:
                line = line.strip()
                full_output.append(line)
                if not line:
                    continue
                debug_print(f"PROCESS: {line}")
                
                # Parse progress and update messages
                if '[youtube]' in line and 'Extracting URL' in line:
                    send_message({'status': 'progress', 'message': '📥 Extracting video information...', 'progress': 10})
                    
                elif '[download]' in line:
                    # Parse download progress
                    if '%' in line:
                        try:
                            match = re.search(r'(\d+\.\d+)%', line)
                            if match:
                                progress = float(match.group(1))
                                # Map download progress from 20% to 80%
                                mapped_progress = 20 + (progress * 0.6)
                                send_message({'status': 'progress', 'message': f'📥 Downloading: {progress:.1f}%', 'progress': int(mapped_progress)})
                        except:
                            pass
                            
                elif '[ExtractAudio]' in line or '[ffmpeg]' in line:
                    send_message({'status': 'progress', 'message': '🔄 Converting to MP3...', 'progress': 85})
                    
                elif '[Metadata]' in line:
                    send_message({'status': 'progress', 'message': '🏷️ Adding metadata...', 'progress': 95})
                    
                # Check for specific errors in output
                if 'ERROR:' in line:
                    if 'Video unavailable' in line:
                        return False, "❌ Video is unavailable or has been removed"
                    elif 'Private video' in line:
                        return False, "❌ This video is private"
                    elif 'Sign in' in line:
                        return False, "❌ Authentication required - check cookies"
                    elif 'Unsupported URL' in line:
                        return False, "❌ Unsupported URL or invalid video ID"
                    elif 'Too many requests' in line:
                        return False, "❌ YouTube rate limit exceeded - try again later"
        
        # Wait for process completion
        process.wait()
        
        if process.returncode == 0:
            return True, "✅ Успешно"
        else:
            # Ищем последнюю строку с ERROR в собранном логе
            error_log = "\n".join([l for l in full_output if "ERROR:" in l])
            return False, f"Ошибка yt-dlp: {error_log}"
                
    except subprocess.TimeoutExpired:
        return False, "⏰ Download process timed out"
    except Exception as e:
        return False, f"💥 Download process error: {str(e)}"

def safe_filename(text, max_length=200):
    if not text: return "Unknown"
    
    # Запрещенные символы Windows
    forbidden = r'[<>:"/\\|?*]'
    text = re.sub(forbidden, ' ', text)
    
    # Убираем управляющие символы
    text = "".join(ch for ch in text if ch.isprintable())
    
    # Резервные имена Windows
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "LPT1"}
    if text.upper() in reserved:
        text += "_res"

    return text.strip()[:max_length]

def get_metadata_with_encoding(mp3_path):
    """Extract metadata with proper encoding handling"""
    try:
        ffprobe_cmd = [
            os.path.join(FFMPEG_PATH, 'ffprobe.exe'),
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            mp3_path
        ]
        
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            # Try with different encoding if UTF-8 fails
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, encoding='cp1251')
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
        
    except Exception as e:
        debug_print(f"Error reading metadata from {mp3_path}: {e}")
        return None

def rename_file_based_on_metadata(mp3_path):
    try:
        metadata = get_metadata_with_encoding(mp3_path)
        if not metadata or 'format' not in metadata or 'tags' not in metadata['format']:
            return False
        
        tags = metadata['format']['tags']
        
        # Extract tags
        artist = tags.get('artist') or tags.get('ARTIST') or 'Unknown Artist'
        title = tags.get('title') or tags.get('TITLE') or 'Unknown Title'
        album = tags.get('album') or tags.get('ALBUM') or ''
        
        debug_print(f"Tags found -> Artist: {artist}, Title: {title}, Album: {album}")

        # FIX DOUBLE NAME: 
        # If title is "Tame Impala - Breathe Deeper", remove "Tame Impala - "
        artist_prefix = re.compile(rf"^{re.escape(artist)}\s*[-—–:—]\s*", re.IGNORECASE)
        clean_title = artist_prefix.sub("", title)
        
        # Construct new filename: "Artist - Title.mp3"
        if artist.upper() == 'NA' or not artist:
            new_filename = f"{safe_filename(clean_title)}.mp3"
        else:
            new_filename = f"{safe_filename(artist)} - {safe_filename(clean_title)}.mp3"
        
        new_path = os.path.join(os.path.dirname(mp3_path), new_filename)
        
        if os.path.basename(mp3_path) == new_filename:
            return True
        
        # Handle existing files
        counter = 1
        while os.path.exists(new_path):
            name_part = os.path.splitext(new_filename)[0]
            new_path = os.path.join(os.path.dirname(mp3_path), f"{name_part} ({counter}).mp3")
            counter += 1
        
        os.rename(mp3_path, new_path)
        return True
        
    except Exception as e:
        debug_print(f"❌ Rename error: {e}")
        return False

def rename_with_ascii_fallback(mp3_path, artist, title):
    """Fallback renaming with ASCII-only characters"""
    try:
        # Convert to ASCII, replacing non-ASCII characters
        def to_ascii(text):
            return text.encode('ascii', 'ignore').decode('ascii')
        
        safe_artist = safe_filename(to_ascii(artist))
        safe_title = safe_filename(to_ascii(title))
        
        new_filename = f"{safe_artist} - {safe_title}.mp3"
        new_path = os.path.join(os.path.dirname(mp3_path), new_filename)
        
        # Avoid conflicts
        counter = 1
        original_new_path = new_path
        while os.path.exists(new_path):
            name_part = f"{safe_artist} - {safe_title}"
            new_filename = f"{name_part} ({counter}).mp3"
            new_path = os.path.join(os.path.dirname(mp3_path), new_filename)
            counter += 1
        
        os.rename(mp3_path, new_path)
        debug_print(f"✅ Renamed with ASCII fallback: {os.path.basename(mp3_path)} -> {new_filename}")
        return True
        
    except Exception as e:
        debug_print(f"❌ ASCII fallback also failed: {e}")
        return False

def crop_to_square(image_path):
    try:
        img = Image.open(image_path)
        img = img.convert('RGB')
        
        width, height = img.size
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        
        img_cropped = img.crop((left, top, left + size, top + size))
        
        img.close() # Закрываем оригинал перед сохранением!
        img_cropped.save(image_path, 'JPEG', quality=95)
        return True
    except Exception as e:
        debug_print(f"Ошибка Pillow: {e}")
        return False

def embed_thumbnail_into_mp3(mp3_path, thumbnail_path):
    """Embed thumbnail into MP3 file using ffmpeg"""
    try:
        debug_print(f"📁 Embedding thumbnail into: {os.path.basename(mp3_path)}")
        
        temp_output = mp3_path + '.temp.mp3'
        
        ffmpeg_cmd = [
            os.path.join(FFMPEG_PATH, 'ffmpeg.exe'),
            '-i', mp3_path,      # Input MP3
            '-i', thumbnail_path, # Input thumbnail
            '-c', 'copy',        # Copy without re-encoding
            '-map', '0',         # Audio stream
            '-map', '1',         # Image stream
            '-id3v2_version', '3',
            '-metadata:s:v', 'title="Album cover"',
            '-metadata:s:v', 'comment="Cover (front)"',
            '-disposition:v', 'attached_pic',
            temp_output
        ]
        
        debug_print(f"Running FFmpeg: {' '.join(ffmpeg_cmd)}")
        
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Replace original file with the new one containing thumbnail
            os.replace(temp_output, mp3_path)
            debug_print(f"✅ Thumbnail embedded successfully: {os.path.basename(mp3_path)}")
            return True
        else:
            debug_print(f"❌ FFmpeg failed: {result.stderr}")
            # Clean up temp file if it exists
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False
            
    except subprocess.TimeoutExpired:
        debug_print("❌ FFmpeg timeout")
        return False
    except Exception as e:
        debug_print(f"❌ Error embedding thumbnail: {str(e)}")
        return False

def process_thumbnails_and_rename(download_dir):
    """Process all thumbnails and rename files based on metadata"""
    try:
        debug_print("🎨 Starting thumbnail processing and file renaming...")
        
        # Find all MP3 files
        mp3_files = glob.glob(os.path.join(download_dir, "*.mp3"))
        debug_print(f"Found {len(mp3_files)} MP3 files")
        
        processed_count = 0
        thumbnail_count = 0
        
        for mp3_path in mp3_files:
            original_filename = os.path.basename(mp3_path)
            try:
                
                debug_print(f"Processing: {original_filename}")
                
                # Step 1: Find corresponding thumbnail
                base_name = os.path.splitext(mp3_path)[0]
                jpg_path = base_name + '.jpg'
                
                thumbnail_processed = False
                if os.path.exists(jpg_path):
                    # Step 2: Crop thumbnail to square
                    if crop_to_square(jpg_path):
                        # Step 3: Embed thumbnail into MP3
                        if embed_thumbnail_into_mp3(mp3_path, jpg_path):
                            thumbnail_processed = True
                            thumbnail_count += 1
                
                # Step 4: Rename file based on metadata (regardless of thumbnail success)
                if rename_file_based_on_metadata(mp3_path):
                    processed_count += 1

                clean_mp3_metadata_title(mp3_path)
                
                # Clean up thumbnail file if it exists
                if os.path.exists(jpg_path):
                    try:
                        os.remove(jpg_path)
                        debug_print(f"🧹 Removed thumbnail: {os.path.basename(jpg_path)}")
                    except:
                        pass
                        
            except Exception as e:
                debug_print(f"❌ Error processing {original_filename}: {str(e)}")
                continue
        
        debug_print(f"✅ Processing completed: {processed_count} files renamed, {thumbnail_count} thumbnails embedded")
        return True
        
    except Exception as e:
        debug_print(f"❌ Thumbnail processing failed: {str(e)}")
        return False

def clean_mp3_metadata_title(mp3_path):
    """Удаляет 'Artist - ' из ID3 титла, оставляя artist как отдельный тег."""
    try:
        metadata = get_metadata_with_encoding(mp3_path)
        if not metadata or 'format' not in metadata or 'tags' not in metadata['format']:
            return False

        tags = metadata['format']['tags'] or {}
        artist = (tags.get('artist') or tags.get('ARTIST') or '').strip()
        title = (tags.get('title') or tags.get('TITLE') or '').strip()

        if not artist or not title:
            return False
        if artist.upper() == 'NA':
            return False

        # Убираем префикс "Artist - " из title (учитываем разные виды тире)
        new_title = re.sub(
            rf'^\s*{re.escape(artist)}\s*[-—–:]\s*',
            '',
            title,
            flags=re.IGNORECASE
        ).strip()

        # Если нечего чистить — выходим
        if not new_title or new_title == title:
            return False

        temp_output = mp3_path + '.meta.temp.mp3'

        ffmpeg_cmd = [
            os.path.join(FFMPEG_PATH, 'ffmpeg.exe'),
            '-i', mp3_path,
            '-map', '0',
            '-c', 'copy',
            '-id3v2_version', '3',
            '-metadata', f'title={new_title}',
            '-metadata', f'artist={artist}',
            temp_output
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            debug_print(f"❌ ffmpeg metadata update failed: {result.stderr}")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False

        os.replace(temp_output, mp3_path)
        debug_print(f"✅ Cleaned ID3 title: '{title}' -> '{new_title}'")
        return True

    except Exception as e:
        debug_print(f"❌ clean_mp3_metadata_title error: {e}")
        return False

def cleanup_download_directory(download_dir):
    """Clean up temporary files after download"""
    try:
        debug_print("🧹 Cleaning up temporary files...")
        files_removed = 0
        
        for f in os.listdir(download_dir):
            full_path = os.path.join(download_dir, f)
            
            # Remove temporary files but keep MP3 files
            if f.lower().endswith(('.webp', '.webm', '.part', '.temp', '.jpg')):
                try:
                    os.remove(full_path)
                    debug_print(f"Removed: {f}")
                    files_removed += 1
                except Exception as e:
                    debug_print(f"Failed to remove {f}: {e}")
        
        debug_print(f"🧹 Cleanup completed: {files_removed} files removed")
        
    except Exception as e:
        debug_print(f"❌ Cleanup error: {e}")

def download(url, use_cookies=False):
    """Main download function with comprehensive error handling"""
    try:
        # Create download directory
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        debug_print(f"📁 Download directory: {DOWNLOAD_DIR}")
        
        send_message({'status': 'progress', 'message': '🚀 Starting download...', 'progress': 5})
        
        # Step 1: Validate URL
        debug_print("Step 1: Validating URL...")
        is_valid, url_result = validate_url(url)
        if not is_valid:
            send_message({'status': 'error', 'message': url_result})
            return False
        
        url = url_result
        
        # Step 2: Check dependencies
        debug_print("Step 2: Checking dependencies...")
        missing_deps = check_dependencies()
        if missing_deps:
            error_msg = "❌ Missing dependencies:\n" + "\n".join(missing_deps)
            send_message({'status': 'error', 'message': error_msg})
            return False
        
        send_message({'status': 'progress', 'message': '✅ Dependencies checked...', 'progress': 15})
        
        # Step 3: Test yt-dlp
        debug_print("Step 3: Testing yt-dlp...")
        yt_dlp_ok, yt_dlp_msg = test_yt_dlp()
        if not yt_dlp_ok:
            send_message({'status': 'error', 'message': yt_dlp_msg})
            return False
        
        send_message({'status': 'progress', 'message': '✅ yt-dlp working...', 'progress': 20})
        
        # Step 4: Get video info
        debug_print("Step 4: Getting video information...")
        video_ok, video_msg = get_video_info(url)
        if not video_ok:
            send_message({'status': 'error', 'message': video_msg})
            return False
        
        send_message({'status': 'progress', 'message': '✅ Video info retrieved...', 'progress': 25})
        
        # Step 5: Perform download
        debug_print("Step 5: Starting download...")
        download_ok, download_msg = download_with_progress(url, DOWNLOAD_DIR, use_cookies)

        
        if download_ok:
            send_message({'status': 'progress', 'message': '🎨 Processing files...', 'progress': 95})
            
            # Step 6: Process thumbnails and rename files based on metadata
            debug_print("Step 6: Processing thumbnails and renaming files...")
            process_thumbnails_and_rename(DOWNLOAD_DIR)
            
            # Step 7: Cleanup
            debug_print("Step 7: Cleaning up...")
            cleanup_download_directory(DOWNLOAD_DIR)
            
            send_message({'status': 'success', 'message': '🎉 Download completed!', 'progress': 100})
            return True
        else:
            send_message({'status': 'error', 'message': download_msg})
            return False
            
    except Exception as e:
        error_msg = f"💥 Unexpected error: {str(e)}"
        debug_print(error_msg)
        debug_print(traceback.format_exc())
        send_message({'status': 'error', 'message': error_msg})
        return False

def main():
    """Main function to handle native messaging"""
    debug_print("🔧 Native host started - Fixed Unicode filename handling")
    
    while True:
        try:
            message = read_message()
            if not message:
                debug_print("No message received, exiting")
                break
                
            debug_print(f"Received message: {message}")
            
            if message.get('action') == 'download':
                url = message.get('url')
                use_cookies = message.get('useCookies', False)
                if url:
                    debug_print(f"Starting download process for: {url}, use_cookies={use_cookies}")
                    download(url, use_cookies)
                else:
                    send_message({'status': 'error', 'message': '❌ No URL provided'})
            else:
                send_message({'status': 'error', 'message': f'❌ Unknown action: {message.get("action")}'})
                
        except Exception as e:

            error_msg = f"💥 Main loop error: {str(e)}"
            debug_print(error_msg)
            send_message({'status': 'error', 'message': error_msg})
            time.sleep(1)

if __name__ == '__main__':
    main()