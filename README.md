# check_bareos_job.py

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-blueviolet?style=for-the-badge" alt="License: MIT">
  <img src="https://img.shields.io/badge/Built%20by-NEMESTER-DARKGREEN?style=for-the-badge" alt="Built by Nous Research"></a>
</p>

A lightweight Icinga2 / Nagios plugin for monitoring a specific Bareos backup job via the Bareos PostgreSQL catalog.

This plugin is focused on a simple and practical use case:

- check a specific Bareos job by name
- optionally evaluate only the latest run
- return a proper Nagios/Icinga state
- expose useful performance data for graphing and alerting (perfdata)

It is intended for environments where standard Bareos job checks are too broad and you need a dedicated check for a single job, or when you want to keep track of job statistics such as file count, size, duration, and runtime age over time.

---

## Features

- Check a specific Bareos job by name
- Match jobs by exact name or SQL `LIKE`
- Evaluate only the latest run or all matching runs
- Filter by backup level:
  - `F` = Full
  - `I` = Incremental
  - `D` = Differential
- Restrict checks to jobs within the last _N_ days
- Optional freshness check for the latest run with `--max-age-hours`
- Configurable state mapping with:
  - `--ok-states`
  - `--warning-states`
- Thresholds for file count:
  - minimum warning / critical
  - maximum warning / critical
- Thresholds for backup size in bytes:
  - minimum warning / critical
  - maximum warning / critical
- Performance data output for:
  - number of files
  - backup size in bytes
  - duration in seconds
  - age of the last run in seconds

---

## Status Mapping

By default, the plugin maps Bareos job states like this:

- `T` → **OK**
- `W` → **CRITICAL** unless explicitly added to `--warning-states` or `--ok-states`
- all other states → **CRITICAL**
- no matching job found → **UNKNOWN**
- database/query errors → **UNKNOWN**

You can override the behavior with:

- `--ok-states`
- `--warning-states`

Examples:

- `--ok-states T`
- `--ok-states T,W`
- `--ok-states T --warning-states W`
- `--ok-states T,W --warning-states A`

A state may only exist in one list. Overlapping definitions are rejected.

---

## Requirements

- Python 3.7 or newer
- PostgreSQL client libraries
- Python package:
  - `psycopg2`

### Install dependency

Using pip:

```bash
pip install psycopg2-binary
```

Using system package:

```bash
apt install python3-psycopg2
```

```bash
yum install python3-psycopg2
```

---

## Bareos Catalog Permissions

The plugin connects directly to the Bareos PostgreSQL catalog and reads the `Job` table.

Make sure the configured database user has permission to connect and query the Bareos catalog.

Typical connection parameters:

- host
- port
- database name
- username
- password

---

## Installation

Clone the repository or copy the script to your monitoring plugins directory, for example:

```bash
/usr/lib/nagios/plugins/check_bareos_job.py
```

Make it executable:

```bash
chmod +x /usr/lib/nagios/plugins/check_bareos_job.py
```

---

## Usage

```bash
check_bareos_job.py -U USER [-p PASSWORD | --password-file FILE] -j JOBNAME [OPTIONS]
```

### Required arguments

- `-U`, `--user`  
  Database user

- `-j`, `--job-name`  
  Bareos job name to check

### Authentication

- `-p`, `--password`  
  Database password

- `--password-file`  
  File containing a line like `Password = secret`

Default password file:

```text
/etc/bareos/bareos-dir.conf
```

### Connection options

- `-H`, `--host`  
  PostgreSQL host  
  Default: `127.0.0.1`

- `-P`, `--port`  
  PostgreSQL port  
  Default: `5432`

- `-d`, `--database`  
  Database name  
  Default: `bareos`

### Job filtering options

- `--name-mode {exact,like}`  
  Match job name exactly or using SQL `LIKE`  
  Default: `exact`

- `--latest-only`  
  Evaluate only the most recent matching job

- `--days N`  
  Only consider jobs started within the last `N` days

