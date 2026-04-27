import os
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

client = FalkorDB(
    host=os.getenv('FALKORDB_HOST'),
    port=int(os.getenv('FALKORDB_PORT')),
    password=os.getenv('FALKORDB_PASSWORD'),
    username=os.getenv('FALKORDB_USERNAME')
)

graph = client.select_graph('resonance_framework')

def run(query, params={}):
    graph.query(query, params)

print("Building Three Forces Framework graph...")

# ── FORCES ──────────────────────────────────────────────
print("Creating Force nodes...")
run("MERGE (f:Force {name: 'Execution'}) SET f.definition = 'How the organization builds and delivers value. Combines Product, Operations, and Integration layers.'")
run("MERGE (f:Force {name: 'Marketing'}) SET f.definition = 'How the organization communicates its value and identity. Answers: What do we say we are, and does reality support that claim?'")
run("MERGE (f:Force {name: 'Revenue'}) SET f.definition = 'How the organization generates, sustains, and grows financial resources. Answers: How do we make money, and is the full revenue system coherent?'")

# ── SUB-LAYERS ───────────────────────────────────────────
print("Creating SubLayer nodes...")

# Execution sub-layers
run("MERGE (s:SubLayer {name: 'Product'}) SET s.force = 'Execution'")
run("MERGE (s:SubLayer {name: 'Operations'}) SET s.force = 'Execution'")
run("MERGE (s:SubLayer {name: 'Integration'}) SET s.force = 'Execution'")

# Marketing has no sub-layers

# Revenue sub-layers
run("MERGE (s:SubLayer {name: 'Revenue_Architecture'}) SET s.force = 'Revenue'")
run("MERGE (s:SubLayer {name: 'Sales_Motion'}) SET s.force = 'Revenue', s.note = 'Downstream symptom layer — surfaces where Execution and Marketing dysfunction lands. Exception: founder-led sales bottlenecks can be root cause.'")
run("MERGE (s:SubLayer {name: 'Financial_Coherence'}) SET s.force = 'Revenue'")

# ── FORCE → SUBLAYER RELATIONSHIPS ───────────────────────
print("Creating Force→SubLayer relationships...")
run("MATCH (f:Force {name: 'Execution'}), (s:SubLayer {name: 'Product'}) MERGE (f)-[:HAS_SUBLAYER]->(s)")
run("MATCH (f:Force {name: 'Execution'}), (s:SubLayer {name: 'Operations'}) MERGE (f)-[:HAS_SUBLAYER]->(s)")
run("MATCH (f:Force {name: 'Execution'}), (s:SubLayer {name: 'Integration'}) MERGE (f)-[:HAS_SUBLAYER]->(s)")
run("MATCH (f:Force {name: 'Revenue'}), (s:SubLayer {name: 'Revenue_Architecture'}) MERGE (f)-[:HAS_SUBLAYER]->(s)")
run("MATCH (f:Force {name: 'Revenue'}), (s:SubLayer {name: 'Sales_Motion'}) MERGE (f)-[:HAS_SUBLAYER]->(s)")
run("MATCH (f:Force {name: 'Revenue'}), (s:SubLayer {name: 'Financial_Coherence'}) MERGE (f)-[:HAS_SUBLAYER]->(s)")

# ── EXECUTION METRICS ────────────────────────────────────
print("Creating Execution metrics...")

execution_metrics = [
    # Product layer
    ("Product-Purpose Alignment", "Product", "Does what they're building serve the stated core purpose?"),
    ("Product Vision Clarity", "Product", "Is the product vision well-articulated and understood?"),
    ("Roadmap-Capacity Match", "Product", "Can the team realistically deliver the planned roadmap on timeline?"),
    ("Product Decision Structure", "Product", "Who decides what gets built? How fast can decisions be made?"),
    ("Product-Market Competitive Fit", "Product", "Are they building what market signals indicate is needed?"),
    # Operations layer
    ("Organizational Structure Clarity", "Operations", "Are reporting lines, roles, and responsibilities clear?"),
    ("Hiring-Roadmap Alignment", "Operations", "Are hiring plans aligned with execution needs?"),
    ("Process Documentation", "Operations", "Are key processes documented and owned by specific people?"),
    ("Operational Capacity Planning", "Operations", "Will operations keep up with projected growth?"),
    ("Cross-functional Resource Conflicts", "Operations", "Are teams competing for shared resources?"),
    # Integration layer
    ("Resource Allocation Coherence", "Integration", "Do resource decisions align across product and operations?"),
    ("Decision Velocity", "Integration", "Can the organization make and execute decisions quickly?"),
    ("Strategic Alignment", "Integration", "Are different departments executing a unified strategy?"),
]

for name, sublayer, definition in execution_metrics:
    run(
        "MERGE (m:Metric {name: $name}) SET m.definition = $definition, m.force = 'Execution', m.sub_layer = $sublayer",
        {'name': name, 'definition': definition, 'sublayer': sublayer}
    )
    run(
        "MATCH (s:SubLayer {name: $sublayer}), (m:Metric {name: $name}) MERGE (s)-[:HAS_METRIC]->(m)",
        {'sublayer': sublayer, 'name': name}
    )

