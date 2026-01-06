# Odoo Log Analyser

A fast, lightweight, dependency-free CLI tool for analyzing Odoo server logs, identifying performance bottlenecks, tracking slow HTTP requests, and debugging system errors.

Compatible with **Odoo 16.0, 17.0, 18.0, 19.0, 20.0+** and **Python 3.8+**.

---

## Features

- **Zero Dependencies:** Pure Python standard library. No external packages needed.
- **Instant Bottleneck Identification:** Pinpoints individual slow requests and endpoints.
- **SQL vs. Python Breakdown:** Separates database query execution time from application server time.
- **Query Count Tracking:** Detects high-volume ORM queries and N+1 query patterns.
- **URL Normalization:** Automatically strips frontend language codes (e.g. `/ar/`, `/en_US/`) to aggregate eCommerce and website traffic accurately.
- **Multi-Tenant Support:** Filter logs by specific database names (`--db`).
- **Clean Formatted Tables:** Clear, aligned terminal reports.

---

## Installation

No installation required. Simply download or clone the repository and run with Python 3:

```bash
git clone https://github.com/ameerweb/odoo_log_analyser.git
cd odoo_log_analyser
```

---

## Quick Start

### Basic Analysis
Analyze requests taking longer than 2.0 seconds (default):

```bash
python odoo_log_analyser.py /path/to/odoo-server.log
```

### Custom Threshold
Analyze requests taking longer than 1.5 seconds:

```bash
python odoo_log_analyser.py /path/to/odoo-server.log -t 1.5
```

### Show Top 5 Slowest
Limit table output to the top 5 entries:

```bash
python odoo_log_analyser.py /path/to/odoo-server.log -t 2.0 -n 5
```

### Filter by Database
Isolate logs for a specific database in multi-tenant environments:

```bash
python odoo_log_analyser.py /path/to/odoo-server.log -d my_company_db
```

### Requests Only
Focus exclusively on HTTP performance and skip system logs:

```bash
python odoo_log_analyser.py /path/to/odoo-server.log -r
```

### Errors Only
Audit system errors, tracebacks, and warnings:

```bash
python odoo_log_analyser.py /path/to/odoo-server.log -e
```

---

## Command-Line Options

| Option | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `logfile` | | Path to the Odoo server log file | *Required* |
| `--min-seconds`, `--threshold` | `-t` | Minimum request duration in seconds | `2.0` |
| `--requests-only` | `-r` | Analyze HTTP request logs only | `False` |
| `--errors-only`, `--no-requests` | `-e`, `-R` | Analyze system errors/warnings only | `False` |
| `--level`, `--severity` | `-l`, `-s` | Minimum log severity (`INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` |
| `--top`, `--limit` | `-n` | Number of ranking rows to show in tables | `10` |
| `--database`, `--db` | `-d` | Filter logs by target database name | `None` |
| `--all-dbs`, `--include-no-db` | `-a`, `-i` | Include logs with undefined database (`?`) | `False` |
| `--verbose` | `-v` | Display progress bar and debug information | `False` |
| `--quiet` | `-q` | Quiet mode: suppress progress updates | `False` |

---

## Sample Output

```text
--- Log Summary Counts ---
  REQUEST   : 245
  INFO      : 1820
  WARNING   : 34
  ERROR     : 12

================================================================================================================
|                                           Top 10 Slowest Requests                                            |
================================================================================================================
| Endpoint                                            | Total (s) | SQL (s) | Python (s) | Queries | DB        |
----------------------------------------------------------------------------------------------------------------
| /web/dataset/call_kw/stock.quant/action_view_quants |    60.000 |  35.200 |     24.800 |     320 | prod_db   |
| /web/dataset/call_kw/account.move/action_post       |    55.800 |  40.500 |     15.300 |     450 | prod_db   |
| /report/pdf/sale.report_saleorder                   |    52.500 |  20.100 |     32.400 |     180 | prod_db   |
----------------------------------------------------------------------------------------------------------------

============================================================================================
|                            Top 10 Slowest Endpoints (Average)                            |
============================================================================================
| Endpoint                                            | Avg Total (s) | Avg SQL (s) | Hits |
--------------------------------------------------------------------------------------------
| /web/dataset/call_kw/stock.quant/action_view_quants |        60.000 |      35.200 |    1 |
| /shop/cart                                          |         7.333 |       1.767 |    3 |
--------------------------------------------------------------------------------------------
```

---

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. See the [LICENSE](LICENSE) file for details.
