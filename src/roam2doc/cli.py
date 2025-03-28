import sys
import argparse
from pathlib import Path
import logging
from roam2doc.io import parse_fileset, parse_one_file, parse_directory, parse_from_filelist 
from roam2doc.setup_logging import setup_logging

logger = logging.getLogger('roam2doc-cli')

def setup_parser():
    """Set up the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Convert org-roam files to HTML documents.",
        epilog="Examples: python roam2doc_cli.py input.org -o output.html --overwrite"
    )
    parser.add_argument(
        "input",
        type=str,
        help="Input file (.org), directory containing .org files, or file list with paths"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output file path for HTML (default: print to stdout)"
    )
    parser.add_argument(
        "-l", "--logging",
        choices=['error', 'warning', 'info', 'debug'],
        default='error',
        help="Enable logging at provided level, has no effect if output goes to stdout",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing output file (default: False)"
    )
    return parser

def process_input(input_path, output_path=None, allow_overwrite=False, logging_level=None):
    """Process the input and generate HTML output."""

    # ensure output request (if any) makes sense before parsing
    if output_path:
        output_path = Path(output_path)
        if output_path.exists() and not allow_overwrite:
            logger.error(f"Refusing to overwrite existing file {output_path}")
            raise SystemExit(1)
        if not output_path.parent.exists():
            logger.error(f"Output directory {output_path.parent} does not exist")
            raise SystemExit(1)
    else:
        if logging_level:
            setup_logging(default_level=logging_level)

    input_path = Path(input_path)
    
    # Determine input type and parse accordingly
    if input_path.is_dir():
        parsers = parse_directory(input_path)
    elif input_path.suffix == '.org':
        parser = parse_one_file(input_path)
        parsers = [parser,]
    else:
        parsers = parse_from_filelist(input_path)

    root = parsers[0].root

    # Handle output
    html_output = root.to_html()
    if output_path:
        with open(output_path, 'w', encoding="utf-8") as f:
            f.write(html_output)
        logger.info(f"HTML written to {output_path}")
    else:
        print(html_output)

    return parsers
    
def main():
    """Main entry point for the CLI."""

    
    # Parse arguments
    parser = setup_parser()
    args = parser.parse_args()

    # Process the input and output
    try:
        parsers = process_input(args.input, args.output, args.overwrite, args.logging)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise SystemExit(1)
    return parsers # for testing

if __name__ == "__main__":
    main()