- `--level {F,I,D}`  
  Restrict to backup level:
  - `F` = Full
  - `I` = Incremental
  - `D` = Differential

- `--max-age-hours HOURS`  
  Return `CRITICAL` if the latest matching job is older than the specified number of hours

### State mapping options

- `--ok-states LIST`  
  Comma-separated Bareos job states treated as OK  
  Example: `T` or `T,W`  
  Default: `T`

- `--warning-states LIST`  
  Comma-separated Bareos job states treated as WARNING  
  Example: `W` or `A,W`

### Threshold options

#### Minimum file count thresholds

- `--warning-min-files N`  
  Return `WARNING` if `JobFiles` is below this value

- `--critical-min-files N`  
  Return `CRITICAL` if `JobFiles` is below this value

Validation rule:

```text
critical-min-files <= warning-min-files
```

#### Maximum file count thresholds

- `--warning-max-files N`  
  Return `WARNING` if `JobFiles` is above this value

- `--critical-max-files N`  
  Return `CRITICAL` if `JobFiles` is above this value

Validation rule:

```text
warning-max-files <= critical-max-files
```

#### Minimum size thresholds

- `--warning-min-size-bytes N`  
  Return `WARNING` if `JobBytes` is below this value

- `--critical-min-size-bytes N`  
  Return `CRITICAL` if `JobBytes` is below this value

Validation rule:

```text
critical-min-size-bytes <= warning-min-size-bytes
```

#### Maximum size thresholds

- `--warning-max-size-bytes N`  
  Return `WARNING` if `JobBytes` is above this value

- `--critical-max-size-bytes N`  
  Return `CRITICAL` if `JobBytes` is above this value

Validation rule:

```text
warning-max-size-bytes <= critical-max-size-bytes
```

### Other options

- `--version`  
  Show plugin version

---

## Examples

### Check the latest run of one exact job

```bash
./check_bareos_job.py -U bareos -p 'secret' -j backup-client1-fd --latest-only
```

### Check only full backups

```bash
./check_bareos_job.py -U bareos -p 'secret' -j backup-client1-fd --latest-only --level F
```

### Check only runs from the last 7 days

```bash
./check_bareos_job.py -U bareos -p 'secret' -j backup-client1-fd --latest-only --days 7
```

### Use SQL `LIKE` matching

```bash
./check_bareos_job.py -U bareos -p 'secret' -j 'backup-client1%' --name-mode like --latest-only
```

### Alert if the latest run is older than 30 hours

```bash
./check_bareos_job.py -U bareos -p 'secret' -j backup-client1-fd --latest-only --max-age-hours 30
```

### Treat `W` as WARNING

```bash
./check_bareos_job.py -U bareos -p 'secret' -j backup-client1-fd --latest-only --ok-states T --warning-states W
```

### Treat `T` and `W` as OK

```bash
./check_bareos_job.py -U bareos -p 'secret' -j backup-client1-fd --latest-only --ok-states T,W
```

### Alert on unusually small backups

```bash
./check_bareos_job.py \
  -U bareos \
  --password-file /etc/bareos/db-password \
  --latest-only \
  -j backup-client1-fd \
  --ok-states T \
  --warning-states W \
  --warning-min-files 40000 \
  --critical-min-files 20000 \
  --warning-min-size-bytes 5000000000 \
  --critical-min-size-bytes 2000000000
```

### Alert on unusually large backups

```bash
./check_bareos_job.py \
  -U bareos \
  --password-file /etc/bareos/db-password \
  --latest-only \
  -j backup-client1-fd \
  --ok-states T \
  --warning-states W \
  --warning-max-files 500000 \
  --critical-max-files 1000000 \
  --warning-max-size-bytes 8000000000000 \
  --critical-max-size-bytes 10000000000000
```

### Use min and max thresholds together

