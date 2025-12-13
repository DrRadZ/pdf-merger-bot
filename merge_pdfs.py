from pathlib import Path
from PyPDF2 import PdfMerger

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "pdfs"
OUTPUT_DIR = BASE_DIR / "output"


def merge_pdfs(output_name: str = "merged.pdf") -> None:
    """
    Merge all PDFs in the INPUT_DIR folder into a single PDF
    saved in OUTPUT_DIR / output_name.
    """
    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}")
        return
    OUTPUT_DIR.mkdir(exist_ok=True)

    merger = PdfMerger()

    try:
        print("Merging PDFs in this order:")
        for pdf_path in pdf_files:
            print(f"  - {pdf_path.name}")
            merger.append(str(pdf_path))

        output_path = OUTPUT_DIR / output_name
        with output_path.open("wb") as f_out:
            merger.write(f_out)

        print(f"\nDone! Merged file saved as: {output_path}")
    finally:
        merger.close()


if __name__ == "__main__":
    # Change the output file name here if you want
    merge_pdfs("8245AE-merged-lecture-notes.pdf")
