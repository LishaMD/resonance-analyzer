"""
orchestrator.py — Resonance Analyzer Pipeline Orchestrator
Coherynce / The Resonance Field LLC

Replaces n8n for Pass 1A + Pass 1B + Pass 1C + Pass 2 orchestration.
Run from Terminal: python orchestrator.py --client_id YOUR_CLIENT_ID

Before running each session:
  1. Make sure your Flask extraction service is running (python app.py)
  2. Make sure ngrok is running and pointing to Flask (ngrok http 5000)
  3. Update NGROK_URL in your .env file to the current ngrok public URL
"""

import os
import json
import uuid
import argparse
import requests
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ── Environment variables ─────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NGROK_URL         = os.environ["NGROK_URL"]
SUPABASE_URL      = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY      = os.environ.get("SUPABASE_SERVICE_KEY", "")
AIRTABLE_TOKEN    = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID  = os.environ.get("AIRTABLE_BASE_ID", "")
AIRTABLE_EVIDENCE_TABLE = os.environ.get("AIRTABLE_EVIDENCE_TABLE", "Evidence Items")
AIRTABLE_PATTERNS_TABLE = os.environ.get("AIRTABLE_PATTERNS_TABLE", "Cross-Force Patterns")

CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ── Prompt templates ──────────────────────────────────────────────────────────
# These are your finalized prompts loaded as strings.
# Template variables are filled at runtime via .replace() before each API call.
# Pass 1A/B/C variables: {{purpose}} {{vision}} {{objectives}} {{documents_text}}
# Pass 2 variables:      {{pass1_evidence_json}} {{assembled_document_text}}

PASS1A_TEMPLATE = 'EXECUTION FORCE ANALYSIS PROMPT\n================================\nFile: /prompts/pass1_execution_force.txt\nPass: 1-A of 3 (Execution)\n\nYou are a business coherence analyst trained in the Coherynce Three Forces Framework.\n\nYour task in this pass is to extract ALL potentially relevant evidence about the EXECUTION FORCE only.\nDo not analyze Marketing or Revenue in this pass — those run in separate calls.\n\n===================\nEXECUTION FORCE DEFINITION\n===================\n\nThe Execution Force represents how the organization builds and delivers value. It combines:\n\n- PRODUCT LAYER: What they\'re building, roadmap priorities, product-purpose alignment\n- OPERATIONS LAYER: Team structure, hiring, processes, capacity, resource allocation\n- INTEGRATION: How product development and operations work together to deliver\n\n===================\nFRAMEWORK METRICS\n===================\n\nPRODUCT LAYER:\n1. Product-Purpose Alignment: Does what they\'re building serve the stated core purpose?\n2. Product Vision Clarity: Is the product vision well-articulated and understood?\n3. Roadmap-Capacity Match: Can the team realistically deliver the planned roadmap on timeline?\n4. Product Decision Structure: Who decides what gets built? How fast can decisions be made?\n5. Product-Market Competitive Fit: Are they building what market signals indicate is needed?\n\nOPERATIONS LAYER:\n6. Organizational Structure Clarity: Are reporting lines, roles, and responsibilities clear?\n7. Hiring-Roadmap Alignment: Are hiring plans aligned with execution needs?\n8. Process Documentation: Are key processes documented and owned by specific people?\n9. Operational Capacity Planning: Will operations keep up with projected growth?\n10. Cross-functional Resource Conflicts: Are teams competing for shared resources?\n\nINTEGRATION LAYER:\n11. Resource Allocation Coherence: Do resource decisions align across product and operations?\n12. Decision Velocity: Can the organization make and execute decisions quickly?\n13. Strategic Alignment: Are different departments executing a unified strategy?\n\n===================\nCLIENT CONTEXT (provided separately)\n===================\n\nCore Purpose: {{purpose}}\nVision (3-year): {{vision}}\nTop Objectives: {{objectives}}\n\nUse this context to assess alignment:\n- Product-Purpose Alignment: Compare roadmap priorities against {{purpose}}\n- Strategic Alignment: Do execution decisions serve {{objectives}}?\n- Vision Clarity: Does the product roadmap move toward {{vision}}?\n\n===================\nCRITICAL INSTRUCTIONS\n===================\n\n1. EVIDENCE REQUIREMENTS:\n   - Extract SPECIFIC evidence with exact quotes from documents\n   - Cite source document AND precise location (page number, slide number, tab name, section heading)\n   - Every finding must be traceable to source material\n   - NEVER invent quotes or evidence not present in documents\n   - Surface ALL potentially relevant evidence — do not filter by significance; Elisha makes significance judgments in review\n\n2. CONFIDENCE LEVELS:\n   - high: Direct evidence with explicit data points, clear quotes, or documented decisions\n   - medium: Strong inference based on multiple indirect signals or patterns\n   - low: Weak signal, speculation, or requires assumption\n\n3. FINDING TYPES:\n   - strength: Something working well that should be protected or leveraged\n   - gap: Clear misalignment, missing element, or dysfunction causing harm\n   - warning: Emerging issue not yet critical but trending negative\n\n4. BUSINESS IMPACT:\n   - For gaps/warnings: Explain what could go wrong or is already going wrong\n   - For strengths: Explain why this matters and how it creates advantage\n   - Be specific: "Wasting engineering resources on features the target market doesn\'t need" not "This could be better"\n\n5. LOOK FOR CONTRADICTIONS:\n   - Documents saying different things (deck vs. roadmap, org chart vs. hiring plan)\n   - Claims vs. reality (stated capacity vs. planned roadmap scope)\n   - Internal inconsistency (purpose statement vs. execution priorities)\n\n6. QUALITY OVER QUANTITY:\n   - Better to have 5-7 high-confidence findings than 20 speculative ones\n   - If a metric cannot be assessed due to missing data, note: "Cannot assess — insufficient data in documents"\n\n7. SUB-LAYER TAGGING:\n   - Every finding must be tagged to one sub-layer: "Product" or "Operations"\n   - Use "Product" for metrics 1-5, "Operations" for metrics 6-10, either is acceptable for metrics 11-13 based on primary evidence source\n\n8. FINANCIAL DATA:\n   - Flag any evidence items touching financial data with requires_validation: true\n\n===================\nOUTPUT FORMAT — REQUIRED JSON STRUCTURE\n===================\n\nReturn ONLY valid JSON. No markdown, no preamble, no explanation.\n\n[\n  {\n    "id": "exec_001",\n    "force": "Execution",\n    "sub_layer": "Product | Operations",\n    "finding_type": "strength | gap | warning",\n    "confidence": "high | medium | low",\n    "finding_text": "Concise description of what you observed (2-3 sentences maximum)",\n    "framework_metric": "Must match one of the 13 metrics listed above exactly",\n    "source_document": "exact filename",\n    "source_location": "page / slide / tab / section heading",\n    "supporting_quote": "Exact text from document (15 words maximum)",\n    "business_impact": "Why this matters — what could go wrong or is going wrong (1-2 sentences)",\n    "analysis": "Your interpretation connecting evidence to framework metric (1-2 sentences)",\n    "requires_validation": false\n  }\n]\n\nREQUIRED FIELDS (all must be present):\n- id: Format as "exec_001", "exec_002", etc. (sequential)\n- force: Always "Execution" in this prompt\n- sub_layer: Must be "Product" or "Operations" — never null for Execution items\n- finding_type: Must be "gap", "strength", or "warning"\n- confidence: Must be "high", "medium", or "low"\n- finding_text: Clear, specific observation\n- framework_metric: Must match one of the 13 metrics listed above exactly\n- source_document: Exact filename from documents provided\n- source_location: Precise location within document\n- supporting_quote: Brief verbatim quote (not paraphrased; 15 words max)\n- business_impact: Consequences or strategic importance\n- analysis: Your reasoning connecting evidence to metric\n- requires_validation: true only for financial evidence; false otherwise\n\n===================\nFEW-SHOT EXAMPLES\n===================\n\nEXAMPLE 1 — GAP (High Confidence):\n{\n  "id": "exec_001",\n  "force": "Execution",\n  "sub_layer": "Product",\n  "finding_type": "gap",\n  "confidence": "high",\n  "finding_text": "Roadmap shows 8 enterprise features planned over 6 months while stated purpose targets small nonprofits who typically do not need or cannot afford enterprise capabilities.",\n  "framework_metric": "Product-Purpose Alignment",\n  "source_document": "product_roadmap.xlsx",\n  "source_location": "Q2 and Q3 tabs, feature priority list",\n  "supporting_quote": "Q2: Enterprise SSO (SAML 2.0). Q3: Multi-tenant security, Admin permission controls",\n  "business_impact": "Engineering resources being spent building features the target market neither needs nor values, creating product-market misalignment and wasted development capacity.",\n  "analysis": "Complete directional mismatch — every planned feature serves enterprise buyers; zero features address small nonprofit needs like simplicity or affordability.",\n  "requires_validation": false\n}\n\nEXAMPLE 2 — STRENGTH (High Confidence):\n{\n  "id": "exec_002",\n  "force": "Execution",\n  "sub_layer": "Operations",\n  "finding_type": "strength",\n  "confidence": "high",\n  "finding_text": "Customer onboarding process is exceptionally well-documented with a clear 5-step workflow, time estimates for each step, and defined ownership for each activity.",\n  "framework_metric": "Process Documentation",\n  "source_document": "customer_onboarding_process.docx",\n  "source_location": "Full document, steps 1-5",\n  "supporting_quote": "Step 1: Kickoff call (45 min) — Sarah leads. Step 2: Data mapping (60 min)",\n  "business_impact": "Creates scalable foundation for consistent customer success, predictable capacity planning, and smooth team transitions.",\n  "analysis": "This level of operational maturity is unusual at this stage and represents a key asset for scaling.",\n  "requires_validation": false\n}\n\nEXAMPLE 3 — WARNING (Medium Confidence):\n{\n  "id": "exec_003",\n  "force": "Execution",\n  "sub_layer": "Operations",\n  "finding_type": "warning",\n  "confidence": "medium",\n  "finding_text": "Customer Success team approaching capacity limit based on current growth trajectory. Currently 47 customers with 1 CS person; financial model projects 4-5 new customers per month.",\n  "framework_metric": "Operational Capacity Planning",\n  "source_document": "org_chart.pptx + financial_model.xlsx",\n  "source_location": "Org chart shows 1 CS role / Financial model tab \'Growth Projections\'",\n  "supporting_quote": "Current state: 47 active customers, Sarah (solo CS). Projection: 4-5 new customers monthly",\n  "business_impact": "Will hit 100% capacity in 3-4 months if growth continues at projected rate. Risk of declining service quality and churn.",\n  "analysis": "Forward-looking concern based on growth rate calculation. Suggests need to hire CS #2 by Q1 to stay ahead of capacity crunch.",\n  "requires_validation": false\n}\n\n===================\nDOCUMENTS TO ANALYZE\n===================\n\n{{documents_text}}\n\n===================\nRETURN JSON ONLY — NO OTHER TEXT\n===================\n'

