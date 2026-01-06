#!/usr/bin/env python3
"""
Odoo Log Analyser
A lightweight, dependency-free performance analysis tool for Odoo server logs.
Compatible with Odoo 16.0, 17.0, 18.0, 19.0, 20.0+ and Python 3.8+.
"""

import argparse
import datetime
import os
import re
import sys
from collections import defaultdict
from logging import getLogger
from operator import itemgetter

_logger = getLogger("odoo_log_analyser")

# Python 3.8 - 3.13 compatibility for logging level names
try:
    from logging import getLevelNamesMapping
    _LEVEL_MAPPING = getLevelNamesMapping()
except ImportError:
    import logging
    _LEVEL_MAPPING = {
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.FATAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "WARN": logging.WARN,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }

LOG_LEVELS = tuple(_LEVEL_MAPPING.keys())
REQUEST_KEY = "REQUEST"

__version__ = "1.0.0"
__author__ = "ameerweb"


# Regular expressions for robust line parsing
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:[,.]\d+)?")
_HTTP_REQUEST_RE = re.compile(r'"([A-Z]+)\s+([^\s"]+)\s+HTTP/[0-9.]+"\s+(\d{3})')
_LANG_PREFIX_RE = re.compile(r"^/[a-z]{2}(?:_[A-Za-z0-9]+)?/")


def clean_endpoint(endpoint: str) -> str:
    """Strip website language prefixes (e.g. /en_US/, /ar_001/, /fr/) for unified stats."""
    return _LANG_PREFIX_RE.sub("/", endpoint)


def read_log(
    logfile: str,
    threshold: float = 2.0,
    severity: int = None,
    ignore_no_db: bool = True,
    target_db: str = None,
):
    """
    Read and parse Odoo log file.

    :param logfile: Path to the log file
    :param threshold: Minimum request execution time in seconds to capture (0 disables request capture)
    :param severity: Minimum logging severity for non-request logs (None disables non-request capture)
    :param ignore_no_db: Ignore logs where database is '?'
    :param target_db: Filter logs for a specific database name
    :return: dict of lists of log entry dicts
    """
    if not threshold and severity is None:
        return {}

    threshold = threshold or 0.0
    if severity is None:
        severity = 1 + max(_LEVEL_MAPPING.values())

    log = defaultdict(list)
    current_line = {}

    file_size = os.path.getsize(logfile) if os.path.exists(logfile) else 0

    with open(logfile, "r", encoding="utf-8", errors="replace") as log_file:
        pos = 0
        for line in log_file:
            pos += len(line)

            if _logger.isEnabledFor(_LEVEL_MAPPING["DEBUG"]):
                if file_size and pos % 50000 < len(line):
                    pct = min(100, int(100 * pos / file_size))
                    sys.stderr.write(f"\rProgress: {pct}%")
                    sys.stderr.flush()

            # Check if line starts with standard date format YYYY-MM-DD
            if _TIMESTAMP_RE.match(line) and any(f" {ll} " in line[:45] for ll in LOG_LEVELS):
                # Flush previous entry
                if current_line:
                    log[current_line["level"]].append(current_line)
                current_line = {}

                fragments = line.split()
                if len(fragments) < 6:
                    continue

                level = fragments[3]
                db = fragments[4]
                logger_name = fragments[5].rstrip(":")

                # Database filtering
                if ignore_no_db and db == "?":
                    continue
                if target_db and db != target_db:
                    continue

                # Process HTTP Werkzeug requests
                if logger_name == "werkzeug" and level == "INFO":
                    if threshold <= 0:
                        continue

                    # Extract query_count, sql_time, other_time safely from line tail
                    try:
                        other_time = float(fragments[-1])
                        sql_time = float(fragments[-2])
                        query_count = int(fragments[-3])
                        total_time = round(sql_time + other_time, 3)
                    except (ValueError, IndexError):
                        # Line without performance numbers (static assets, polling, etc.)
                        continue

                    if total_time < threshold:
                        continue

                    # Parse HTTP details (Method, Endpoint, Status Code)
                    http_match = _HTTP_REQUEST_RE.search(line)
                    if http_match:
                        method = http_match.group(1)
                        endpoint = http_match.group(2)
                        status = http_match.group(3)
                    else:
                        method = fragments[11].lstrip('"') if len(fragments) > 11 else "GET"
                        endpoint = fragments[12] if len(fragments) > 12 else "/"
                        status = fragments[14] if len(fragments) > 14 else "200"

                    current_line["ip"] = fragments[6] if len(fragments) > 6 else "-"
                    current_line["method"] = method
                    current_line["endpoint"] = endpoint
                    current_line["status"] = status
                    current_line["other_time"] = other_time
                    current_line["sql_time"] = sql_time
                    current_line["total_time"] = total_time
                    current_line["query_count"] = query_count
                    current_line["level"] = REQUEST_KEY

                else:
                    # Non-request system log
                    if _LEVEL_MAPPING.get(level, 0) < severity:
                        continue
                    current_line["message"] = " ".join(fragments[6:])
                    current_line["context"] = []

                # Common metadata
                date_str = fragments[0]
                time_str = fragments[1].split(".")[0].split(",")[0]
                try:
                    current_line["timestamp"] = datetime.datetime.strptime(
                        f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    current_line["timestamp"] = None

                try:
                    current_line["pid"] = int(fragments[2])
                except ValueError:
                    current_line["pid"] = 0

                current_line.setdefault("level", level)
                current_line["db"] = db
                current_line["logger"] = logger_name

            else:
                # Continuation / Traceback line
                if "context" in current_line:
                    current_line["context"].append(line)

        # Flush final entry
        if current_line:
            log[current_line["level"]].append(current_line)

    if _logger.isEnabledFor(_LEVEL_MAPPING["DEBUG"]):
        sys.stderr.write("\rProgress: 100%\n")
        sys.stderr.flush()

    return log


def _print_formatted_table(title: str, headers: list, rows: list):
    """Print an aligned, professional ASCII table."""
    if not rows:
        return

    # Calculate column widths based on headers and data
    num_cols = len(headers)
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(val)))

    table_width = sum(col_widths) + (3 * num_cols) + 1

    print("=" * table_width)
    print(f"| {title:^{table_width - 4}} |")
    print("=" * table_width)

    # Header row
    header_str = "| " + " | ".join(f"{str(h):<{col_widths[i]}}" for i, h in enumerate(headers)) + " |"
    print(header_str)
    print("-" * table_width)

    # Data rows
    for row in rows:
        row_str = "| " + " | ".join(
            f"{str(val):>{col_widths[i]}}" if isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('.', '', 1).isdigit())
            else f"{str(val):<{col_widths[i]}}"
            for i, val in enumerate(row)
        ) + " |"
        print(row_str)

    print("-" * table_width)
    print()


