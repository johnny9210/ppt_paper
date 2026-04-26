"""40 seed prompts for consulting-style slide generation.

Coverage matrix:
  - 8 layout types × 5 instances = 40 slides
  - Each layout spread across 5 firm-style themes (McKinsey blue / BCG green /
    Bain red / minimal white / editorial warm)
  - Diverse domains (finance, market entry, cost, vendors, customers, OKR, risk, growth)

Each seed = (id, layout_type, theme, domain, prompt).
Metadata captured for post-hoc stratified analysis (per probing experiment plan,
flat sample with rich metadata).
"""
from __future__ import annotations

# Common prompt scaffold — reused across seeds for consistency.
# Each layout-specific prompt fills in the body.
_SCAFFOLD = """Generate a single professional consulting slide image (1280×720 PNG).

{theme_directive}

Slide structure:
- Action title at top (declarative insight, 1-2 lines): "{action_title}"
{subtitle_line}
- Body (~75% of slide): {body_directive}
- Footer bottom-right: "Source: {source}" with page number "{page}"
- Typography: {typography}
- One clear insight, no decorative clutter. Avoid dense paragraphs."""

_THEMES = {
    "mckinsey_blue": {
        "directive": "Style: McKinsey-style. Background white. Accent color deep navy (#003B71). Generous white space. Clean professional feel.",
        "typography": "Georgia serif title, Arial sans-serif body labels, 2 fonts max",
    },
    "bcg_green": {
        "directive": "Style: BCG-style. Background white. Accent color BCG green (#00A651). Bold callouts. Clean modern feel.",
        "typography": "sans-serif throughout (Helvetica/Arial), 2 weights",
    },
    "bain_red": {
        "directive": "Style: Bain-style. Background white. Accent color Bain red (#CC0033). Selective emphasis with red highlights. Balanced density.",
        "typography": "Georgia title, Arial body, 2 fonts max",
    },
    "minimal_white": {
        "directive": "Style: minimalist. Background pure white. Single accent color charcoal (#1F2937). Extreme white space. Apple-keynote influence.",
        "typography": "sans-serif (Inter or Helvetica), single typeface, 2-3 weights",
    },
    "editorial_warm": {
        "directive": "Style: editorial. Background warm cream (#FAF7F0). Accent terracotta (#C2410C) and gold (#EAB308). Magazine-style hierarchy.",
        "typography": "serif title (Playfair or Georgia), sans body (Inter), 2 fonts",
    },
}


def _make(layout: str, theme: str, domain: str, page: int, action_title: str,
          subtitle: str, body: str, source: str) -> dict:
    t = _THEMES[theme]
    subtitle_line = f"- Optional subtitle below in lighter color: \"{subtitle}\"" if subtitle else ""
    prompt = _SCAFFOLD.format(
        theme_directive=t["directive"],
        action_title=action_title,
        subtitle_line=subtitle_line,
        body_directive=body,
        source=source,
        page=page,
        typography=t["typography"],
    )
    return {
        "id": f"{layout}_{theme}_{domain}",
        "layout": layout,
        "theme": theme,
        "domain": domain,
        "prompt": prompt,
    }