PASS1B_TEMPLATE = 'MARKETING FORCE ANALYSIS PROMPT\n================================\nFile: /prompts/pass1_marketing_force.txt\nPass: 1-B of 3 (Marketing)\n\nYou are a business coherence analyst trained in the Coherynce Three Forces Framework.\n\nYour task in this pass is to extract ALL potentially relevant evidence about the MARKETING FORCE only.\nDo not analyze Execution or Revenue in this pass — those run in separate calls.\n\n===================\nMARKETING FORCE DEFINITION\n===================\n\nThe Marketing Force represents how the organization communicates its value and identity to the world.\nIt answers: "What do we say we are, and does reality support that claim?"\n\nMarketing is a singular diagnostic force — it has no internal sub-layers. All Marketing findings use sub_layer: null.\n\n===================\nFRAMEWORK METRICS\n===================\n\n1. Positioning Consistency: Is the message the same across all channels (website, deck, sales materials)?\n\n2. Promise-Reality Gaps: Can they actually deliver what marketing promises?\n\n3. Audience Segmentation Clarity: Do they know exactly who they serve? Is it consistent everywhere?\n\n4. Value Proposition Coherence: Are buyer needs and product benefits clearly aligned?\n\n5. Messaging-Product Alignment: Is marketing highlighting features and capabilities that actually exist?\n\n6. Transformation Claims vs. Delivery Capability: Is the "emotional arc" or transformation promise supported by evidence of delivery?\n\n7. Sales Activation of Marketing Messaging: Does the marketing message actually show up in sales conversations and materials, or does the handoff from marketing to sales break down? Look for: sales playbooks, pitch scripts, sales decks, and any materials the sales team uses — do they reflect the same language, framing, and promises communicated externally? Sourced from Q17 of intake and any sales-facing documents provided. This metric surfaces Marketing→Revenue cross-force breakdowns without reassigning Sales to the Marketing force.\n\n===================\nCLIENT CONTEXT (provided separately)\n===================\n\nCore Purpose: {{purpose}}\nVision (3-year): {{vision}}\nTop Objectives: {{objectives}}\n\nUse this context to assess alignment:\n- Does marketing messaging reflect {{purpose}}?\n- Are marketing claims achievable given {{vision}} and capabilities?\n- Is the target audience in marketing materials consistent with {{purpose}}?\n- Does the sales team activate the marketing message, or does the handoff lose coherence?\n\n===================\nCRITICAL INSTRUCTIONS\n===================\n\n1. EVIDENCE REQUIREMENTS:\n   - Extract SPECIFIC evidence with exact quotes from documents\n   - Cite source document AND precise location\n   - Compare statements across different documents to find contradictions\n   - NEVER invent quotes or evidence not present in documents\n   - Surface ALL potentially relevant evidence — do not filter by significance; Elisha makes significance judgments in review\n\n2. CONFIDENCE LEVELS:\n   - high: Direct contradictions between documents, explicit claims, clear audience definitions\n   - medium: Strong inference from patterns, implicit messaging, tone analysis\n   - low: Weak signal, speculation, or requires assumptions\n\n3. FINDING TYPES:\n   - strength: Consistent, authentic, aligned messaging that builds trust\n   - gap: Contradictions, false promises, confused positioning, or marketing message that does not reach the sales conversation\n   - warning: Emerging inconsistency or trend toward inauthenticity\n\n4. LOOK FOR CONTRADICTIONS BETWEEN:\n   - Pitch deck vs. website copy\n   - Homepage vs. product pages\n   - Sales materials vs. actual product capabilities (from roadmap or feature docs)\n   - Different audience definitions across documents\n   - External marketing language vs. language used in sales-facing materials (metric 7)\n\n5. FOR METRIC 7 — SALES ACTIVATION: Look specifically for sales playbooks, sales decks, pitch scripts, or any materials the sales team uses in conversations. Compare the language, positioning, and promises in those materials against external marketing materials. If no sales-facing documents are provided, note: "Cannot assess Sales Activation — no sales-facing documents provided."\n\n6. SUB-LAYER TAGGING:\n   - All Marketing findings must use sub_layer: null\n   - Marketing is a singular diagnostic force with no sub-layers\n\n7. QUALITY OVER QUANTITY:\n   - Focus on high-confidence findings with clear evidence\n   - If messaging is consistent, say so (strength finding)\n   - If a metric cannot be assessed due to missing documents, note: "Cannot assess — insufficient data"\n\n8. FINANCIAL DATA:\n   - Flag any evidence items touching financial data with requires_validation: true\n\n===================\nOUTPUT FORMAT — REQUIRED JSON STRUCTURE\n===================\n\nReturn ONLY valid JSON. No markdown, no preamble, no explanation.\n\n[\n  {\n    "id": "mkt_001",\n    "force": "Marketing",\n    "sub_layer": null,\n    "finding_type": "strength | gap | warning",\n    "confidence": "high | medium | low",\n    "finding_text": "Concise description of what you observed (2-3 sentences maximum)",\n    "framework_metric": "Must match one of the 7 metrics listed above exactly",\n    "source_document": "exact filename(s) — use \'vs.\' to show contradictions",\n    "source_location": "precise location(s) within document(s)",\n    "supporting_quote": "Brief verbatim quote(s) (15 words max each)",\n    "business_impact": "Why this matters (1-2 sentences)",\n    "analysis": "Your interpretation (1-2 sentences)",\n    "requires_validation": false\n  }\n]\n\nREQUIRED FIELDS (all must be present):\n- id: Format as "mkt_001", "mkt_002", etc. (sequential)\n- force: Always "Marketing" in this prompt\n- sub_layer: Always null for Marketing — never a string value\n- finding_type: Must be "gap", "strength", or "warning"\n- confidence: Must be "high", "medium", or "low"\n- finding_text: Clear, specific observation\n- framework_metric: Must match one of the 7 metrics listed above exactly\n- source_document: Exact filename(s)\n- source_location: Precise location(s) within document(s)\n- supporting_quote: Brief verbatim quote(s)\n- business_impact: Consequences or strategic importance\n- analysis: Your reasoning connecting evidence to metric\n- requires_validation: true only for financial evidence; false otherwise\n\n===================\nFEW-SHOT EXAMPLES\n===================\n\nEXAMPLE 1 — GAP (High Confidence):\n{\n  "id": "mkt_001",\n  "force": "Marketing",\n  "sub_layer": null,\n  "finding_type": "gap",\n  "confidence": "high",\n  "finding_text": "Fundamental contradiction in target audience definition between pitch deck and website copy. Deck targets \'mid-market teams (100-500 employees)\' while website hero section addresses \'scrappy nonprofits doing more with less.\'",\n  "framework_metric": "Audience Segmentation Clarity",\n  "source_document": "pitch_deck.pdf vs. website_copy.notion",\n  "source_location": "Deck slide 3 \'Target Market\' / Website homepage hero section",\n  "supporting_quote": "Deck: \'We serve mid-market teams\' vs. Website: \'Built for scrappy nonprofits\'",\n  "business_impact": "Fragmented message leads to high CAC and poor lead quality as no single audience is accurately targeted. Sales and marketing likely working at cross-purposes.",\n  "analysis": "Organization attempting to speak to two completely different market segments simultaneously, resulting in strategic confusion and ineffective spend.",\n  "requires_validation": false\n}\n\nEXAMPLE 2 — STRENGTH (High Confidence):\n{\n  "id": "mkt_002",\n  "force": "Marketing",\n  "sub_layer": null,\n  "finding_type": "strength",\n  "confidence": "high",\n  "finding_text": "Positioning messaging is highly consistent across all channels. The phrase \'democratize data access\' appears verbatim in pitch deck, website hero, sales playbook, and marketing guide.",\n  "framework_metric": "Positioning Consistency",\n  "source_document": "pitch_deck.pdf + website_copy.notion + sales_playbook.docx + marketing_messaging_guide.pdf",\n  "source_location": "Deck slide 1 / Website hero / Playbook page 3 / Marketing guide page 2",\n  "supporting_quote": "\'Democratize data access\' appears in all four documents as primary value proposition",\n  "business_impact": "Creates clear, memorable brand identity. Sales, marketing, and product teams aligned on core message, reducing friction and increasing conversion effectiveness.",\n  "analysis": "This messaging discipline is rare and indicates strong internal alignment on mission and positioning. Should be protected and reinforced.",\n  "requires_validation": false\n}\n\nEXAMPLE 3 — GAP (High Confidence, Sales Activation):\n{\n  "id": "mkt_003",\n  "force": "Marketing",\n  "sub_layer": null,\n  "finding_type": "gap",\n  "confidence": "high",\n  "finding_text": "Sales playbook uses entirely different language and framing than external marketing materials. Marketing leads with transformation and mission language; sales playbook opens with feature comparisons and pricing tiers, with no mention of the transformation narrative.",\n  "framework_metric": "Sales Activation of Marketing Messaging",\n  "source_document": "sales_playbook.docx vs. website_copy.notion",\n  "source_location": "Playbook pages 1-3 \'Opening the Conversation\' / Website homepage and About page",\n  "supporting_quote": "Playbook: \'Lead with our price-per-seat advantage\' vs. Website: \'We exist to democratize impact\'",\n  "business_impact": "The marketing message is not reaching the sales conversation. Prospects who engaged with external marketing are getting a different story from sales, creating trust gaps and conversion friction.",\n  "analysis": "The Marketing→Sales handoff is broken. External positioning builds emotional resonance; internal sales motion commoditizes. This disconnect surfaces as a Revenue Force finding as well.",\n  "requires_validation": false\n}\n\nEXAMPLE 4 — WARNING (Medium Confidence):\n{\n  "id": "mkt_004",\n  "force": "Marketing",\n  "sub_layer": null,\n  "finding_type": "warning",\n  "confidence": "medium",\n  "finding_text": "Competitive analysis shows all 5 competitors target enterprise customers with $500K+ ARR, while company\'s own marketing targets small nonprofits. Suggests potential upmarket pressure not yet reflected in positioning.",\n  "framework_metric": "Value Proposition Coherence",\n  "source_document": "competitive_analysis.xlsx + website_copy.notion",\n  "source_location": "Competitive tab \'Pricing/Target\' column / Website positioning throughout",\n  "supporting_quote": "Competitors: \'$100-500K enterprise deals\' vs. Our site: \'Affordable for small teams\'",\n  "business_impact": "If market dynamics push toward enterprise, current marketing positioning will need complete overhaul. Could signal emerging misalignment.",\n  "analysis": "Not yet a problem, but the competitive landscape reality doesn\'t match current positioning. Worth monitoring for signs of strategic drift.",\n  "requires_validation": false\n}\n\n===================\nDOCUMENTS TO ANALYZE\n===================\n\n{{documents_text}}\n\n===================\nRETURN JSON ONLY — NO OTHER TEXT\n===================\n'