def display_results(logs: dict, top_n: int = 10, show_requests: bool = True):
    """Format and print log analysis metrics."""
    # Summary of log levels
    print("\n--- Log Summary Counts ---")
    for level, entries in sorted(logs.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {level:<10}: {len(entries)}")
    print()

    if not show_requests or REQUEST_KEY not in logs or not logs[REQUEST_KEY]:
        return

    requests = logs[REQUEST_KEY]

    # 1. Top Slow Individual Requests (with SQL vs Python breakdown and Queries)
    sorted_requests = sorted(requests, key=itemgetter("total_time"), reverse=True)[:top_n]
    headers = ["Endpoint", "Total (s)", "SQL (s)", "Python (s)", "Queries", "DB"]
    rows = [
        [
            r["endpoint"],
            f"{r['total_time']:.3f}",
            f"{r['sql_time']:.3f}",
            f"{r['other_time']:.3f}",
            r["query_count"],
            r["db"],
        ]
        for r in sorted_requests
    ]
    _print_formatted_table(f"Top {min(top_n, len(rows))} Slowest Requests", headers, rows)

    # Aggregate by cleaned endpoint (stripping /en_US/, /ar/, etc.)
    ep_hits = defaultdict(int)
    ep_total_time = defaultdict(float)
    ep_sql_time = defaultdict(float)

    for r in requests:
        ep = clean_endpoint(r["endpoint"])
        ep_hits[ep] += 1
        ep_total_time[ep] += r["total_time"]
        ep_sql_time[ep] += r["sql_time"]

    # 2. Top Slow Endpoints (by Average Response Time)
    slowest_endpoints = sorted(
        ep_total_time.keys(),
        key=lambda ep: ep_total_time[ep] / ep_hits[ep],
        reverse=True,
    )[:top_n]

    headers_slow = ["Endpoint", "Avg Total (s)", "Avg SQL (s)", "Hits"]
    rows_slow = [
        [
            ep,
            f"{(ep_total_time[ep] / ep_hits[ep]):.3f}",
            f"{(ep_sql_time[ep] / ep_hits[ep]):.3f}",
            ep_hits[ep],
        ]
        for ep in slowest_endpoints
    ]
    _print_formatted_table(f"Top {min(top_n, len(rows_slow))} Slowest Endpoints (Average)", headers_slow, rows_slow)

    # 3. Top Most Hit Endpoints (among requests exceeding the threshold)
    most_hit_endpoints = sorted(
        ep_hits.keys(),
        key=lambda ep: ep_hits[ep],
        reverse=True,
    )[:top_n]

    headers_hit = ["Endpoint", "Hits", "Avg Total (s)", "Avg SQL (s)"]
    rows_hit = [
        [
            ep,
            ep_hits[ep],
            f"{(ep_total_time[ep] / ep_hits[ep]):.3f}",
            f"{(ep_sql_time[ep] / ep_hits[ep]):.3f}",
        ]
        for ep in most_hit_endpoints
    ]
    _print_formatted_table(f"Top {min(top_n, len(rows_hit))} Most Hit Slow Endpoints", headers_hit, rows_hit)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build a user-friendly and backward-compatible argument parser."""
    parser = argparse.ArgumentParser(
        prog="odoo_log_analyser",
        description="Analyze Odoo server logs for performance bottlenecks, slow queries, and errors (Odoo 16-20+).",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Required file argument
    parser.add_argument(
        "logfile",
        type=str,
        help="Path to the Odoo log file (e.g. /var/log/odoo/odoo-server.log)",
    )

    # Performance Threshold (User-friendly + Backwards compatible)
    parser.add_argument(
        "-t",
        "--min-seconds",
        "--threshold",
        dest="threshold",
        type=float,
        default=2.0,
        help="Minimum request time in seconds to analyze (default: 2.0s).\n"
             "Examples: -t 1.5, -t 5, --min-seconds 0.8",
    )

    # Mode: Requests only vs Errors only
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "-r",
        "--requests-only",
        "--just-requests",
        dest="requests_only",
        action="store_true",
        help="Analyze HTTP requests and performance only (skip general logs/errors).",
    )
    mode_group.add_argument(
        "-e",
        "-R",
        "--errors-only",
        "--no-requests",
        dest="errors_only",
        action="store_true",
        help="Analyze system errors and warnings only (skip HTTP requests).",
    )

    # Logging Severity Level
    parser.add_argument(
        "-l",
        "-s",
        "--level",
        "--severity",
        dest="severity",
        choices=LOG_LEVELS,
        default="INFO",
        help="Minimum log severity for system events (default: INFO).\n"
             "Options: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    # Number of rows to display
    parser.add_argument(
        "-n",
        "--top",
        "--limit",
        dest="top_n",
        type=int,
        default=10,
        help="Number of items to show in ranking tables (default: 10).",
    )

    # Database filter
    parser.add_argument(
        "-d",
        "--database",
        "--db",
        dest="target_db",
        type=str,
        default=None,
        help="Filter logs for a specific database name in multi-tenant environments.",
    )

    # Database filtering: include logs with db = '?'
    parser.add_argument(
        "-a",
        "-i",
        "--all-dbs",
        "--include-no-db",
        dest="include_no_db",
        action="store_true",
        help="Include logs where database is undefined ('?') like startup or health checks.",
    )

    # Verbosity & Output
    parser.add_argument(
        "-v",
        "--verbose",
        "--vervose",
        dest="verbose",
        action="store_true",
        help="Show detailed progress bar and debug information.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Quiet mode: suppress progress updates.",
    )

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.verbose:
        _logger.setLevel("DEBUG")
    elif args.quiet:
        _logger.setLevel("WARNING")

    # Resolve threshold and severity based on mode
    threshold = 0.0 if args.errors_only else args.threshold
    severity = None if args.requests_only else _LEVEL_MAPPING.get(args.severity, 1000)

    try:
        logs = read_log(
            logfile=args.logfile,
            threshold=threshold,
            severity=severity,
            ignore_no_db=not args.include_no_db,
            target_db=args.target_db,
        )
    except FileNotFoundError:
        sys.stderr.write(f"Error: Log file not found: '{args.logfile}'\n")
        sys.exit(1)
    except Exception as exc:
        sys.stderr.write(f"Error reading log file: {exc}\n")
        sys.exit(1)

    display_results(
        logs=logs,
        top_n=args.top_n,
        show_requests=not args.errors_only,
    )


if __name__ == "__main__":
    main()
