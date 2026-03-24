from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_pdf_to_txt(pdf_path: Path, out_dir: Path) -> Path:
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"\n\n--- PAGE {page_index} ---\n")
        parts.append(text)

    out_path = out_dir / f"{pdf_path.stem}.txt"
    out_path.write_text("".join(parts), encoding="utf-8")
    return out_path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    pdf_dir = root / "docs" / "mesob docs"
    out_dir = pdf_dir / "extracted"
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = [
        pdf_dir / "STOCK-MANAGEMENT-MANUAL-2002-AMHARIC.pdf",
        pdf_dir / "Stock_Management_Manual_English.pdf",
    ]

    for pdf_path in pdfs:
        if not pdf_path.exists():
            raise FileNotFoundError(str(pdf_path))

        out_path = extract_pdf_to_txt(pdf_path, out_dir)
        print(f"Wrote: {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