PASS1C_TEMPLATE = 'REVENUE FORCE ANALYSIS PROMPT\n==============================\nFile: /prompts/pass1_revenue_force.txt\nPass: 1-C of 3 (Revenue)\n\nYou are a business coherence analyst trained in the Coherynce Three Forces Framework.\n\nYour task in this pass is to extract ALL potentially relevant evidence about the REVENUE FORCE only.\nDo not analyze Execution or Marketing in this pass — those run in separate calls.\n\n===================\nREVENUE FORCE DEFINITION\n===================\n\nThe Revenue Force represents how the organization generates, sustains, and grows financial resources.\nIt answers: "How do we make money, and is the full revenue system coherent — model, motion, and financial health?"\n\nThe Revenue Force is examined across three sub-layers:\n\n- REVENUE ARCHITECTURE: How the revenue model is structured — streams, pricing, alignment with value and values\n- SALES MOTION: How customers are acquired and closed — process, friction, pipeline visibility\n- FINANCIAL COHERENCE: Whether the financial picture matches the growth goals — metrics, burn, unit economics\n\nEvery Revenue finding must be tagged to one of these three sub-layers.\n\n===================\nFRAMEWORK METRICS\n===================\n\nREVENUE ARCHITECTURE:\n1. Revenue Model Alignment: Does the way they make money support or undermine the stated mission?\n2. Pricing-Value Coherence: Is the price point appropriate for the target audience and value delivered?\n3. Revenue-Mission Integrity: Does the revenue model exclude or include the stated target market?\n4. Revenue Model Sustainability: Can the current model fund the organization\'s next phase?\n\nSALES MOTION:\n5. Sales Process Clarity: Is the path from first contact to closed deal defined, documented, and consistently followed? Is it clear whether the motion is inbound, outbound, referral-driven, or a mix?\n6. Sales-to-Close Friction: Where do deals stall, prospects go cold, or conversations lose momentum? What are the most common reasons deals are lost?\n7. Pipeline and Conversion Visibility: Does the organization have meaningful insight into conversion rates, stage-by-stage pipeline health, and average time to close — or is this opaque?\n\nEvidence sources to look for under Sales Motion: sales playbook, pipeline report, CRM export, sales OKRs, win/loss data, sales team structure documentation.\n\nFINANCIAL COHERENCE:\n8. Unit Economics Sustainability: Are CAC (Customer Acquisition Cost), LTV (Lifetime Value), and burn rates healthy?\n9. Financial Model Coherence: Are financial projections supported by current growth reality and market assumptions?\n10. Revenue Metrics vs. Targets: How do actual MRR, ARR, ARPU, and churn compare to stated targets?\n\n===================\nCLIENT CONTEXT (provided separately)\n===================\n\nCore Purpose: {{purpose}}\nVision (3-year): {{vision}}\nTop Objectives: {{objectives}}\n\nUse this context to assess alignment:\n- Does the revenue model support {{purpose}}?\n- Is pricing accessible to the audience implied by {{purpose}}?\n- Does the sales motion reflect the kind of organization {{vision}} describes?\n- Do financial projections align with {{vision}} timeline?\n\n===================\nCRITICAL INSTRUCTIONS\n===================\n\n1. EVIDENCE REQUIREMENTS:\n   - Extract SPECIFIC numbers, pricing data, financial metrics, and process descriptions\n   - Cite source document AND precise location (tab name, cell references for Excel, slide numbers for decks)\n   - Look for contradictions between pricing page, financial model, sales materials, and stated mission\n   - NEVER invent financial data not present in documents\n   - Surface ALL potentially relevant evidence — do not filter by significance; Elisha makes significance judgments in review\n\n2. CONFIDENCE LEVELS:\n   - high: Explicit financial data, clear pricing, documented metrics, or explicitly described sales process\n   - medium: Can calculate or infer from multiple data points; sales process implied but not documented\n   - low: Speculation based on limited data; sales process completely absent from documents\n\n3. FINDING TYPES:\n   - strength: Sustainable model, aligned pricing, healthy unit economics, clear and documented sales motion\n   - gap: Unsustainable economics, pricing misalignment, revenue-mission conflict, undefined or broken sales process\n   - warning: Trending toward unsustainability, early warning signals, sales process gaps beginning to show friction\n\n4. FOR SALES MOTION FINDINGS:\n   - If a sales playbook, CRM export, or pipeline report is provided, analyze it directly\n   - If no sales-facing documents are provided but intake responses reference sales (Q23-25), use intake context as low-confidence evidence\n   - If neither documents nor intake data describe the sales process, note: "Cannot assess Sales Motion — no sales-facing documents or intake data provided"\n   - Do NOT reassign sales findings to Marketing — sales process and conversion belong to Revenue\n\n5. KEY CALCULATIONS TO PERFORM (Financial Coherence):\n   - If you see MRR and monthly burn: Calculate runway\n   - If you see pricing and CAC: Assess payback period\n   - If you see customer count and revenue: Calculate ARPU\n   - If you see growth rate and capacity: Check if operationally feasible\n   - Be precise with numbers: not "low runway" but "8 months runway at current burn"\n\n6. SUB-LAYER TAGGING:\n   - Every Revenue finding must be tagged to one sub-layer: "Revenue_Architecture", "Sales_Motion", or "Financial_Coherence"\n   - Never leave sub_layer null for Revenue items\n\n7. FINANCIAL DATA:\n   - Flag ALL financial evidence items with requires_validation: true\n   - Do not make inferences about projected vs. actual revenue without explicit confirmation from documents\n\n8. QUALITY OVER QUANTITY:\n   - Financial findings require numerical evidence\n   - If financial data is missing, note: "Cannot assess — financial documents not provided"\n   - Better to have 5-7 high-confidence findings than 20 speculative ones\n\n===================\nOUTPUT FORMAT — REQUIRED JSON STRUCTURE\n===================\n\nReturn ONLY valid JSON. No markdown, no preamble, no explanation.\n\n[\n  {\n    "id": "rev_001",\n    "force": "Revenue",\n    "sub_layer": "Revenue_Architecture | Sales_Motion | Financial_Coherence",\n    "finding_type": "strength | gap | warning",\n    "confidence": "high | medium | low",\n    "finding_text": "Concise description with specific numbers where available (2-3 sentences maximum)",\n    "framework_metric": "Must match one of the 10 metrics listed above exactly",\n    "source_document": "exact filename",\n    "source_location": "page / slide / tab / section — include cell references for Excel",\n    "supporting_quote": "Specific numbers or exact text from document (15 words maximum)",\n    "business_impact": "Why this matters financially or strategically (1-2 sentences)",\n    "analysis": "Your interpretation with calculations if relevant (1-2 sentences)",\n    "requires_validation": true\n  }\n]\n\nREQUIRED FIELDS (all must be present):\n- id: Format as "rev_001", "rev_002", etc. (sequential)\n- force: Always "Revenue" in this prompt\n- sub_layer: Must be "Revenue_Architecture", "Sales_Motion", or "Financial_Coherence" — never null for Revenue items\n- finding_type: Must be "gap", "strength", or "warning"\n- confidence: Must be "high", "medium", or "low"\n- finding_text: Clear observation; include specific numbers where available\n- framework_metric: Must match one of the 10 metrics listed above exactly\n- source_document: Exact filename\n- source_location: Precise location (tab name and cell references if Excel)\n- supporting_quote: Specific numbers or quotes from document\n- business_impact: Financial or strategic consequences\n- analysis: Your interpretation (include calculations if performed)\n- requires_validation: true for all financial evidence; false only for non-financial Sales Motion findings\n\n===================\nFEW-SHOT EXAMPLES\n===================\n\nEXAMPLE 1 — GAP, Revenue Architecture (High Confidence):\n{\n  "id": "rev_001",\n  "force": "Revenue",\n  "sub_layer": "Revenue_Architecture",\n  "finding_type": "gap",\n  "confidence": "high",\n  "finding_text": "Pricing strategy fundamentally excludes stated target market. Average price point is $800/month while stated mission targets \'small nonprofits\' who typically have software budgets under $200/month.",\n  "framework_metric": "Revenue-Mission Integrity",\n  "source_document": "pricing_page.pdf + pitch_deck.pdf",\n  "source_location": "Pricing page \'Standard Plan\' / Deck slide 2 \'Mission\'",\n  "supporting_quote": "Pricing: \'$800/month Standard plan\' vs. Mission: \'Democratize data access for small nonprofits\'",\n  "business_impact": "Revenue model makes product inaccessible to the very market the mission claims to serve. Either mission or pricing is fundamentally misaligned with business reality.",\n  "analysis": "Small nonprofits cannot afford $9,600/year for software. Pricing suggests enterprise focus despite mission statement claiming otherwise.",\n  "requires_validation": true\n}\n\nEXAMPLE 2 — GAP, Sales Motion (High Confidence):\n{\n  "id": "rev_002",\n  "force": "Revenue",\n  "sub_layer": "Sales_Motion",\n  "finding_type": "gap",\n  "confidence": "high",\n  "finding_text": "No documented sales process exists. Intake responses describe a referral-driven motion with no defined stages, qualification criteria, or handoff points. The organization cannot articulate where deals stall because stages are not tracked.",\n  "framework_metric": "Sales Process Clarity",\n  "source_document": "intake_form_responses + pitch_deck.pdf",\n  "source_location": "Intake Q23-24 / Deck has no sales section",\n  "supporting_quote": "Intake Q23: \'We mostly get clients through word of mouth and introductions\'",\n  "business_impact": "Without a defined sales process, the organization cannot diagnose conversion problems, train new salespeople, or forecast reliably. Growth is constrained by the founder\'s personal network.",\n  "analysis": "The absence of a documented sales motion means revenue growth is non-repeatable. This is the most common scaling bottleneck for founder-led sales organizations.",\n  "requires_validation": false\n}\n\nEXAMPLE 3 — WARNING, Sales Motion (Medium Confidence):\n{\n  "id": "rev_003",\n  "force": "Revenue",\n  "sub_layer": "Sales_Motion",\n  "finding_type": "warning",\n  "confidence": "medium",\n  "finding_text": "Pipeline report shows 60% of deals stall at the proposal stage with no follow-up logged after 14 days. Win/loss data is not tracked, making it impossible to identify the most common objection or reason for loss.",\n  "framework_metric": "Sales-to-Close Friction",\n  "source_document": "pipeline_report.xlsx",\n  "source_location": "Pipeline tab, Stage column — \'Proposal Sent\' rows",\n  "supporting_quote": "23 of 38 open deals last activity: \'Proposal Sent\' — no follow-up logged",\n  "business_impact": "More than half of qualified pipeline is going cold at the proposal stage. Without win/loss tracking, the organization cannot address the root cause or improve conversion.",\n  "analysis": "Proposal-stage stall is a classic symptom of either pricing friction or unclear value proposition. Requires intervention at the sales process level, not just more leads.",\n  "requires_validation": false\n}\n\nEXAMPLE 4 — GAP, Financial Coherence (High Confidence):\n{\n  "id": "rev_004",\n  "force": "Revenue",\n  "sub_layer": "Financial_Coherence",\n  "finding_type": "gap",\n  "confidence": "high",\n  "finding_text": "Critical revenue-burn gap threatens sustainability. Currently generating $14,000 MRR against $65,000 monthly burn, creating 8 months runway with current $520,000 cash balance.",\n  "framework_metric": "Unit Economics Sustainability",\n  "source_document": "financial_model.xlsx",\n  "source_location": "P&L tab row 15 (MRR), row 28 (burn), row 5 (cash)",\n  "supporting_quote": "MRR: $14,000 | Monthly burn: $65,000 | Cash: $520,000",\n  "business_impact": "Company will run out of cash in Q3 without significant revenue acceleration or additional funding. Forces rushed strategic decisions under financial pressure.",\n  "analysis": "Burn rate is 4.6x revenue. To reach break-even at current burn would require growing revenue by $51,000/month (364% growth). Unsustainable without dramatic changes.",\n  "requires_validation": true\n}\n\nEXAMPLE 5 — STRENGTH, Financial Coherence (High Confidence):\n{\n  "id": "rev_005",\n  "force": "Revenue",\n  "sub_layer": "Financial_Coherence",\n  "finding_type": "strength",\n  "confidence": "high",\n  "finding_text": "Healthy unit economics with strong retention. LTV is $10,800 (36 months at $300 ARPU with 92% net retention) against CAC of $2,400, yielding 4.5:1 LTV:CAC ratio.",\n  "framework_metric": "Unit Economics Sustainability",\n  "source_document": "financial_model.xlsx",\n  "source_location": "Unit Economics tab, rows 8-12",\n  "supporting_quote": "ARPU: $300 | CAC: $2,400 | Retention: 92% | Calculated LTV: $10,800",\n  "business_impact": "Strong unit economics provide foundation for profitable growth. Each customer acquired pays back acquisition cost in 8 months and generates $8,400 in lifetime profit.",\n  "analysis": "4.5:1 LTV:CAC is healthy (SaaS benchmark is 3:1+). 92% retention is excellent. Model can scale profitably if customer acquisition can be maintained at current efficiency.",\n  "requires_validation": true\n}\n\n===================\nDOCUMENTS TO ANALYZE\n===================\n\n{{documents_text}}\n\n===================\nRETURN JSON ONLY — NO OTHER TEXT\n===================\n'

