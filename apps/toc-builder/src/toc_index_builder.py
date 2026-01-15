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

    def _extract_metadata(self, toc_file: Path) -> Dict[str, Any]:
        """
        Extract metadata from ToC structure file.

        Args:
            toc_file: Path to ToC structure JSON file

        Returns:
            Metadata dict with doc_id, doc_name, summary, year
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

            return {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "toc_path": toc_file.name,
                "summary": summary,
                "year": year,
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

    def build_index(self) -> Dict[str, Any]:
        """
        Build ToC index from all ToC structure files.

        Returns:
            Index dict with list of documents and metadata
        """
        logger.info("[TOC-INDEX] Building ToC index...")

        documents = []

        # Find all *_structure.json files in toc_dir
        toc_files = sorted(self.toc_dir.glob("*_structure.json"))

        logger.info(f"[TOC-INDEX] Found {len(toc_files)} ToC files")

        for toc_file in toc_files:
            metadata = self._extract_metadata(toc_file)
            if metadata:
                documents.append(metadata)
                logger.info(
                    f"  - {metadata['doc_id']}: {metadata['doc_name']} ({metadata['year'] or 'no year'})"
                )

        # Create index structure
        index = {
            "total_documents": len(documents),
            "documents": documents,
        }

        logger.info(f"[TOC-INDEX] Total documents indexed: {len(documents)}")

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
