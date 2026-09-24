"""S3-D-2 Streamlit dashboard — 5 tabs over the discover-intel warehouse.

Data-loader functions are pure functions of a sqlite3.Connection and are
tested independently. Streamlit rendering wraps them at run time.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def opportunities_data(conn: sqlite3.Connection,
                       watchlist_threshold: float = 45.0) -> pd.DataFrame:
    """Latest topic_scores at or above watchlist_threshold, sorted by TOS desc."""
    latest_at = conn.execute(
        "SELECT MAX(scored_at) FROM topic_scores"
    ).fetchone()[0]
    if latest_at is None:
        return pd.DataFrame(columns=[
            "entity", "tos", "suggested_format", "momentum", "headroom",
            "timing", "format_match", "lane_fit", "evidence_json",
        ])
    df = pd.read_sql_query(
        "SELECT entity, tos, suggested_format, momentum, headroom, timing, "
        "format_match, lane_fit, evidence_json "
        "FROM topic_scores "
        "WHERE scored_at = ? AND tos >= ? "
        "ORDER BY tos DESC",
        conn, params=(latest_at, watchlist_threshold),
    )
    return df


def feed_composition_data(conn: sqlite3.Connection
                          ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(host_share_24h, per_post_efficiency) for the Feed composition tab."""
    host_share = pd.read_sql_query(
        "SELECT host, COUNT(*) AS items_24h FROM items "
        "WHERE first_seen_at >= datetime('now', '-24 hours') "
        "GROUP BY host ORDER BY items_24h DESC LIMIT 30",
        conn,
    )
    efficiency = pd.read_sql_query(
        "SELECT i.host, "
        "COUNT(DISTINCT io.item_id) AS matched_items, "
        "AVG(o.visibility) AS avg_visibility "
        "FROM items i "
        "JOIN item_outcomes io ON io.item_id = i.item_id "
        "JOIN discover_articles o ON o.obs_id = io.obs_id "
        "GROUP BY i.host "
        "HAVING matched_items > 0 "
        "ORDER BY avg_visibility DESC LIMIT 30",
        conn,
    )
    return host_share, efficiency


def velocity_data(conn: sqlite3.Connection) -> pd.DataFrame:
    """Items/hour per host over last 7 days."""
    return pd.read_sql_query(
        "SELECT host, "
        "substr(first_seen_at, 1, 13) || ':00:00Z' AS hour, "
        "COUNT(*) AS item_count "
        "FROM items "
        "WHERE first_seen_at >= datetime('now', '-7 days') "
        "GROUP BY host, hour ORDER BY hour ASC, item_count DESC",
        conn,
    )


