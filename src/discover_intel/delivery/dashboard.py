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


def coverage_trends_data(conn: sqlite3.Connection,
                          window_start: str,
                          window_end: str) -> pd.DataFrame:
    """Per-lane distinct-entity counts in [window_start, window_end] and the
    prior equal-length window immediately before it. Returns:
    [lane, entity_count, prior_entity_count, delta].
    """
    # Compute prior window as the same duration immediately before this one.
    # Use SQLite datetime arithmetic: duration = end - start; prior_start = start - duration.
    df = pd.read_sql_query(
        """
        WITH lanes AS (
          SELECT taxonomy_id, label FROM taxonomy WHERE kind = 'lane'
        ),
        this_window AS (
          SELECT e.taxonomy_id, COUNT(DISTINCT e.entity) AS entity_count
          FROM item_entities e
          JOIN items i ON ('item:' || i.item_id) = e.source_key
          WHERE e.taxonomy_id LIKE 'lane:%'
            AND i.first_seen_at >= ? AND i.first_seen_at <= ?
          GROUP BY e.taxonomy_id
        ),
        prior_window AS (
          SELECT e.taxonomy_id, COUNT(DISTINCT e.entity) AS prior_count
          FROM item_entities e
          JOIN items i ON ('item:' || i.item_id) = e.source_key
          WHERE e.taxonomy_id LIKE 'lane:%'
            AND i.first_seen_at >= datetime(?, '-' ||
              CAST((julianday(?) - julianday(?)) * 86400 AS INTEGER) || ' seconds')
            AND i.first_seen_at < ?
          GROUP BY e.taxonomy_id
        )
        SELECT l.label AS lane,
          COALESCE(tw.entity_count, 0) AS entity_count,
          COALESCE(pw.prior_count, 0) AS prior_entity_count,
          COALESCE(tw.entity_count, 0) - COALESCE(pw.prior_count, 0) AS delta
        FROM lanes l
        LEFT JOIN this_window tw ON tw.taxonomy_id = l.taxonomy_id
        LEFT JOIN prior_window pw ON pw.taxonomy_id = l.taxonomy_id
        ORDER BY entity_count DESC
        """,
        conn,
        params=(window_start, window_end, window_start, window_end, window_start,
                window_start),
    )
    return df


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


_PLOTLY_TEMPLATE = "plotly_dark"
_ACCENT = "#F5A623"      # ET amber
_ACCENT_ALT = "#8B5CF6"  # violet for secondary series
_MUTED = "#6B7280"


def _system_status(conn: sqlite3.Connection) -> dict:
    """Compact status counters shown in the hero header."""
    def _c(sql: str, params: tuple = ()) -> int:
        row = conn.execute(sql, params).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    sources_enabled = _c("SELECT COUNT(*) FROM sources WHERE enabled = 1")
    items_24h = _c("SELECT COUNT(*) FROM items "
                   "WHERE first_seen_at >= datetime('now', '-24 hours')")
    obs_24h = _c("SELECT COUNT(*) FROM discover_articles "
                 "WHERE observed_at >= datetime('now', '-24 hours')")
    latest_ts_row = conn.execute(
        "SELECT MAX(scored_at) FROM topic_scores"
    ).fetchone()
    latest_ts = latest_ts_row[0] if latest_ts_row else None
    topics_publish = 0
    topics_watchlist = 0
    if latest_ts:
        topics_publish = _c(
            "SELECT COUNT(*) FROM topic_scores WHERE scored_at = ? AND tos >= 60",
            (latest_ts,),
        )
        topics_watchlist = _c(
            "SELECT COUNT(*) FROM topic_scores WHERE scored_at = ? AND tos BETWEEN 45 AND 59.999",
            (latest_ts,),
        )
    return {
        "sources_enabled": sources_enabled,
        "items_24h": items_24h,
        "obs_24h": obs_24h,
        "topics_publish": topics_publish,
        "topics_watchlist": topics_watchlist,
        "latest_scored_at": latest_ts or "never",
    }


