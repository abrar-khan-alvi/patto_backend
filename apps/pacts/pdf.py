from textwrap import wrap

from apps.pacts.models import PactVersion


def build_pact_pdf_bytes(*, version: PactVersion) -> bytes:
    pact = version.pact
    lines = [
        "Patto Relationship Pact",
        f"Pact: {pact.title}",
        f"Version: {version.version}",
        f"Activated at: {version.activated_at.isoformat() if version.activated_at else ''}",
        "",
        "Shared agreements:",
    ]
    for index, clause in enumerate(version.clauses.order_by("sort_order"), start=1):
        clause_lines = wrap(f"{index}. {clause.text}", width=88) or [f"{index}."]
        lines.extend(clause_lines)
        lines.append("")
    lines.append("This PDF is an immutable snapshot of the live pact version stored by Patto.")
    return render_simple_pdf(lines)


def render_simple_pdf(lines: list[str]) -> bytes:
    escaped_lines = [escape_pdf_text(line) for line in lines]
    y = 780
    content_parts = ["BT", "/F1 12 Tf", "50 780 Td"]
    first = True
    for line in escaped_lines:
        if first:
            content_parts.append(f"({line}) Tj")
            first = False
        else:
            content_parts.append("0 -16 Td")
            content_parts.append(f"({line}) Tj")
        y -= 16
        if y < 60:
            break
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