```bash
./check_bareos_job.py \
  -U bareos \
  --password-file /etc/bareos/db-password \
  --latest-only \
  -j backup-client1-fd \
  --ok-states T \
  --warning-states W \
  --warning-min-files 40000 \
  --critical-min-files 20000 \
  --warning-max-files 200000 \
  --critical-max-files 400000 \
  --warning-min-size-bytes 5000000000 \
  --critical-min-size-bytes 2000000000 \
  --warning-max-size-bytes 20000000000 \
  --critical-max-size-bytes 50000000000
```

---

## Example Output

### OK

```text
[OK] Job 'backup-client1-fd' latest run: state=T (Job terminated normally), level=F, files=128934, size=84.72 GB, duration=1420s, age=3600s, ok_states=T, warning_states=W | files=128934c;;;; size_bytes=90991857664B;;;; duration_seconds=1420s;;;; age_seconds=3600s;;;;
```

### WARNING

```text
[WARNING] Job 'backup-client1-fd' latest run: state=W (Job terminated normally with warnings), level=F, files=128934, size=84.72 GB, duration=1420s, age=3600s, ok_states=T, warning_states=W | files=128934c;;;; size_bytes=90991857664B;;;; duration_seconds=1420s;;;; age_seconds=3600s;;;;
```

### CRITICAL

```text
[CRITICAL] Job 'backup-client1-fd' latest run: state=E (Job terminated in error), level=F, files=0, size=0.00 B, duration=12s, age=240s, ok_states=T, warning_states=W | files=0c;;;; size_bytes=0B;;;; duration_seconds=12s;;;; age_seconds=240s;;;;
```

### CRITICAL due to threshold

```text
[CRITICAL] Job 'backup-client1-fd' latest run: state=T (Job terminated normally), level=F, files=15000, size=1.80 GB, duration=1420s, age=3600s, ok_states=T, warning_states=W, threshold_hits=files<20000 (critical); size<2000000000B (critical) | files=15000c;40000:200000;20000:400000;; size_bytes=1800000000B;5000000000:20000000000;2000000000:50000000000;; duration_seconds=1420s;;;; age_seconds=3600s;;;;
```

### UNKNOWN

```text
[UNKNOWN] No matching Bareos job found for 'backup-client1-fd'
```

---

## Performance Data

The plugin returns standard Nagios/Icinga performance data.

Typical metrics:

- `files`
- `size_bytes`
- `duration_seconds`
- `age_seconds`

Example without thresholds:

```text
files=128934c;;;; size_bytes=90991857664B;;;; duration_seconds=1420s;;;; age_seconds=3600s;;;;
```

Example with min/max thresholds:

```text
files=44248c;20000:200000;10000:400000;;
size_bytes=6223550585B;5000000000:20000000000;2000000000:50000000000;;
duration_seconds=389s;;;;
age_seconds=236521s;;;;
```

These values can be used for graphing in tools such as Grafana, PNP4Nagios, InfluxDB-based stacks, or other performance data processors.

---

## Icinga2 Example

Example `CheckCommand`:

```icinga2
object CheckCommand "bareos_job" {
  import "plugin-check-command"

  command = [ PluginDir + "/check_bareos_job.py" ]

  arguments = {
    "-H" = "$bareos_db_host$"
    "-P" = "$bareos_db_port$"
    "-d" = "$bareos_db_name$"
    "-U" = "$bareos_db_user$"
    "-p" = "$bareos_db_password$"
    "-j" = "$bareos_job_name$"

    "--name-mode" = "$bareos_name_mode$"
    "--latest-only" = {
      set_if = "$bareos_latest_only$"
    }
    "--days" = "$bareos_days$"
    "--level" = "$bareos_level$"
    "--max-age-hours" = "$bareos_max_age_hours$"
    "--ok-states" = "$bareos_ok_states$"
    "--warning-states" = "$bareos_warning_states$"

    "--warning-min-files" = "$bareos_warning_min_files$"
    "--critical-min-files" = "$bareos_critical_min_files$"
    "--warning-max-files" = "$bareos_warning_max_files$"
    "--critical-max-files" = "$bareos_critical_max_files$"

    "--warning-min-size-bytes" = "$bareos_warning_min_size_bytes$"
    "--critical-min-size-bytes" = "$bareos_critical_min_size_bytes$"
    "--warning-max-size-bytes" = "$bareos_warning_max_size_bytes$"
    "--critical-max-size-bytes" = "$bareos_critical_max_size_bytes$"
  }
}
```

