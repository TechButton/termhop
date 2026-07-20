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
    # Pack two QR rows into one terminal cell. This keeps the code compact
    # enough to scan from a normal laptop display without zooming out while
    # preserving each module's contrast.
    rows = []
    for index in range(0, len(matrix), 2):
        top = matrix[index]
        bottom = matrix[index + 1] if index + 1 < len(matrix) else [False] * len(top)
        line = []
        for top_dark, bottom_dark in zip(top, bottom):
            if top_dark and bottom_dark:
                line.append("█")
            elif top_dark:
                line.append("▀")
            elif bottom_dark:
                line.append("▄")
            else:
                line.append(" ")
        rows.append("".join(line))
    return "\n".join(rows)


def print_pairing_qr(value: str) -> None:
    print("QR code (scan with the browser client):")
    print(render_pairing_qr(value))
