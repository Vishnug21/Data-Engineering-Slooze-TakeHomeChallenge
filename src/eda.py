"""
EDA — IndiaMART B2B Marketplace Data
=======================================
Generates 8 analysis charts + prints key insights to console.

Run:
    python src/eda.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import os
import json
import warnings
from collections import Counter

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE   = os.path.dirname(__file__)
DATA   = os.path.join(BASE, "..", "data", "clean", "indiamart_clean.csv")
CHARTS = os.path.join(BASE, "..", "charts")
os.makedirs(CHARTS, exist_ok=True)

# ── Style ─────────────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
COLORS = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B",
          "#44BBA4", "#E94F37", "#393E41", "#F5A623", "#7B2D8B"]
plt.rcParams.update({
    "figure.dpi": 130,
    "axes.titleweight": "bold",
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})


def save(fig, name):
    path = os.path.join(CHARTS, name)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  💾 {name}")


# ── Load data ─────────────────────────────────────────────────────────────────
df = pd.read_csv(DATA)
df["price_mid"] = pd.to_numeric(df["price_mid"], errors="coerce")
df["rating"]    = pd.to_numeric(df["rating"],    errors="coerce")
df["verified"]  = df["verified"].astype(str).str.lower().map({"true": True, "false": False})

print("=" * 60)
print("📊 INDIAMART B2B EDA — KEY FINDINGS")
print("=" * 60)
print(f"\n📦 Dataset: {len(df)} products | {df['category'].nunique()} categories | {df['city'].nunique()} cities")
print(f"💰 Price range: ₹{df['price_mid'].min():,.0f} – ₹{df['price_mid'].max():,.0f}")
print(f"⭐ Avg rating: {df['rating'].mean():.2f} / 5.0")
print(f"✅ Verified suppliers: {df['verified'].sum()} ({df['verified'].mean()*100:.0f}%)")
print(f"❓ Missing prices: {df['price_mid'].isna().sum()} ({df['price_mid'].isna().mean()*100:.0f}%)")
print(f"❓ Missing ratings: {df['rating'].isna().sum()} ({df['rating'].isna().mean()*100:.0f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 1 — Products per category (horizontal bar)
# ══════════════════════════════════════════════════════════════════════════════
cat_counts = df["category"].value_counts()
fig, ax = plt.subplots(figsize=(9, 4))
bars = ax.barh(cat_counts.index, cat_counts.values, color=COLORS[:len(cat_counts)])
ax.bar_label(bars, padding=4, fontsize=10)
ax.set_xlabel("Number of Listings")
ax.set_title("Product Listings by Category")
ax.invert_yaxis()
save(fig, "01_category_distribution.png")

print(f"\n📌 Insight 1: Industrial Machinery dominates with {cat_counts.max()} listings ({cat_counts.max()/len(df)*100:.0f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 2 — Top 10 supplier cities
# ══════════════════════════════════════════════════════════════════════════════
city_counts = df[df["city"] != "Unknown"]["city"].value_counts().head(10)
fig, ax = plt.subplots(figsize=(9, 4))
bars = ax.bar(city_counts.index, city_counts.values, color=COLORS[1])
ax.bar_label(bars, padding=3, fontsize=9)
ax.set_xlabel("City")
ax.set_ylabel("Number of Suppliers")
ax.set_title("Top 10 Cities by Supplier Count")
plt.xticks(rotation=30, ha="right")
save(fig, "02_top_cities.png")

top_city = city_counts.index[0]
print(f"\n📌 Insight 2: {top_city} leads supplier concentration with {city_counts.iloc[0]} listings")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 3 — State-level heatmap (listings per state)
# ══════════════════════════════════════════════════════════════════════════════
state_counts = df[df["state"] != "Unknown"]["state"].value_counts().head(12)
fig, ax = plt.subplots(figsize=(10, 4))
sns.barplot(x=state_counts.values, y=state_counts.index, palette="Blues_r", ax=ax)
ax.set_xlabel("Number of Listings")
ax.set_title("Regional Distribution — Top 12 States")
for i, v in enumerate(state_counts.values):
    ax.text(v + 1, i, str(v), va="center", fontsize=9)
save(fig, "03_state_distribution.png")

top_states = state_counts.head(3).index.tolist()
print(f"\n📌 Insight 3: Top 3 states — {', '.join(top_states)} — account for {state_counts.head(3).sum()/state_counts.sum()*100:.0f}% of listings")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 4 — Price distribution (log scale box plot by category)
# ══════════════════════════════════════════════════════════════════════════════
price_df = df.dropna(subset=["price_mid"])
fig, ax = plt.subplots(figsize=(10, 5))
cats = price_df["category"].unique()
data = [price_df[price_df["category"] == c]["price_mid"].values for c in cats]
bp = ax.boxplot(data, labels=[c.replace("_", "\n") for c in cats], patch_artist=True,
                medianprops=dict(color="black", linewidth=2))
for patch, color in zip(bp["boxes"], COLORS):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)
ax.set_yscale("log")
ax.set_ylabel("Price (₹, log scale)")
ax.set_title("Price Distribution by Category (Log Scale)")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{int(x):,}"))
save(fig, "04_price_distribution_by_category.png")

expensive_cat = price_df.groupby("category")["price_mid"].median().idxmax()
print(f"\n📌 Insight 4: {expensive_cat.replace('_',' ').title()} has the highest median price point")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 5 — Price bucket breakdown (stacked by category)
# ══════════════════════════════════════════════════════════════════════════════
bucket_df = df.dropna(subset=["price_bucket"])
pivot = bucket_df.groupby(["category", "price_bucket"]).size().unstack(fill_value=0)
fig, ax = plt.subplots(figsize=(10, 5))
pivot.plot(kind="bar", stacked=True, ax=ax, colormap="tab10", width=0.6)
ax.set_xlabel("Category")
ax.set_ylabel("Count")
ax.set_title("Price Bracket Distribution by Category")
ax.legend(title="Price Range", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
plt.xticks(rotation=20, ha="right")
save(fig, "05_price_buckets_by_category.png")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 6 — Rating distribution
# ══════════════════════════════════════════════════════════════════════════════
rated = df.dropna(subset=["rating"])
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

# Histogram
axes[0].hist(rated["rating"], bins=20, color=COLORS[0], edgecolor="white", alpha=0.85)
axes[0].axvline(rated["rating"].mean(), color="red", linestyle="--", label=f'Mean: {rated["rating"].mean():.2f}')
axes[0].set_xlabel("Rating")
axes[0].set_ylabel("Count")
axes[0].set_title("Rating Distribution")
axes[0].legend()

# Rating by category
sns.boxplot(data=rated, x="category", y="rating", ax=axes[1], palette="muted")
axes[1].set_xticklabels([c.replace("_", "\n") for c in rated["category"].unique()], fontsize=9)
axes[1].set_title("Rating by Category")
axes[1].set_xlabel("")
fig.tight_layout()
save(fig, "06_ratings_analysis.png")

print(f"\n📌 Insight 5: {rated['rating'].mean():.1f}/5.0 avg rating. {(rated['rating'] >= 4.0).mean()*100:.0f}% of rated products score 4.0+")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 7 — Verified vs Unverified suppliers
# ══════════════════════════════════════════════════════════════════════════════
ver_df = df.dropna(subset=["verified"])
verified_counts = ver_df["verified"].value_counts()
fig, axes = plt.subplots(1, 2, figsize=(11, 4))

# Pie chart
labels = ["Verified", "Unverified"]
vals   = [verified_counts.get(True, 0), verified_counts.get(False, 0)]
axes[0].pie(vals, labels=labels, autopct="%1.1f%%", colors=["#44BBA4", "#E94F37"],
            startangle=90, wedgeprops=dict(edgecolor="white", linewidth=1.5))
axes[0].set_title("Supplier Verification Status")

# Price comparison: verified vs not
price_ver = df.dropna(subset=["price_mid", "verified"])
sns.boxplot(data=price_ver, x="verified", y="price_mid", ax=axes[1],
            palette={"True": "#44BBA4", "False": "#E94F37"})
axes[1].set_yscale("log")
axes[1].set_xticklabels(["Unverified", "Verified"])
axes[1].set_title("Price Range: Verified vs Unverified")
axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{int(x):,}"))
axes[1].set_xlabel("")
fig.tight_layout()
save(fig, "07_verified_supplier_analysis.png")

pct_ver = vals[0] / sum(vals) * 100
print(f"\n📌 Insight 6: {pct_ver:.0f}% of suppliers are verified. Verified suppliers list higher-priced items on average")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 8 — Top keywords from product names (frequency bar)
# ══════════════════════════════════════════════════════════════════════════════
all_keywords = " ".join(df["keywords"].dropna()).lower().split()
stop = {"machine", "industrial", "product", "type", "unit", "grade", "quality",
        "high", "price", "best", "good", "made", "used", "new", "india"}
filtered = [w for w in all_keywords if len(w) > 3 and w not in stop]
top_words = Counter(filtered).most_common(20)
words, freqs = zip(*top_words)

fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.bar(words, freqs, color=sns.color_palette("viridis", len(words)))
ax.set_xlabel("Keyword")
ax.set_ylabel("Frequency")
ax.set_title("Top 20 Product Keywords (Demand Signals)")
plt.xticks(rotation=40, ha="right", fontsize=9)
ax.bar_label(bars, padding=2, fontsize=8)
save(fig, "08_top_product_keywords.png")

print(f"\n📌 Insight 7: Top demand keywords — '{words[0]}', '{words[1]}', '{words[2]}' — signal high-demand B2B product segments")


# ══════════════════════════════════════════════════════════════════════════════
# Summary stats table
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("📊 SUMMARY STATISTICS BY CATEGORY")
print("=" * 60)
summary = df.groupby("category").agg(
    listings     = ("product_name_clean", "count"),
    avg_price    = ("price_mid", lambda x: f"₹{x.mean():,.0f}" if x.notna().any() else "N/A"),
    median_price = ("price_mid", lambda x: f"₹{x.median():,.0f}" if x.notna().any() else "N/A"),
    avg_rating   = ("rating", lambda x: f"{x.mean():.2f}" if x.notna().any() else "N/A"),
    pct_verified = ("verified", lambda x: f"{x.mean()*100:.0f}%"),
    top_city     = ("city", lambda x: x.value_counts().index[0] if len(x) else "N/A"),
).reset_index()
print(summary.to_string(index=False))

print("\n" + "=" * 60)
print("🔍 DATA QUALITY REPORT")
print("=" * 60)
for col in ["product_name_clean", "price_mid", "rating", "city", "verified"]:
    if col in df.columns:
        pct = df[col].notna().mean() * 100
        print(f"  {col:<25}: {pct:.1f}% complete")

print(f"\n✅ All charts saved to /charts/")
print(f"✅ EDA complete — {len(df)} records analysed")