PASS2_TEMPLATE = 'CROSS-FORCE PATTERN SYNTHESIS PROMPT\n=====================================\nFile: /prompts/pass2_synthesis.txt\nPass: 2 (Cross-Force Pattern Detection)\n\nYou are a business coherence analyst trained in the Coherynce Three Forces Framework.\n\nYou have received evidence from three separate force extractions (Execution, Marketing, Revenue).\nYour task is to identify systemic patterns and relationships between forces.\n\nFind how issues in one force create pressure on another, or how strengths reinforce across forces.\nEvery pattern must be grounded in specific evidence items from Pass 1.\n\n===================\nINPUT\n===================\n\nYou will receive:\n- Pass 1 evidence JSON: merged array of all findings from Execution, Marketing, and Revenue extractions\n- Original document text (for reference if you need to verify a connection)\n\nEvidence item IDs follow this convention:\n- Execution findings: exec_001, exec_002, etc.\n- Marketing findings: mkt_001, mkt_002, etc.\n- Revenue findings: rev_001, rev_002, etc.\n\n===================\nPATTERN TYPES TO IDENTIFY\n===================\n\n1. VIRTUOUS CYCLE (virtuous_cycle)\n   Where strength in one force enables strength in another, creating reinforcing positive momentum.\n   Example: Strong process documentation (Execution) → Enables consistent customer experience → Marketing can promise reliability → Drives higher retention (Revenue) → Resources to improve processes further.\n\n2. VICIOUS CYCLE (vicious_cycle)\n   Where misalignment in one force creates pressure that triggers misalignment in another, which reinforces the original problem.\n   Example: Revenue pressure → Forces upmarket pivot → Requires enterprise product features (Execution) → But marketing still targets small customers (Marketing) → Creates organizational confusion → Worsens revenue problem.\n\n3. LEVERAGE POINT (leverage_point)\n   A single change that would unlock benefits across multiple forces simultaneously.\n   Example: Making a decisive market choice would align the product roadmap (Execution), clarify marketing message (Marketing), and resolve pricing confusion (Revenue).\n\n4. BOTTLENECK (bottleneck)\n   One problem in a single force that is cascading and creating problems in other forces.\n   Example: Unclear decision-making structure (Execution) → Slows product development → Creates uncertainty in marketing about what to promise → Makes revenue projections unreliable.\n\nCRITICAL: "coherence_bottleneck" is NOT a valid pattern type. The correct enum value is "bottleneck". Never use "coherence_bottleneck" in output.\n\n===================\nCROSS-FORCE PAIR COVERAGE\n===================\n\nWork through all three force pairs explicitly before forming your output:\n\n1. EXECUTION ↔ MARKETING\n   - Does the roadmap support what marketing promises?\n   - Does build capacity match the brand\'s ambition?\n   - Are team capabilities aligned with brand commitments?\n\n2. EXECUTION ↔ REVENUE\n   - Does the product monetize its actual strengths?\n   - Does the revenue model fund product development?\n   - Are operational costs aligned with pricing?\n\n3. MARKETING ↔ REVENUE\n   - Does pricing match the positioning?\n   - Is the marketing message being activated in the sales motion, or does the Marketing→Revenue handoff break down?\n   - Does the revenue model incentivize the right customer behaviors?\n\nFor the Marketing ↔ Revenue pair: pay particular attention to whether Marketing findings tagged "Sales Activation of Marketing Messaging" (mkt_xxx) connect to Revenue findings tagged sub_layer: "Sales_Motion" (rev_xxx). This is the most common cross-force breakdown in founder-led organizations and must be explicitly checked.\n\n===================\nCRITICAL INSTRUCTIONS\n===================\n\n1. EVIDENCE CHAIN REQUIREMENTS:\n   - Each pattern must reference at least 2 finding IDs (minimum), preferably 3-4\n   - Findings must actually support the pattern — re-read them to verify before including\n   - NEVER reference finding IDs that don\'t exist in the evidence provided\n   - Include the sub-layer of each finding in the evidence chain\n\n2. PATTERN IDENTIFICATION:\n   - Look for causal relationships, not just correlation\n   - Ask: "Does finding A create conditions that lead to finding B?"\n   - Be specific about the mechanism — HOW does one force affect another?\n\n3. STRATEGIC FOCUS:\n   - Prioritize patterns with highest business impact\n   - Focus on 2-4 major patterns rather than 6-8 minor ones\n   - Make recommendations actionable — what specifically should change?\n\n4. QUALITY OVER QUANTITY:\n   - Better to identify 2 well-supported vicious cycles than 5 speculative patterns\n   - If you cannot find strong cross-force connections for a pair, say so briefly\n   - Not every analysis will have all 4 pattern types — that\'s okay\n\n5. STANDALONE SIGNAL RULE:\n   - Every signal must be reported as its own discrete finding regardless of co-occurrence with other signals\n   - If Signal A and Signal B appear in the same document or the same evidence chain, they must still be reported as separate pattern entries if they represent distinct patterns\n   - Do NOT bundle multiple patterns into a single entry because they share a source document or evidence item\n   - Ask yourself: "Would a consultant treat these as separate recommendations?" If yes, they are separate patterns\n\n6. FINANCIAL DATA:\n   - Flag any pattern where financial evidence is central with requires_validation: true\n\n===================\nOUTPUT FORMAT — REQUIRED JSON STRUCTURE\n===================\n\nReturn ONLY valid JSON. No markdown, no preamble, no explanation.\n\n[\n  {\n    "id": "pattern_001",\n    "pattern_type": "virtuous_cycle | vicious_cycle | leverage_point | bottleneck",\n    "forces_involved": ["Execution", "Marketing"],\n    "sub_layers_involved": ["Product", "Sales_Motion"],\n    "pattern_title": "Short memorable title (6-8 words)",\n    "description": "Clear explanation of the pattern and how forces interact (3-4 sentences)",\n    "evidence_chain": [\n      {\n        "finding_id": "rev_001",\n        "force": "Revenue",\n        "sub_layer": "Sales_Motion",\n        "element": "Brief summary of what this finding contributes to the pattern"\n      },\n      {\n        "finding_id": "mkt_003",\n        "force": "Marketing",\n        "sub_layer": null,\n        "element": "How this connects to the revenue finding above"\n      }\n    ],\n    "flow_description": "Step-by-step causal flow: Finding A creates pressure → which causes Finding B → which reinforces Finding C",\n    "business_impact": "Why this pattern matters strategically and what happens if it continues (2-3 sentences)",\n    "recommendation": "Specific, actionable recommendation to break the cycle or leverage the pattern (2-3 sentences)",\n    "strategic_significance": "high | medium | low",\n    "requires_validation": false\n  }\n]\n\nREQUIRED FIELDS (all must be present):\n- id: Format as "pattern_001", "pattern_002", etc.\n- pattern_type: Must be "virtuous_cycle", "vicious_cycle", "leverage_point", or "bottleneck" — "coherence_bottleneck" is invalid\n- forces_involved: Array of force names involved in the pattern\n- sub_layers_involved: Array of sub-layer names involved (use null entries if Marketing findings are included, since Marketing has no sub-layers)\n- pattern_title: Short, memorable (6-8 words)\n- description: Clear explanation of pattern (3-4 sentences)\n- evidence_chain: Array of 2-4 findings with finding_id, force, sub_layer, and element\n- flow_description: Step-by-step causal explanation\n- business_impact: Strategic consequences\n- recommendation: Specific action to address pattern\n- strategic_significance: Must be "high", "medium", or "low"\n- requires_validation: true if financial evidence is central to the pattern; false otherwise\n\n===================\nFEW-SHOT EXAMPLES\n===================\n\nEXAMPLE 1 — VICIOUS CYCLE (Product-Market):\n{\n  "id": "pattern_001",\n  "pattern_type": "vicious_cycle",\n  "forces_involved": ["Revenue", "Execution", "Marketing"],\n  "sub_layers_involved": ["Financial_Coherence", "Product", null],\n  "pattern_title": "Revenue Pressure Drives Mission Drift",\n  "description": "Financial pressure is forcing an upmarket product pivot toward enterprise features, but marketing messaging has not shifted to match, creating organizational confusion about target customer. This confusion undermines sales effectiveness, worsening the original revenue problem. The organization is caught between two strategies — enterprise (roadmap) and small customer (marketing) — and executing neither well.",\n  "evidence_chain": [\n    {\n      "finding_id": "rev_004",\n      "force": "Revenue",\n      "sub_layer": "Financial_Coherence",\n      "element": "Revenue-burn gap ($14K MRR vs $65K burn) creates 8-month runway crisis"\n    },\n    {\n      "finding_id": "exec_001",\n      "force": "Execution",\n      "sub_layer": "Product",\n      "element": "Product roadmap pivots to enterprise features (SSO, SAML, multi-tenant security) to chase higher ARPU"\n    },\n    {\n      "finding_id": "mkt_001",\n      "force": "Marketing",\n      "sub_layer": null,\n      "element": "Marketing still positions for \'small nonprofits doing more with less\' — hasn\'t adjusted to enterprise pivot"\n    }\n  ],\n  "flow_description": "Revenue crisis → Forces upmarket product pivot → Engineering builds enterprise features → Marketing unchanged → Sales team attracts wrong leads → CAC increases, conversion drops → Revenue problems worsen → Reinforces crisis",\n  "business_impact": "Organization is stuck between two markets and serving neither well. Engineering builds features that small customers don\'t want, while marketing attracts small customers who can\'t afford enterprise pricing.",\n  "recommendation": "Make a decisive market choice within 30 days: commit to enterprise (update marketing, hire enterprise sales, accept different growth curve) OR recommit to small customers (revise roadmap, lower pricing, embrace volume model). Attempting both is destroying efficiency across all three forces.",\n  "strategic_significance": "high",\n  "requires_validation": true\n}\n\nEXAMPLE 2 — VICIOUS CYCLE (Sales Motion):\n{\n  "id": "pattern_002",\n  "pattern_type": "vicious_cycle",\n  "forces_involved": ["Marketing", "Revenue"],\n  "sub_layers_involved": [null, "Sales_Motion"],\n  "pattern_title": "Marketing Message Lost at the Sales Handoff",\n  "description": "External marketing builds an emotionally resonant mission-driven brand, but the sales team pitches using feature comparisons and price advantages with no reference to that positioning. Prospects who engaged with the brand message encounter a mismatched sales experience, creating trust friction. Lower conversion rates increase revenue pressure, which pushes leadership to prioritize volume over message alignment — further weakening the handoff. The cycle compounds.",\n  "evidence_chain": [\n    {\n      "finding_id": "mkt_003",\n      "force": "Marketing",\n      "sub_layer": null,\n      "element": "Sales playbook uses entirely different language than external marketing — feature comparisons instead of transformation narrative"\n    },\n    {\n      "finding_id": "rev_002",\n      "force": "Revenue",\n      "sub_layer": "Sales_Motion",\n      "element": "No documented sales process; referral-driven motion with no defined stages or qualification criteria"\n    },\n    {\n      "finding_id": "rev_003",\n      "force": "Revenue",\n      "sub_layer": "Sales_Motion",\n      "element": "60% of deals stall at proposal stage with no follow-up — symptom of inconsistent pitch quality"\n    }\n  ],\n  "flow_description": "Marketing builds resonant external brand → Sales team receives no activation training on that brand → Sales pitches features and price instead → Prospect trust gap at handoff → Conversion drops at proposal stage → Revenue pressure rises → Leadership pushes volume not alignment → Handoff worsens",\n  "business_impact": "The organization is investing in brand-building that evaporates the moment a prospect talks to sales. Every dollar of marketing spend is partially offset by sales conversion friction. Without fixing the handoff, scaling marketing spend will not proportionally improve revenue.",\n  "recommendation": "Create a 1-page sales activation brief that translates the core marketing narrative into sales language — same transformation promise, same target customer, adapted for conversation. Require sales to open every call with the mission framing before moving to features. Measure conversion rate before and after as the leading indicator.",\n  "strategic_significance": "high",\n  "requires_validation": false\n}\n\nEXAMPLE 3 — LEVERAGE POINT:\n{\n  "id": "pattern_003",\n  "pattern_type": "leverage_point",\n  "forces_involved": ["Execution", "Marketing", "Revenue"],\n  "sub_layers_involved": ["Operations", null, "Sales_Motion"],\n  "pattern_title": "Undiscovered Process Strength as Sales Asset",\n  "description": "Exceptional operational process documentation (Execution strength) is not reflected in marketing materials or sales conversations. This creates a missed opportunity: the operational maturity that makes delivery reliable could be a powerful differentiator in both positioning and sales close.",\n  "evidence_chain": [\n    {\n      "finding_id": "exec_002",\n      "force": "Execution",\n      "sub_layer": "Operations",\n      "element": "Customer onboarding process exceptionally well-documented with clear ownership and time estimates — unusual at this stage"\n    },\n    {\n      "finding_id": "mkt_003",\n      "force": "Marketing",\n      "sub_layer": null,\n      "element": "Marketing does not highlight process maturity or operational excellence as differentiator"\n    },\n    {\n      "finding_id": "rev_002",\n      "force": "Revenue",\n      "sub_layer": "Sales_Motion",\n      "element": "Sales process undocumented; no evidence of reliability or process being used as a close argument"\n    }\n  ],\n  "flow_description": "Operational excellence exists (Execution) → Not communicated externally (Marketing gap) → Not used in sales conversations (Sales Motion gap) → Competitive advantage hidden from the buyers who would most value it",\n  "business_impact": "This operational maturity is rare and represents a defensible competitive differentiator that is currently invisible to the market. Surfacing it would improve both positioning and conversion without requiring product changes.",\n  "recommendation": "Add an \'operational reliability\' proof point to marketing materials — case study, onboarding timeline, or transparency document. Train sales team to use it as a close argument for risk-averse buyers. This single change improves Marketing coherence and Sales Motion simultaneously.",\n  "strategic_significance": "medium",\n  "requires_validation": false\n}\n\nEXAMPLE 4 — BOTTLENECK:\n{\n  "id": "pattern_004",\n  "pattern_type": "bottleneck",\n  "forces_involved": ["Execution", "Marketing", "Revenue"],\n  "sub_layers_involved": ["Product", null, "Financial_Coherence"],\n  "pattern_title": "Decision Ambiguity Cascading Across All Forces",\n  "description": "Unclear product decision-making structure is creating downstream problems in marketing promises and revenue projections. Without knowing who decides what gets built or when, other forces cannot make reliable commitments.",\n  "evidence_chain": [\n    {\n      "finding_id": "exec_004",\n      "force": "Execution",\n      "sub_layer": "Product",\n      "element": "Product decision structure unclear — no documented decision-making authority or process"\n    },\n    {\n      "finding_id": "mkt_005",\n      "force": "Marketing",\n      "sub_layer": null,\n      "element": "Marketing uncertain what features to promise — has promoted features that were later deprioritized"\n    },\n    {\n      "finding_id": "rev_006",\n      "force": "Revenue",\n      "sub_layer": "Financial_Coherence",\n      "element": "Revenue projections based on feature launches with no committed timeline"\n    }\n  ],\n  "flow_description": "Unclear product decisions (Execution) → Marketing can\'t reliably promise features → Credibility issues with customers → Revenue projections become guesswork → Undermines strategic planning across all forces",\n  "business_impact": "This single bottleneck is creating ripple effects across all forces. Marketing makes promises it can\'t keep. Revenue projections are unreliable. Sales loses deals because customers don\'t trust delivery commitments.",\n  "recommendation": "Implement a clear product decision framework: (1) designate final decision-maker for product direction, (2) create a quarterly roadmap with confidence levels (Committed / Probable / Exploring), (3) require sign-off before marketing mentions features publicly. This single fix stabilizes all three forces.",\n  "strategic_significance": "high",\n  "requires_validation": false\n}\n\n===================\nEVIDENCE TO ANALYZE\n===================\n\nPASS 1 EVIDENCE (merged from all three force extractions):\n{{pass1_evidence_json}}\n\nORIGINAL DOCUMENT CONTEXT (for reference):\n{{assembled_document_text}}\n\n===================\nRETURN JSON ONLY — NO OTHER TEXT\n===================\n'

PASS3_TEMPLATE = '''RESONANCE ANALYSIS REPORT GENERATION
=====================================
Pass: 3 (Report Generation)

You are a senior business coherence analyst at Coherynce writing a client-facing
Resonance Analysis Report. Your tone is: grounded, intelligent, warm, executive.
No jargon. No hedging. Write as a trusted advisor who has studied this business deeply.

===================
REPORT STRUCTURE
===================

Generate the following sections using the exact markers shown.
The rendering system uses these markers to format the PDF.

[EXECUTIVE_SUMMARY]
Start with 3-5 key takeaway bullets. These are the most critical things the founder
needs to know immediately. Each bullet should be one sharp sentence — specific, not generic.

FORMAT:
TAKEAWAY: [one sharp sentence]
TAKEAWAY: [one sharp sentence]
TAKEAWAY: [one sharp sentence]

Then write a narrative below the bullets. 2-3 tight paragraphs. Impactful, not verbose.
Connect the dots between the takeaways. Name the core tension in the business.
What is working, what is broken, what matters most right now.
End with one sentence on what becomes possible when coherence is restored.

Then name the single most critical cross-force pattern explicitly:
CRITICAL_PATTERN: [pattern name]
[/EXECUTIVE_SUMMARY]

[FORCE_SCORES]
Return a JSON block with preliminary scores and one-line rationale for each.

{
  "execution": {"score": X, "rationale": "one sentence"},
  "marketing": {"score": X, "rationale": "one sentence"},
  "revenue": {"score": X, "rationale": "one sentence"},
  "cross_force": {"score": X, "rationale": "one sentence"}
}

Scores are 1-10. Be honest — a 4 is a 4. Do not cluster everything at 6-7.
[/FORCE_SCORES]

[EXECUTION_ANALYSIS]
Line 1: Force score label — SCORE: [X]/10
Line 2-3: 2-3 key takeaway bullets for this force.
FORMAT:
TAKEAWAY: [one sharp sentence]
TAKEAWAY: [one sharp sentence]

Then a short narrative — 2-3 sentences that give context and connect the bullets.
Impactful, not verbose.

Then present findings in three groups. For each group use the exact group markers:

STRENGTHS:
For each strength finding:
FINDING_START
TITLE: [short descriptive title for this finding]
TEXT: [the finding text]
IMPACT: [business impact]
SOURCE: [source_document]
FINDING_END

GAPS:
For each gap finding — same format as strengths.

WARNINGS:
For each warning finding — same format as strengths.

Then close with numbered prioritized recommendations:
RECOMMENDATIONS:
1. [specific actionable recommendation]
2. [specific actionable recommendation]
3. [specific actionable recommendation]
[/EXECUTION_ANALYSIS]

[MARKETING_ANALYSIS]
Same structure as EXECUTION_ANALYSIS.
SCORE: [X]/10
TAKEAWAY bullets, short narrative, STRENGTHS/GAPS/WARNINGS findings, RECOMMENDATIONS.
[/MARKETING_ANALYSIS]

[REVENUE_ANALYSIS]
Same structure. Financial findings marked requires_validation must include:
VALIDATION_NOTE: Pending consultant validation before client delivery.
SCORE: [X]/10
TAKEAWAY bullets, short narrative, STRENGTHS/GAPS/WARNINGS findings, RECOMMENDATIONS.
[/REVENUE_ANALYSIS]

[CROSS_FORCE_PATTERNS]
Present each pattern as a named block. Order by strategic significance: high first.

For each pattern:
PATTERN_START
PATTERN_NAME: [name]
PATTERN_TYPE: [Vicious Cycle / Virtuous Cycle / Leverage Point / Bottleneck]
PATTERN_SUMMARY: [2-3 sentences describing what is happening and why it matters]
PATTERN_FLOW: [the causal chain in one sentence]
FORCES: [e.g. Execution → Marketing → Revenue]
PATTERN_RECOMMENDATION: [specific and actionable recommendation]
PATTERN_END
[/CROSS_FORCE_PATTERNS]

[NEXT_STEPS]
Write 4-6 numbered prioritized actions with timeframes. Be specific.
FORMAT:
1. [action] — [timeframe]
2. [action] — [timeframe]
...

Then close with 2-3 sentences acknowledging the work it takes to see a business this clearly.
State the next engagement step (Alignment Intensive or Ongoing Partnership).
End with a single line that lands with weight — the essence of what coherence makes possible.
[/NEXT_STEPS]

[SOURCES]
List every unique source document referenced across all findings. Number them.
FORMAT:
1. [source document name]
2. [source document name]
...
[/SOURCES]

===================
CRITICAL INSTRUCTIONS
===================

1. Use only the evidence provided — do not invent findings or patterns
2. Findings marked elisha_notes contain consultant edits — incorporate them exactly
3. Financial findings marked requires_validation must include VALIDATION_NOTE
4. Use the exact markers shown — the rendering system depends on them
5. The [FORCE_SCORES] block must be valid JSON
6. Tone: grounded, intelligent, warm, executive — never corporate, never generic
7. Every finding in the evidence must appear in the report
8. Source references use the numbered list from [SOURCES] — reference as [1], [2] etc.

===================
CLIENT CONTEXT
===================

Company: {{company_name}}
Stage: {{stage}}
Core Purpose: {{purpose}}
Vision: {{vision}}
Top Objectives: {{objectives}}
Founder Tension: {{founder_tension}}

===================
APPROVED EVIDENCE FINDINGS
===================

{{evidence_json}}

===================
APPROVED CROSS-FORCE PATTERNS
===================

{{patterns_json}}
'''

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def fill_pass1_template(template: str, client_context: dict, retrieved_context: dict) -> str:
    """Fill template variables in a Pass 1 prompt using retrieved chunks from RAG."""
    # Build retrieved evidence section from graph + vector retrieval
    retrieved_sections = []
    for metric_ctx in retrieved_context.get("metrics", []):
        metric_name = metric_ctx["metric"]
        definition = metric_ctx["definition"]
        chunks = metric_ctx["retrieved_chunks"]
        if not chunks:
            continue
        retrieved_sections.append(f"\n── {metric_name} ──")
        retrieved_sections.append(f"Definition: {definition}")
        for chunk in chunks:
            retrieved_sections.append(
                f"[{chunk['document_name']} / {chunk['structural_location']}] "
                f"(score: {chunk['similarity_score']})\n{chunk['chunk_text']}"
            )

    retrieved_text = "\n".join(retrieved_sections) if retrieved_sections else "No retrieved chunks available."

    return (
        template
        .replace("{{purpose}}", client_context.get("core_purpose", "Not provided"))
        .replace("{{vision}}", client_context.get("vision", "Not provided"))
        .replace("{{objectives}}", client_context.get("objectives", "Not provided"))
        .replace("{{documents_text}}", retrieved_text)
    )


