#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# check_bareos_job.py - Icinga2 / Nagios plugin for Bareos job monitoring
#
# Copyright (C) 2026 Manuel Sonder
#
# This plugin checks a specific Bareos job in the PostgreSQL catalog,
# optionally evaluates only the most recent run, and returns monitoring
# status plus performance data for files, size, duration, and age.
#
# SPDX-License-Identifier: MIT
#
# Changelog
# 2026-04-10   V1.0    Initial implementation
# 2026-04-14   V1.1    Added parameters '--ok-states', '--warning-states' and
#                      thresholds for nof files ('--warning-[min|max]-files' / '--critical-[min|max]-files') 
#                      and backup size ('--warning-[min|max]-size-bytes' / '--critical-[min|max]-size-bytes')

import argparse
import sys
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras


VERSION = "1.1"

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3

JOBSTATES = {
    'A': 'Job canceled by user',
    'B': 'Job blocked',
    'C': 'Job created but not yet running',
    'D': 'Verify differences',
    'E': 'Job terminated in error',
    'F': 'Job waiting on File daemon',
    'I': 'Incomplete Job',
    'L': 'Committing data (last despool)',
    'M': 'Job waiting for Mount',
    'R': 'Job running',
    'S': 'Job waiting on the Storage daemon',
    'T': 'Job terminated normally',
    'W': 'Job terminated normally with warnings',
    'a': 'SD despooling attributes',
    'c': 'Waiting for Client resource',
    'd': 'Waiting for maximum jobs',
    'e': 'Non-fatal error',
    'f': 'Fatal error',
    'i': 'Doing batch insert file records',
    'j': 'Waiting for job resource',
    'l': 'Doing data despooling',
    'm': 'Waiting for new media',
    'p': 'Waiting for higher priority jobs to finish',
    'q': 'Queued waiting for device',
    's': 'Waiting for storage resource',
    't': 'Waiting for start time'
}


def read_password_from_file(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if "Password" in line:
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2].strip('"')
    raise ValueError(f"No password found in {path}")


def human_bytes(value: int) -> str:
    if value is None:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{value} B"


def plugin_exit(code: int, message: str, perfdata: str = "") -> None:
    if perfdata:
        print(f"{message} | {perfdata}")
    else:
        print(message)
    sys.exit(code)


def connect_db(args):
    try:
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            dbname=args.database,
            user=args.user,
            password=args.password,
        )
        return conn
    except Exception as exc:
        plugin_exit(UNKNOWN, f"[UNKNOWN] Database connection failed: {exc}")


def parse_state_list(value: str) -> set[str]:
    states = {item.strip() for item in value.split(",") if item.strip()}

    if not states:
        raise argparse.ArgumentTypeError("State list must not be empty")

    invalid = sorted(state for state in states if state not in JOBSTATES)
    if invalid:
        raise argparse.ArgumentTypeError(
            f"Invalid Bareos job state(s): {', '.join(invalid)}"
        )

    return states


def validate_state_sets(ok_states: set[str], warning_states: set[str]) -> None:
    overlap = sorted(ok_states & warning_states)
    if overlap:
        raise ValueError(
            f"State(s) defined in both --ok-states and --warning-states: {', '.join(overlap)}"
        )


def validate_min_thresholds(
    warning_min_files,
    critical_min_files,
    warning_min_size_bytes,
    critical_min_size_bytes,
) -> None:
    if (
        warning_min_files is not None
        and critical_min_files is not None
        and critical_min_files > warning_min_files
    ):
        raise ValueError(
            "--critical-min-files must be less than or equal to --warning-min-files"
        )

    if (
        warning_min_size_bytes is not None
        and critical_min_size_bytes is not None
        and critical_min_size_bytes > warning_min_size_bytes
    ):
        raise ValueError(
            "--critical-min-size-bytes must be less than or equal to --warning-min-size-bytes"
        )


