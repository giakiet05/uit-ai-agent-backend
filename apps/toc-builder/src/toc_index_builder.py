"""
Build ToC index from all ToC structure files.

Scan all ToC files and create a master index (toc_index.json) with metadata
for multi-document reasoning-based RAG.
"""

import json
from pathlib import Path
from typing import Dict, List, Any

from config import settings
from utils.logger import logger


class TocIndexBuilder:
    """Build master ToC index from all ToC structure files."""

    def __init__(self):
        """Initialize ToC index builder."""
        self.toc_dir = settings.paths.TOC_DIR
        self.index_file = settings.paths.TOC_INDEX_FILE
        self.raw_dir = settings.paths.DATA_DIR / "raw"

    def _detect_doc_type(self, doc_id: str) -> tuple[str, str | None]:
        """
        Detect document type based on raw file location.

        Args:
            doc_id: Document ID

        Returns:
            Tuple of (doc_type, source_url)
            - doc_type: "regulation" | "curriculum"
            - source_url: URL string for curriculum, None for regulation
        """
        # Check if PDF exists in regulation folder
        regulation_pdf = self.raw_dir / "regulation" / f"{doc_id}.pdf"
        if regulation_pdf.exists():
            return ("regulation", None)

        # Check if MD exists in curriculum folder
        curriculum_md = self.raw_dir / "curriculum" / f"{doc_id}.md"
        if curriculum_md.exists():
            # TODO: Map doc_id to actual UIT curriculum URL
            # For now, return None - will be filled manually later
            return ("curriculum", None)

        # Default to regulation if file not found
        logger.warning(f"[DETECT] Could not find raw file for {doc_id}, defaulting to regulation")
        return ("regulation", None)

    def _extract_metadata(self, toc_file: Path) -> Dict[str, Any]:
        """
        Extract metadata from ToC structure file.

        Args:
            toc_file: Path to ToC structure JSON file

        Returns:
            Metadata dict with doc_id, doc_name, summary, year, doc_type, source_url
        """
        try:
            with open(toc_file, "r", encoding="utf-8") as f:
                toc_data = json.load(f)

            # Get doc_name from structure (or fallback to filename)
            doc_name = toc_data.get("doc_name", toc_file.stem.replace("_structure", ""))

            # Get top-level summary (first level of tree)
            summary = self._get_doc_summary(toc_data.get("structure", {}))

            # Extract year and date from doc_name
            year = self._extract_year(doc_name)
            date_str = self._extract_date(doc_name)

            # Append date to summary if found
            if date_str:
                summary = f"{summary} ({date_str})"

            # Get doc_id from filename (remove _structure.json)
            doc_id = toc_file.stem.replace("_structure", "")

            # Detect doc_type based on raw file location
            doc_type, source_url = self._detect_doc_type(doc_id)

            return {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "toc_path": toc_file.name,
                "summary": summary,
                "year": year,
                "doc_type": doc_type,
                "source_url": source_url,
            }

        except Exception as e:
            logger.error(f"[ERROR] Failed to extract metadata from {toc_file.name}: {e}")
            return None

    def _get_doc_summary(self, structure: Dict | List) -> str:
        """
        Get document summary from top-level tree nodes.

        Args:
            structure: Tree structure (dict or list of nodes)

        Returns:
            Summary text (concatenated top-level titles)
        """
        summaries = []

        if isinstance(structure, dict):
            # Single root node
            if "title" in structure:
                summaries.append(structure["title"])
            # Get first-level children summaries
            if "nodes" in structure and structure["nodes"]:
                for node in structure["nodes"][:3]:  # Top 3 children
                    if isinstance(node, dict) and "title" in node:
                        summaries.append(node["title"])

        elif isinstance(structure, list):
            # Multiple root nodes
            for node in structure[:5]:  # Top 5 nodes
                if isinstance(node, dict) and "title" in node:
                    summaries.append(node["title"])

        return " | ".join(summaries)

    def _extract_year(self, text: str) -> int | None:
        """
        Extract year from text (doc_name).

        Args:
            text: Text to search for year

        Returns:
            Year as integer, or None if not found
        """
        import re

        # Look for 4-digit year (2020-2030)
        pattern = r"20[2-3]\d"
        match = re.search(pattern, text)

        if match:
            return int(match.group())

        return None

    def _extract_date(self, text: str) -> str | None:
        """
        Extract date (dd/mm/yyyy) from text.

        Args:
            text: Text to search for date (usually doc_name)

        Returns:
            Date string in dd/mm/yyyy format, or None if not found
        """
        import re

        # Pattern: day-month-year (e.g., 08-03-2022, 5-6-2024, 28-9-22)
        pattern = r"(\d{1,2})-(\d{1,2})-(\d{2,4})"
        match = re.search(pattern, text)

        if match:
            day = match.group(1).zfill(2)
            month = match.group(2).zfill(2)
            year = match.group(3)
            if len(year) == 2:
                year = f"20{year}"
            return f"{day}/{month}/{year}"

        return None

    def _load_existing_index(self) -> Dict[str, Any]:
        """
        Load existing toc_index.json if exists.

        Returns:
            Existing index dict, or empty index if not found
        """
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    existing_index = json.load(f)
                logger.info(f"[TOC-INDEX] Loaded existing index with {existing_index.get('total_documents', 0)} documents")
                return existing_index
            except Exception as e:
                logger.warning(f"[TOC-INDEX] Failed to load existing index: {e}. Starting fresh.")
        
        return {"total_documents": 0, "documents": []}

    def build_index(self) -> Dict[str, Any]:
        """
        Build ToC index from all ToC structure files.
        
        Merges with existing index:
        - Preserves existing documents (keeps hand-written summaries)
        - Only adds NEW documents (not yet in index)

        Returns:
            Index dict with list of documents and metadata
        """
        logger.info("[TOC-INDEX] Building ToC index...")

        # Load existing index
        existing_index = self._load_existing_index()
        existing_docs = {doc["doc_id"]: doc for doc in existing_index.get("documents", [])}

        # Find all *_structure.json files in toc_dir
        toc_files = sorted(self.toc_dir.glob("*_structure.json"))

        logger.info(f"[TOC-INDEX] Found {len(toc_files)} ToC files")

        new_count = 0
        kept_count = 0

        for toc_file in toc_files:
            metadata = self._extract_metadata(toc_file)
            if not metadata:
                continue
            
            doc_id = metadata["doc_id"]
            
            # Check if document already exists in index
            if doc_id in existing_docs:
                # Keep existing entry (preserves hand-written summary)
                logger.info(f"  ✓ {doc_id}: KEPT existing entry")
                kept_count += 1
            else:
                # Add new document
                existing_docs[doc_id] = metadata
                logger.info(f"  + {doc_id}: ADDED new entry - {metadata['doc_name']} ({metadata['year'] or 'no year'})")
                new_count += 1

        # Convert back to list
        documents = list(existing_docs.values())

        # Create index structure
        index = {
            "total_documents": len(documents),
            "documents": documents,
        }

        logger.info(f"[TOC-INDEX] Summary: {kept_count} kept, {new_count} added, {len(documents)} total")

        return index

    def save_index(self, index: Dict[str, Any]) -> None:
        """
        Save index to toc_index.json.

        Args:
            index: Index dict to save
        """
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        logger.info(f"[TOC-INDEX] Index saved to: {self.index_file}")

    def build_and_save(self) -> Dict[str, Any]:
        """
        Build and save ToC index.

        Returns:
            Index dict
        """
        index = self.build_index()
        self.save_index(index)
        return index


def main():
    """
    CLI interface for ToC index builder.

    Usage:
        python -m src.toc_index_builder
    """
    builder = TocIndexBuilder()

    try:
        index = builder.build_and_save()

        logger.info("[SUCCESS] ToC index built successfully!")
        logger.info(f"  Total documents: {index['total_documents']}")

    except Exception as e:
        logger.error(f"[ERROR] Failed to build ToC index: {e}")
        raise


if __name__ == "__main__":
    main()