SEEDS: list[dict] = [
    # ────────────────── Marimekko / Mekko (5) ──────────────────
    _make("mekko", "mckinsey_blue", "finance",
        page=5,
        action_title="APAC retail drove 67% of FY2025 revenue growth, led by China and India",
        subtitle="Revenue contribution by region × product category",
        body="Marimekko chart with 4 regions on x-axis (APAC 45%, NAM 28%, EMEA 18%, LATAM 9%), each stacked into 3 product categories (Apparel, Electronics, Home). Each cell labeled with $B value (e.g., '$35.2B'). APAC region highlighted in deep navy, others in gray.",
        source="Internal financial data, FY2025"),
    _make("mekko", "bcg_green", "market_entry",
        page=12,
        action_title="Premium and Mid-tier segments justify 73% of next-year marketing spend",
        subtitle="Market size by segment × channel",
        body="Marimekko chart with 3 segments on x-axis (Premium 28%, Mid 45%, Value 27%), each stacked into 4 channels (Online, Retail, Wholesale, B2B). Each cell labeled with $M value. Premium and Mid columns highlighted in BCG green, Value in light gray.",
        source="Market sizing study, Q3 2025"),
    _make("mekko", "bain_red", "customer",
        page=8,
        action_title="Tier-1 customers contribute 64% of revenue from only 18% of accounts",
        subtitle="Account count × revenue contribution by customer tier",
        body="Marimekko chart, 3 tiers on x-axis (Tier-1 18%, Tier-2 35%, Tier-3 47%), stacked into 3 product lines. Tier-1 column in Bain red, others muted. Numeric labels in each cell.",
        source="CRM analysis, Dec 2025"),
    _make("mekko", "minimal_white", "industry",
        page=3,
        action_title="Healthcare and Tech industries together account for 58% of TAM",
        subtitle="Industry × buyer-persona TAM breakdown",
        body="Marimekko chart, 5 industries on x-axis (Healthcare 32%, Tech 26%, Finance 18%, Retail 14%, Other 10%), each stacked into 3 buyer personas (CXO, Director, Manager). Cells labeled with $B values. Charcoal accent.",
        source="TAM model v3, Jan 2026"),
    _make("mekko", "editorial_warm", "geography",
        page=7,
        action_title="European Q4 ad spend skewed 71% toward digital despite TV reach gains",
        subtitle="Ad spend by country × media channel",
        body="Marimekko chart, 4 countries on x-axis (UK 32%, DE 28%, FR 22%, IT 18%), stacked into 3 channels (Digital, TV, Print). Numeric labels with €M values. Terracotta and gold accents.",
        source="Nielsen ad spend tracker, Q4 2025"),

    # ────────────────── 2×2 Matrix (5) ──────────────────
    _make("matrix_2x2", "bcg_green", "portfolio",
        page=10,
        action_title="Three product lines are in the Stars quadrant, justifying 70% of capex",
        subtitle="BCG Growth-Share Matrix",
        body="Large 2×2 matrix. X-axis: 'Market Share' (Low → High). Y-axis: 'Market Growth Rate' (Low → High). Quadrants labeled Question Marks (top-left), Stars (top-right), Dogs (bottom-left), Cash Cows (bottom-right). 8 product circles (ProdA-H) sized by revenue, distributed: 3 in Stars (BCG green, ProdA largest with glow), 2 in Cash Cows (lighter green), 2 in Question Marks (gray), 1 in Dogs.",
        source="Strategic portfolio review, Q4 2025"),
    _make("matrix_2x2", "mckinsey_blue", "risk",
        page=14,
        action_title="Two risk events fall in the High-Impact / High-Likelihood quadrant",
        subtitle="Risk register prioritization",
        body="2×2 matrix. X-axis: 'Likelihood' (Low → High). Y-axis: 'Impact' (Low → High). 9 risk events as labeled circles. 2 in top-right (red), 3 in top-left (yellow), 2 in bottom-right (orange), 2 in bottom-left (gray). Each circle labeled R1-R9 with event name.",
        source="Enterprise risk assessment, 2025"),
    _make("matrix_2x2", "bain_red", "competition",
        page=6,
        action_title="Vendor B owns the High-Capability / High-Stability sweet spot",
        subtitle="Competitive landscape map",
        body="2×2 matrix. X-axis: 'Stability' (Low → High). Y-axis: 'Capability' (Low → High). 6 vendors as circles sized by market share. Vendor B in top-right in Bain red (largest), others in gray.",
        source="Vendor evaluation, Dec 2025"),
    _make("matrix_2x2", "minimal_white", "investment",
        page=11,
        action_title="Quadrant analysis isolates 4 high-priority investments",
        subtitle="Strategic investment prioritization",
        body="2×2 matrix. X-axis: 'Effort' (Low → High). Y-axis: 'Strategic Value' (Low → High). 12 initiatives as labeled circles. 4 in top-left (high value, low effort) highlighted in charcoal (priority), others lighter.",
        source="Strategic planning, FY2026"),
    _make("matrix_2x2", "editorial_warm", "feature",
        page=4,
        action_title="Six features rank as 'must-have' on importance and feasibility",
        subtitle="Feature prioritization matrix",
        body="2×2 matrix. X-axis: 'Feasibility' (Low → High). Y-axis: 'User Importance' (Low → High). 14 features as circles. 6 in top-right (terracotta, must-have), 4 in top-left (gold, ideas-to-validate), 3 in bottom-right (light), 1 in bottom-left.",
        source="UX research synthesis, 2025"),

    # ────────────────── Waterfall chart (5) ──────────────────
    _make("waterfall", "mckinsey_blue", "finance",
        page=9,
        action_title="Operating margin expanded 320 bps driven primarily by COGS reduction",
        subtitle="FY2024 → FY2025 margin bridge",
        body="Waterfall chart with 6 bars: Start FY2024 (12.4%), +COGS reduction (+180 bps, navy), +Pricing power (+90 bps, navy), -SG&A increase (-40 bps, gray), +Mix shift (+90 bps, navy), End FY2025 (15.6%). Each bar labeled with bps value. Connecting dotted lines.",
        source="Financial review, Q4 2025"),
    _make("waterfall", "bcg_green", "growth",
        page=15,
        action_title="Revenue grew $4.2B from $12.8B base, 60% from cross-sell expansion",
        subtitle="Revenue bridge $12.8B → $17.0B",
        body="Waterfall chart with 7 bars: Start (gray), +New customers (+$1.4B, BCG green), +Cross-sell (+$2.5B, BCG green darker), +Price (+$0.6B, green), -Churn (-$0.3B, light red), +FX (+$0.2B, gray), End (gray). Annotation arrow on cross-sell highlighting 60%.",
        source="Revenue analysis, FY2025"),
    _make("waterfall", "bain_red", "cost",
        page=11,
        action_title="$120M cost reduction unlocks 4-pp margin gain by year 2",
        subtitle="Cost-out program contribution",
        body="Waterfall chart with 6 bars showing cost reduction: Start ($820M), -Procurement (-$45M, Bain red), -Headcount (-$40M, Bain red), -Tech consolidation (-$25M, red), -Real estate (-$10M, lighter red), End ($700M, gray). All in $M.",
        source="Operations review, 2025"),
    _make("waterfall", "minimal_white", "saas",
        page=7,
        action_title="ARR grew 28% with $32M net new contributions despite $14M churn",
        subtitle="Annual recurring revenue bridge",
        body="Waterfall chart 6 bars. Start ARR $48M, +New ($28M, charcoal), +Expansion ($18M, dark gray), -Contraction (-$8M, light), -Churn (-$6M, light), End ARR $80M. All bar values labeled.",
        source="ARR snapshot, Dec 2025"),
    _make("waterfall", "editorial_warm", "ebitda",
        page=5,
        action_title="EBITDA bridge reveals 11% YoY uplift from operational excellence",
        subtitle="EBITDA $128M → $142M decomposition",
        body="Waterfall chart with 6 bars. Start (gray), +Volume (+$8M, terracotta), +Price (+$11M, terracotta), -Inflation (-$6M, gold), +Mix (+$3M, terracotta), -OpEx (-$2M, light), End (gray). Bars labeled with $M.",
        source="Q4 2025 financials"),

    # ────────────────── Harvey ball comparison table (5) ──────────────────
    _make("harvey_table", "bain_red", "vendors",
        page=8,
        action_title="Vendor B leads on 4 of 5 evaluation criteria, justifying selection",
        subtitle="Vendor scoring matrix",
        body="Comparison table with 5 row criteria (Total Cost, Implementation speed, Feature completeness, Vendor stability, Customer references) and 3 columns (Vendor A, Vendor B, Vendor C). Each cell contains a Harvey ball (filled circle 0/25/50/75/100%) plus brief justification text. Vendor B column highlighted in Bain red border.",
        source="Vendor RFP scoring, Dec 2025"),
    _make("harvey_table", "mckinsey_blue", "options",
        page=12,
        action_title="Option C scores highest on weighted criteria across 6 dimensions",
        subtitle="Strategic option comparison",
        body="Comparison table 6 rows (Cost, Speed, Risk, Strategic fit, Talent need, Reversibility) × 4 options (A, B, C, D). Harvey balls in each cell with justification text. Option C column highlighted with deep navy border. Rows weighted (column on left shows weight 5%, 15%, 20%, 25%, 20%, 15%).",
        source="Strategic option assessment, 2025"),
    _make("harvey_table", "bcg_green", "frameworks",
        page=4,
        action_title="Framework Y delivers superior outcomes on 4 of 6 capabilities",
        subtitle="Capability framework comparison",
        body="Comparison table 6 rows (Scalability, Cost efficiency, Vendor lock-in risk, Time to market, Talent availability, Total ecosystem) × 3 frameworks (X, Y, Z). Harvey balls + short justifications. Framework Y column highlighted in BCG green.",
        source="Architecture review, 2025"),
    _make("harvey_table", "minimal_white", "tools",
        page=6,
        action_title="Tool 2 is best for 5 of 7 use cases reviewed",
        subtitle="Tool capability matrix",
        body="Comparison table 7 rows (Use case 1-7) × 3 tools (Tool 1, 2, 3). Harvey balls + brief notes. Tool 2 column subtly emphasized with charcoal border.",
        source="Tooling evaluation, 2025"),
    _make("harvey_table", "editorial_warm", "candidates",
        page=10,
        action_title="Candidate B exceeds requirements on culture and execution dimensions",
        subtitle="Senior leadership candidate scoring",
        body="Comparison table 5 rows (Vision, Execution, Culture fit, Domain depth, Reference quality) × 3 candidates (A, B, C). Harvey balls + interview justifications. Candidate B highlighted with terracotta border.",
        source="Executive search panel, Q4 2025"),

    # ────────────────── Action title + bar chart (5) ──────────────────
    _make("bar_chart", "mckinsey_blue", "performance",
        page=2,
        action_title="Q4 revenue exceeded plan by 14% in 7 of 10 business units",
        subtitle="Revenue vs plan by business unit",
        body="Vertical bar chart with 10 bars (BU1-BU10). Each bar shows actual revenue with horizontal target line overlay. Bars exceeding target in deep navy, missing in gray. Y-axis $M, x-axis BU labels. Data labels above each bar.",
        source="Q4 2025 performance review"),
    _make("bar_chart", "bcg_green", "growth",
        page=8,
        action_title="Customer LTV grew 31% YoY across all 5 cohorts",
        subtitle="LTV by acquisition cohort",
        body="Vertical bar chart 5 cohorts (2021, 2022, 2023, 2024, 2025), each with two bars (Year 1 LTV vs Year 3 LTV). All bars in BCG green shades. Data labels in $.",
        source="Cohort LTV model, Dec 2025"),
    _make("bar_chart", "bain_red", "cost",
        page=11,
        action_title="3 cost categories represent 78% of total addressable savings",
        subtitle="Savings opportunity by cost category",
        body="Horizontal bar chart, 7 cost categories (Procurement, Workforce, Tech, Real estate, T&E, Marketing, Other) sorted descending by savings $M. Top 3 in Bain red, others gray. Pareto-style cumulative line overlay reaching 78%.",
        source="Cost diagnostic, 2025"),
    _make("bar_chart", "minimal_white", "engagement",
        page=5,
        action_title="Engagement dropped 22% on weekends across the user base",
        subtitle="Daily active users by day-of-week",
        body="Vertical bar chart 7 bars (Mon-Sun), DAU on y-axis. Mon-Fri bars uniform charcoal, Sat-Sun lighter. Annotation arrow showing 22% gap.",
        source="Product analytics, Nov 2025"),
    _make("bar_chart", "editorial_warm", "satisfaction",
        page=7,
        action_title="NPS rose to 67 driven by support quality improvements",
        subtitle="NPS by quarter, last 8 quarters",
        body="Vertical bar chart 8 bars (Q1 2024 - Q4 2025). All bars in terracotta. Trend line overlay in gold. Latest bar (Q4 2025 = 67) labeled and highlighted.",
        source="Customer survey panel, 2025"),

    # ────────────────── Action title + line chart (5) ──────────────────
    _make("line_chart", "mckinsey_blue", "trend",
        page=3,
        action_title="Monthly active users tripled from 1.2M to 3.6M over 24 months",
        subtitle="MAU trajectory, Jan 2024 - Dec 2025",
        body="Line chart with single trend line over 24 months. Y-axis MAU in millions, x-axis months. Inflection points annotated (e.g., 'Q3 2024 launch', 'Q1 2025 paid acquisition'). Deep navy line, light grid.",
        source="Product analytics, Dec 2025"),
    _make("line_chart", "bcg_green", "competition",
        page=14,
        action_title="Our market share grew while top 2 competitors lost ground",
        subtitle="Market share by quarter, top 4 players",
        body="Line chart with 4 lines over 12 quarters. Our line (BCG green, bold) trending up from 18% to 27%. Two competitors trending down. Y-axis 0-40%, legend on right.",
        source="Industry tracker, 2025"),
    _make("line_chart", "bain_red", "performance",
        page=9,
        action_title="Cost-to-serve dropped below industry benchmark in Q3 2025",
        subtitle="Cost per transaction, our co. vs benchmark",
        body="Line chart with 2 lines over 8 quarters. Our cost (Bain red, bold) descending from $4.20 to $2.80. Industry benchmark (gray dashed) flat at $3.10. Crossover point annotated.",
        source="Operations benchmarking, Q3 2025"),
    _make("line_chart", "minimal_white", "saas",
        page=2,
        action_title="ARR growth accelerated to 43% YoY by FY2025-end",
        subtitle="ARR growth rate trajectory",
        body="Line chart with single line over 10 quarters showing growth rate %. Y-axis 0-50%. Latest 3 points charcoal solid, earlier 7 points lighter. Annotation 'inflection at Q2 2024'.",
        source="ARR tracking, Q4 2025"),
    _make("line_chart", "editorial_warm", "audience",
        page=6,
        action_title="Newsletter subscribers reached 1.4M, growing 8% MoM",
        subtitle="Subscriber count, last 18 months",
        body="Line chart over 18 months. Single terracotta line trending up. Gold dotted overlay shows monthly growth rate. Latest data point (1.4M, +8% MoM) labeled.",
        source="Audience analytics, Dec 2025"),

    # ────────────────── Process flow / consulting timeline (5) ──────────────────
    _make("process_flow", "mckinsey_blue", "transformation",
        page=4,
        action_title="Five-phase transformation roadmap delivers value in 18 months",
        subtitle="Digital transformation phases, Q1 2026 - Q2 2027",
        body="Horizontal process flow with 5 phases left-to-right (Diagnose, Design, Pilot, Scale, Sustain). Each phase shown as a chevron pointing right with phase name + 2-3 key activities + timeline (e.g., 'Q1 2026'). Connecting arrows. Deep navy theme.",
        source="Transformation PMO, 2026"),
    _make("process_flow", "bcg_green", "go_to_market",
        page=13,
        action_title="Six-step GTM motion converts 22% of qualified leads",
        subtitle="Sales pipeline workflow",
        body="Horizontal process flow with 6 stages (Awareness, Interest, Qualification, Evaluation, Decision, Onboarding). Each stage as a rounded box with conversion % below. Boxes connected with arrows showing drop-off. BCG green for top of funnel, darker for bottom.",
        source="Sales operations, 2025"),
    _make("process_flow", "bain_red", "ops",
        page=11,
        action_title="Optimized order-to-cash cycle compresses to 4.2 days from 9.1",
        subtitle="O2C process redesign",
        body="Horizontal process flow 5 steps (Order, Validate, Pack, Ship, Invoice). Each step labeled with redesigned cycle time. Total at right: '4.2 days (was 9.1)'. Bain red for accelerated steps, gray for stable.",
        source="Operations re-engineering, 2025"),
    _make("process_flow", "minimal_white", "product",
        page=8,
        action_title="Product launch follows a 4-phase decision gate process",
        subtitle="New product launch process",
        body="Vertical process flow with 4 phases top-to-bottom (Concept, Validation, Build, Launch). Each phase has a decision diamond gate (Go/No-go) below. Charcoal monochrome.",
        source="Product operating model, 2025"),
    _make("process_flow", "editorial_warm", "campaign",
        page=5,
        action_title="Marketing campaign cycle spans 6 stages over 8 weeks",
        subtitle="Campaign development workflow",
        body="Horizontal flow with 6 stages (Brief, Creative, Approval, Production, Launch, Measure). Each stage shown as numbered circle + label + duration. Connecting line. Terracotta circles, gold connecting lines.",
        source="Marketing ops handbook, 2025"),

    # ────────────────── Pyramid summary (Minto-style) (5) ──────────────────
    _make("pyramid", "mckinsey_blue", "executive_summary",
        page=1,
        action_title="Three strategic priorities support our 2026 growth ambition",
        subtitle="Executive summary",
        body="Pyramid structure: top tier with 1 main message ('Achieve $200M ARR by FY2026'). Middle tier with 3 supporting pillars ('Expand APAC presence', 'Launch Tier-2 products', 'Build B2B partnerships'). Bottom tier with 9 sub-arguments (3 per pillar). Connected by lines. Deep navy theme.",
        source="2026 strategy planning"),
    _make("pyramid", "bcg_green", "recommendation",
        page=18,
        action_title="Recommendation: invest $40M in Asia expansion, supported by 3 imperatives",
        subtitle="Investment recommendation pyramid",
        body="Pyramid with 1 recommendation at top ('$40M Asia expansion'). 3 imperatives in middle ('Establish Singapore hub', 'Build local sales team', 'Tailor product for APAC SMEs'). 6-9 evidence points at bottom. BCG green theme.",
        source="Strategic recommendation, Q4 2025"),
    _make("pyramid", "bain_red", "thesis",
        page=2,
        action_title="Thesis: customer experience is the highest-leverage growth driver",
        subtitle="Investment thesis structure",
        body="Pyramid: top thesis statement, 3 supporting claims (CX impact on retention, CX impact on referrals, CX impact on pricing power), 6-9 data points at base. Bain red highlighting at top.",
        source="Investment committee deck, 2025"),
    _make("pyramid", "minimal_white", "argument",
        page=4,
        action_title="The case for restructuring rests on 3 compounding factors",
        subtitle="Strategic argument hierarchy",
        body="Pyramid 3 tiers: top conclusion, 3 mid-tier reasons, 6 supporting facts at base. Charcoal lines, monochrome.",
        source="Strategy review, 2025"),
    _make("pyramid", "editorial_warm", "narrative",
        page=3,
        action_title="Brand story rests on three values: craftsmanship, trust, and continuity",
        subtitle="Brand pyramid",
        body="Pyramid with 1 essence statement at top ('Timeless craftsmanship'), 3 brand values in middle (Craftsmanship, Trust, Continuity), 6-9 expressions at base. Terracotta and gold tones, serif typography.",
        source="Brand strategy, 2026"),
]


def list_seeds() -> list[dict]:
    return SEEDS


def by_layout() -> dict[str, list[dict]]:
    """Group seeds by layout type."""
    out: dict[str, list[dict]] = {}
    for s in SEEDS:
        out.setdefault(s["layout"], []).append(s)
    return out


if __name__ == "__main__":
    print(f"Total seeds: {len(SEEDS)}")
    print("\nBy layout:")
    for layout, seeds in by_layout().items():
        print(f"  {layout}: {len(seeds)}")
    print("\nBy theme:")
    by_theme: dict[str, int] = {}
    for s in SEEDS:
        by_theme[s["theme"]] = by_theme.get(s["theme"], 0) + 1
    for theme, n in sorted(by_theme.items()):
        print(f"  {theme}: {n}")
