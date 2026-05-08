import argparse
import json
import re
from pathlib import Path
from typing import Optional

from pypdf import PdfReader
from tqdm import tqdm

from app.models import DocumentRecord


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        pages = [(p.extract_text() or "") for p in reader.pages]
        return "\n".join(pages).strip()
    except Exception:
        return ""


def parse_case_type(case_folder: str) -> Optional[str]:
    m = re.match(r"^\d+\._([^_]+)", case_folder)
    return m.group(1) if m else None


def parse_case_id(name: str) -> Optional[str]:
    m = re.search(r"(RS[_-]\d{4}-\d+)", name)
    if not m:
        return None
    return m.group(1).replace("_", "-")


def detect_doc_type(filename: str) -> str:
    low = filename.lower()
    if "protokoll" in low:
        return "minutes"
    if "interpellation" in low:
        return "interpellation"
    if "motion" in low:
        return "motion"
    if "förslag" in low or "forslag" in low:
        return "proposal"
    if "svar" in low:
        return "response"
    if "tjänsteutlåtande" in low or "tjansteutlatande" in low:
        return "service_memo"
    return "document"


def ingest(source: Path, out_file: Path, min_chars: int, max_files: int):
    pdfs = sorted(source.rglob("*.pdf"))
    if max_files > 0:
        pdfs = pdfs[:max_files]

    out_file.parent.mkdir(parents=True, exist_ok=True)
    written = 0

    with out_file.open("w", encoding="utf-8") as f:
        for pdf in tqdm(pdfs, desc="Ingesting PDFs"):
            text = extract_pdf_text(pdf)
            if len(text) < min_chars:
                continue

            rel = pdf.relative_to(source)
            parts = rel.parts
            case_folder = parts[0] if len(parts) > 1 else ""

            rec = DocumentRecord(
                meeting_date=source.name,
                case_folder=case_folder,
                case_type=parse_case_type(case_folder),
                case_id=parse_case_id(case_folder) or parse_case_id(pdf.name),
                document_title=pdf.stem,
                document_path=str(pdf),
                document_type=detect_doc_type(pdf.name),
                text=text,
            )
            f.write(json.dumps(rec.model_dump(), ensure_ascii=False) + "\n")
            written += 1

    print(f"Wrote {written} records to {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Ingest Region Stockholm PDFs into JSONL")
    parser.add_argument("--source", required=True, help="Folder like /home/demo/data/2026-05-05")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--min-chars", type=int, default=200, help="Skip docs with too little extracted text")
    parser.add_argument("--max-files", type=int, default=0, help="Optional cap for quick tests")
    args = parser.parse_args()

    ingest(Path(args.source), Path(args.out), args.min_chars, args.max_files)


if __name__ == "__main__":
    main()
