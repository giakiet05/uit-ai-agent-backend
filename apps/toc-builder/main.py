"""
ToC Builder - Build table of contents for reasoning-based RAG.

Entry point for toc-builder CLI.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def main():
    """Main CLI entry point."""
    import argparse
    from utils.logger import logger

    parser = argparse.ArgumentParser(
        description="ToC Builder - Build table of contents for reasoning-based RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse single PDF
  utb parse <pdf_path>

  # Parse all PDFs in folder
  utb parse --dir <folder_path>

  # Build ToC from single file
  utb build-toc --pdf <pdf_path>
  utb build-toc --md <md_path>

  # Build ToC from all files in folder
  utb build-toc --pdf-dir <folder_path>
  utb build-toc --md-dir <folder_path>

  # Build ToC index
  utb build-index
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Parse command
    parse_parser = subparsers.add_parser("parse", help="Parse PDF to markdown (text or scanned)")
    parse_parser.add_argument("pdf_path", nargs="?", help="Path to input PDF file")
    parse_parser.add_argument(
        "--dir", dest="pdf_dir", help="Path to folder containing PDF files"
    )
    parse_parser.add_argument(
        "--output", help="Optional output path (only for single file)"
    )
    parse_parser.add_argument(
        "--no-skip", dest="no_skip", action="store_true",
        help="Don't skip existing files, re-parse them"
    )

    # Build ToC command
    build_parser = subparsers.add_parser("build-toc", help="Build ToC from document")
    build_parser.add_argument(
        "--pdf", help="Path to PDF file", dest="pdf_path"
    )
    build_parser.add_argument(
        "--md", help="Path to markdown file", dest="md_path"
    )
    build_parser.add_argument(
        "--pdf-dir", help="Path to folder containing PDF files", dest="pdf_dir"
    )
    build_parser.add_argument(
        "--md-dir", help="Path to folder containing markdown files", dest="md_dir"
    )
    build_parser.add_argument(
        "--summary",
        choices=["yes", "no"],
        default="no",
        help="Add node summaries (default: no)",
    )
    build_parser.add_argument(
        "--text",
        choices=["yes", "no"],
        default="yes",
        help="Add node text (default: yes)",
    )

    # Build index command
    index_parser = subparsers.add_parser(
        "build-index", help="Build ToC index from all ToC files"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "parse":
            from llamaparse_ocr import LlamaParseOCR

            if not args.pdf_path and not args.pdf_dir:
                logger.error("[ERROR] Must provide pdf_path or --dir")
                sys.exit(1)

            llama_parser = LlamaParseOCR()
            skip_existing = not args.no_skip

            if args.pdf_dir:
                pdf_dir = Path(args.pdf_dir)
                pdf_files = sorted(pdf_dir.glob("*.pdf"))
                logger.info(f"[PARSE] Found {len(pdf_files)} PDF files in {pdf_dir}")

                for pdf_file in pdf_files:
                    try:
                        llama_parser.parse_pdf(pdf_path=pdf_file, skip_existing=skip_existing)
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to parse {pdf_file.name}: {e}")
            else:
                llama_parser.parse_pdf(
                    pdf_path=args.pdf_path,
                    output_path=args.output,
                    skip_existing=skip_existing,
                )

        elif args.command == "build-toc":
            from run_pageindex import build_toc

            if not any([args.pdf_path, args.md_path, args.pdf_dir, args.md_dir]):
                logger.error("[ERROR] Must provide --pdf, --md, --pdf-dir, or --md-dir")
                sys.exit(1)

            add_summary = args.summary == "yes"
            add_text = args.text == "yes"

            if args.pdf_dir:
                pdf_dir = Path(args.pdf_dir)
                pdf_files = sorted(pdf_dir.glob("*.pdf"))
                logger.info(f"[BUILD-TOC] Found {len(pdf_files)} PDF files in {pdf_dir}")

                for pdf_file in pdf_files:
                    try:
                        build_toc(pdf_path=str(pdf_file), add_summary=add_summary, add_text=add_text)
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to build ToC for {pdf_file.name}: {e}")

            elif args.md_dir:
                md_dir = Path(args.md_dir)
                md_files = sorted(md_dir.glob("*.md"))
                logger.info(f"[BUILD-TOC] Found {len(md_files)} markdown files in {md_dir}")

                for md_file in md_files:
                    try:
                        build_toc(md_path=str(md_file), add_summary=add_summary, add_text=add_text)
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to build ToC for {md_file.name}: {e}")

            else:
                build_toc(
                    pdf_path=args.pdf_path,
                    md_path=args.md_path,
                    add_summary=add_summary,
                    add_text=add_text,
                )

        elif args.command == "build-index":
            from toc_index_builder import TocIndexBuilder

            builder = TocIndexBuilder()
            builder.build_and_save()

    except Exception as e:
        logger.error(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
