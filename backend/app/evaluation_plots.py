"""Small SVG exports drawn only from saved experiment metrics."""

from html import escape


def roc_svg(result: dict) -> str:
    width, height = 640, 440
    left, right, top, bottom = 70, 600, 45, 365

    def position(point: dict) -> str:
        x = left + point["false_positive_rate"] * (right - left)
        y = bottom - point["true_positive_rate"] * (bottom - top)
        return f"{x:.2f},{y:.2f}"

    lines = []
    for model_type, color in (("baseline", "#4f46e5"), ("siamese", "#059669")):
        points = result["models"][model_type]["roc"]
        lines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="3" '
            f'points="{" ".join(position(point) for point in points)}" />'
        )
    subtitle = (
        "Exploratory curve: class counts below the AUC/EER reporting gate"
        if not result["models"]["baseline"]["metrics"]["auc_eer_supported"]
        else "Held-out known-user verification"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        'viewBox="0 0 640 440" role="img" aria-label="ROC comparison">'
        '<rect width="640" height="440" fill="white" />'
        '<text x="70" y="25" font-family="Arial" font-size="19" font-weight="bold">ROC comparison</text>'
        f'<text x="70" y="42" font-family="Arial" font-size="11" fill="#475569">{escape(subtitle)}</text>'
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#334155" />'
        f'<line x1="{left}" y1="{bottom}" x2="{left}" y2="{top}" stroke="#334155" />'
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{top}" stroke="#cbd5e1" stroke-dasharray="5 5" />'
        f'{"".join(lines)}'
        '<text x="280" y="402" font-family="Arial" font-size="13">False positive rate</text>'
        '<text x="10" y="205" transform="rotate(-90 10 205)" font-family="Arial" font-size="13">True positive rate</text>'
        '<text x="65" y="383" font-family="Arial" font-size="11">0</text>'
        '<text x="596" y="383" font-family="Arial" font-size="11">1</text>'
        '<text x="52" y="50" font-family="Arial" font-size="11">1</text>'
        '<line x1="385" y1="420" x2="410" y2="420" stroke="#4f46e5" stroke-width="3" />'
        '<text x="416" y="424" font-family="Arial" font-size="11">Baseline</text>'
        '<line x1="495" y1="420" x2="520" y2="420" stroke="#059669" stroke-width="3" />'
        '<text x="526" y="424" font-family="Arial" font-size="11">Siamese</text>'
        '</svg>'
    )


def confusion_svg(result: dict) -> str:
    pieces = [
        ('<svg xmlns="http://www.w3.org/2000/svg" width="760" height="340" '
        'viewBox="0 0 760 340" role="img" aria-label="Confusion matrices">'
        '<rect width="760" height="340" fill="white" />'
        '<text x="30" y="28" font-family="Arial" font-size="19" font-weight="bold">Held-out confusion matrices</text>'
        '<text x="100" y="70" font-family="Arial" font-size="12">Predicted accept</text>'
        '<text x="240" y="70" font-family="Arial" font-size="12">Predicted reject</text>'
        '<text x="470" y="70" font-family="Arial" font-size="12">Predicted accept</text>'
        '<text x="610" y="70" font-family="Arial" font-size="12">Predicted reject</text>')
    ]
    for model_type, offset, label in (
        ("baseline", 0, "Baseline"), ("siamese", 370, "Siamese")
    ):
        metrics = result["models"][model_type]["metrics"]
        pieces.append(
            f'<text x="{30 + offset}" y="58" font-family="Arial" '
            f'font-size="15" font-weight="bold">{label}</text>'
        )
        for row, actual in enumerate(("Genuine", "Impostor")):
            pieces.append(
                f'<text x="{30 + offset}" y="{128 + row * 100}" '
                f'font-family="Arial" font-size="12">{actual}</text>'
            )
        for column, row, key, color in (
            (0, 0, "true_positive", "#dcfce7"),
            (1, 0, "false_negative", "#fef3c7"),
            (0, 1, "false_positive", "#fee2e2"),
            (1, 1, "true_negative", "#e0e7ff"),
        ):
            x, y = 100 + offset + column * 140, 85 + row * 100
            pieces.append(
                f'<rect x="{x}" y="{y}" width="125" height="85" '
                f'rx="7" fill="{color}" />'
                f'<text x="{x + 62}" y="{y + 52}" text-anchor="middle" '
                f'font-family="Arial" font-size="25">{metrics[key]}</text>'
            )
    pieces.append('</svg>')
    return "".join(pieces)