def fill_pass2_template(template: str, pass1_evidence: list, documents_text: str) -> str:
    """Fill template variables in the Pass 2 prompt."""
    return (
        template
        .replace("{{pass1_evidence_json}}", json.dumps(pass1_evidence, indent=2))
        .replace("{{assembled_document_text}}", documents_text[:40000])
    )


def call_claude(prompt: str, label: str) -> list:
    """Call Claude API with retry logic for rate limits."""
    log(f"Calling Claude — {label}...")
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": prompt}],
    }

    max_retries = 5
    for attempt in range(max_retries):
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=180,
        )

        if response.status_code == 429:
            wait = 60 * (attempt + 1)
            log(f"  Rate limited — waiting {wait}s before retry {attempt + 1}/{max_retries}...")
            time.sleep(wait)
            continue

        response.raise_for_status()
        raw = response.json()["content"][0]["text"].strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(raw)
            log(f"  ✓ {label} returned {len(parsed)} items")
            return parsed
        except json.JSONDecodeError as e:
            log(f"  ✗ JSON parse failed for {label}: {e}")
            log(f"  Retrying with json repair...")
            try:
                import json_repair
                parsed = json_repair.repair_json(raw, return_objects=True)
                if isinstance(parsed, list) and len(parsed) > 0:
                    log(f"  ✓ JSON repaired — {len(parsed)} items")
                    return parsed
            except Exception:
                pass
            log(f"  Raw response (first 500 chars): {raw[:500]}")
            raise

    raise Exception(f"Max retries exceeded for {label}")


def call_flask_extraction(file_urls: list) -> list:
    """Call the local Flask extraction service via ngrok."""
    log(f"Calling Flask extraction service for {len(file_urls)} file(s)...")
    url = NGROK_URL.rstrip("/") + "/extract"
    files_payload = [
        {"url": f, "filename": f.split("/")[-1].replace("%20", " ")}
        for f in file_urls
    ]
    response = requests.post(url, json={"files": files_payload}, timeout=120)
    response.raise_for_status()
    result = response.json()
    docs = result.get("files", result)
    log(f"  ✓ Extracted text from {len(docs)} document(s)")
    return docs


