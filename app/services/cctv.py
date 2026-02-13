"""CCTV: signed URL generation for token-gated HLS stream."""
import hashlib
import hmac
import time
from urllib.parse import urlencode

from app.models.branch import CCTVConfig


def generate_signed_stream_url(config: CCTVConfig, *, student_id: str, expires_in: int = 3600) -> str:
    """Generate time-limited signed URL for HLS stream (IP/Token restriction)."""
    expiry = int(time.time()) + expires_in
    payload = f"{config.stream_id}:{student_id}:{expiry}"
    sig = hmac.new(
        config.token_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    params = {"token": sig, "expires": expiry, "student_id": student_id}
    base = config.hls_playlist_url.rstrip("/")
    return f"{base}?{urlencode(params)}"