def _render(db_path: str) -> None:
    """Streamlit render entry. Imports streamlit lazily so tests can import
    this module without spinning up Streamlit."""
    import plotly.express as px
    import streamlit as st

    from discover_intel import db as db_mod

    st.set_page_config(
        page_title="Discover Intel",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"About": "Discover Intelligence System - ET US Growth/SEO"},
    )

    # Global CSS: pane radius, muted table headers, tighter metric cards
    st.markdown(
        """
        <style>
          .block-container { padding-top: 2rem; padding-bottom: 3rem; }
          h1, h2, h3 { font-weight: 600; letter-spacing: -0.01em; }
          div[data-testid="stMetricValue"] { font-size: 2rem; font-weight: 600; }
          div[data-testid="stMetricLabel"] { color: #9AA0A6; font-size: 0.85rem;
              text-transform: uppercase; letter-spacing: 0.05em; }
          div[data-testid="stMetricDelta"] { font-size: 0.85rem; }
          .stTabs [data-baseweb="tab-list"] { gap: 1.5rem; }
          .stTabs [data-baseweb="tab"] { height: 3rem; font-size: 1rem;
              font-weight: 500; }
          .stTabs [aria-selected="true"] { color: #F5A623 !important; }
          .stDataFrame { border-radius: 8px; }
          .status-banner { background: linear-gradient(90deg, #1B2027 0%, #0E1117 100%);
              padding: 1.25rem 1.5rem; border-radius: 12px;
              border: 1px solid rgba(245,166,35,0.15); margin-bottom: 1.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # HERO HEADER
    st.markdown(
        "<h1 style='margin-bottom:0.25rem;'>"
        "<span style='color:#F5A623;'>Discover</span> Intelligence"
        "</h1>"
        "<p style='color:#9AA0A6; margin-top:0; font-size:1.05rem;'>"
        "US Google Discover -- topic opportunities, publisher pulse, "
        "and pre-publish readiness."
        "</p>",
        unsafe_allow_html=True,
    )

    conn = db_mod.connect(db_path)
    try:
        status = _system_status(conn)

        # Status strip (5 metrics)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Sources active", f"{status['sources_enabled']:,}")
        c2.metric("Items (24h)", f"{status['items_24h']:,}")
        c3.metric("Discover obs (24h)", f"{status['obs_24h']:,}")
        c4.metric("Topics >= publish", f"{status['topics_publish']:,}",
                  delta=f"{status['topics_watchlist']:,} on watchlist" if status['topics_watchlist'] else None,
                  delta_color="off")
        c5.metric("Last TOS run",
                  status["latest_scored_at"].split("T")[0] if status["latest_scored_at"] != "never" else "never",
                  delta=status["latest_scored_at"].split("T")[1].rstrip("Z") if status["latest_scored_at"] != "never" else None,
                  delta_color="off")

        st.markdown("<br/>", unsafe_allow_html=True)

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Opportunities", "Feed composition", "Competitor velocity",
            "Lane coverage", "Scorecard",
        ])

        # ---------- TAB 1: Opportunities ----------
        with tab1:
            st.subheader("Today's opportunities")
            st.caption("Latest scoring run: entities with TOS >= 45. "
                       "Watchlist = 45-59. Publish = 60+.")
            df = opportunities_data(conn, watchlist_threshold=45.0)
            if df.empty:
                st.info("No topic_scores yet. Run "
                        "`discover_intel build-topic-stats` then "
                        "`discover_intel tos` to populate this view.")
            else:
                # Metric cards summary
                total = len(df)
                pub = int((df["tos"] >= 60).sum())
                watch = total - pub
                m1, m2, m3 = st.columns(3)
                m1.metric("Total topics", f"{total:,}")
                m2.metric("Publish (>=60)", f"{pub:,}")
                m3.metric("Watchlist (45-59)", f"{watch:,}")

                # Score histogram
                fig = px.histogram(df, x="tos", nbins=20,
                                   title="TOS distribution",
                                   color_discrete_sequence=[_ACCENT],
                                   template=_PLOTLY_TEMPLATE)
                fig.update_layout(showlegend=False,
                                  margin={"t": 60, "b": 40, "l": 40, "r": 20})
                fig.add_vline(x=60, line_dash="dash", line_color="#EF4444",
                              annotation_text="publish >= 60")
                fig.add_vline(x=45, line_dash="dot", line_color=_MUTED,
                              annotation_text="watch 45+")
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("**Top topics** (click row to see evidence)")
                display_df = df[["entity", "tos", "suggested_format",
                                 "momentum", "headroom", "timing",
                                 "format_match", "lane_fit"]].copy()
                display_df["tos"] = display_df["tos"].round(1)
                for col in ("momentum", "headroom", "timing",
                            "format_match", "lane_fit"):
                    display_df[col] = display_df[col].round(2)
                st.dataframe(display_df, use_container_width=True, height=420)

                with st.expander("Evidence for top entity"):
                    if len(df) > 0:
                        import json as _json
                        top = df.iloc[0]
                        try:
                            ev = _json.loads(top["evidence_json"])
                            st.markdown(f"**{top['entity']}** - TOS {top['tos']:.1f}")
                            titles = ev.get("top_discover_titles", []) or []
                            if titles:
                                st.markdown("_Top Discover titles:_")
                                for t in titles[:3]:
                                    st.markdown(
                                        f"- {t.get('title', '?')} "
                                        f"_(host: {t.get('host', '?')}, "
                                        f"visibility: {t.get('visibility', 0):.0f})_"
                                    )
                            hosts = ev.get("competitor_hosts") or []
                            if hosts:
                                st.markdown(
                                    "_Competitor hosts:_ " + ", ".join(hosts[:10])
                                )
                            queries = ev.get("beat_queries") or []
                            if queries:
                                st.markdown(
                                    "_Beat queries firing:_ " + ", ".join(queries)
                                )
                        except Exception:
                            st.code(top["evidence_json"])

        # ---------- TAB 2: Feed composition ----------
        with tab2:
            st.subheader("Feed composition")
            st.caption("Where content is coming from and what's being rewarded.")
            hs, eff = feed_composition_data(conn)
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Items per host (last 24h)**")
                if hs.empty:
                    st.info("No items in the last 24h.")
                else:
                    fig = px.bar(hs.head(15), x="items_24h", y="host",
                                 orientation="h",
                                 color_discrete_sequence=[_ACCENT],
                                 template=_PLOTLY_TEMPLATE)
                    fig.update_layout(yaxis={"categoryorder": "total ascending"},
                                      margin={"t": 20, "b": 40, "l": 40, "r": 20},
                                      xaxis_title="Items (24h)",
                                      yaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)
            with col_b:
                st.markdown("**Per-post efficiency (avg Discover visibility)**")
                if eff.empty:
                    st.info("No matched observations yet -- run "
                            "`discover_intel match-outcomes` after tagger.")
                else:
                    fig = px.bar(eff.head(15), x="avg_visibility", y="host",
                                 orientation="h",
                                 color_discrete_sequence=[_ACCENT_ALT],
                                 template=_PLOTLY_TEMPLATE)
                    fig.update_layout(yaxis={"categoryorder": "total ascending"},
                                      margin={"t": 20, "b": 40, "l": 40, "r": 20},
                                      xaxis_title="Avg visibility",
                                      yaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)

        # ---------- TAB 3: Competitor velocity ----------
        with tab3:
            st.subheader("Competitor velocity")
            st.caption("Items/hour by publisher, last 7 days. "
                       "Spikes signal breaking-topic activity.")
            v = velocity_data(conn)
            if v.empty:
                st.info("No items in the last 7 days.")
            else:
                # Reduce visual noise: only top 12 hosts by total items
                top_hosts = (v.groupby("host")["item_count"].sum()
                             .nlargest(12).index.tolist())
                v_top = v[v["host"].isin(top_hosts)]
                fig = px.line(v_top, x="hour", y="item_count", color="host",
                              template=_PLOTLY_TEMPLATE)
                fig.update_layout(margin={"t": 20, "b": 40, "l": 40, "r": 20},
                                  xaxis_title="Hour (UTC)",
                                  yaxis_title="Items",
                                  legend={"orientation": "h",
                                          "yanchor": "top", "y": -0.2,
                                          "xanchor": "center", "x": 0.5})
                st.plotly_chart(fig, use_container_width=True)

        # ---------- TAB 4: Lane coverage ----------
        with tab4:
            st.subheader("Lane coverage")
            st.caption("Which lanes have activity vs which lanes are winning "
                       "Discover visibility.")
            pub, cap = lane_coverage_data(conn)
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Items published per lane**")
                if pub.empty:
                    st.info("No lane tags yet -- run "
                            "`discover_intel tag-entities`.")
                else:
                    fig = px.bar(pub, x="items", y="lane", orientation="h",
                                 color_discrete_sequence=[_ACCENT],
                                 template=_PLOTLY_TEMPLATE)
                    fig.update_layout(yaxis={"categoryorder": "total ascending"},
                                      margin={"t": 20, "b": 40, "l": 40, "r": 20},
                                      xaxis_title="Items", yaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)
            with col_b:
                st.markdown("**Discover visibility captured per lane**")
                if cap.empty:
                    st.info("No matched observations yet.")
                else:
                    fig = px.bar(cap, x="visibility", y="lane", orientation="h",
                                 color_discrete_sequence=[_ACCENT_ALT],
                                 template=_PLOTLY_TEMPLATE)
                    fig.update_layout(yaxis={"categoryorder": "total ascending"},
                                      margin={"t": 20, "b": 40, "l": 40, "r": 20},
                                      xaxis_title="Visibility captured",
                                      yaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)

        # ---------- TAB 5: Scorecard ----------
        with tab5:
            st.subheader("Scorecard")
            st.caption("Weekly measurement (Sprint 4). Latest available week + "
                       "coverage trends + ET conversion.")

            # Latest scorecard row if present
            latest_sc = conn.execute(
                "SELECT iso_week, digest_topics_count, market_precision, "
                "et_conversion_json, coverage_trends_json, computed_at "
                "FROM scorecards ORDER BY computed_at DESC LIMIT 1"
            ).fetchone()
            if latest_sc is None:
                st.info("No scorecards yet -- run "
                        "`discover_intel scorecard --db data\\warehouse.db`.")
            else:
                iso_week, topics, precision, et_json, cov_json, _ = latest_sc
                m1, m2, m3 = st.columns(3)
                m1.metric("ISO week", iso_week)
                m2.metric("Digest topics", f"{topics:,}")
                m3.metric(
                    "Market precision",
                    f"{precision:.1f}%" if precision is not None else "N/A",
                )

                # Coverage trends
                import json as _json
                cov = _json.loads(cov_json) if cov_json else []
                if cov:
                    import pandas as _pd
                    cov_df = _pd.DataFrame(cov).sort_values("entity_count",
                                                            ascending=True)
                    st.markdown("**Coverage trends** (this week vs prior)")
                    fig = px.bar(cov_df, x="entity_count", y="lane",
                                 orientation="h",
                                 color="delta", color_continuous_scale="RdYlGn",
                                 template=_PLOTLY_TEMPLATE)
                    fig.update_layout(margin={"t": 20, "b": 40, "l": 40, "r": 20},
                                      xaxis_title="Entity count",
                                      yaxis_title="",
                                      coloraxis_colorbar={"title": "Δ"})
                    st.plotly_chart(fig, use_container_width=True)

                # ET conversion breakout
                et = _json.loads(et_json) if et_json else {}
                st.markdown("---")
                st.markdown("**ET conversion** (GSC-based)")
                if not et.get("gsc_populated"):
                    st.warning(et.get("message",
                                      "GSC not populated. Enable the GSC job."))
                else:
                    ec1, ec2 = st.columns(2)
                    ec1.metric("On-digest avg impressions",
                               f"{int(et.get('on_digest_avg_impressions', 0)):,}")
                    ec1.metric("On-digest avg clicks",
                               f"{int(et.get('on_digest_avg_clicks', 0)):,}")
                    ec2.metric("Off-digest avg impressions",
                               f"{int(et.get('off_digest_avg_impressions', 0)):,}")
                    ec2.metric("Off-digest avg clicks",
                               f"{int(et.get('off_digest_avg_clicks', 0)):,}")

            st.markdown("---")
            st.markdown("**Historical market precision** "
                        "(last 7 days from live warehouse):")
            mp = market_precision_data(conn)
            if mp.empty:
                st.info("No digest history yet.")
            else:
                st.dataframe(mp, use_container_width=True)

        # Footer
        st.markdown("<br/>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='text-align:center; color:{_MUTED}; font-size:0.85rem;'>"
            f"Discover Intelligence - reading from <code>{db_path}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )
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