def compile_document_text(extracted_docs: list, client_context: dict) -> str:
    """Assemble extracted documents + client context into a single text block."""
    lines = []
    lines.append("CLIENT CONTEXT:")
    lines.append(f"Company: {client_context.get('company_name', 'Unknown')}")
    lines.append(f"Stage: {client_context.get('stage', 'Unknown')}")
    lines.append(f"Core Purpose: {client_context.get('core_purpose', 'Not provided')}")
    lines.append(f"Vision (3-year): {client_context.get('vision', 'Not provided')}")
    lines.append(f"Top Objectives: {client_context.get('objectives', 'Not provided')}")
    lines.append(f"Founder Tension: {client_context.get('founder_tension', 'Not provided')}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("DOCUMENTS TO ANALYZE:")
    lines.append("=" * 60)
    lines.append("")
    for doc in extracted_docs:
        lines.append(f"DOCUMENT: {doc['filename']}")
        lines.append("-" * 40)
        lines.append(doc.get("extracted_text") or doc.get("text") or "")
        lines.append("")
    return "\n".join(lines)


# ── Storage ───────────────────────────────────────────────────────────────────

def write_to_supabase(table: str, records: list):
    if not SUPABASE_URL or not SUPABASE_KEY:
        log(f"  Supabase not configured — skipping write to {table}")
        return
    if not records:
        return
    log(f"Writing {len(records)} records to Supabase:{table}...")
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    response = requests.post(url, headers=headers, json=records, timeout=60)
    if response.status_code in (200, 201):
        log(f"  ✓ Supabase:{table} write successful")
    else:
        log(f"  ✗ Supabase:{table} failed: {response.status_code} — {response.text}")


def write_to_airtable(table_name: str, records: list):
    if not AIRTABLE_TOKEN or not AIRTABLE_BASE_ID:
        log(f"  Airtable not configured — skipping write to {table_name}")
        return
    if not records:
        return
    log(f"Writing {len(records)} records to Airtable:{table_name}...")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{requests.utils.quote(table_name)}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    for i in range(0, len(records), 10):
        batch = records[i: i + 10]
        payload = {"records": [{"fields": r} for r in batch]}
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            log(f"  ✓ Airtable batch {i // 10 + 1} written ({len(batch)} records)")
        else:
            log(f"  ✗ Airtable write failed: {response.status_code} — {response.text}")


def update_supabase_pipeline_status(client_id: str, status: str):
    if not SUPABASE_URL or not SUPABASE_KEY:
        log(f"  Pipeline status: {status} (Supabase not configured)")
        return
    url = f"{SUPABASE_URL}/rest/v1/clients?client_id=eq.{client_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    response = requests.patch(url, headers=headers, json={"pipeline_status": status}, timeout=30)
    if response.status_code in (200, 204):
        log(f"  ✓ Pipeline status → {status}")
    else:
        log(f"  Pipeline status: {status} (Supabase update skipped)")


# ── Record builders ───────────────────────────────────────────────────────────

def build_evidence_supabase_record(finding: dict, client_id: str, engagement_id: str = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "engagement_id": engagement_id,
        "force": finding.get("force"),
        "sub_layer": finding.get("sub_layer"),
        "finding_type": finding.get("finding_type"),
        "confidence": finding.get("confidence"),
        "finding_text": finding.get("finding_text"),
        "finding_title": finding.get("finding_title") or finding.get("framework_metric"),
        "business_impact": finding.get("business_impact"),
        "supporting_quote": finding.get("supporting_quote"),
        "framework_metric": finding.get("framework_metric"),
        "source_document": finding.get("source_document"),
        "source_location": finding.get("source_location"),
        "include_in_report": True,
        "elisha_notes": None,
    }


def build_evidence_airtable_record(finding: dict, client_id: str) -> dict:
    return {
        "Client ID": client_id,
        "Finding ID": finding.get("id"),
        "Force": finding.get("force"),
        "Sub-Layer": finding.get("sub_layer") or "—",
        "Finding Type": finding.get("finding_type"),
        "Confidence": finding.get("confidence"),
        "Finding Text": finding.get("finding_text"),
        "Framework Metric": finding.get("framework_metric"),
        "Source Document": finding.get("source_document"),
        "Source Location": finding.get("source_location"),
        "Supporting Quote": finding.get("supporting_quote"),
        "Business Impact": finding.get("business_impact"),
        "Analysis": finding.get("analysis"),
        "Requires Validation": finding.get("requires_validation", False),
        "Include in Report": True,
        "Elisha Notes": "",
    }


def build_pattern_supabase_record(pattern: dict, client_id: str, engagement_id: str = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "engagement_id": engagement_id,
        "pattern_type": pattern.get("pattern_type"),
        "forces_involved": pattern.get("forces_involved"),
        "sub_layers_involved": pattern.get("sub_layers_involved"),
        "pattern_title": pattern.get("pattern_title"),
        "description": pattern.get("description"),
        "evidence_chain": pattern.get("evidence_chain"),
        "strategic_significance": pattern.get("strategic_significance"),
    }


def build_pattern_airtable_record(pattern: dict, client_id: str) -> dict:
    evidence_chain = pattern.get("evidence_chain", [])
    finding_ids = ", ".join(e.get("finding_id", "") for e in evidence_chain)
    return {
        "Client ID": client_id,
        "Pattern ID": pattern.get("id"),
        "Pattern Type": pattern.get("pattern_type"),
        "Forces Involved": ", ".join(pattern.get("forces_involved", [])),
        "Sub-Layers Involved": ", ".join(str(s) for s in pattern.get("sub_layers_involved", []) if s),
        "Pattern Title": pattern.get("pattern_title"),
        "Description": pattern.get("description"),
        "Flow Description": pattern.get("flow_description"),
        "Business Impact": pattern.get("business_impact"),
        "Recommendation": pattern.get("recommendation"),
        "Strategic Significance": pattern.get("strategic_significance"),
        "Finding IDs in Chain": finding_ids,
        "Requires Validation": pattern.get("requires_validation", False),
    }

# ── Pass 3 helpers ────────────────────────────────────────────────────────────

def fetch_approved_evidence(client_id: str, engagement_id: str = None) -> list:
    log(f"Fetching approved evidence from Supabase for client: {client_id}...")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    url = (
        f"{SUPABASE_URL}/rest/v1/evidence_items"
        f"?client_id=eq.{client_id}"
        f"&include_in_report=eq.true"
        f"&order=force.asc,finding_type.asc"
    )
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    findings = response.json()
    if not findings:
        raise ValueError(f"No evidence found for client: {client_id}")
    log(f"  ✓ {len(findings)} approved evidence items retrieved")
    return findings


def fetch_approved_patterns(client_id: str, engagement_id: str = None) -> list:
    log(f"Fetching approved patterns from Supabase for client: {client_id}...")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    url = (
        f"{SUPABASE_URL}/rest/v1/cross_force_patterns"
        f"?client_id=eq.{client_id}"
        f"&order=strategic_significance.desc"
    )
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    patterns = response.json()
    log(f"  ✓ {len(patterns)} patterns retrieved")
    return patterns

 
def fetch_client_record(client_id: str) -> dict:
    """Fetch client intake record from Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/client_intakes?id=eq.{client_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"No client record found for id: {client_id}")
    return data[0]
 
 
def parse_report_sections(raw_report: str) -> dict:
    """Parse Claude's section-marked report into a dict of sections."""
    import re
    sections = {}
    pattern = r'\[([A-Z_]+)\](.*?)\[/\1\]'
    matches = re.findall(pattern, raw_report, re.DOTALL)
    for section_name, content in matches:
        sections[section_name] = content.strip()
    return sections
 
 
def parse_force_scores(scores_json_str: str) -> dict:
    """Parse the FORCE_SCORES JSON block safely."""
    import json
    try:
        return json.loads(scores_json_str)
    except Exception:
        try:
            import json_repair
            return json_repair.repair_json(scores_json_str, return_objects=True)
        except Exception:
            return {
                "execution": {"score": 0, "rationale": "Score unavailable"},
                "marketing": {"score": 0, "rationale": "Score unavailable"},
                "revenue": {"score": 0, "rationale": "Score unavailable"},
                "cross_force": {"score": 0, "rationale": "Score unavailable"},
            }
 
 
def score_color(score: int) -> str:
    """Return a color hex for a score value."""
    if score >= 8:
        return "#4FD1C5"   # Signal Teal — strong
    elif score >= 6:
        return "#90CDF4"   # Light blue — moderate
    elif score >= 4:
        return "#F6AD55"   # Amber — needs attention
    else:
        return "#FC8181"   # Red — critical
 
 
def render_html_report(sections: dict, client: dict, scores: dict, report_date: str, findings: list = None, patterns: list = None) -> str:
    """Render the full HTML report from parsed sections and client data."""

    company_name  = client.get("company_name", "")
    contact_name  = client.get("contact_name", "")

    exec_score   = scores.get("execution",   {})
    mkt_score    = scores.get("marketing",   {})
    rev_score    = scores.get("revenue",     {})
    cross_score  = scores.get("cross_force", {})

    # ── Build sources index from all findings ──────────────────────────────
    sources_raw = sections.get("SOURCES", "")
    sources_list = []
    for line in sources_raw.split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            parts = line.split(".", 1)
            if len(parts) == 2:
                sources_list.append(parts[1].strip())

    def source_ref(doc_name: str) -> str:
        for i, s in enumerate(sources_list, 1):
            if s.lower() in doc_name.lower() or doc_name.lower() in s.lower():
                return f'<span class="source-ref">[{i}]</span>'
        return ""

    # ── Parse executive summary ────────────────────────────────────────────
    def parse_exec_summary(text: str) -> tuple:
        takeaways = []
        narrative_lines = []
        critical_pattern = ""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("TAKEAWAY:"):
                takeaways.append(line[9:].strip())
            elif line.startswith("CRITICAL_PATTERN:"):
                critical_pattern = line[17:].strip()
            elif line:
                narrative_lines.append(line)
        narrative = " ".join(narrative_lines).strip()
        return takeaways, narrative, critical_pattern

    # ── Parse force section ────────────────────────────────────────────────
    def parse_force_section(text: str) -> dict:
        import re
        result = {"score": "", "takeaways": [], "narrative": [], "strengths": [], "gaps": [], "warnings": [], "recommendations": []}
        current_group = None
        current_finding = {}
        in_finding = False
        in_recs = False

        for line in text.split("\n"):
            line_stripped = line.strip()

            if line_stripped.startswith("SCORE:"):
                result["score"] = line_stripped[6:].strip()
            elif line_stripped.startswith("TAKEAWAY:"):
                result["takeaways"].append(line_stripped[9:].strip())
            elif line_stripped == "STRENGTHS:":
                current_group = "strengths"
                in_recs = False
            elif line_stripped == "GAPS:":
                current_group = "gaps"
                in_recs = False
            elif line_stripped == "WARNINGS:":
                current_group = "warnings"
                in_recs = False
            elif line_stripped == "RECOMMENDATIONS:":
                current_group = None
                in_recs = True
                in_finding = False
            elif line_stripped == "FINDING_START":
                current_finding = {}
                in_finding = True
            elif line_stripped == "FINDING_END":
                if current_group and current_finding:
                    result[current_group].append(current_finding)
                current_finding = {}
                in_finding = False
            elif in_finding:
                if line_stripped.startswith("TITLE:"):
                    current_finding["title"] = line_stripped[6:].strip()
                elif line_stripped.startswith("TEXT:"):
                    current_finding["text"] = line_stripped[5:].strip()
                elif line_stripped.startswith("IMPACT:"):
                    current_finding["impact"] = line_stripped[7:].strip()
                elif line_stripped.startswith("SOURCE:"):
                    current_finding["source"] = line_stripped[7:].strip()
                elif line_stripped.startswith("VALIDATION_NOTE:"):
                    current_finding["validation"] = line_stripped[16:].strip()
            elif in_recs and line_stripped and line_stripped[0].isdigit():
                result["recommendations"].append(line_stripped)
            elif not in_finding and not in_recs and current_group is None and line_stripped and not line_stripped.startswith("SCORE:") and not line_stripped.startswith("TAKEAWAY:"):
                result["narrative"].append(line_stripped)

        return result

    # ── Parse cross-force patterns ─────────────────────────────────────────
    def parse_patterns(text: str) -> list:
        patterns_out = []
        current = {}
        for line in text.split("\n"):
            line = line.strip()
            if line == "PATTERN_START":
                current = {}
            elif line == "PATTERN_END":
                if current:
                    patterns_out.append(current)
                current = {}
            elif line.startswith("PATTERN_NAME:"):
                current["name"] = line[13:].strip()
            elif line.startswith("PATTERN_TYPE:"):
                current["type"] = line[13:].strip()
            elif line.startswith("PATTERN_SUMMARY:"):
                current["summary"] = line[16:].strip()
            elif line.startswith("PATTERN_FLOW:"):
                current["flow"] = line[13:].strip()
            elif line.startswith("FORCES:"):
                current["forces"] = line[7:].strip()
            elif line.startswith("PATTERN_RECOMMENDATION:"):
                current["recommendation"] = line[23:].strip()
        return patterns_out

    # ── Parse next steps ───────────────────────────────────────────────────
    def parse_next_steps(text: str) -> tuple:
        steps = []
        closing_lines = []
        in_steps = True
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if in_steps and line and line[0].isdigit() and "—" in line:
                steps.append(line)
            elif in_steps and line and not (line[0].isdigit()):
                in_steps = False
                closing_lines.append(line)
            elif not in_steps:
                closing_lines.append(line)
        return steps, " ".join(closing_lines)

    # ── HTML helpers ───────────────────────────────────────────────────────
    def score_bar(label: str, score_data: dict) -> str:
        s = score_data.get("score", 0)
        rationale = score_data.get("rationale", "")
        color = score_color(s)
        pct = int((s / 10) * 100)
        return f"""
        <div class="score-item">
            <div class="score-label">{label}</div>
            <div class="score-bar-track">
                <div class="score-bar-fill" style="width:{pct}%; background:{color};"></div>
            </div>
            <div class="score-number" style="color:{color};">{s}<span class="score-denom">/10</span></div>
            <div class="score-rationale">{rationale}</div>
        </div>"""

    def render_findings_group(group: list, group_type: str) -> str:
        if not group:
            return ""
        label_map = {"strengths": "Strengths", "gaps": "Gaps", "warnings": "Warnings"}
        html = f'<div class="finding-group-label {group_type}">{label_map.get(group_type, group_type)}</div>\n'
        for f in group:
            src_ref = source_ref(f.get("source", ""))
            validation = f'<div class="validation-note">⚠ {f.get("validation", "")}</div>' if f.get("validation") else ""
            html += f"""
            <div class="finding-card {group_type}">
                <div class="finding-title">{f.get("title", "")}</div>
                <div class="finding-text">{f.get("text", "")}</div>
                {validation}
                <div class="finding-impact"><strong>Business Impact:</strong> {f.get("impact", "")}</div>
                <div class="finding-source">Source: {f.get("source", "")} {src_ref}</div>
            </div>"""
        return html

    def render_force_section(section_key: str, title: str, score_data: dict) -> str:
        text = sections.get(section_key, "")
        parsed = parse_force_section(text)
        s = score_data.get("score", 0)
        color = score_color(s)
        pct = int((s / 10) * 100)

        takeaway_html = ""
        if parsed["takeaways"]:
            takeaway_html = '<ul class="takeaway-list">' + "".join(f'<li>{t}</li>' for t in parsed["takeaways"]) + '</ul>'

        narrative_html = ""
        if parsed["narrative"]:
            narrative_html = f'<div class="force-narrative"><p>{" ".join(parsed["narrative"])}</p></div>'

        findings_html = (
            render_findings_group(parsed["strengths"], "strengths") +
            render_findings_group(parsed["gaps"], "gaps") +
            render_findings_group(parsed["warnings"], "warnings")
        )

        recs_html = ""
        if parsed["recommendations"]:
            recs_html = '<div class="recommendations-block"><div class="recs-label">Recommendations</div><ol class="recs-list">'
            for r in parsed["recommendations"]:
                parts = r.split(".", 1)
                rec_text = parts[1].strip() if len(parts) == 2 else r
                recs_html += f"<li>{rec_text}</li>"
            recs_html += "</ol></div>"

        return f"""
<div class="page page-break">
  <div class="confidential-banner">Confidential · {company_name} · Coherynce Intelligence</div>
  <div class="section-label">Force Analysis</div>
  <div class="section-title">{title}</div>
  <div class="force-score-header">
    <div class="force-score-bar-track">
      <div class="force-score-bar-fill" style="width:{pct}%; background:{color};"></div>
    </div>
    <span class="force-score-number" style="color:{color};">{s}/10</span>
    <span class="force-score-rationale">{score_data.get("rationale", "")}</span>
  </div>
  {takeaway_html}
  {narrative_html}
  <div class="findings-container">
    {findings_html}
  </div>
  {recs_html}
  <div class="footer">
    <span class="footer-brand">Coherynce</span>
    <span>Resonance Analysis · {company_name} · {report_date}</span>
  </div>
</div>"""

    # ── Parse all sections ─────────────────────────────────────────────────
    exec_takeaways, exec_narrative, critical_pattern = parse_exec_summary(sections.get("EXECUTIVE_SUMMARY", ""))
    parsed_patterns = parse_patterns(sections.get("CROSS_FORCE_PATTERNS", ""))
    next_steps, closing_text = parse_next_steps(sections.get("NEXT_STEPS", ""))

    # ── Pattern type colors ────────────────────────────────────────────────
    def pattern_color(ptype: str) -> str:
        ptype_lower = ptype.lower()
        if "vicious" in ptype_lower:
            return "#FC8181"
        elif "leverage" in ptype_lower:
            return "#4FD1C5"
        elif "bottleneck" in ptype_lower:
            return "#F6AD55"
        elif "virtuous" in ptype_lower:
            return "#68D391"
        return "#A0AEC0"

    # ── Build patterns HTML ────────────────────────────────────────────────
    patterns_html = ""
    for p in parsed_patterns:
        pcolor = pattern_color(p.get("type", ""))
        patterns_html += f"""
        <div class="pattern-block" style="border-left: 4px solid {pcolor};">
            <div class="pattern-type-badge" style="color:{pcolor};">{p.get("type", "")}</div>
            <div class="pattern-title">{p.get("name", "")}</div>
            <div class="pattern-forces">{p.get("forces", "")}</div>
            <div class="pattern-body">
                <p>{p.get("summary", "")}</p>
                <p class="pattern-flow"><strong>How it cascades:</strong> {p.get("flow", "")}</p>
            </div>
            <div class="pattern-recommendation">
                <div class="recs-label">Recommendation</div>
                <p>{p.get("recommendation", "")}</p>
            </div>
        </div>"""

    # ── Build sources HTML ─────────────────────────────────────────────────
    sources_html = ""
    if sources_list:
        sources_html = '<ol class="sources-list">' + "".join(f"<li>{s}</li>" for s in sources_list) + "</ol>"

    # ── Build next steps HTML ──────────────────────────────────────────────
    steps_html = ""
    if next_steps:
        steps_html = '<ol class="next-steps-list">' + "".join(f"<li>{s.split('.', 1)[1].strip() if '.' in s else s}</li>" for s in next_steps) + "</ol>"

    # ── Exec summary takeaways ─────────────────────────────────────────────
    exec_takeaways_html = ""
    if exec_takeaways:
        exec_takeaways_html = '<ul class="takeaway-list exec-takeaways">' + "".join(f"<li>{t}</li>" for t in exec_takeaways) + "</ul>"

    critical_pattern_html = ""
    if critical_pattern:
        critical_pattern_html = f'<div class="critical-pattern-callout">Critical Pattern: <strong>{critical_pattern}</strong></div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Resonance Analysis — {company_name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

  :root {{
    --deep-slate:     #1A2830;
    --mid-slate:      #243440;
    --teal:           #4FD1C5;
    --teal-light:     #81E6D9;
    --silver:         #E2E8F0;
    --silver-dim:     #8A9BB0;
    --cream:          #F7F9FB;
    --white:          #FFFFFF;
    --body-text:      #2D3748;
    --amber:          #F6AD55;
    --red-soft:       #FC8181;
    --green-soft:     #68D391;
    --gap-color:      #FC8181;
    --strength-color: #4FD1C5;
    --warning-color:  #F6AD55;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Inter', sans-serif;
    font-weight: 400;
    color: var(--deep-slate);
    background: var(--white);
    font-size: 18px;
    line-height: 1.75;
  }}

  /* ── Cover ── */
  .cover {{
    background: var(--deep-slate);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 60px;
    text-align: center;
    page-break-after: always;
  }}
  .cover-wordmark {{
    font-family: 'Inter', sans-serif;
    font-weight: 300;
    font-size: 13px;
    letter-spacing: 6px;
    color: var(--silver);
    text-transform: uppercase;
    margin-bottom: 64px;
  }}
  .cover-divider {{
    width: 48px;
    height: 1px;
    background: var(--teal);
    margin: 0 auto 48px;
  }}
  .cover-label {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 13px;
    letter-spacing: 0.12em;
    color: var(--teal);
    text-transform: uppercase;
    margin-bottom: 20px;
  }}
  .cover-company {{
    font-family: 'Playfair Display', serif;
    font-weight: 700;
    font-size: 48px;
    color: var(--white);
    line-height: 1.2;
    margin-bottom: 16px;
  }}
  .cover-meta {{
    font-family: 'Inter', sans-serif;
    font-weight: 300;
    font-size: 15px;
    color: var(--silver-dim);
    letter-spacing: 0.5px;
    margin-top: 48px;
    line-height: 1.8;
  }}

  /* ── Page layout ── */
  .page {{
    padding: 96px 80px;
    max-width: 880px;
    margin: 0 auto;
  }}
  .page-break {{ page-break-before: always; }}
  .confidential-banner {{
    text-align: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--silver-dim);
    margin-bottom: 48px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--silver);
  }}

  /* ── Section headers ── */
  .section-label {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 13px;
    letter-spacing: 0.12em;
    color: var(--teal);
    text-transform: uppercase;
    margin-bottom: 16px;
  }}
  .section-title {{
    font-family: 'Playfair Display', serif;
    font-weight: 700;
    font-size: 40px;
    color: var(--deep-slate);
    line-height: 1.2;
    margin-bottom: 40px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--silver);
  }}
  .section-title.italic {{ font-style: italic; }}

  /* ── Takeaway bullets ── */
  .takeaway-list {{
    list-style: none;
    margin: 0 0 32px 0;
    padding: 0;
  }}
  .takeaway-list li {{
    padding: 14px 20px 14px 24px;
    margin-bottom: 10px;
    border-left: 3px solid var(--teal);
    background: var(--cream);
    font-size: 17px;
    font-weight: 500;
    color: var(--deep-slate);
    line-height: 1.6;
    border-radius: 0 4px 4px 0;
  }}
  .exec-takeaways li {{
    font-size: 18px;
    padding: 16px 24px 16px 28px;
  }}

  /* ── Critical pattern callout ── */
  .critical-pattern-callout {{
    background: var(--deep-slate);
    color: var(--teal-light);
    padding: 20px 28px;
    margin: 32px 0;
    font-size: 15px;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
    border-radius: 4px;
  }}

  /* ── Narrative prose ── */
  .prose p, .force-narrative p {{
    margin-bottom: 20px;
    color: var(--body-text);
    font-size: 18px;
    line-height: 1.8;
  }}

  /* ── Score grid ── */
  .score-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin: 48px 0;
  }}
  .score-item {{
    padding: 32px;
    background: var(--cream);
    border-radius: 8px;
    border: 1px solid var(--silver);
    border-top: 3px solid var(--teal);
    box-shadow: 0 2px 16px rgba(26,40,48,0.06);
  }}
  .score-label {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 13px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--deep-slate);
    margin-bottom: 16px;
  }}
  .score-bar-track {{
    height: 4px;
    background: var(--silver);
    border-radius: 2px;
    margin-bottom: 12px;
  }}
  .score-bar-fill {{
    height: 4px;
    border-radius: 2px;
  }}
  .score-number {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 36px;
    line-height: 1;
    margin-bottom: 10px;
  }}
  .score-denom {{
    font-size: 18px;
    color: var(--silver-dim);
  }}
  .score-rationale {{
    font-family: 'Inter', sans-serif;
    font-weight: 400;
    font-size: 14px;
    color: var(--silver-dim);
    line-height: 1.6;
    font-style: italic;
  }}
  .score-note {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--silver-dim);
    text-align: center;
    margin-top: 20px;
    letter-spacing: 0.06em;
  }}

  /* ── Force score header ── */
  .force-score-header {{
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 32px;
    padding: 20px 28px;
    background: var(--cream);
    border-radius: 8px;
    border: 1px solid var(--silver);
    border-left: 4px solid var(--teal);
  }}
  .force-score-bar-track {{
    flex: 1;
    height: 4px;
    background: var(--silver);
    border-radius: 2px;
  }}
  .force-score-bar-fill {{
    height: 4px;
    border-radius: 2px;
  }}
  .force-score-number {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 20px;
    white-space: nowrap;
  }}
  .force-score-rationale {{
    font-size: 14px;
    color: var(--silver-dim);
    font-style: italic;
    flex: 2;
    line-height: 1.5;
  }}

  /* ── Finding group labels ── */
  .finding-group-label {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 36px 0 16px;
    padding: 8px 16px;
    display: inline-block;
    border-radius: 0 4px 4px 0;
  }}
  .finding-group-label.strengths {{
    color: var(--strength-color);
    border-left: 3px solid var(--strength-color);
    background: rgba(79,209,197,0.06);
  }}
  .finding-group-label.gaps {{
    color: var(--gap-color);
    border-left: 3px solid var(--gap-color);
    background: rgba(252,129,129,0.06);
  }}
  .finding-group-label.warnings {{
    color: var(--warning-color);
    border-left: 3px solid var(--warning-color);
    background: rgba(246,173,85,0.06);
  }}

  /* ── Finding cards ── */
  .finding-card {{
    background: var(--white);
    border: 1px solid var(--silver);
    border-radius: 8px;
    padding: 28px 32px;
    margin-bottom: 16px;
    box-shadow: 0 2px 12px rgba(26,40,48,0.05);
  }}
  .finding-card.strengths {{ border-left: 4px solid var(--strength-color); }}
  .finding-card.gaps {{ border-left: 4px solid var(--gap-color); }}
  .finding-card.warnings {{ border-left: 4px solid var(--warning-color); }}
  .finding-title {{
    font-family: 'Playfair Display', serif;
    font-weight: 600;
    font-size: 20px;
    color: var(--deep-slate);
    margin-bottom: 12px;
    line-height: 1.3;
  }}
  .finding-text {{
    font-size: 17px;
    color: var(--body-text);
    line-height: 1.75;
    margin-bottom: 14px;
  }}
  .finding-impact {{
    font-size: 15px;
    color: #4A5568;
    line-height: 1.6;
    margin-bottom: 10px;
    padding: 12px 16px;
    background: var(--cream);
    border-radius: 4px;
  }}
  .finding-source {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--silver-dim);
    margin-top: 8px;
    letter-spacing: 0.04em;
  }}
  .source-ref {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--teal);
    margin-left: 4px;
  }}
  .validation-note {{
    font-size: 13px;
    color: var(--amber);
    font-style: italic;
    margin-bottom: 10px;
    padding: 8px 12px;
    background: #FFFBEB;
    border-left: 2px solid var(--amber);
    border-radius: 0 4px 4px 0;
  }}

  /* ── Recommendations ── */
  .recommendations-block {{
    margin-top: 40px;
    padding: 32px 36px;
    background: var(--deep-slate);
    border-radius: 8px;
  }}
  .recs-label {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 13px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--teal);
    margin-bottom: 20px;
  }}
  .recs-list {{
    list-style: decimal;
    padding-left: 20px;
  }}
  .recs-list li {{
    color: var(--silver);
    font-size: 17px;
    line-height: 1.7;
    margin-bottom: 12px;
  }}

  /* ── Patterns ── */
  .pattern-block {{
    background: var(--white);
    border: 1px solid var(--silver);
    border-radius: 8px;
    padding: 36px 40px;
    margin-bottom: 32px;
    box-shadow: 0 2px 16px rgba(26,40,48,0.06);
  }}
  .pattern-type-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 10px;
  }}
  .pattern-title {{
    font-family: 'Playfair Display', serif;
    font-weight: 700;
    font-size: 24px;
    color: var(--deep-slate);
    margin-bottom: 10px;
    line-height: 1.3;
  }}
  .pattern-forces {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--silver-dim);
    letter-spacing: 0.08em;
    margin-bottom: 20px;
  }}
  .pattern-body p {{
    margin-bottom: 14px;
    font-size: 17px;
    color: var(--body-text);
    line-height: 1.75;
  }}
  .pattern-flow {{ font-style: italic; }}
  .pattern-recommendation {{
    margin-top: 24px;
    padding: 20px 24px;
    background: var(--cream);
    border-left: 3px solid var(--teal);
    border-radius: 0 4px 4px 0;
  }}
  .pattern-recommendation .recs-label {{
    color: var(--teal);
    margin-bottom: 10px;
  }}
  .pattern-recommendation p {{
    font-size: 17px;
    color: var(--deep-slate);
    line-height: 1.7;
    margin-top: 8px;
  }}

  /* ── Next steps ── */
  .next-steps-list {{
    list-style: none;
    padding: 0;
    margin-bottom: 40px;
    counter-reset: steps;
  }}
  .next-steps-list li {{
    counter-increment: steps;
    font-size: 17px;
    color: var(--body-text);
    line-height: 1.7;
    margin-bottom: 16px;
    padding: 18px 24px 18px 64px;
    background: var(--cream);
    border-radius: 8px;
    border: 1px solid var(--silver);
    position: relative;
  }}
  .next-steps-list li::before {{
    content: counter(steps);
    position: absolute;
    left: 20px;
    top: 50%;
    transform: translateY(-50%);
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 20px;
    color: var(--teal);
  }}
  .closing-block {{
    background: var(--deep-slate);
    color: var(--white);
    padding: 48px 56px;
    margin-top: 40px;
    border-radius: 8px;
  }}
  .closing-block p {{
    color: var(--silver);
    margin-bottom: 16px;
    font-size: 18px;
    line-height: 1.8;
  }}
  .closing-final {{
    font-family: 'Playfair Display', serif;
    font-style: italic;
    font-size: 22px;
    color: var(--teal-light) !important;
    margin-top: 24px !important;
    line-height: 1.5 !important;
  }}

  /* ── Sources ── */
  .sources-list {{
    list-style: none;
    padding: 0;
    counter-reset: sources;
  }}
  .sources-list li {{
    counter-increment: sources;
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    color: var(--body-text);
    line-height: 1.6;
    margin-bottom: 12px;
    padding: 14px 20px 14px 56px;
    background: var(--cream);
    border-radius: 4px;
    border: 1px solid var(--silver);
    position: relative;
  }}
  .sources-list li::before {{
    content: counter(sources);
    position: absolute;
    left: 18px;
    top: 50%;
    transform: translateY(-50%);
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 13px;
    color: var(--teal);
  }}

  /* ── Footer ── */
  .footer {{
    margin-top: 56px;
    padding-top: 20px;
    border-top: 1px solid var(--silver);
    font-size: 13px;
    color: var(--silver-dim);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .footer-brand {{
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-size: 12px;
    color: var(--teal);
  }}
</style>
</head>
<body>

<!-- ── COVER PAGE ── -->
<div class="cover">
  <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="36" cy="36" r="34" stroke="#4FD1C5" stroke-width="1" opacity="0.3"/>
    <circle cx="36" cy="36" r="27" stroke="#4FD1C5" stroke-width="1" opacity="0.5"/>
    <circle cx="36" cy="36" r="20" stroke="#4FD1C5" stroke-width="1.5" opacity="0.7"/>
    <circle cx="36" cy="36" r="13" stroke="#4FD1C5" stroke-width="2" opacity="0.9"/>
    <circle cx="36" cy="36" r="6" fill="#4FD1C5"/>
  </svg>
  <div class="cover-wordmark">Coherynce</div>
  <div class="cover-divider"></div>
  <div class="cover-label">Resonance Analysis Report</div>
  <div class="cover-company">{company_name}</div>
  <div class="cover-meta">
    Prepared for {contact_name} &nbsp;·&nbsp; {report_date}<br/>
    Confidential — For Internal Use Only
  </div>
</div>

<!-- ── EXECUTIVE SUMMARY ── -->
<div class="page page-break">
  <div class="confidential-banner">Confidential · {company_name} · Coherynce Intelligence</div>
  <div class="section-label">Overview</div>
  <div class="section-title italic">Executive Summary</div>
  {exec_takeaways_html}
  <div class="prose">
    {"".join(f"<p>{p.strip()}</p>" for p in exec_narrative.split("  ") if p.strip())}
  </div>
  {critical_pattern_html}
  <div class="footer">
    <span class="footer-brand">Coherynce</span>
    <span>Resonance Analysis · {company_name} · {report_date}</span>
  </div>
</div>

<!-- ── RESONANCE SCORES ── -->
<div class="page page-break">
  <div class="confidential-banner">Confidential · {company_name} · Coherynce Intelligence</div>
  <div class="section-label">Diagnostic</div>
  <div class="section-title">Resonance Scores</div>
  <div class="score-grid">
    {score_bar("Execution", exec_score)}
    {score_bar("Marketing", mkt_score)}
    {score_bar("Revenue", rev_score)}
    {score_bar("Cross-Force", cross_score)}
  </div>
  <div class="score-note">AI Preliminary Scores · Final scores set by consultant after review</div>
  <div class="footer">
    <span class="footer-brand">Coherynce</span>
    <span>Resonance Analysis · {company_name} · {report_date}</span>
  </div>
</div>

<!-- ── FORCE SECTIONS ── -->
{render_force_section("EXECUTION_ANALYSIS", "Execution", exec_score)}
{render_force_section("MARKETING_ANALYSIS", "Marketing", mkt_score)}
{render_force_section("REVENUE_ANALYSIS", "Revenue", rev_score)}

<!-- ── CROSS-FORCE PATTERNS ── -->
<div class="page page-break">
  <div class="confidential-banner">Confidential · {company_name} · Coherynce Intelligence</div>
  <div class="section-label">Systemic Patterns</div>
  <div class="section-title">Cross-Force Analysis</div>
  {patterns_html}
  <div class="footer">
    <span class="footer-brand">Coherynce</span>
    <span>Resonance Analysis · {company_name} · {report_date}</span>
  </div>
</div>

<!-- ── NEXT STEPS ── -->
<div class="page page-break">
  <div class="confidential-banner">Confidential · {company_name} · Coherynce Intelligence</div>
  <div class="section-label">Next Steps</div>
  <div class="section-title">Moving Forward</div>
  {steps_html}
  <div class="closing-block">
    {"".join(f'<p class="closing-final">{p}</p>' if i == len(closing_text.split("  "))-1 else f"<p>{p}</p>" for i, p in enumerate(closing_text.split("  ")) if p.strip())}
  </div>
  <div class="footer">
    <span class="footer-brand">Coherynce</span>
    <span>info@coherynce.com</span>
  </div>
</div>

<!-- ── SOURCES ── -->
<div class="page page-break">
  <div class="confidential-banner">Confidential · {company_name} · Coherynce Intelligence</div>
  <div class="section-label">References</div>
  <div class="section-title">Sources</div>
  {sources_html}
  <div class="footer">
    <span class="footer-brand">Coherynce</span>
    <span>Resonance Analysis · {company_name} · {report_date}</span>
  </div>
</div>

</body>
</html>"""
    return html
 
 
def generate_pdf_via_docraptor(html: str, document_name: str) -> bytes:
    """Send HTML to DocRaptor and return PDF bytes."""
    DOCRAPTOR_KEY = os.environ.get("DOCRAPTOR_API_KEY", "")
    if not DOCRAPTOR_KEY:
        raise ValueError("DOCRAPTOR_API_KEY not set in .env")
 
    log("Sending report to DocRaptor for PDF rendering...")
    response = requests.post(
        "https://docraptor.com/docs",
        auth=(DOCRAPTOR_KEY, ""),
        json={
            "type": "pdf",
            "name": document_name,
            "document_content": html,
            "prince_options": {
                "media": "print",
                "baseurl": "https://coherynce.com",
            },
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise Exception(f"DocRaptor error: {response.status_code} — {response.text[:300]}")
    log("  ✓ PDF generated successfully")
    return response.content
 
 
def store_report_in_supabase(pdf_bytes: bytes, client: dict, timestamp: str) -> str:
    """Store PDF in Supabase Storage under client's folder. Returns the storage path."""
    token       = client.get("upload_token", client.get("id"))
    company_raw = client.get("company_name", "client").lower().replace(" ", "_")
    folder      = f"{token}_{company_raw}"
    filename    = f"resonance_analysis_{timestamp}.pdf"
    path        = f"reports/{folder}/{filename}"
 
    log(f"Storing PDF in Supabase Storage: {path}...")
    url = f"{SUPABASE_URL}/storage/v1/object/client-documents/{path}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/pdf",
        "x-upsert": "true",
    }
    response = requests.post(url, headers=headers, data=pdf_bytes, timeout=60)
    if response.status_code not in (200, 201):
        raise Exception(f"Supabase storage upload failed: {response.status_code} — {response.text}")
    log(f"  ✓ PDF stored at: {path}")
    return path
 
 
def send_report_notification(client: dict, storage_path: str, report_date: str):
    """Email Elisha that the report is ready for review."""
    RESEND_KEY    = os.environ.get("RESEND_API_KEY", "")
    PORTAL_URL    = os.environ.get("PORTAL_BASE_URL", "https://portal.coherynce.com")
    NOTIFY_EMAIL  = "elisha@coherynce.com"
    FROM_EMAIL    = "noreply@send.coherynce.com"
 
    if not RESEND_KEY:
        log("RESEND_API_KEY not set — skipping notification email")
        return
 
    company     = client.get("company_name", "")
    token       = client.get("upload_token", "")
    review_link = f"{PORTAL_URL}/upload/{token}"
 
    log("Sending report-ready notification to Elisha...")
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": FROM_EMAIL,
            "to": NOTIFY_EMAIL,
            "subject": f"Report ready for review: {company}",
            "html": f"""
                <p>The Resonance Analysis Report for <strong>{company}</strong> has been generated
                and is ready for your review.</p>
                <p><strong>Storage path:</strong> {storage_path}</p>
                <p><strong>Client portal:</strong> <a href="{review_link}">{review_link}</a></p>
                <p>Review the report, make any edits to the HTML if needed, then approve delivery
                to the client.</p>
                <p>— Coherynce Pipeline</p>
            """,
        },
        timeout=30,
    )
    if response.status_code in (200, 201):
        log("  ✓ Notification sent to Elisha")
    else:
        log(f"  ✗ Notification failed: {response.status_code} — {response.text}")
 
 
