"""
Slooze Supply Chain Data Dashboard
===================================
Interactive multi-source B2B marketplace analysis with:
- Real-time supplier risk scoring
- Data quality metrics
- Anomaly detection
- Supply chain intelligence
- Multi-platform comparisons

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import json
from datetime import datetime

st.set_page_config(
    page_title="Slooze Supply Chain Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { padding: 2rem; }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ── Load Data ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    """Load combined dataset."""
    try:
        df = pd.read_csv("data/combined_raw.csv")
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

df = load_data()

if df is None:
    st.error("Could not load data. Please ensure data/combined_raw.csv exists.")
    st.stop()

# ── Header ─────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📊 Slooze Supply Chain Intelligence")
    st.markdown("**Multi-source B2B marketplace analysis platform**")
with col2:
    st.metric("Total Records", len(df))

st.divider()

# ── Sidebar Navigation ─────────────────────────────────────────────────────────
page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Supplier Map", "Categories", "Anomalies", "Supply Chain Intel", "Quality Report"]
)

# ── PAGE 1: OVERVIEW ───────────────────────────────────────────────────────────
if page == "Overview":
    st.header("Data Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Products", len(df))
    with col2:
        st.metric("Data Sources", df['source'].nunique())
    with col3:
        st.metric("Categories", df['category'].nunique() if 'category' in df.columns else 0)
    with col4:
        st.metric("Suppliers", df['supplier_name'].nunique() if 'supplier_name' in df.columns else 0)

    st.divider()

    # Source breakdown
    col1, col2 = st.columns(2)

    with col1:
        source_dist = df['source'].value_counts()
        fig = go.Figure(data=[go.Pie(labels=source_dist.index, values=source_dist.values)])
        fig.update_layout(title="Data Distribution by Source", height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if 'category' in df.columns:
            cat_dist = df['category'].value_counts()
            fig = go.Figure(data=[go.Bar(x=cat_dist.index, y=cat_dist.values)])
            fig.update_layout(title="Products by Category", height=400)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Sample Data")
    st.dataframe(df[['product_name', 'supplier_name', 'category', 'source']].head(10), use_container_width=True)

# ── PAGE 2: SUPPLIER MAP ──────────────────────────────────────────────────────
elif page == "Supplier Map":
    st.header("Supplier Geographic Distribution")

    STATE_COORDS = {
        "Gujarat": (22.26, 71.19), "Maharashtra": (19.75, 75.71),
        "West Bengal": (22.99, 87.85), "Haryana": (29.06, 76.09),
        "Uttar Pradesh": (26.85, 80.95), "Punjab": (31.15, 75.34),
        "Rajasthan": (27.02, 74.22), "Tamil Nadu": (11.13, 78.66),
        "Karnataka": (15.32, 75.71), "Delhi": (28.70, 77.10),
        "Andhra Pradesh": (15.91, 79.74), "Telangana": (18.11, 79.02),
        "Madhya Pradesh": (22.97, 78.66), "Odisha": (20.95, 85.10),
        "Jharkhand": (23.61, 85.28), "Bihar": (25.10, 85.31),
        "Himachal Pradesh": (31.10, 77.17), "Uttarakhand": (30.07, 79.09),
        "Goa": (15.30, 74.12), "Assam": (26.14, 92.94),
    }
    INTL_COORDS = {
        "Guangdong": (23.13, 113.26), "Singapore": (1.35, 103.82),
        "Shanghai": (31.23, 121.47), "Shandong": (36.34, 118.15),
        "Beijing": (39.90, 116.41),
    }

    state_col = "location/state" if "location/state" in df.columns else "location_state"
    location_counts = df[state_col].value_counts().reset_index()
    location_counts.columns = ["location", "count"]

    domestic = location_counts[location_counts["location"].isin(STATE_COORDS)]
    international = location_counts[location_counts["location"].isin(INTL_COORDS)]
    total_mapped = domestic["count"].sum() + international["count"].sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Indian States", len(domestic), f"{domestic['count'].sum()} suppliers")
    with col2:
        st.metric("International Locations", len(international), f"{international['count'].sum()} suppliers")
    with col3:
        pct = int(domestic["count"].sum() / total_mapped * 100) if total_mapped else 0
        st.metric("Domestic %", f"{pct}%", "of mapped suppliers")

    st.divider()

    # Build map data
    map_rows = []
    for _, row in domestic.iterrows():
        lat, lon = STATE_COORDS[row["location"]]
        map_rows.append({"location": row["location"], "count": row["count"],
                         "lat": lat, "lon": lon, "region": "India"})
    for _, row in international.iterrows():
        if row["location"] in INTL_COORDS:
            lat, lon = INTL_COORDS[row["location"]]
            map_rows.append({"location": row["location"], "count": row["count"],
                             "lat": lat, "lon": lon, "region": "International"})

    map_df = pd.DataFrame(map_rows)

    if not map_df.empty:
        fig = px.scatter_geo(
            map_df, lat="lat", lon="lon",
            size="count", color="region",
            hover_name="location", hover_data={"count": True, "lat": False, "lon": False},
            size_max=50,
            color_discrete_map={"India": "#4361ee", "International": "#f72585"},
            title="Supplier Concentration by Location",
            projection="natural earth",
        )
        fig.update_geos(
            showcountries=True, countrycolor="lightgrey",
            showcoastlines=True, coastlinecolor="lightgrey",
            showland=True, landcolor="#f8f9fa",
            center={"lat": 22, "lon": 82}, projection_scale=3,
        )
        fig.update_layout(height=500, margin={"r": 0, "t": 40, "l": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Indian States")
        fig2 = px.bar(
            domestic.sort_values("count", ascending=True).tail(10),
            x="count", y="location", orientation="h",
            color="count", color_continuous_scale="Blues",
            labels={"count": "Suppliers", "location": "State"},
        )
        fig2.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("International Presence")
        if not international.empty:
            fig3 = px.bar(
                international.sort_values("count", ascending=False),
                x="location", y="count",
                color="count", color_continuous_scale="Reds",
                labels={"count": "Suppliers", "location": "Location"},
            )
            fig3.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No international suppliers in dataset.")

    st.divider()
    st.subheader("Supply Chain Risk: Concentration Analysis")
    top_state = domestic.iloc[0] if not domestic.empty else None
    if top_state is not None:
        top_pct = int(top_state["count"] / domestic["count"].sum() * 100)
        st.warning(
            f"**Geographic concentration risk:** {top_state['location']} accounts for "
            f"{top_pct}% of all domestic suppliers. Over-reliance on a single state "
            f"creates supply chain vulnerability to regional disruptions."
        )

# ── PAGE 3: CATEGORIES ────────────────────────────────────────────────────────
elif page == "Categories":
    st.header("Category Analysis")

    if 'category' in df.columns:
        col1, col2 = st.columns(2)

        with col1:
            cat_counts = df['category'].value_counts()
            fig = go.Figure(data=[go.Bar(x=cat_counts.index, y=cat_counts.values)])
            fig.update_layout(title="Products per Category", height=400)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Category by source
            cat_source = pd.crosstab(df['category'], df['source'])
            fig = go.Figure(data=[
                go.Bar(name=col, x=cat_source.index, y=cat_source[col])
                for col in cat_source.columns
            ])
            fig.update_layout(title="Categories by Source", height=400)
            st.plotly_chart(fig, use_container_width=True)

# ── PAGE 3: ANOMALIES ──────────────────────────────────────────────────────────
elif page == "Anomalies":
    st.header("Data Anomalies & Quality Flags")

    anomalies = []

    # Check for missing critical fields
    critical_fields = ['product_name', 'category']
    for field in critical_fields:
        if field in df.columns:
            missing = df[field].isna().sum()
            if missing > 0:
                anomalies.append({
                    "Type": "Missing Field",
                    "Field": field,
                    "Count": missing,
                    "Percentage": f"{(missing/len(df)*100):.1f}%"
                })

    # Check for duplicate product names
    dupes = df[df.duplicated(subset=['product_name'], keep=False)]
    if len(dupes) > 0:
        anomalies.append({
            "Type": "Duplicate Products",
            "Field": "product_name",
            "Count": len(dupes),
            "Percentage": f"{(len(dupes)/len(df)*100):.1f}%"
        })

    if anomalies:
        anomaly_df = pd.DataFrame(anomalies)
        st.dataframe(anomaly_df, use_container_width=True)

        st.divider()
        st.subheader("Quality Score by Source")

        quality_by_source = {}
        for source in df['source'].unique():
            source_df = df[df['source'] == source]
            completeness = source_df[critical_fields].notna().mean().mean() * 100
            quality_by_source[source] = completeness

        fig = go.Figure(data=[go.Bar(
            x=list(quality_by_source.keys()),
            y=list(quality_by_source.values())
        )])
        fig.update_layout(title="Data Completeness Score by Source", yaxis_title="Completeness %")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("No critical anomalies detected!")

# ── PAGE 4: SUPPLY CHAIN INTEL ─────────────────────────────────────────────────
elif page == "Supply Chain Intel":
    st.header("Supply Chain Intelligence")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Data Sources", df['source'].nunique())
        st.caption("Number of B2B marketplaces")

    with col2:
        if 'category' in df.columns:
            st.metric("Market Segments", df['category'].nunique())
            st.caption("Product categories tracked")

    with col3:
        unique_suppliers = df['supplier_name'].nunique()
        st.metric("Unique Suppliers", unique_suppliers)
        st.caption("Total suppliers identified")

    st.divider()

    st.subheader("Cross-Platform Analysis")

    if 'category' in df.columns:
        source_cat = pd.crosstab(df['source'], df['category'])
        st.dataframe(source_cat, use_container_width=True)

        st.caption("Products by marketplace and category - useful for comparative analysis")

# ── PAGE 5: QUALITY REPORT ─────────────────────────────────────────────────────
elif page == "Quality Report":
    st.header("Data Quality Report")

    st.subheader("Data Quality Metrics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Overall Completeness", f"{(df.notna().mean().mean() * 100):.1f}%")
    with col2:
        st.metric("Duplicate Rows", df.duplicated().sum())
    with col3:
        st.metric("Data Sources", df['source'].nunique())

    st.divider()

    # AI Enrichment section
    ai_progress_file = "data/ai_enrichment_progress.json"
    if os.path.exists(ai_progress_file):
        with open(ai_progress_file) as f:
            ai_data = json.load(f)

        enriched_rows = [v for v in ai_data.values() if v.get("ai_product_type")]
        st.subheader(f"AI Enrichment — Qwen 2.5 7B (Local)")
        st.caption(f"{len(enriched_rows)} of 236 IndiaMART rows enriched with AI-extracted fields")

        col1, col2, col3, col4 = st.columns(4)
        ai_df = pd.DataFrame(enriched_rows)
        with col1:
            filled = ai_df["ai_product_type"].notna().sum()
            st.metric("Product Type", f"{filled}", "fields extracted")
        with col2:
            filled = ai_df["ai_material"].notna().sum()
            st.metric("Material", f"{filled}", "fields extracted")
        with col3:
            filled = ai_df["ai_use_case"].notna().sum()
            st.metric("Use Case", f"{filled}", "fields extracted")
        with col4:
            filled = ai_df["ai_business_role"].notna().sum()
            st.metric("Business Role", f"{filled}", "fields extracted")

        st.divider()

        # Before/After comparison
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Before AI Enrichment (IndiaMART)**")
            before = pd.DataFrame({
                "Field": ["ai_product_type", "ai_material", "ai_use_case", "ai_business_role"],
                "Completeness": ["0%", "0%", "0%", "0%"]
            })
            st.dataframe(before, use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**After AI Enrichment (Qwen 2.5 7B)**")
            after_rows = []
            for field in ["ai_product_type", "ai_material", "ai_use_case", "ai_business_role"]:
                pct = int(ai_df[field].notna().sum() / 236 * 100) if not ai_df.empty else 0
                after_rows.append({"Field": field, "Completeness": f"{pct}%"})
            st.dataframe(pd.DataFrame(after_rows), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**Sample AI Extracted Data**")
        sample = pd.DataFrame([
            {"product_name": name, **vals}
            for name, vals in list(ai_data.items())[:10]
            if vals.get("ai_product_type")
        ])
        if not sample.empty:
            st.dataframe(sample, use_container_width=True, hide_index=True)
    else:
        st.info("AI enrichment not yet run. Start LM Studio with Qwen 2.5 7B and run: `python src/ai_enrichment.py`")

    st.divider()
    st.subheader("Field Completeness — All 138 Columns")
    completeness = {col: f"{(df[col].notna().sum() / len(df) * 100):.1f}%" for col in df.columns}
    completeness_df = pd.DataFrame(list(completeness.items()), columns=["Field", "Completeness"])
    st.dataframe(completeness_df.sort_values("Completeness", ascending=False), use_container_width=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.markdown("""
---
**Slooze Data Engineering Challenge** | Multi-source B2B marketplace analysis
Built with Streamlit | Data: IndiaMART + TradeIndia | Total Records: 584
""")
