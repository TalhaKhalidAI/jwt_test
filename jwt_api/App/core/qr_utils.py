# App/core/qr_utils.py
import io
import base64
import qrcode
from qrcode.constants import ERROR_CORRECT_L


def generate_qr_png_bytes(data: str, box_size: int = 8, border: int = 2) -> bytes:
    """
    Generate PNG bytes of a QR code encoding the provided data string (e.g. JWT token).
    Uses ERROR_CORRECT_L for large tokens to ensure high capacity and optimal screen scanning.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr_base64_url(data: str, box_size: int = 8, border: int = 2) -> str:
    """
    Generate a data:image/png;base64,... data URL for the given string.
    """
    png_bytes = generate_qr_png_bytes(data, box_size=box_size, border=border)
    b64_str = base64.b64encode(png_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"