def validate_max_thresholds(
    warning_max_files,
    critical_max_files,
    warning_max_size_bytes,
    critical_max_size_bytes,
) -> None:
    if (
        warning_max_files is not None
        and critical_max_files is not None
        and warning_max_files > critical_max_files
    ):
        raise ValueError(
            "--warning-max-files must be less than or equal to --critical-max-files"
        )

    if (
        warning_max_size_bytes is not None
        and critical_max_size_bytes is not None
        and warning_max_size_bytes > critical_max_size_bytes
    ):
        raise ValueError(
            "--warning-max-size-bytes must be less than or equal to --critical-max-size-bytes"
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Icinga/Nagios plugin for checking a specific Bareos job"
    )

    parser.add_argument("-H", "--host", default="127.0.0.1", help="PostgreSQL host")
    parser.add_argument("-P", "--port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("-d", "--database", default="bareos", help="Database name")
    parser.add_argument("-U", "--user", required=True, help="Database user")

    pw_group = parser.add_mutually_exclusive_group()
    pw_group.add_argument("-p", "--password", help="Database password")
    pw_group.add_argument(
        "--password-file",
        default="/etc/bareos/bareos-dir.conf",
        help="File containing 'Password = ...'",
    )

    parser.add_argument("-j", "--job-name", required=True, help="Bareos job name to check")
    parser.add_argument(
        "--name-mode",
        choices=["exact", "like"],
        default="exact",
        help="Match job name exactly or with SQL LIKE",
    )
    parser.add_argument(
        "--latest-only",
        action="store_true",
        help="Only evaluate the most recent matching job",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only consider jobs started within the last N days",
    )
    parser.add_argument(
        "--level",
        choices=["F", "I", "D"],
        default=None,
        help="Restrict to backup level: F=Full, I=Incremental, D=Differential",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        help="Return CRITICAL if the latest matching job is older than this many hours",
    )
    parser.add_argument(
        "--ok-states",
        type=parse_state_list,
        default={"T"},
        help="Comma-separated Bareos job states treated as OK, e.g. T or T,W (default: T)",
    )
    parser.add_argument(
        "--warning-states",
        type=parse_state_list,
        default=set(),
        help="Comma-separated Bareos job states treated as WARNING, e.g. W or A,W",
    )

    parser.add_argument(
        "--warning-min-files",
        type=int,
        default=None,
        help="Return WARNING if JobFiles is below this value",
    )
    parser.add_argument(
        "--critical-min-files",
        type=int,
        default=None,
        help="Return CRITICAL if JobFiles is below this value",
    )
    parser.add_argument(
        "--warning-min-size-bytes",
        type=int,
        default=None,
        help="Return WARNING if JobBytes is below this value",
    )
    parser.add_argument(
        "--critical-min-size-bytes",
        type=int,
        default=None,
        help="Return CRITICAL if JobBytes is below this value",
    )

    parser.add_argument(
        "--warning-max-files",
        type=int,
        default=None,
        help="Return WARNING if JobFiles is above this value",
    )
    parser.add_argument(
        "--critical-max-files",
        type=int,
        default=None,
        help="Return CRITICAL if JobFiles is above this value",
    )
    parser.add_argument(
        "--warning-max-size-bytes",
        type=int,
        default=None,
        help="Return WARNING if JobBytes is above this value",
    )
    parser.add_argument(
        "--critical-max-size-bytes",
        type=int,
        default=None,
        help="Return CRITICAL if JobBytes is above this value",
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    args = parser.parse_args()

    try:
        validate_state_sets(args.ok_states, args.warning_states)
        validate_min_thresholds(
            args.warning_min_files,
            args.critical_min_files,
            args.warning_min_size_bytes,
            args.critical_min_size_bytes,
        )
        validate_max_thresholds(
            args.warning_max_files,
            args.critical_max_files,
            args.warning_max_size_bytes,
            args.critical_max_size_bytes,
        )
    except ValueError as exc:
        parser.error(str(exc))

    return args


def build_query(args):
    where = []
    params = []

    if args.name_mode == "exact":
        where.append("Name = %s")
        params.append(args.job_name)
    else:
        where.append("Name LIKE %s")
        params.append(args.job_name)

    if args.level:
        where.append("Level = %s")
        params.append(args.level)

    if args.days is not None:
        where.append("StartTime >= NOW() - (%s * INTERVAL '1 day')")
        params.append(args.days)

    where_sql = " AND ".join(where)

    base_sql = f"""
        SELECT
            JobId,
            Name,
            Level,
            JobStatus,
            StartTime,
            EndTime,
            JobFiles,
            JobBytes
        FROM Job
        WHERE {where_sql}
        ORDER BY StartTime DESC NULLS LAST, JobId DESC
    """

    if args.latest_only:
        base_sql += " LIMIT 1"

    return base_sql, params


def state_to_exit(job_status: str, ok_states: set[str], warning_states: set[str]) -> int:
    if job_status in ok_states:
        return OK
    if job_status in warning_states:
        return WARNING
    return CRITICAL


def format_status_text(job_status: str) -> str:
    return JOBSTATES.get(job_status, f"Unknown state {job_status}")


def compute_age_seconds(start_time):
    if start_time is None:
        return None

    now = datetime.now(timezone.utc)
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return int((now - start_time).total_seconds())


def compute_duration_seconds(start_time, end_time):
    if start_time is None:
        return None

    end = end_time or datetime.now(start_time.tzinfo or timezone.utc)
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    return max(0, int((end - start_time).total_seconds()))


def format_state_list(states: set[str]) -> str:
    return ",".join(sorted(states)) if states else "-"


def apply_min_thresholds(value: int, warning_min, critical_min) -> int:
    if critical_min is not None and value < critical_min:
        return CRITICAL
    if warning_min is not None and value < warning_min:
        return WARNING
    return OK


def apply_max_thresholds(value: int, warning_max, critical_max) -> int:
    if critical_max is not None and value > critical_max:
        return CRITICAL
    if warning_max is not None and value > warning_max:
        return WARNING
    return OK


def combine_codes(*codes: int) -> int:
    return max(codes) if codes else OK


def check_job(args):
    conn = connect_db(args)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            sql, params = build_query(args)
            cur.execute(sql, params)
            rows = cur.fetchall()

            if not rows:
                plugin_exit(
                    UNKNOWN,
                    f"[UNKNOWN] No matching Bareos job found for '{args.job_name}'"
                )

            if args.latest_only:
                row = rows[0]
                evaluate_single_result(row, args)
            else:
                worst_code = OK
                worst_row = rows[0]

                for row in rows:
                    row_code = evaluate_row_code(row, args)
                    if row_code > worst_code:
                        worst_code = row_code
                        worst_row = row

                evaluate_multi_result(rows, worst_row, args)
    except Exception as exc:
        plugin_exit(UNKNOWN, f"[UNKNOWN] Query failed: {exc}")
    finally:
        conn.close()


def evaluate_row_code(row, args) -> int:
    job_status = row["jobstatus"]
    start_time = row["starttime"]
    job_files = int(row["jobfiles"] or 0)
    job_bytes = int(row["jobbytes"] or 0)

    age_seconds = compute_age_seconds(start_time)

    state_code = state_to_exit(job_status, args.ok_states, args.warning_states)

    age_code = OK
    if args.max_age_hours is not None and age_seconds is not None:
        if age_seconds > int(args.max_age_hours * 3600):
            age_code = CRITICAL

    files_min_code = apply_min_thresholds(
        job_files,
        args.warning_min_files,
        args.critical_min_files,
    )
    files_max_code = apply_max_thresholds(
        job_files,
        args.warning_max_files,
        args.critical_max_files,
    )

    size_min_code = apply_min_thresholds(
        job_bytes,
        args.warning_min_size_bytes,
        args.critical_min_size_bytes,
    )
    size_max_code = apply_max_thresholds(
        job_bytes,
        args.warning_max_size_bytes,
        args.critical_max_size_bytes,
    )

    return combine_codes(
        state_code,
        age_code,
        files_min_code,
        files_max_code,
        size_min_code,
        size_max_code,
    )


def build_threshold_messages(job_files: int, job_bytes: int, args) -> list[str]:
    messages = []

    if args.critical_min_files is not None and job_files < args.critical_min_files:
        messages.append(f"files<{args.critical_min_files} (critical)")
    elif args.warning_min_files is not None and job_files < args.warning_min_files:
        messages.append(f"files<{args.warning_min_files} (warning)")

    if args.critical_max_files is not None and job_files > args.critical_max_files:
        messages.append(f"files>{args.critical_max_files} (critical)")
    elif args.warning_max_files is not None and job_files > args.warning_max_files:
        messages.append(f"files>{args.warning_max_files} (warning)")

    if args.critical_min_size_bytes is not None and job_bytes < args.critical_min_size_bytes:
        messages.append(f"size<{args.critical_min_size_bytes}B (critical)")
    elif args.warning_min_size_bytes is not None and job_bytes < args.warning_min_size_bytes:
        messages.append(f"size<{args.warning_min_size_bytes}B (warning)")

    if args.critical_max_size_bytes is not None and job_bytes > args.critical_max_size_bytes:
        messages.append(f"size>{args.critical_max_size_bytes}B (critical)")
    elif args.warning_max_size_bytes is not None and job_bytes > args.warning_max_size_bytes:
        messages.append(f"size>{args.warning_max_size_bytes}B (warning)")

    return messages


def evaluate_single_result(row, args):
    job_status = row["jobstatus"]
    start_time = row["starttime"]
    end_time = row["endtime"]
    job_files = int(row["jobfiles"] or 0)
    job_bytes = int(row["jobbytes"] or 0)

    age_seconds = compute_age_seconds(start_time)
    duration_seconds = compute_duration_seconds(start_time, end_time)

    code = evaluate_row_code(row, args)

    age_text = f"{age_seconds}s" if age_seconds is not None else "n/a"
    duration_text = f"{duration_seconds}s" if duration_seconds is not None else "n/a"
    level_text = row["level"] or "n/a"

    threshold_messages = build_threshold_messages(job_files, job_bytes, args)
    threshold_text = f", threshold_hits={'; '.join(threshold_messages)}" if threshold_messages else ""

    message = (
        f"[{status_label(code)}] "
        f"Job '{row['name']}' latest run: state={job_status} ({format_status_text(job_status)}), "
        f"level={level_text}, files={job_files}, size={human_bytes(job_bytes)}, "
        f"duration={duration_text}, age={age_text}, "
        f"ok_states={format_state_list(args.ok_states)}, "
        f"warning_states={format_state_list(args.warning_states)}"
        f"{threshold_text}"
    )

    perfdata = (
        f"files={job_files}c;"
        f"{args.warning_min_files if args.warning_min_files is not None else ''}:"
        f"{args.warning_max_files if args.warning_max_files is not None else ''};"
        f"{args.critical_min_files if args.critical_min_files is not None else ''}:"
        f"{args.critical_max_files if args.critical_max_files is not None else ''};; "
        f"size_bytes={job_bytes}B;"
        f"{args.warning_min_size_bytes if args.warning_min_size_bytes is not None else ''}:"
        f"{args.warning_max_size_bytes if args.warning_max_size_bytes is not None else ''};"
        f"{args.critical_min_size_bytes if args.critical_min_size_bytes is not None else ''}:"
        f"{args.critical_max_size_bytes if args.critical_max_size_bytes is not None else ''};; "
        f"duration_seconds={duration_seconds if duration_seconds is not None else 0}s;;;; "
        f"age_seconds={age_seconds if age_seconds is not None else 0}s;;;;"
    )

    plugin_exit(code, message, perfdata)


def evaluate_multi_result(rows, worst_row, args):
    total = len(rows)
    ok_count = 0
    warning_count = 0
    critical_count = 0

    for row in rows:
        code = evaluate_row_code(row, args)
        if code == OK:
            ok_count += 1
        elif code == WARNING:
            warning_count += 1
        else:
            critical_count += 1

    worst_code = evaluate_row_code(worst_row, args)

    message = (
        f"[{status_label(worst_code)}] "
        f"Job '{args.job_name}': checked {total} matching run(s), "
        f"OK={ok_count}, WARNING={warning_count}, CRITICAL={critical_count}; "
        f"worst state={worst_row['jobstatus']} ({format_status_text(worst_row['jobstatus'])}), "
        f"latest matching run size={human_bytes(int(worst_row['jobbytes'] or 0))}, "
        f"files={int(worst_row['jobfiles'] or 0)}, "
        f"ok_states={format_state_list(args.ok_states)}, "
        f"warning_states={format_state_list(args.warning_states)}"
    )

    perfdata = (
        f"matching_runs={total}c;;;; "
        f"ok_runs={ok_count}c;;;; "
        f"warning_runs={warning_count}c;;;; "
        f"critical_runs={critical_count}c;;;; "
        f"files={int(worst_row['jobfiles'] or 0)}c;"
        f"{args.warning_min_files if args.warning_min_files is not None else ''}:"
        f"{args.warning_max_files if args.warning_max_files is not None else ''};"
        f"{args.critical_min_files if args.critical_min_files is not None else ''}:"
        f"{args.critical_max_files if args.critical_max_files is not None else ''};; "
        f"size_bytes={int(worst_row['jobbytes'] or 0)}B;"
        f"{args.warning_min_size_bytes if args.warning_min_size_bytes is not None else ''}:"
        f"{args.warning_max_size_bytes if args.warning_max_size_bytes is not None else ''};"
        f"{args.critical_min_size_bytes if args.critical_min_size_bytes is not None else ''}:"
        f"{args.critical_max_size_bytes if args.critical_max_size_bytes is not None else ''};;"
    )

    plugin_exit(worst_code, message, perfdata)


def status_label(code: int) -> str:
    return {
        OK: "OK",
        WARNING: "WARNING",
        CRITICAL: "CRITICAL",
        UNKNOWN: "UNKNOWN",
    }.get(code, "UNKNOWN")


def main():
    args = parse_args()

    if not args.password:
        try:
            args.password = read_password_from_file(args.password_file)
        except Exception as exc:
            plugin_exit(UNKNOWN, f"[UNKNOWN] Could not read password: {exc}")

    check_job(args)


if __name__ == "__main__":
    main()