def lane_coverage_data(conn: sqlite3.Connection
                       ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(items_per_lane, visibility_per_lane) — filtered to lane taxonomy_ids."""
    published = pd.read_sql_query(
        "SELECT t.label AS lane, COUNT(DISTINCT e.source_key) AS items "
        "FROM item_entities e "
        "JOIN taxonomy t ON t.taxonomy_id = e.taxonomy_id "
        "WHERE t.kind = 'lane' "
        "GROUP BY t.label ORDER BY items DESC",
        conn,
    )
    captured = pd.read_sql_query(
        "SELECT t.label AS lane, "
        "COALESCE(SUM(o.visibility), 0.0) AS visibility "
        "FROM item_entities e "
        "JOIN taxonomy t ON t.taxonomy_id = e.taxonomy_id "
        "JOIN item_outcomes io ON io.item_id = substr(e.source_key, 6) "
        "JOIN discover_articles o ON o.obs_id = io.obs_id "
        "WHERE t.kind = 'lane' AND e.source_key LIKE 'item:%' "
        "GROUP BY t.label ORDER BY visibility DESC",
        conn,
    )
    return published, captured


def market_precision_data(conn: sqlite3.Connection) -> pd.DataFrame:
    """% of digest topics (last 7 days) that appeared in discover_articles within 48h.

    Returns columns: [scored_at_day, topics_count, hits_count, precision_pct]."""
    return pd.read_sql_query(
        """
        WITH digests AS (
          SELECT substr(scored_at, 1, 10) AS day, entity, MIN(scored_at) AS scored_at
          FROM topic_scores
          WHERE tos >= 60.0
            AND scored_at >= datetime('now', '-7 days')
          GROUP BY day, entity
        ),
        hits AS (
          SELECT d.day, d.entity,
            CASE WHEN EXISTS (
              SELECT 1 FROM discover_articles o
              WHERE o.observed_at BETWEEN d.scored_at
                AND datetime(d.scored_at, '+48 hours')
                AND o.title LIKE '%' || d.entity || '%'
            ) THEN 1 ELSE 0 END AS hit
          FROM digests d
        )
        SELECT day AS scored_at_day,
          COUNT(*) AS topics_count,
          SUM(hit) AS hits_count,
          ROUND(100.0 * SUM(hit) / NULLIF(COUNT(*), 0), 1) AS precision_pct
        FROM hits GROUP BY day ORDER BY day DESC
        """,
        conn,
    )


def et_conversion_data(conn: sqlite3.Connection) -> dict:
    """ET Discover conversion — compares ET articles matched vs unmatched to digest.

    Returns dict with 'gsc_populated' flag; when False, dashboard shows N/A message.
    """
    (n_gsc,) = conn.execute("SELECT COUNT(*) FROM gsc_discover").fetchone()
    if n_gsc == 0:
        return {"gsc_populated": False,
                "message": "GSC not populated -- run discover_intel gsc after "
                           "prerequisites are done. See README."}
    on_digest = pd.read_sql_query(
        "SELECT AVG(g.impressions) AS avg_imp, AVG(g.clicks) AS avg_clk "
        "FROM gsc_discover g "
        "JOIN items i ON i.canonical_url = g.page OR i.url = g.page "
        "JOIN item_outcomes io ON io.item_id = i.item_id "
        "JOIN discover_articles o ON o.obs_id = io.obs_id "
        "WHERE i.host = 'economictimes.indiatimes.com'",
        conn,
    )
    off_digest = pd.read_sql_query(
        "SELECT AVG(g.impressions) AS avg_imp, AVG(g.clicks) AS avg_clk "
        "FROM gsc_discover g "
        "LEFT JOIN items i ON i.canonical_url = g.page OR i.url = g.page "
        "WHERE i.host IS NULL OR i.host != 'economictimes.indiatimes.com'",
        conn,
    )
    return {"gsc_populated": True, "on_digest": on_digest, "off_digest": off_digest}


def _render(db_path: str) -> None:
    """Streamlit render entry. Imports streamlit lazily so tests can import
    this module without spinning up Streamlit."""
    import plotly.express as px
    import streamlit as st

    from discover_intel import db as db_mod

    st.set_page_config(page_title="Discover Intel", layout="wide")
    st.title("Discover Intelligence -- Sprint 3 Dashboard")

    conn = db_mod.connect(db_path)
    try:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Opportunities", "Feed composition", "Competitor velocity",
            "Lane coverage", "Scorecard",
        ])

        with tab1:
            st.subheader("Latest topic_scores (>=45)")
            df = opportunities_data(conn, watchlist_threshold=45.0)
            if df.empty:
                st.info("No topic_scores yet -- run `discover_intel tos` first.")
            else:
                st.dataframe(df, use_container_width=True)

        with tab2:
            st.subheader("Feed composition (last 24h)")
            hs, eff = feed_composition_data(conn)
            if hs.empty:
                st.info("No items yet.")
            else:
                st.plotly_chart(px.bar(hs, x="host", y="items_24h",
                                       title="Items per host (24h)"),
                                use_container_width=True)
            if not eff.empty:
                st.plotly_chart(
                    px.bar(eff, x="host", y="avg_visibility",
                           title="Avg visibility per matched item"),
                    use_container_width=True,
                )

        with tab3:
            st.subheader("Competitor velocity (last 7 days)")
            v = velocity_data(conn)
            if v.empty:
                st.info("No items yet.")
            else:
                st.plotly_chart(
                    px.line(v, x="hour", y="item_count", color="host",
                            title="Items/hour by host"),
                    use_container_width=True,
                )

        with tab4:
            st.subheader("Lane coverage")
            pub, cap = lane_coverage_data(conn)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Items published per lane**")
                if not pub.empty:
                    st.plotly_chart(px.bar(pub, x="lane", y="items"),
                                    use_container_width=True)
                else:
                    st.info("No lane tags yet.")
            with col2:
                st.markdown("**Discover visibility captured per lane**")
                if not cap.empty:
                    st.plotly_chart(px.bar(cap, x="lane", y="visibility"),
                                    use_container_width=True)
                else:
                    st.info("No matched observations yet.")

        with tab5:
            st.subheader("Scorecard (S4-early)")
            st.markdown("**Market precision** -- % of digest topics that "
                        "appeared in discover_articles within 48h.")
            mp = market_precision_data(conn)
            if mp.empty:
                st.info("No digest history yet.")
            else:
                st.dataframe(mp, use_container_width=True)
            st.markdown("---")
            st.markdown("**ET conversion** -- GSC-based measurement")
            et = et_conversion_data(conn)
            if not et.get("gsc_populated"):
                st.warning(et.get("message", "GSC not populated"))
            else:
                st.markdown("**On-digest averages:**")
                st.dataframe(et["on_digest"], use_container_width=True)
                st.markdown("**Off-digest averages:**")
                st.dataframe(et["off_digest"], use_container_width=True)
    finally:
        conn.close()


def main(args) -> int:
    """CLI: launches Streamlit as a subprocess."""
    import subprocess
    import sys
    dashboard_path = str(Path(__file__).resolve())
    port = getattr(args, "port", 8501) or 8501
    cmd = [sys.executable, "-m", "streamlit", "run", dashboard_path,
           "--server.port", str(port), "--", "--db", args.db]
    print(f"dashboard: launching streamlit on port {port}; "
          f"visit http://localhost:{port}/")
    return subprocess.call(cmd)


# Streamlit entry point (when invoked via `streamlit run dashboard.py`)
if __name__ == "__main__":
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--db", default="data/warehouse.db")
    _a, _ = _p.parse_known_args()
    _render(_a.db)
