"""
Load ToC structures from data/toc/ folder.

Provides access to:
- toc_index.json: Master index with document metadata
- Individual ToC structure files: Hierarchical document structures
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..config.settings import settings


class TocLoader:
    """Load and manage ToC structures for reasoning-based retrieval."""

    def __init__(self):
        """Initialize ToC loader."""
        self.toc_dir = settings.paths.DATA_DIR / "toc"
        self.index_file = self.toc_dir / "toc_index.json"

        self._index_cache: Optional[Dict[str, Any]] = None
        self._toc_cache: Dict[str, Dict[str, Any]] = {}

    def get_index(self) -> Dict[str, Any]:
        """
        Get master ToC index with all document metadata.

        Returns:
            Index dict with total_documents and documents list
        """
        if self._index_cache is not None:
            return self._index_cache

        if not self.index_file.exists():
            raise FileNotFoundError(f"ToC index not found: {self.index_file}")

        with open(self.index_file, "r", encoding="utf-8") as f:
            self._index_cache = json.load(f)

        return self._index_cache

    def get_index_for_llm(self) -> str:
        """
        Get index formatted for LLM document selection.

        Returns only essential metadata (no keywords, minimal info).

        Returns:
            Formatted string for LLM prompt
        """
        index = self.get_index()

        lines = []
        for doc in index["documents"]:
            line = f"- {doc['doc_id']}: {doc['doc_name']}"
            if doc.get("year"):
                line += f" ({doc['year']})"
            if doc.get("summary"):
                line += f" - {doc['summary'][:100]}"
            lines.append(line)

        return "\n".join(lines)

    def get_toc_structure(self, doc_id: str) -> Dict[str, Any]:
        """
        Get ToC structure for a specific document.

        Args:
            doc_id: Document ID (filename without _structure.json)

        Returns:
            ToC structure dict with doc_name and structure tree
        """
        if doc_id in self._toc_cache:
            return self._toc_cache[doc_id]

        toc_file = self.toc_dir / f"{doc_id}_structure.json"

        if not toc_file.exists():
            raise FileNotFoundError(f"ToC structure not found: {toc_file}")

        with open(toc_file, "r", encoding="utf-8") as f:
            toc_data = json.load(f)

        self._toc_cache[doc_id] = toc_data
        return toc_data

    def get_toc_for_llm(self, doc_id: str, include_text: bool = False) -> str:
        """
        Get ToC structure formatted for LLM node selection.

        Args:
            doc_id: Document ID
            include_text: Whether to include node text (default: False for selection phase)

        Returns:
            Formatted string showing hierarchical structure
        """
        toc_data = self.get_toc_structure(doc_id)
        structure = toc_data.get("structure", [])

        lines = [f"Document: {toc_data.get('doc_name', doc_id)}"]
        lines.append("")

        self._format_structure(structure, lines, depth=0, include_text=include_text)

        return "\n".join(lines)

    def _format_structure(
        self,
        structure: List[Dict[str, Any]] | Dict[str, Any],
        lines: List[str],
        depth: int = 0,
        include_text: bool = False
    ):
        """Format structure (list or dict) for LLM display."""
        if isinstance(structure, list):
            for node in structure:
                self._format_node(node, lines, depth, include_text)
        else:
            self._format_node(structure, lines, depth, include_text)

    def _format_node(
        self,
        node: Dict[str, Any],
        lines: List[str],
        depth: int = 0,
        include_text: bool = False
    ):
        """Recursively format single node for LLM display."""
        indent = "  " * depth

        node_id = node.get("node_id", "")
        title = node.get("title", "Untitled")

        line = f"{indent}[{node_id}] {title}"

        if node.get("summary"):
            line += f" - {node['summary'][:80]}"

        lines.append(line)

        if include_text and node.get("text"):
            text_preview = node["text"][:200] + "..." if len(node.get("text", "")) > 200 else node.get("text", "")
            lines.append(f"{indent}    Text: {text_preview}")

        for child in node.get("nodes", []):
            self._format_node(child, lines, depth + 1, include_text)

    def get_node_text(self, doc_id: str, node_ids: List[str]) -> Dict[str, str]:
        """
        Get text content for specific nodes.

        Args:
            doc_id: Document ID
            node_ids: List of node IDs to retrieve text for

        Returns:
            Dict mapping node_id to text content
        """
        toc_data = self.get_toc_structure(doc_id)
        structure = toc_data.get("structure", [])

        result = {}
        self._collect_from_structure(structure, node_ids, result)

        return result

    def _collect_from_structure(
        self,
        structure: List[Dict[str, Any]] | Dict[str, Any],
        target_ids: List[str],
        result: Dict[str, str]
    ):
        """Collect text from structure (list or dict)."""
        if isinstance(structure, list):
            for node in structure:
                self._collect_node_text(node, target_ids, result)
        else:
            self._collect_node_text(structure, target_ids, result)

    def _collect_node_text(
        self,
        node: Dict[str, Any],
        target_ids: List[str],
        result: Dict[str, str]
    ):
        """Recursively collect text from target nodes."""
        node_id = node.get("node_id", "")

        if node_id in target_ids:
            result[node_id] = node.get("text", "")

        for child in node.get("nodes", []):
            self._collect_node_text(child, target_ids, result)

    def get_all_doc_ids(self) -> List[str]:
        """Get list of all available document IDs."""
        index = self.get_index()
        return [doc["doc_id"] for doc in index["documents"]]