# ── MARKETING METRICS ────────────────────────────────────
print("Creating Marketing metrics...")

marketing_metrics = [
    ("Positioning Consistency", "Is the message the same across all channels — website, deck, sales materials?"),
    ("Promise-Reality Gaps", "Can they actually deliver what marketing promises?"),
    ("Audience Segmentation Clarity", "Do they know exactly who they serve? Is it consistent everywhere?"),
    ("Value Proposition Coherence", "Are buyer needs and product benefits clearly aligned?"),
    ("Messaging-Product Alignment", "Is marketing highlighting features and capabilities that actually exist?"),
    ("Transformation Claims vs. Delivery Capability", "Is the transformation promise supported by evidence of delivery capability?"),
    ("Sales Activation of Marketing Messaging", "Does the marketing message actually show up in sales conversations and materials, or does the handoff from marketing to sales break down?"),
]

for name, definition in marketing_metrics:
    run(
        "MERGE (m:Metric {name: $name}) SET m.definition = $definition, m.force = 'Marketing', m.sub_layer = 'none'",
        {'name': name, 'definition': definition}
    )
    run(
        "MATCH (f:Force {name: 'Marketing'}), (m:Metric {name: $name}) MERGE (f)-[:HAS_METRIC]->(m)",
        {'name': name}
    )

# ── REVENUE METRICS ──────────────────────────────────────
print("Creating Revenue metrics...")

revenue_metrics = [
    # Revenue Architecture
    ("Revenue Model Alignment", "Revenue_Architecture", "Does the way they make money support or undermine the stated mission?"),
    ("Pricing-Value Coherence", "Revenue_Architecture", "Is the price point appropriate for the target audience and value delivered?"),
    ("Revenue-Mission Integrity", "Revenue_Architecture", "Does the revenue model exclude or include the stated target market?"),
    ("Revenue Model Sustainability", "Revenue_Architecture", "Can the current model fund the organization's next phase?"),
    # Sales Motion
    ("Sales Process Clarity", "Sales_Motion", "Is the path from first contact to closed deal defined, documented, and consistently followed?"),
    ("Sales-to-Close Friction", "Sales_Motion", "Where do deals stall, prospects go cold, or conversations lose momentum?"),
    ("Pipeline and Conversion Visibility", "Sales_Motion", "Does the organization have meaningful insight into conversion rates and pipeline health?"),
    # Financial Coherence
    ("Unit Economics Sustainability", "Financial_Coherence", "Are CAC, LTV, and burn rates healthy?"),
    ("Financial Model Coherence", "Financial_Coherence", "Are financial projections supported by current growth reality and market assumptions?"),
    ("Revenue Metrics vs. Targets", "Financial_Coherence", "How do actual MRR, ARR, ARPU, and churn compare to stated targets?"),
]

for name, sublayer, definition in revenue_metrics:
    run(
        "MERGE (m:Metric {name: $name}) SET m.definition = $definition, m.force = 'Revenue', m.sub_layer = $sublayer",
        {'name': name, 'definition': definition, 'sublayer': sublayer}
    )
    run(
        "MATCH (s:SubLayer {name: $sublayer}), (m:Metric {name: $name}) MERGE (s)-[:HAS_METRIC]->(m)",
        {'sublayer': sublayer, 'name': name}
    )

# ── CROSS-FORCE PAIRS ────────────────────────────────────
print("Creating cross-force pair relationships...")
run("MATCH (e:Force {name: 'Execution'}), (m:Force {name: 'Marketing'}) MERGE (e)-[:PAIRS_WITH {pair_name: 'Execution-Marketing'}]->(m)")
run("MATCH (e:Force {name: 'Execution'}), (r:Force {name: 'Revenue'}) MERGE (e)-[:PAIRS_WITH {pair_name: 'Execution-Revenue'}]->(r)")
run("MATCH (m:Force {name: 'Marketing'}), (r:Force {name: 'Revenue'}) MERGE (m)-[:PAIRS_WITH {pair_name: 'Marketing-Revenue'}]->(r)")

# ── DOWNSTREAM RELATIONSHIPS ─────────────────────────────
print("Creating downstream relationships...")
run("MATCH (s:SubLayer {name: 'Sales_Motion'}), (e:Force {name: 'Execution'}) MERGE (s)-[:DOWNSTREAM_OF]->(e)")
run("MATCH (s:SubLayer {name: 'Sales_Motion'}), (m:Force {name: 'Marketing'}) MERGE (s)-[:DOWNSTREAM_OF]->(m)")

# ── VERIFICATION ─────────────────────────────────────────
print("\nVerifying graph...")
result = graph.query("MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY type")
for record in result.result_set:
    print(f"  {record[0]}: {record[1]} nodes")

result = graph.query("MATCH ()-[r]->() RETURN type(r) as rel, count(r) as count ORDER BY rel")
for record in result.result_set:
    print(f"  {record[0]}: {record[1]} relationships")

print("\nFramework graph build complete.")