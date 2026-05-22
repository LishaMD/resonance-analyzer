import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const FROM_EMAIL = "noreply@send.coherynce.com";
const NOTIFY_EMAIL = "elisha@coherynce.com";
const PORTAL_BASE_URL = "https://portal.coherynce.com";

Deno.serve(async (req) => {
  try {
    const payload = await req.json();

    // Supabase storage webhook payload
    const record = payload.record;
    if (!record) {
      return new Response("No record", { status: 400 });
    }

    // Extract token from storage path (token/timestamp-filename)
    const pathParts = record.name?.split("/");
    if (!pathParts || pathParts.length < 2) {
      return new Response("Invalid path", { status: 400 });
    }
    const token = pathParts[0];
    const fileName = pathParts.slice(1).join("/");

    // Look up client record by token
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
    const { data: client, error } = await supabase
      .from("client_intakes")
      .select("company_name, contact_name, contact_email, status")
      .eq("upload_token", token)
      .maybeSingle();

    if (error || !client) {
      console.error("Client lookup failed:", error);
      return new Response("Client not found", { status: 404 });
    }

    const resumeLink = `${PORTAL_BASE_URL}/upload/${token}`;

    // Email to client
    await sendEmail({
      to: client.contact_email,
      subject: "Your documents have been received — Syntara Intelligence",
      html: `
        <p>Hi ${client.contact_name},</p>
        <p>We've received your documents for <strong>${client.company_name}</strong>. 
        Elisha will review them and be in touch within 3–5 business days.</p>
        <p>Need to add more documents? You can return to your upload page anytime:</p>
        <p><a href="${resumeLink}">${resumeLink}</a></p>
        <p>— Syntara Intelligence</p>
      `,
    });

    // Email to Elisha
    await sendEmail({
      to: NOTIFY_EMAIL,
      subject: `New upload: ${client.company_name}`,
      html: `
        <p><strong>${client.contact_name}</strong> (${client.contact_email}) 
        from <strong>${client.company_name}</strong> just uploaded a file.</p>
        <p><strong>File:</strong> ${fileName}</p>
        <p><strong>Review their documents:</strong><br/>
        <a href="${resumeLink}">${resumeLink}</a></p>
      `,
    });

    // Update status to documents_uploaded
    await supabase
      .from("client_intakes")
      .update({ status: "documents_uploaded", updated_at: new Date().toISOString() })
      .eq("upload_token", token);

    return new Response("OK", { status: 200 });

  } catch (err) {
    console.error("Edge function error:", err);
    return new Response("Internal error", { status: 500 });
  }
});

async function sendEmail({ to, subject, html }: {
  to: string;
  subject: string;
  html: string;
}) {
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: FROM_EMAIL,
      to,
      subject,
      html,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Resend error: ${err}`);
  }
}