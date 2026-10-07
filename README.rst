clickhouse-log-retention plugin for `Tutor <https://docs.tutor.edly.io>`__
##########################################################################

Stops ClickHouse's own ``system.*`` log tables (``trace_log``, ``text_log``, ``metric_log``,
``asynchronous_metric_log``, ...) from filling the disk. Works for both **Cairn**
(``cairn-clickhouse``) and **Aspects** (``clickhouse``).

ClickHouse records its own telemetry in the ``system`` database and never expires it. On
Open edX instances this telemetry is often more than 95% of what ClickHouse stores.

What it does
************

1. Sets a TTL on every system log table (default 7 days, ``query_log`` 30 days).
2. Turns the query profiler off (it is what makes ``system.trace_log`` huge).

Nothing else is touched: no data database, no live table is dropped.

Installation
************

.. code-block:: bash

    pip install git+https://github.com/Abstract-Tech/tutor-contrib-clickhouse-log-retention

Usage
*****

.. code-block:: bash

    tutor plugins enable clickhouse-log-retention
    tutor config save
    tutor local restart clickhouse          # Aspects
    tutor local restart cairn-clickhouse    # Cairn

Settings (``tutor config save --set NAME=value``):

- ``CLICKHOUSE_LOG_RETENTION_DAYS``: days to keep the diagnostic logs (default ``7``).
- ``CLICKHOUSE_LOG_RETENTION_QUERY_LOG_DAYS``: days to keep ``system.query_log`` (default ``30``).
  The Aspects performance dashboards read it, so keep it longer.

A value below 1 is treated as 1.

After the first restart (important)
***********************************

ClickHouse renames every existing system log table to ``<name>_0``, ``<name>_1``, ... and
creates a fresh one with the TTL. The renamed copies keep their data and their disk space
until you drop them. List them:

.. code-block:: sql

    SELECT name, formatReadableSize(total_bytes) AS size
    FROM system.tables
    WHERE database = 'system' AND match(name, '_log_[0-9]+$')
    ORDER BY total_bytes DESC;

Each ``system.<name>_N`` listed is an old copy of ClickHouse's own diagnostics: nothing
writes to it and neither Cairn nor Aspects reads it, so ``DROP TABLE system.<name>_N`` is
safe. Never drop a table without a numeric suffix.

To free space that is already used, clean up **before** enabling the plugin: drop old
monthly partitions with ``ALTER TABLE system.<table> DROP PARTITION ID 'YYYYMM'`` (the
renamed copies then stay small).

Disabling the plugin does **not** remove what it rendered. Delete
``env/local/docker-compose.override.yml`` and ``env/plugins/clickhouse-log-retention`` and
run ``tutor config save`` again.

How it works
************

All the XML is in ``tutorclickhouse_log_retention/templates`` (real files, easy to read).
``plugin.py`` has the full explanation.

- Aspects: the TTL goes through Aspects' own patch ``clickhouse-server-config`` (present in
  every release since 0.70). The profiler setting needs its own file in the ``users``
  directory Aspects mounts, because ClickHouse ignores a second ``<profiles>`` block in
  the same file.
- Cairn: no patch exists, so two XML files are rendered and mounted by a
  ``docker-compose.override.yml`` in ``env/local`` (Tutor loads it for ``tutor local``).
  It replaces an existing override file of that name. Kubernetes is not covered.

Tested with Tutor 16 to 22 (Cairn 16 to 22, Aspects 0.107 to 6.0), and against real
ClickHouse 22.1, 24.1, 24.2, 24.3, 24.8 and 25.8 containers.

Hosts that are not Tutor (plain Docker Compose)
***********************************************

Mount the two files in ``manual/`` into the ClickHouse container (the profiler file must be
in ``users.d``, not ``config.d``):

.. code-block:: yaml

    volumes:
      - ./data:/var/lib/clickhouse/
      - ./zz-system-ttl.xml:/etc/clickhouse-server/config.d/zz-system-ttl.xml:ro
      - ./zz-noprofiler.xml:/etc/clickhouse-server/users.d/zz-noprofiler.xml:ro

Recreate the container (``docker compose up -d``). The same renaming as above happens on
the first start.

License
*******

This software is licensed under the terms of the AGPLv3.
