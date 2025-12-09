import os
import sys

import pdfplumber
import pyttsx3
import platform
from langdetect import detect, LangDetectException

try:
    # tkinter is usually included with Python; if this import fails,
    # you can fall back to typing the path manually.
    from tkinter import Tk, filedialog
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

def init_tts_engine():
    system = platform.system()
    if system == "Windows":
        engine = pyttsx3.init("sapi5")
    elif system == "Darwin":
        engine = pyttsx3.init("nsss")
    else:
        engine = pyttsx3.init("espeak")

    rate = engine.getProperty("rate")
    engine.setProperty("rate", rate - 20)  # slightly slower

    return engine

def build_language_voice_map(engine):
    """
    Returns a dict like {"en": voice_id, "fr": voice_id}
    based on installed voices.
    """
    voices = engine.getProperty("voices")
    lang_voice_map = {}

    print("Available voices:")
    for i, v in enumerate(voices):
        print(f"{i}: id={v.id}, name={getattr(v, 'name', '')}")

    def voice_matches(v, keywords):
        text = (v.id + " " + getattr(v, "name", "")).lower()
        return any(k.lower() in text for k in keywords)

    # Try to find English voice
    for v in voices:
        if voice_matches(v, ["en", "english"]):
            lang_voice_map["en"] = v.id
            break

    # Try to find French voice
    for v in voices:
        if voice_matches(v, ["fr", "french", "français", "francais"]):
            lang_voice_map["fr"] = v.id
            break

    print("Language → voice map:", lang_voice_map)
    return lang_voice_map

def detect_language_of_text(text: str) -> str:
    """
    Detects the language code ('en', 'fr', etc.) of the given text.
    Returns 'unknown' on failure.
    """
    sample = text[:800]  # use first ~800 chars
    try:
        lang = detect(sample)
        print(f"Detected language: {lang}")
        return lang
    except LangDetectException:
        print("Could not detect language, defaulting to 'unknown'")
        return "unknown"


def choose_pdf_file() -> str | None:
    """
    Opens a file dialog to let the user choose a PDF.
    Returns the selected path, or None if nothing chosen.
    """
    if not TK_AVAILABLE:
        # Fallback: ask for path in console
        pdf_path = input("Enter the full path to your PDF file: ").strip()
        return pdf_path if pdf_path else None

    root = Tk()
    root.withdraw()  # hide the main window

    file_path = filedialog.askopenfilename(
        title="Select a PDF file to read aloud",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )

    root.destroy()
    return file_path if file_path else None


def extract_text_from_pdf(pdf_path: str):
    """
    Extracts and returns a list of (page_number, text) tuples
    from the given PDF file.
    """
    all_pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                print(f"[info] Page {i} has no extractable text (maybe scanned).")
                continue

            # Basic cleanup: collapse whitespace
            cleaned_text = " ".join(text.split())
            if cleaned_text.strip():
                all_pages_text.append((i, cleaned_text))

    return all_pages_text


def read_text_aloud(pages_text, start_page: int | None = None):
    """
    Uses pyttsx3 to read the text of each page aloud.
    Detects language (en/fr) and picks appropriate voice if available.
    """
    if not pages_text:
        print("No text to read.")
        return

    engine = init_tts_engine()
    lang_voice_map = build_language_voice_map(engine)

    # Default language if detection fails
    default_lang = "en"

    # Filter pages if a starting page was provided
    if start_page is not None:
        pages_text = [(num, text) for (num, text) in pages_text if num >= start_page]
        if not pages_text:
            print(f"No pages found starting from page {start_page}.")
            return

    for page_num, text in pages_text:
        print(f"\n--- Reading page {page_num} ---")

        # Detect language of this page
        lang = detect_language_of_text(text)
        if lang not in lang_voice_map:
            print(f"No dedicated voice for language '{lang}', using default.")
            lang = default_lang

        # Set voice for this page (if we have one)
        voice_id = lang_voice_map.get(lang)
        if voice_id:
            engine.setProperty("voice", voice_id)
            print(f"Using voice '{voice_id}' for language '{lang}'")

        # Say page number in that language
        if lang == "fr":
            engine.say(f"Page {page_num}")
        else:
            engine.say(f"Page {page_num}")

        engine.say(text)
        engine.runAndWait()

    print("Finished reading all pages.")

def main():
    # 1. Get PDF path either from command line or file chooser
    if len(sys.argv) >= 2:
        pdf_path = sys.argv[1]
    else:
        print("No PDF path provided as an argument. Opening file chooser...")
        pdf_path = choose_pdf_file()

    if not pdf_path:
        print("No file selected. Exiting.")
        return

    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    if not pdf_path.lower().endswith(".pdf"):
        print("The selected file is not a PDF.")
        return

    print(f"Using PDF: {pdf_path}")

    # 2. Extract text
    print("Extracting text from PDF...")
    pages_text = extract_text_from_pdf(pdf_path)

    if not pages_text:
        print("No readable text found in this PDF. It might be scanned images.")
        return

    # 3. Ask user which page to start from (optional)
    print(f"The PDF has {len(pages_text)} pages with extractable text.")
    start_page_input = input(
        "Enter a page number to start from (or press Enter to start at the beginning): "
    ).strip()

    start_page = None
    if start_page_input:
        try:
            start_page = int(start_page_input)
        except ValueError:
            print("Invalid page number. Starting from the beginning.")
            start_page = None

    # 4. Read aloud
    print("Starting text-to-speech...")
    read_text_aloud(pages_text, start_page=start_page)
    print("Done.")


if __name__ == "__main__":
    main()
