/**
 * Cloudflare Worker: BI Jobs Subscriber Proxy
 *
 * Receives email from the notification form on raselmia.live/bi-jobs/
 * and adds it as a contact to a Resend Audience.
 *
 * Environment variables (set in Cloudflare dashboard):
 *   RESEND_API_KEY   — your Resend API key
 *   RESEND_AUDIENCE_ID — your Resend audience ID
 *   ALLOWED_ORIGIN   — e.g. "https://raselmia.live" (CORS)
 *
 * Deploy:
 *   1. Go to Cloudflare dashboard → Workers & Pages → Create
 *   2. Name it "bi-jobs-subscribe" (or similar)
 *   3. Paste this code in the editor
 *   4. Add environment variables (Settings → Variables)
 *   5. Deploy and note the worker URL (e.g. https://bi-jobs-subscribe.<you>.workers.dev)
 *   6. Update the notification form in bi-jobs/index.html to POST to this URL
 */

export default {
  async fetch(request, env) {
    const ALLOWED = env.ALLOWED_ORIGIN || "https://raselmia.live";

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": ALLOWED,
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405, ALLOWED);
    }

    try {
      const body = await request.json();
      const email = (body.email || "").trim().toLowerCase();

      if (!email || !email.includes("@")) {
        return jsonResponse({ error: "Invalid email address" }, 400, ALLOWED);
      }

      // Add contact to Resend Audience
      const resendResp = await fetch(
        `https://api.resend.com/audiences/${env.RESEND_AUDIENCE_ID}/contacts`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.RESEND_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: email,
            unsubscribed: false,
          }),
        }
      );

      if (resendResp.ok) {
        return jsonResponse({ success: true, message: "Subscribed!" }, 200, ALLOWED);
      }

      const errText = await resendResp.text();

      // Resend returns 409 if contact already exists — treat as success
      if (resendResp.status === 409 || errText.includes("already exists")) {
        return jsonResponse({ success: true, message: "Already subscribed!" }, 200, ALLOWED);
      }

      console.error("Resend error:", resendResp.status, errText);
      return jsonResponse({ error: "Failed to subscribe" }, 500, ALLOWED);
    } catch (err) {
      console.error("Worker error:", err);
      return jsonResponse({ error: "Server error" }, 500, ALLOWED);
    }
  },
};

function jsonResponse(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": origin,
    },
  });
}
