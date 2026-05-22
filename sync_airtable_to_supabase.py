"""
sync_airtable_to_supabase.py — Coherynce / The Resonance Field LLC

Syncs your Airtable review edits back to Supabase before running Pass 3.
Run this after you finish reviewing findings in Airtable for a client.

Usage:
  python sync_airtable_to_supabase.py --client_id YOUR_CLIENT_ID

What it does:
  1. Pulls all Evidence Items and Cross-Force Patterns for the client from Airtable
  2. Updates Supabase evidence_items: include_in_report + elisha_notes
  3. Updates Supabase cross_force_patterns: include_in_report + elisha_notes
  4. Confirms sync counts so you know it worked before running Pass 3
"""

import os
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_TOKEN          = os.environ["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID        = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_EVIDENCE_TABLE = os.environ.get("AIRTABLE_EVIDENCE_TABLE", "Evidence Items")
AIRTABLE_PATTERNS_TABLE = os.environ.get("AIRTABLE_PATTERNS_TABLE", "Cross-Force Patterns")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def log(msg: str):
    print(f"  {msg}")


# ── Airtable helpers ──────────────────────────────────────────────────────────

def airtable_get_all(table_name: str, client_id: str) -> list:
    """Pull all records for a client from an Airtable table."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{requests.utils.quote(table_name)}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    params = {
        "filterByFormula": f"{{Client ID}} = '{client_id}'",
        "pageSize": 100,
    }

    records = []
    while True:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset

    return records


# ── Supabase helpers ──────────────────────────────────────────────────────────

def supabase_update_evidence(finding_id: str, include_in_report: bool, elisha_notes: str):
    """Update a single evidence_items row in Supabase by finding_id."""
    url = f"{SUPABASE_URL}/rest/v1/evidence_items?finding_id=eq.{finding_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    payload = {
        "include_in_report": include_in_report,
        "elisha_notes": elisha_notes or None,
    }
    response = requests.patch(url, headers=headers, json=payload, timeout=30)
    if response.status_code not in (200, 204):
        log(f"✗ Supabase update failed for {finding_id}: {response.status_code} — {response.text}")
        return False
    return True


def supabase_update_pattern(pattern_id: str, include_in_report: bool, elisha_notes: str):
    """Update a single cross_force_patterns row in Supabase by pattern_id."""
    url = f"{SUPABASE_URL}/rest/v1/cross_force_patterns?pattern_id=eq.{pattern_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    payload = {
        "include_in_report": include_in_report,
        "elisha_notes": elisha_notes or None,
    }
    response = requests.patch(url, headers=headers, json=payload, timeout=30)
    if response.status_code not in (200, 204):
        log(f"✗ Supabase update failed for {pattern_id}: {response.status_code} — {response.text}")
        return False
    return True


# ── Main sync ─────────────────────────────────────────────────────────────────

def sync(client_id: str):
    print(f"\n=== Airtable → Supabase Sync ===")
    print(f"Client ID: {client_id}\n")

    # ── Evidence Items ────────────────────────────────────────────────────────
    print("Syncing Evidence Items...")
    evidence_records = airtable_get_all(AIRTABLE_EVIDENCE_TABLE, client_id)
    log(f"Found {len(evidence_records)} evidence records in Airtable")

    evidence_synced = 0
    evidence_skipped = 0

    for record in evidence_records:
        fields = record.get("fields", {})
        finding_id = fields.get("Finding ID")
        if not finding_id:
            evidence_skipped += 1
            continue

        include = fields.get("Include in Report", True)
        notes   = fields.get("Elisha Notes", "") or ""

        success = supabase_update_evidence(finding_id, include, notes)
        if success:
            evidence_synced += 1
        else:
            evidence_skipped += 1

    log(f"✓ {evidence_synced} evidence items synced | {evidence_skipped} skipped")

    # ── Cross-Force Patterns ──────────────────────────────────────────────────
    print("\nSyncing Cross-Force Patterns...")
    pattern_records = airtable_get_all(AIRTABLE_PATTERNS_TABLE, client_id)
    log(f"Found {len(pattern_records)} pattern records in Airtable")

    patterns_synced = 0
    patterns_skipped = 0

    for record in pattern_records:
        fields = record.get("fields", {})
        pattern_id = fields.get("Pattern ID")
        if not pattern_id:
            patterns_skipped += 1
            continue

        include = fields.get("Include in Report", True)
        notes   = fields.get("Elisha Notes", "") or ""

        success = supabase_update_pattern(pattern_id, include, notes)
        if success:
            patterns_synced += 1
        else:
            patterns_skipped += 1

    log(f"✓ {patterns_synced} patterns synced | {patterns_skipped} skipped")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n=== Sync Complete ===")
    print(f"  Evidence items synced : {evidence_synced}")
    print(f"  Patterns synced       : {patterns_synced}")
    print(f"\nReady to run Pass 3 for client: {client_id}")
    print(f"  python orchestrator.py --pass3 --client_id {client_id}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Airtable review edits to Supabase")
    parser.add_argument("--client_id", required=True, help="Client ID to sync")
    args = parser.parse_args()
    sync(args.client_id)
