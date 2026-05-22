import os
import secrets
import argparse
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL")  # e.g. https://your-lovable-app.lovable.app

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def create_client_record(
    company_name,
    contact_name,
    contact_email,
    contact_title=None,
    website_url=None,
    engagement_tier="resonance_analyzer"
):
    token = "tok_" + secrets.token_urlsafe(12)

    data = {
        "company_name": company_name,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_title": contact_title,
        "website_url": website_url,
        "upload_token": token,
        "engagement_tier": engagement_tier,
        "status": "intake_received"
    }

    result = supabase.table("client_intakes").insert(data).execute()

    if not result.data:
        print("Error creating client record.")
        return

    record = result.data[0]
    upload_url = f"{PORTAL_BASE_URL}/upload/{token}"

    print("\n✅ Client record created.")
    print(f"   Company:    {company_name}")
    print(f"   Contact:    {contact_name} ({contact_email})")
    print(f"   Token:      {token}")
    print(f"   Upload URL: {upload_url}")
    print(f"\n📋 Send this link to the client:\n   {upload_url}\n")

    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new Coherynce client record")
    parser.add_argument("--company", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--website", default=None)
    parser.add_argument("--tier", default="resonance_analyzer")

    args = parser.parse_args()

    create_client_record(
        company_name=args.company,
        contact_name=args.name,
        contact_email=args.email,
        contact_title=args.title,
        website_url=args.website,
        engagement_tier=args.tier
    )