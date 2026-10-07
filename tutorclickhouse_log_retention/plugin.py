"""Retention for ClickHouse system.* telemetry, for Cairn and Aspects.

Problem: ClickHouse writes its own telemetry (system.trace_log, text_log, metric_log, ...)
next to the real data and never expires it, so the disk fills up slowly.

What this plugin does (nothing else):
  1. TTL: every system log table deletes rows older than N days.
  2. Query profiler off: the profiler is what makes system.trace_log huge.

Settings (config.yml, per instance):
  CLICKHOUSE_LOG_RETENTION_DAYS            days to keep the diagnostic logs (default 7)
  CLICKHOUSE_LOG_RETENTION_QUERY_LOG_DAYS  days to keep system.query_log (default 30),
                                           longer because the Aspects dashboards read it

After enabling, restart ClickHouse. ClickHouse then renames every existing system log
table to <name>_0, <name>_1, ... and creates a fresh one with the TTL. The renamed copies
keep their data and disk space until they are dropped (see README).

How the XML reaches ClickHouse (all files are in templates/):

  Aspects (service "clickhouse")
    - TTL: Aspects' own patch "clickhouse-server-config" (inside <clickhouse> in
      config.d/server_config.xml). The patch is the file patches/clickhouse-server-config.
      Same patch name in every Aspects release since 0.70.
    - Profiler: its own file in the users directory Aspects mounts. Aspects' patch
      "clickhouse-user-config" cannot carry it: that file already has a <profiles> block
      and ClickHouse ignores a second one in the same file.
      (templates/aspects/apps/clickhouse/users/zz-noprofiler.xml; Aspects renders every
      file under aspects/apps, ours included, and mounts the whole directory.)

  Cairn (service "cairn-clickhouse")
    - Cairn has no patch for ClickHouse config. Two XML files are rendered by this plugin
      (templates/clickhouse-log-retention/apps/) and mounted by
      templates/local/docker-compose.override.yml, which Tutor loads for `tutor local`
      (core renders everything under local/, ours included).
"""

import os
from glob import glob

from tutor import hooks

_HERE = os.path.dirname(os.path.abspath(__file__))

########################################
# CONFIGURATION
########################################

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("CLICKHOUSE_LOG_RETENTION_DAYS", 7),
        ("CLICKHOUSE_LOG_RETENTION_QUERY_LOG_DAYS", 30),
    ]
)

########################################
# TEMPLATE RENDERING
########################################

hooks.Filters.ENV_TEMPLATE_ROOTS.add_item(os.path.join(_HERE, "templates"))

# Only our own XML needs a target. The Aspects file (aspects/apps/...) and the compose
# override (local/...) are rendered by Aspects' and by Tutor core's own targets.
hooks.Filters.ENV_TEMPLATE_TARGETS.add_item(
    ("clickhouse-log-retention/apps", "plugins")
)

########################################
# PATCH LOADING
########################################

# One patch per file in patches/: the file name is the patch name.
for path in glob(os.path.join(_HERE, "patches", "*")):
    with open(path, encoding="utf-8") as patch_file:
        hooks.Filters.ENV_PATCHES.add_item((os.path.basename(path), patch_file.read()))
