import os
import json
import subprocess
import hashlib
from datetime import datetime
from flask import current_app
from app.models import ConversionType

FFPROBE_BIN = os.environ.get('FFPROBE_BIN', 'ffprobe')

class VideoMetadataError(Exception):
    pass

def run_ffprobe(path: str) -> dict:
    """Run ffprobe and return parsed json info."""
    cmd = [
        FFPROBE_BIN, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', path
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise VideoMetadataError("ffprobe not found. Install ffmpeg or set FFPROBE_BIN env var.")
    except subprocess.TimeoutExpired:
        raise VideoMetadataError("ffprobe timed out")
    if proc.returncode != 0:
        raise VideoMetadataError(f"ffprobe failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as je:
        raise VideoMetadataError(f"ffprobe output JSON parse error: {je}")


def extract_metadata(path: str) -> dict:
    info = run_ffprobe(path)
    fmt = info.get('format', {})
    streams = info.get('streams', [])
    v_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
    a_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)

    duration = None
    try:
        duration = float(fmt.get('duration')) if fmt.get('duration') else None
    except Exception:
        duration = None

    meta = {
        'format_name': fmt.get('format_name'),
        'duration_seconds': duration,
        'bit_rate': fmt.get('bit_rate'),
        'video_codec': v_stream.get('codec_name') if v_stream else None,
        'audio_codec': a_stream.get('codec_name') if a_stream else None,
        'width': v_stream.get('width') if v_stream else None,
        'height': v_stream.get('height') if v_stream else None,
        'avg_frame_rate': v_stream.get('avg_frame_rate') if v_stream else None,
        'nb_streams': fmt.get('nb_streams'),
    }
    return meta


def convert_video_metadata(path: str):
    """Return (markdown_content, ConversionType.VIDEO_METADATA) or (error, None)."""
    def format_bytes(num: int) -> str:
        if num is None:
            return 'N/A'
        units = ['B','KB','MB','GB','TB']
        size = float(num)
        for u in units:
            if size < 1024 or u == units[-1]:
                return f"{size:.2f} {u}"
            size /= 1024

    def format_duration(seconds: float) -> str:
        if not seconds and seconds != 0:
            return 'N/A'
        # seconds may be float
        s = int(seconds)
        ms = int((seconds - s) * 1000)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"
        else:
            return f"{m:02d}:{sec:02d}.{ms:03d}"
    try:
        file_stats = os.stat(path)
        with open(path, 'rb') as f:
            sha256_hash = hashlib.sha256(f.read()).hexdigest()
        meta = extract_metadata(path)
    except VideoMetadataError as ve:
        return f"Video metadata extraction failed: {ve}", None
    except Exception as e:
        return f"Unexpected video processing error: {e}", None

    front = {
        'source_file': os.path.basename(path),
        'provider': 'video-metadata',
        'hash_sha256': sha256_hash,
        'file_size_bytes': file_stats.st_size,
        'modified_time': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
        'video': {**meta, 'duration_human': format_duration(meta.get('duration_seconds'))},
        'file_size_human': format_bytes(file_stats.st_size),  # 放在最后，方便阅读
    }

    # simple yaml dump
    def dump_yaml(d, indent=0):
        lines = []
        for k,v in d.items():
            if isinstance(v, dict):
                lines.append(' ' * indent + f"{k}:")
                for sk, sv in v.items():
                    lines.append(' ' * (indent + 2) + f"{sk}: {sv}")
            else:
                lines.append(' ' * indent + f"{k}: {v}")
        return '\n'.join(lines)

    yaml_block = dump_yaml(front)
    md_parts = ["---", yaml_block, "---", f"# {os.path.basename(path)}", "(视频元数据占位，尚未生成转录内容)"]
    content = '\n\n'.join(md_parts) + '\n'
    return content, ConversionType.VIDEO_METADATA