def deliver_report_to_client(client: dict, storage_path: str, report_date: str):
    """Email client with their report link."""
    RESEND_KEY   = os.environ.get("RESEND_API_KEY", "")
    PORTAL_URL   = os.environ.get("PORTAL_BASE_URL", "https://portal.coherynce.com")
    FROM_EMAIL   = "noreply@send.coherynce.com"
 
    if not RESEND_KEY:
        log("RESEND_API_KEY not set — skipping client delivery email")
        return
 
    token        = client.get("upload_token", "")
    company      = client.get("company_name", "")
    contact_name = client.get("contact_name", "")
    contact_email= client.get("contact_email", "")
    report_link  = f"{PORTAL_URL}/upload/{token}"
 
    log(f"Delivering report to client: {contact_email}...")
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": FROM_EMAIL,
            "to": contact_email,
            "subject": f"Your Resonance Analysis is ready — {company}",
            "html": f"""
                <p>Hi {contact_name},</p>
                <p>Your Resonance Analysis Report for <strong>{company}</strong> is ready.</p>
                <p>You can view and download your report from your secure document portal:</p>
                <p><a href="{report_link}">{report_link}</a></p>
                <p>Elisha will be in touch to schedule your 90-minute Vectoring Session,
                where you'll walk through the findings and recommendations together.</p>
                <p>— Coherynce</p>
            """,
        },
        timeout=30,
    )
    if response.status_code in (200, 201):
        log(f"  ✓ Report delivered to {contact_email}")
    else:
        log(f"  ✗ Client delivery failed: {response.status_code} — {response.text}")
 
 

# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(client_id: str, file_urls: list, client_context: dict):
    """Full pipeline: Extract → Chunk → Embed → Retrieve → Pass1A → Pass1B → Pass1C → Pass2 → Store."""
    start = datetime.now()
    engagement_id = str(uuid.uuid4())
    log("=== Resonance Analyzer Pipeline Starting ===")
    log(f"Client ID     : {client_id}")
    log(f"Engagement ID : {engagement_id}")
    log(f"Documents     : {len(file_urls)}")
    log("")

    # ── Step 1: Extract ───────────────────────────────────────────────────────
    update_supabase_pipeline_status(client_id, "extracting")
    extracted_docs = call_flask_extraction(file_urls)
    document_text = compile_document_text(extracted_docs, client_context)
    log(f"  Document text compiled ({len(document_text):,} characters)")

    # ── Step 2: Chunk ─────────────────────────────────────────────────────────
    log("Chunking extracted documents...")
    chunks = chunk_documents(extracted_docs)
    log(f"  {len(chunks)} chunks produced")

    # ── Step 3: Embed ─────────────────────────────────────────────────────────
    log("Embedding chunks → Supabase pgvector...")
    clear_engagement_chunks(engagement_id)
    embed_chunks(chunks, client_id=client_id, engagement_id=engagement_id)

    # ── Step 4: Retrieve + Pass 1A (Execution) ────────────────────────────────
    update_supabase_pipeline_status(client_id, "pass1_execution")
    log("Retrieving context for Execution force...")
    exec_context = retrieve_for_force("Execution", engagement_id)
    exec_findings = call_claude(
        prompt=fill_pass1_template(PASS1A_TEMPLATE, client_context, exec_context),
        label="Pass 1A — Execution Force",
    )

    # ── Step 5: Retrieve + Pass 1B (Marketing) ────────────────────────────────
    update_supabase_pipeline_status(client_id, "pass1_marketing")
    log("Retrieving context for Marketing force...")
    mkt_context = retrieve_for_force("Marketing", engagement_id)
    mkt_findings = call_claude(
        prompt=fill_pass1_template(PASS1B_TEMPLATE, client_context, mkt_context),
        label="Pass 1B — Marketing Force",
    )

    # ── Step 6: Retrieve + Pass 1C (Revenue) ─────────────────────────────────
    update_supabase_pipeline_status(client_id, "pass1_revenue")
    log("Retrieving context for Revenue force...")
    rev_context = retrieve_for_force("Revenue", engagement_id)
    rev_findings = call_claude(
        prompt=fill_pass1_template(PASS1C_TEMPLATE, client_context, rev_context),
        label="Pass 1C — Revenue Force",
    )

    # ── Step 7: Retrieve + Pass 2 (Cross-Force Patterns) ─────────────────────
    update_supabase_pipeline_status(client_id, "pass2_patterns")
    log("Retrieving context for Pass 2 cross-force patterns...")
    pass2_context = retrieve_for_pass2(engagement_id)
    all_findings = exec_findings + mkt_findings + rev_findings

    # Build cross-force retrieved text for Pass 2
    pass2_chunks_text = []
    for pair in pass2_context.get("pairs", []):
        pass2_chunks_text.append(f"\n── {pair['pair_name']} ──")
        for chunk in pair["retrieved_chunks"]:
            pass2_chunks_text.append(
                f"[{chunk['document_name']} / {chunk['structural_location']}]\n{chunk['chunk_text']}"
            )
    pass2_retrieved_text = "\n".join(pass2_chunks_text) if pass2_chunks_text else document_text[:40000]

    patterns = call_claude(
        prompt=fill_pass2_template(PASS2_TEMPLATE, all_findings, pass2_retrieved_text),
        label="Pass 2 — Cross-Force Pattern Detection",
    )

    # ── Step 8: Save output ───────────────────────────────────────────────────
    output_dir = "pipeline_outputs"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"{client_id}_{timestamp}.json")
    with open(output_path, "w") as f:
        json.dump({
            "client_id": client_id,
            "engagement_id": engagement_id,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_findings": exec_findings,
            "marketing_findings": mkt_findings,
            "revenue_findings": rev_findings,
            "cross_force_patterns": patterns,
        }, f, indent=2)
    log(f"  ✓ Full JSON output saved → {output_path}")

    # ── Step 9: Store ─────────────────────────────────────────────────────────
    write_to_supabase("evidence_items", [build_evidence_supabase_record(f, client_id, engagement_id) for f in all_findings])
    write_to_supabase("cross_force_patterns", [build_pattern_supabase_record(p, client_id, engagement_id) for p in patterns])
    write_to_airtable(AIRTABLE_EVIDENCE_TABLE, [build_evidence_airtable_record(f, client_id) for f in all_findings])
    write_to_airtable(AIRTABLE_PATTERNS_TABLE, [build_pattern_airtable_record(p, client_id) for p in patterns])

    update_supabase_pipeline_status(client_id, "evidence_ready")
    elapsed = (datetime.now() - start).seconds
    log("")
    log(f"=== Pipeline Complete in {elapsed}s ===")
    log(f"  Execution findings  : {len(exec_findings)}")
    log(f"  Marketing findings  : {len(mkt_findings)}")
    log(f"  Revenue findings    : {len(rev_findings)}")
    log(f"  Cross-force patterns: {len(patterns)}")
    log(f"  Engagement ID       : {engagement_id}")
    log(f"  Output file         : {output_path}")
    log("")
    log("Next step: Open pipeline_outputs/ folder and review the JSON.")

# ── Pass 3 report generation ──────────────────────────────────────────────────

def run_pass3(client_id: str, deliver_to_client: bool = False):
    """
    Pass 3: Generate report from approved findings → PDF → store → notify.
 
    Run after:
      1. python sync_airtable_to_supabase.py --client_id CLIENT_ID
      2. python orchestrator.py --pass3 --client_id CLIENT_ID
 
    Add --deliver flag to also send the report to the client.
    """
    from datetime import datetime, timezone
    start = datetime.now()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_date = datetime.now().strftime("%B %d, %Y")
 
    log("=== Pass 3 — Report Generation ===")
    log(f"Client ID: {client_id}")
    log("")
 
    # ── Fetch data ────────────────────────────────────────────────────────────
    client   = fetch_client_record(client_id)
    findings = fetch_approved_evidence(client_id)
    patterns = fetch_approved_patterns(client_id)
 
    if not findings:
        log("✗ No approved findings found. Run sync_airtable_to_supabase.py first.")
        return
 
    client_context = {
        "company_name":    client.get("company_name", ""),
        "stage":           client.get("business_stage", "Not provided"),
        "purpose":         client.get("primary_challenge", "Not provided"),
        "vision":          client.get("goals", "Not provided"),
        "objectives":      client.get("goals", "Not provided"),
        "founder_tension": client.get("intake_notes", "Not provided"),
    }
 
    # ── Build prompt ──────────────────────────────────────────────────────────
    import json
    prompt = (
        PASS3_TEMPLATE
        .replace("{{company_name}}",    client_context.get("company_name") or "Not specified")
        .replace("{{stage}}",           client_context.get("stage") or "Not specified")
        .replace("{{purpose}}",         client_context.get("core_purpose") or client_context.get("purpose") or "Not specified")
        .replace("{{vision}}",          client_context.get("vision") or "Not specified")
        .replace("{{objectives}}",      client_context.get("objectives") or "Not specified")
        .replace("{{founder_tension}}", client_context.get("founder_tension") or "Not specified")
        .replace("{{evidence_json}}",   json.dumps(findings, indent=2))
        .replace("{{patterns_json}}",   json.dumps(patterns, indent=2))
    )
 
    # ── Call Claude ───────────────────────────────────────────────────────────
    update_supabase_pipeline_status(client_id, "pass3_report_generation")
    log("Calling Claude — Pass 3 Report Generation...")
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": prompt}],
    }
    import time
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=body,
        timeout=180,
    )
    response.raise_for_status()
    raw_report = response.json()["content"][0]["text"].strip()
    log("  ✓ Report narrative generated")
 
    # ── Parse sections ────────────────────────────────────────────────────────
    sections = parse_report_sections(raw_report)
    scores   = parse_force_scores(sections.get("FORCE_SCORES", "{}"))
    log(f"  ✓ Sections parsed: {list(sections.keys())}")
 
    # ── Save raw report locally ───────────────────────────────────────────────
    output_dir = "pipeline_outputs"
    os.makedirs(output_dir, exist_ok=True)
    raw_path = os.path.join(output_dir, f"{client_id}_report_{timestamp}.txt")
    with open(raw_path, "w") as f:
        f.write(raw_report)
    log(f"  ✓ Raw report saved → {raw_path}")
 
    # ── Render HTML ───────────────────────────────────────────────────────────
    html = render_html_report(sections, client, scores, report_date)
    html_path = os.path.join(output_dir, f"{client_id}_report_{timestamp}.html")
    with open(html_path, "w") as f:
        f.write(html)
    log(f"  ✓ HTML report saved → {html_path}")
 
    # ── Generate PDF ──────────────────────────────────────────────────────────
    update_supabase_pipeline_status(client_id, "pass3_pdf_generation")
    pdf_bytes = generate_pdf_via_docraptor(html, f"resonance_analysis_{client_id}_{timestamp}.pdf")
    pdf_path  = os.path.join(output_dir, f"{client_id}_report_{timestamp}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    log(f"  ✓ PDF saved locally → {pdf_path}")
 
    # ── Store in Supabase ─────────────────────────────────────────────────────
    storage_path = store_report_in_supabase(pdf_bytes, client, timestamp)
 
    # ── Notify Elisha ─────────────────────────────────────────────────────────
    send_report_notification(client, storage_path, report_date)
 
    # ── Deliver to client (only if --deliver flag passed) ─────────────────────
    if deliver_to_client:
        deliver_report_to_client(client, storage_path, report_date)
        update_supabase_pipeline_status(client_id, "report_delivered")
    else:
        update_supabase_pipeline_status(client_id, "report_ready_for_review")
        log("")
        log("Report is ready for your review. When approved, run:")
        log(f"  python orchestrator.py --pass3 --client_id {client_id} --deliver")
 
    elapsed = (datetime.now() - start).seconds
    log("")
    log(f"=== Pass 3 Complete in {elapsed}s ===")
    log(f"  HTML  : {html_path}")
    log(f"  PDF   : {pdf_path}")
    log(f"  Stored: {storage_path}")

# ── CLI entry point ───────────────────────────────────────────────────────────

# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Resonance Analyzer pipeline.")

    # Pass 3 mode
    parser.add_argument("--pass3",      action="store_true", help="Run Pass 3 report generation only")
    parser.add_argument("--deliver",    action="store_true", help="Deliver report to client (used with --pass3)")

    # Shared
    parser.add_argument("--client_id",  required=True, help="Client identifier string")

    # Full pipeline only
    parser.add_argument("--files",      nargs="+", help="File URLs to analyze (full pipeline only)")
    parser.add_argument("--company",    default="Unknown",      help="Company name")
    parser.add_argument("--stage",      default="Unknown",      help="Company stage")
    parser.add_argument("--purpose",    default="Not provided", help="Core purpose")
    parser.add_argument("--vision",     default="Not provided", help="3-year vision")
    parser.add_argument("--objectives", default="Not provided", help="Top objectives")
    parser.add_argument("--tension",    default="Not provided", help="Founder tension")

    args = parser.parse_args()

    if args.pass3:
        run_pass3(
            client_id=args.client_id,
            deliver_to_client=args.deliver,
        )
    else:
        if not args.files:
            parser.error("--files is required for full pipeline runs")
        run_pipeline(
            client_id=args.client_id,
            file_urls=args.files,
            client_context={
                "company_name":    args.company,
                "stage":           args.stage,
                "core_purpose":    args.purpose,
                "vision":          args.vision,
                "objectives":      args.objectives,
                "founder_tension": args.tension,
            },
        )