"""Render a short-lived pairing URI as a terminal QR code.

The URI is already printed as a text fallback. This renderer deliberately uses
only the qrcode matrix API (not Pillow), so it works over SSH and on Linux,
macOS, and Windows terminals without creating an image file.
"""

import qrcode


def render_pairing_qr(value: str) -> str:
    code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=2,
    )
    code.add_data(value)
    code.make(fit=True)
    matrix = code.get_matrix()
    # Two horizontal terminal cells per QR module preserve the square aspect
    # ratio on typical terminals (which are taller than they are wide).
    return "\n".join(
        "".join("██" if dark else "  " for dark in row) for row in matrix
    )


def print_pairing_qr(value: str) -> None:
    print("QR code (scan with the browser client):")
    print(render_pairing_qr(value))