Example service:

```icinga2
apply Service "bareos-job-" for (job_name => config in host.vars.bareos_jobs) {
  import "generic-service"

  check_command = "bareos_job"

  vars.bareos_db_host = host.vars.bareos_db_host
  vars.bareos_db_port = host.vars.bareos_db_port
  vars.bareos_db_name = host.vars.bareos_db_name
  vars.bareos_db_user = host.vars.bareos_db_user
  vars.bareos_db_password = host.vars.bareos_db_password

  vars.bareos_job_name = job_name
  vars.bareos_latest_only = true
  vars.bareos_level = config.level
  vars.bareos_max_age_hours = config.max_age_hours
  vars.bareos_ok_states = config.ok_states
  vars.bareos_warning_states = config.warning_states

  vars.bareos_warning_min_files = config.warning_min_files
  vars.bareos_critical_min_files = config.critical_min_files
  vars.bareos_warning_max_files = config.warning_max_files
  vars.bareos_critical_max_files = config.critical_max_files

  vars.bareos_warning_min_size_bytes = config.warning_min_size_bytes
  vars.bareos_critical_min_size_bytes = config.critical_min_size_bytes
  vars.bareos_warning_max_size_bytes = config.warning_max_size_bytes
  vars.bareos_critical_max_size_bytes = config.critical_max_size_bytes

  assign where host.vars.bareos_jobs
}
```

Example host vars:

```icinga2
vars.bareos_db_host = "127.0.0.1"
vars.bareos_db_port = 5432
vars.bareos_db_name = "bareos"
vars.bareos_db_user = "bareos"
vars.bareos_db_password = "secret"

vars.bareos_jobs["backup-client1-fd"] = {
  level = "F"
  max_age_hours = 30
  ok_states = "T"
  warning_states = "W"

  warning_min_files = 40000
  critical_min_files = 20000
  warning_max_files = 200000
  critical_max_files = 400000

  warning_min_size_bytes = 5000000000
  critical_min_size_bytes = 2000000000
  warning_max_size_bytes = 20000000000
  critical_max_size_bytes = 50000000000
}
```

Instead of exposing the Bareos database to the monitoring system you can also use a wrapper script and a corresponding configuration in NRPE, for example:

In `/etc/nagios/nrpe_local.cfg`:

```ini
command[check_bareos_job]=/usr/local/lib/nagios/plugins/check_bareos_job.py -U bareos --password-file /etc/bareos/db-password  $ARG1$
```

Example wrapper script on Icinga host:

```bash
#!/usr/bin/env bash
#
# check_bareos_latest.sh
#
# Wrapper for check_bareos_job.py via NRPE
#
# This script executes a remote check for a specific Bareos backup job
# using the check_bareos_job.py plugin on a remote host via NRPE.
#
# It evaluates the **latest run only** and allows flexible configuration
# of job state handling and threshold-based alerting.
#
# Features:
#   - Check latest execution state of a specific Bareos job
#   - Custom mapping of job states:
#       * OK states        (--ok-states)
#       * WARNING states   (--warning-states)
#   - Age validation of last run (--max-age-hours)
#   - Threshold checks:
#       * Minimum/maximum number of files
#       * Minimum/maximum backup size (bytes)
#   - Pass-through of performance data from remote plugin
#
# The wrapper builds the argument string and forwards it via NRPE.
#
# Requirements:
#   - NRPE installed on remote host
#   - NRPE command configured to execute check_bareos_job.py
#   - check_bareos_job.py available on remote system
#
# Usage:
#   check_bareos_latest.sh -H <nrpe_host> -j <jobname> [options]
#
# Example:
#   check_bareos_latest.sh -H backuphost -j backup-client1-fd \
#     --ok-states T \
#     --warning-states W \
#     --max-age-hours 30 \
#     --warning-min-files 40000 \
#     --critical-min-files 20000 \
#     --warning-max-size-bytes 8000000000000 \
#     --critical-max-size-bytes 10000000000000
#
# Exit Codes:
#   0 - OK
#   1 - WARNING
#   2 - CRITICAL
#   3 - UNKNOWN
#
# Notes:
#   - The actual evaluation logic is implemented in check_bareos_job.py
#   - This wrapper only handles argument parsing and NRPE communication
#   - Job name and parameters should not contain shell-special characters
#
# Changelog:
#   1.0 - 2026-04-14 - Initial implementation


set -euo pipefail

NRPE_BIN="${NRPE_BIN:-/usr/lib/nagios/plugins/check_nrpe}"
NRPE_HOST="${NRPE_HOST:-}"
NRPE_PORT="${NRPE_PORT:-5666}"
NRPE_TIMEOUT="${NRPE_TIMEOUT:-10}"
NRPE_CMD="${NRPE_CMD:-check_bareos_job}"

JOBNAME="${JOBNAME:-}"
OK_STATES="${OK_STATES:-}"
WARNING_STATES="${WARNING_STATES:-}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-}"

WARNING_MIN_FILES="${WARNING_MIN_FILES:-}"
CRITICAL_MIN_FILES="${CRITICAL_MIN_FILES:-}"
WARNING_MAX_FILES="${WARNING_MAX_FILES:-}"
CRITICAL_MAX_FILES="${CRITICAL_MAX_FILES:-}"

WARNING_MIN_SIZE_BYTES="${WARNING_MIN_SIZE_BYTES:-}"
CRITICAL_MIN_SIZE_BYTES="${CRITICAL_MIN_SIZE_BYTES:-}"
WARNING_MAX_SIZE_BYTES="${WARNING_MAX_SIZE_BYTES:-}"
CRITICAL_MAX_SIZE_BYTES="${CRITICAL_MAX_SIZE_BYTES:-}"

usage() {
  cat <<EOF
Usage:
  $0 -H <nrpe_host> -j <jobname> [options]

Required:
  -H, --host                  NRPE host
  -j, --job                   Bareos job name

Optional:
  -p, --port                  NRPE port (default: 5666)
  -t, --timeout               NRPE timeout (default: 10)
      --nrpe-cmd              NRPE command name (default: check_bareos_job)

      --ok-states             Comma-separated OK states, e.g. T or T,W
      --warning-states        Comma-separated WARNING states, e.g. W
      --max-age-hours         CRITICAL if latest run is older than this many hours

      --warning-min-files     WARNING if files below this value
      --critical-min-files    CRITICAL if files below this value
      --warning-max-files     WARNING if files above this value
      --critical-max-files    CRITICAL if files above this value

      --warning-min-size-bytes    WARNING if size below this value
      --critical-min-size-bytes   CRITICAL if size below this value
      --warning-max-size-bytes    WARNING if size above this value
      --critical-max-size-bytes   CRITICAL if size above this value

Example:
  $0 -H backuphost -j backup-client1-fd --ok-states T --warning-states W --max-age-hours 30
EOF
}

append_arg() {
  local key="$1"
  local value="$2"

  if [[ -n "$value" ]]; then
    REMOTE_ARGS+=" $key $value"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -H|--host) NRPE_HOST="$2"; shift 2;;
    -p|--port) NRPE_PORT="$2"; shift 2;;
    -t|--timeout) NRPE_TIMEOUT="$2"; shift 2;;
    -j|--job) JOBNAME="$2"; shift 2;;
    --nrpe-cmd) NRPE_CMD="$2"; shift 2;;

    --ok-states) OK_STATES="$2"; shift 2;;
    --warning-states) WARNING_STATES="$2"; shift 2;;
    --max-age-hours) MAX_AGE_HOURS="$2"; shift 2;;

    --warning-min-files) WARNING_MIN_FILES="$2"; shift 2;;
    --critical-min-files) CRITICAL_MIN_FILES="$2"; shift 2;;
    --warning-max-files) WARNING_MAX_FILES="$2"; shift 2;;
    --critical-max-files) CRITICAL_MAX_FILES="$2"; shift 2;;

    --warning-min-size-bytes) WARNING_MIN_SIZE_BYTES="$2"; shift 2;;
    --critical-min-size-bytes) CRITICAL_MIN_SIZE_BYTES="$2"; shift 2;;
    --warning-max-size-bytes) WARNING_MAX_SIZE_BYTES="$2"; shift 2;;
    --critical-max-size-bytes) CRITICAL_MAX_SIZE_BYTES="$2"; shift 2;;

    -h|--help) usage; exit 0;;
    *) echo "UNKNOWN - unsupported arg: $1"; usage; exit 3;;
  esac
done

if [[ -z "${NRPE_HOST}" ]]; then
  echo "UNKNOWN - missing NRPE host"
  exit 3
fi

if [[ -z "${JOBNAME}" ]]; then
  echo "UNKNOWN - missing job name"
  exit 3
fi

if [[ ! -x "${NRPE_BIN}" ]]; then
  echo "UNKNOWN - check_nrpe not found: ${NRPE_BIN}"
  exit 3
fi

REMOTE_ARGS="-j $JOBNAME --latest-only"

append_arg "--ok-states" "$OK_STATES"
append_arg "--warning-states" "$WARNING_STATES"
append_arg "--max-age-hours" "$MAX_AGE_HOURS"

append_arg "--warning-min-files" "$WARNING_MIN_FILES"
append_arg "--critical-min-files" "$CRITICAL_MIN_FILES"
append_arg "--warning-max-files" "$WARNING_MAX_FILES"
append_arg "--critical-max-files" "$CRITICAL_MAX_FILES"

append_arg "--warning-min-size-bytes" "$WARNING_MIN_SIZE_BYTES"
append_arg "--critical-min-size-bytes" "$CRITICAL_MIN_SIZE_BYTES"
append_arg "--warning-max-size-bytes" "$WARNING_MAX_SIZE_BYTES"
append_arg "--critical-max-size-bytes" "$CRITICAL_MAX_SIZE_BYTES"

set +e
OUTPUT="$("${NRPE_BIN}" \
  -H "${NRPE_HOST}" \
  -p "${NRPE_PORT}" \
  -t "${NRPE_TIMEOUT}" \
  -c "${NRPE_CMD}" \
  -a "${REMOTE_ARGS}" 2>&1)"
RC=$?
set -e

echo "${OUTPUT}"
exit "${RC}"

```

