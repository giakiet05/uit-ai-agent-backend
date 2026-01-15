# ToC Builder (utb)

Build table of contents (ToC) from documents for reasoning-based RAG using PageIndex.

## Overview

This service is responsible for:
- **Parse PDFs** (text or scanned) to markdown using LlamaParse
- **Build ToC structures** from PDF or markdown files using PageIndex
- **Create ToC index** (master index file) for multi-document search

## Setup

### 1. Install dependencies

```bash
cd apps/toc-builder
uv sync
```

This will install the `utb` (UIT ToC Builder) command.

### 2. Configure environment

Create `.env` file:

```bash
# OpenAI API (for PageIndex tree building)
OPENAI_API_KEY=your_key_here

# LlamaCloud API (for OCR)
LLAMA_CLOUD_API_KEY=your_key_here
```

## Usage

### Parse PDF to markdown

Parse PDF (text or scanned) to markdown using LlamaParse:

```bash
# Parse and auto-save to data/markdown/{category}/
utb parse <pdf_path> --category regulation

# Parse and save to custom path
utb parse <pdf_path> --category curriculum --output /path/to/output.md
```

**Example:**
```bash
utb parse ../../data/raw/regulation/828.pdf --category regulation
```

### Build ToC from PDF (text PDF)

```bash
# Build ToC with default settings (no summary, with text - optimal for reasoning-based RAG)
utb build-toc --pdf <pdf_path> --category regulation

# Build ToC with summary and text
utb build-toc --pdf <pdf_path> --category regulation --summary yes

# Build ToC without text (only structure + summary)
utb build-toc --pdf <pdf_path> --category curriculum --text no --summary yes
```

**Example:**
```bash
# Default (recommended)
utb build-toc --pdf ../../data/raw/regulation/790.pdf --category regulation

# With summary
utb build-toc --pdf ../../data/raw/regulation/790.pdf --category regulation --summary yes
```

### Build ToC from markdown

```bash
# Build ToC from markdown with default settings (no summary, with text)
utb build-toc --md <md_path> --category regulation

# Build ToC with summary
utb build-toc --md <md_path> --category curriculum --summary yes

# Build ToC without text
utb build-toc --md <md_path> --category regulation --text no
```

**Example:**
```bash
# Default (recommended)
utb build-toc --md ../../data/markdown/regulation/828.md --category regulation

# With summary
utb build-toc --md ../../data/markdown/regulation/828.md --category regulation --summary yes
```

### Build ToC index

After building ToC for all documents, create the master index:

```bash
utb build-index
```

This scans all `data/toc/` files and creates `data/toc/toc_index.json` with metadata.

## Workflow

### Option 1: Parse PDF to markdown first (recommended for scanned PDFs or complex layouts)
1. Parse to markdown: `utb parse <pdf> --category regulation`
2. Build ToC: `utb build-toc --md <md> --category regulation`
3. Build index: `utb build-index`

### Option 2: Build ToC directly from PDF (faster for simple text PDFs)
1. Build ToC directly: `utb build-toc --pdf <pdf> --category regulation`
2. Build index: `utb build-index`

### Option 3: Use existing markdown (e.g., from LlamaParse in knowledge-builder)
1. Build ToC: `utb build-toc --md <md> --category curriculum`
2. Build index: `utb build-index`

## Output Structure

```
data/
├── markdown/          # LlamaParse output
│   ├── regulation/
│   │   └── 828.md
│   └── curriculum/
│       └── ktpm-2025.md
└── toc/               # ToC structures
    ├── regulation/
    │   ├── 790_structure.json
    │   └── 828_structure.json
    ├── curriculum/
    │   └── ktpm-2025_structure.json
    └── toc_index.json  # Master index
```

### ToC Index Format

```json
{
  "total_documents": 3,
  "documents": [
    {
      "doc_id": "790",
      "doc_name": "Quy chế đào tạo ĐHCNTT 2022",
      "category": "regulation",
      "toc_path": "regulation/790_structure.json",
      "summary": "Chương I: Quy định chung | Chương II: Điều kiện tốt nghiệp",
      "year": 2022,
      "keywords": ["đào tạo", "tốt nghiệp", "quy chế", ...]
    },
    ...
  ]
}
```

## Configuration

### Command-line Arguments

**build-toc command:**
- `--summary yes|no`: Add LLM-generated summaries to nodes (default: **no**)
  - `no`: Optimal for reasoning-based RAG (saves tokens during search)
  - `yes`: Useful if you want summaries for each node
- `--text yes|no`: Include full text in nodes (default: **yes**)
  - `yes`: Required for answer generation (provides context)
  - `no`: Only structure, no text (smaller file size)

**Recommended settings:**
- For reasoning-based RAG: `--summary no --text yes` (default)
- For exploration only: `--summary yes --text no`

### Environment Variables

Key settings in `src/config/settings.py` (can be overridden in `.env`):

- `ADD_NODE_SUMMARY`: Default for summary (default: no)
- `ADD_NODE_TEXT`: Default for text (default: yes)
- `PARSE_MODE`: LlamaParse mode (default: "parse_page_with_agent")
- `PARSE_MODEL`: LLM model for parsing (default: "openai-gpt-4-1-mini")
- `LLM_MODEL`: LLM model for tree building (default: "gpt-5-mini")

Example `.env`:
```bash
# Override defaults
ADD_NODE_SUMMARY=yes
ADD_NODE_TEXT=yes
LLM_MODEL=gpt-5-mini
PARSE_MODEL=openai-gpt-4-1-mini
```

## Notes

- **Text vs Summary**:
  - For search: Remove text from ToC (saves tokens)
  - For answer generation: Use full text from selected nodes
  - Default: text=yes, summary=no (optimal for reasoning-based RAG)

- **LlamaParse**: Supports both text PDFs and scanned PDFs with high-quality extraction

- **Markdown vs PDF**:
  - PDF: Natural page-based chunking
  - Markdown: Header-based chunking (may have too many levels if over-structured)
  - For complex layouts or scanned PDFs, parse to markdown first gives better ToC quality

## Development

Structure:
```
apps/toc-builder/
├── main.py                    # CLI entry point
├── src/
│   ├── config/
│   │   └── settings.py        # Configuration
│   ├── llamaparse_ocr.py      # LlamaParse OCR wrapper
│   ├── toc_index_builder.py   # Master index builder
│   ├── run_pageindex.py       # PageIndex wrapper
│   ├── pageindex/             # PageIndex package (copied from experiments)
│   └── utils/
│       └── logger.py
├── pyproject.toml             # uv config
└── README.md
```
