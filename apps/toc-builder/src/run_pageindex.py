"""
Wrapper for PageIndex ToC building.

Integrates PageIndex with toc-builder settings.
"""

import argparse
import os
import json
from pathlib import Path
from pageindex import *
from pageindex.page_index_md import md_to_tree

from config import settings
from utils.logger import logger


def build_toc(
    pdf_path: str = None,
    md_path: str = None,
    add_summary: bool = False,
    add_text: bool = True,
    model: str = "gpt-5-mini",
) -> Path:
    """
    Build ToC structure from PDF or markdown file.

    Args:
        pdf_path: Path to PDF file (for text PDFs)
        md_path: Path to markdown file
        add_summary: Whether to add node summaries
        add_text: Whether to add node text
        model: LLM model to use

    Returns:
        Path to saved ToC structure file

    Raises:
        ValueError: If neither pdf_path nor md_path provided
        FileNotFoundError: If file not found
    """
    if not pdf_path and not md_path:
        raise ValueError("Either pdf_path or md_path must be provided")

    if pdf_path and md_path:
        raise ValueError("Only one of pdf_path or md_path can be provided")

    # Get document ID
    if pdf_path:
        doc_id = Path(pdf_path).stem
    else:
        doc_id = Path(md_path).stem

    logger.info(f"[TOC-BUILD] Building ToC for: {doc_id}")
    logger.info(f"  Add summary: {add_summary}")
    logger.info(f"  Add text: {add_text}")

    # Output path
    output_file = settings.paths.get_toc_file(doc_id)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Build ToC based on file type
    if pdf_path:
        logger.info("[TOC-BUILD] Building ToC from PDF...")

        # Configure options
        opt = config(
            model=model,
            toc_check_page_num=20,
            max_page_num_each_node=10,
            max_token_num_each_node=20000,
            if_add_node_id="yes",
            if_add_node_summary="yes" if add_summary else "no",
            if_add_doc_description="no",
            if_add_node_text="yes" if add_text else "no",
        )

        # Process the PDF
        toc_structure = page_index_main(pdf_path, opt)

    else:  # md_path
        logger.info("[TOC-BUILD] Building ToC from markdown...")

        import asyncio

        # Process markdown - md_to_tree reads file itself
        toc_structure = asyncio.run(
            md_to_tree(
                md_path=md_path,
                model=model,
                if_add_node_id="yes",
                if_add_node_summary="yes" if add_summary else "no",
                if_add_doc_description="no",
                if_add_node_text="yes" if add_text else "no",
            )
        )

    # Save results
    logger.info(f"[TOC-BUILD] Saving to: {output_file}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(toc_structure, f, ensure_ascii=False, indent=2)

    logger.info(f"[TOC-BUILD] ToC structure saved successfully")

    return output_file

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process PDF or Markdown document and generate structure')
    parser.add_argument('--pdf_path', type=str, help='Path to the PDF file')
    parser.add_argument('--md_path', type=str, help='Path to the Markdown file')

    parser.add_argument('--model', type=str, default='gpt-4o-2024-11-20', help='Model to use')

    parser.add_argument('--toc-check-pages', type=int, default=20, 
                      help='Number of pages to check for table of contents (PDF only)')
    parser.add_argument('--max-pages-per-node', type=int, default=10,
                      help='Maximum number of pages per node (PDF only)')
    parser.add_argument('--max-tokens-per-node', type=int, default=20000,
                      help='Maximum number of tokens per node (PDF only)')

    parser.add_argument('--if-add-node-id', type=str, default='yes',
                      help='Whether to add node id to the node')
    parser.add_argument('--if-add-node-summary', type=str, default='yes',
                      help='Whether to add summary to the node')
    parser.add_argument('--if-add-doc-description', type=str, default='no',
                      help='Whether to add doc description to the doc')
    parser.add_argument('--if-add-node-text', type=str, default='no',
                      help='Whether to add text to the node')
                      
    # Markdown specific arguments
    parser.add_argument('--if-thinning', type=str, default='no',
                      help='Whether to apply tree thinning for markdown (markdown only)')
    parser.add_argument('--thinning-threshold', type=int, default=5000,
                      help='Minimum token threshold for thinning (markdown only)')
    parser.add_argument('--summary-token-threshold', type=int, default=200,
                      help='Token threshold for generating summaries (markdown only)')
    args = parser.parse_args()
    
    # Validate that exactly one file type is specified
    if not args.pdf_path and not args.md_path:
        raise ValueError("Either --pdf_path or --md_path must be specified")
    if args.pdf_path and args.md_path:
        raise ValueError("Only one of --pdf_path or --md_path can be specified")
    
    if args.pdf_path:
        # Validate PDF file
        if not args.pdf_path.lower().endswith('.pdf'):
            raise ValueError("PDF file must have .pdf extension")
        if not os.path.isfile(args.pdf_path):
            raise ValueError(f"PDF file not found: {args.pdf_path}")
            
        # Process PDF file
        # Configure options
        opt = config(
            model=args.model,
            toc_check_page_num=args.toc_check_pages,
            max_page_num_each_node=args.max_pages_per_node,
            max_token_num_each_node=args.max_tokens_per_node,
            if_add_node_id=args.if_add_node_id,
            if_add_node_summary=args.if_add_node_summary,
            if_add_doc_description=args.if_add_doc_description,
            if_add_node_text=args.if_add_node_text
        )

        # Process the PDF
        toc_with_page_number = page_index_main(args.pdf_path, opt)
        print('Parsing done, saving to file...')
        
        # Save results
        pdf_name = os.path.splitext(os.path.basename(args.pdf_path))[0]    
        output_dir = './results'
        output_file = f'{output_dir}/{pdf_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2)
        
        print(f'Tree structure saved to: {output_file}')
            
    elif args.md_path:
        # Validate Markdown file
        if not args.md_path.lower().endswith(('.md', '.markdown')):
            raise ValueError("Markdown file must have .md or .markdown extension")
        if not os.path.isfile(args.md_path):
            raise ValueError(f"Markdown file not found: {args.md_path}")
            
        # Process markdown file
        print('Processing markdown file...')
        
        # Process the markdown
        import asyncio
        
        # Use ConfigLoader to get consistent defaults (matching PDF behavior)
        from pageindex.utils import ConfigLoader
        config_loader = ConfigLoader()
        
        # Create options dict with user args
        user_opt = {
            'model': args.model,
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'if_add_node_id': args.if_add_node_id
        }
        
        # Load config with defaults from config.yaml
        opt = config_loader.load(user_opt)
        
        toc_with_page_number = asyncio.run(md_to_tree(
            md_path=args.md_path,
            if_thinning=args.if_thinning.lower() == 'yes',
            min_token_threshold=args.thinning_threshold,
            if_add_node_summary=opt.if_add_node_summary,
            summary_token_threshold=args.summary_token_threshold,
            model=opt.model,
            if_add_doc_description=opt.if_add_doc_description,
            if_add_node_text=opt.if_add_node_text,
            if_add_node_id=opt.if_add_node_id
        ))
        
        print('Parsing done, saving to file...')
        
        # Save results
        md_name = os.path.splitext(os.path.basename(args.md_path))[0]    
        output_dir = './results'
        output_file = f'{output_dir}/{md_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2, ensure_ascii=False)
        
        print(f'Tree structure saved to: {output_file}')