---

## Security Notes

- The plugin uses parameterized SQL queries to avoid SQL injection.
- Avoid passing passwords on the command line if possible, because they may appear in process listings.
- Prefer `--password-file` or a protected wrapper script.
- Restrict file permissions on configuration files containing credentials.

Recommended permissions:

```bash
chmod 600 /etc/bareos/bareos-dir.conf
```

---

## Troubleshooting

### `UNKNOWN - Database connection failed`

Check:

- PostgreSQL is reachable
- host, port, database, user, and password are correct
- firewall rules allow the connection
- the user has access to the Bareos catalog

### `UNKNOWN - No matching Bareos job found`

Check:

- the job name is correct
- use `--name-mode like` if needed
- the job exists in the selected time window
- the selected backup level matches the actual jobs

### Plugin returns `CRITICAL` although backups seem fine

Check the configured `--ok-states` and `--warning-states`.  
By design, any state not explicitly mapped to OK or WARNING becomes CRITICAL.

### `NRPE: Unable to read output`

Typical causes:

- the NRPE user cannot execute the script
- the NRPE user cannot read the password file
- the command definition in NRPE is wrong
- the NRPE timeout is too low


---

## Backlog / Ideas

Possible future improvements:

- human-readable size arguments like `10G` or `2T`
- relative growth checks compared with previous runs
- age threshold with WARNING and CRITICAL levels
- support for checking expected schedule gaps
- JSON output mode for external integrations

---

## License

MIT
