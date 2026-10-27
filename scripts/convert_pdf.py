import argparse
from pathlib import Path
import re
from xml.sax.saxutils import escape

from docling.document_converter import DocumentConverter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepInFrame,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

def markdown_to_flowables(markdown: str, body_style, heading_styles):
    def paragraph_text(text: str) -> str:
        safe_text = escape(text)
        safe_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe_text)
        safe_text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", safe_text)
        return safe_text.replace("`", "")

    def table_cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    story = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue

        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                row = table_cells(lines[index])
                is_separator = all(
                    re.fullmatch(r":?-{3,}:?", cell.replace(" ", ""))
                    for cell in row
                )
                if not is_separator:
                    rows.append(row)
                index += 1
            if rows:
                column_count = max(map(len, rows))
                data = [
                    [
                        Paragraph(paragraph_text(cell), body_style)
                        for cell in row + [""] * (column_count - len(row))
                    ]
                    for row in rows
                ]
                table = Table(data, repeatRows=1, hAlign="LEFT")
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
                            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                            ("FONTNAME", (0, 0), (-1, -1), "DoclingFont"),
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 5),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.extend([table, Spacer(1, 8)])
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = min(len(heading.group(1)), 3)
            story.append(
                Paragraph(paragraph_text(heading.group(2)), heading_styles[level])
            )
        else:
            text = re.sub(r"^\s*[-*+]\s+", "• ", line)
            story.append(Paragraph(paragraph_text(text), body_style))
        index += 1
    return story


def render_pdf(markdown_pages: list[str], output_path: Path) -> None:
    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    if not font_path.exists():
        raise FileNotFoundError(f"Chinese-capable font not found: {font_path}")

    pdfmetrics.registerFont(TTFont("DoclingFont", str(font_path), subfontIndex=0))
    pdfmetrics.registerFontFamily(
        "DoclingFont",
        normal="DoclingFont",
        bold="DoclingFont",
        italic="DoclingFont",
        boldItalic="DoclingFont",
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "DoclingBody",
        parent=styles["BodyText"],
        fontName="DoclingFont",
        fontSize=9,
        leading=13,
        alignment=TA_LEFT,
        wordWrap="CJK",
        spaceAfter=5,
    )
    heading_styles = {
        1: ParagraphStyle(
            "DoclingH1", parent=body_style, fontSize=18, leading=23, spaceAfter=10
        ),
        2: ParagraphStyle(
            "DoclingH2", parent=body_style, fontSize=15, leading=20, spaceAfter=8
        ),
        3: ParagraphStyle(
            "DoclingH3", parent=body_style, fontSize=12, leading=16, spaceAfter=7
        ),
    }

    story = []
    page_width = A4[0] - 84
    page_height = A4[1] - 84
    for page_number, markdown in enumerate(markdown_pages):
        page_content = markdown_to_flowables(markdown, body_style, heading_styles)
        if not page_content:
            page_content = [Spacer(1, 1)]
        story.append(
            KeepInFrame(
                page_width,
                page_height,
                page_content,
                mode="shrink",
                hAlign="LEFT",
                vAlign="TOP",
            )
        )
        if page_number < len(markdown_pages) - 1:
            story.append(PageBreak())

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title=output_path.stem,
    )
    document.build(story)


def convert_pdf(pdf_path: Path, output_dir: Path) -> None:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / f"{pdf_path.stem}_text_tables.md"
    pdf_output_path = output_dir / f"{pdf_path.stem}_text_tables.pdf"

    result = DocumentConverter().convert(pdf_path)
    page_count = len(result.document.pages)
    markdown_pages = [
        result.document.export_to_markdown(
            image_placeholder="", page_no=page_number
        )
        for page_number in range(1, page_count + 1)
    ]
    markdown_path.write_text("\n\n---\n\n".join(markdown_pages), encoding="utf-8")
    render_pdf(markdown_pages, pdf_output_path)

    print(f"Saved Markdown to: {markdown_path}")
    print(f"Saved PDF to: {pdf_output_path} ({page_count} pages, matching the source)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract PDF text and tables while omitting pictures."
    )
    parser.add_argument(
        "pdfs",
        nargs="*",
        type=Path,
        help="PDF files to convert (defaults to data/REF1.pdf).",
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent.parent
    pdf_paths = args.pdfs or [project_root / "data" / "REF1.pdf"]
    output_dir = project_root / "output"
    for pdf_path in pdf_paths:
        convert_pdf(pdf_path, output_dir)


if __name__ == "__main__":
    main()
