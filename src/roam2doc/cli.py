#!/usr/bin/env python
import sys
import json
import argparse
from pathlib import Path
import subprocess
from subprocess import Popen
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
        "-t", "--doc_type",
        choices=['html', 'json', 'latex'],
        default='html',
        help="Output file path for HTML (default: html)"
    )
    parser.add_argument(
        "-j", "--include_json",
        action="store_true",
        help="Include a json version of the parsed document tree in the html head section",
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
    res = check_for_converter()
    if res:
        help = "Use wkhtmltopdf to convert output to PDF"
        if "patched" not in res:
            help += " (Links and Table of Contents Unavailable)"
        parser.add_argument(
            "--wk_pdf",
            action="store_true",
            help=help
        )
    
    return parser

def check_for_converter(): # pragma: no cover
    try:
        x = Popen(['wkhtmltopdf', '-V'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return False
    res,error = x.communicate()
    if error:
        return False
    return str(res)
    
def convert_to_pdf(tmpf, target_path):

    cs = check_for_converter()
    if "patched" in cs:
        command = ['wkhtmltopdf',
               'toc',
               '--xsl-style-sheet',
               str(xsl_path),
               '--enable-internal-links',
               '--enable-local-file-access',
               tmpf,
               str(target_path)]
    else:
        command = ['wkhtmltopdf',
                   '--enable-local-file-access',
                   tmpf,
                   str(target_path)]
    xsl_path = Path(Path(__file__).parent.resolve(), "default2.xsl")
    x = Popen(command)
    res,error = x.communicate()
    
    
def process_input(args):
    """Process the input and generate HTML output."""

    # ensure output request (if any) makes sense before parsing
    output_path = None
    if args.output:
        output_path = Path(args.output)
        if output_path.exists() and not args.overwrite:
            logger.error(f"Refusing to overwrite existing file {output_path}")
            raise SystemExit(1)
        if not output_path.parent.exists():
            logger.error(f"Output directory {output_path.parent} does not exist")
            raise SystemExit(1)
        if args.logging:
            setup_logging(default_level=args.logging)


    input_path = Path(args.input)
    
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
    if args.doc_type == "html":
        output_text = root.to_html(include_json=args.include_json)
    elif args.doc_type == "latex":
        output_text = root.to_latex()
    elif args.doc_type == "json":
        output_text = json.dumps(root.to_json_dict(), indent=2)
    if output_path:
        if args.wk_pdf:
            tmp_path = Path(str(output_path) + ".html")
            with open(tmp_path, 'w', encoding="utf-8") as f:
                f.write(output_text)
            convert_to_pdf(tmp_path, output_path)
            tmp_path.unlink()
            return parsers
        with open(output_path, 'w', encoding="utf-8") as f:
            f.write(output_text)
        if args.doc_type == "html":
            logger.info(f"HTML written to {output_path}")
        elif args.doc_type == "json":
            logger.info(f"JSON written to {output_path}")
    else:
        print(output_text)

    return parsers
    
def main():
    """Main entry point for the CLI."""

    
    # Parse arguments
    parser = setup_parser()
    args = parser.parse_args()

    # Process the input and output
    try:
        parsers = process_input(args)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise SystemExit(1)
    return parsers # for testing

if __name__ == "__main__":
    main()
