import { NextRequest, NextResponse } from "next/server";

type GoogleTokenResponse = {
  access_token?: string;
  expires_in?: number;
  id_token?: string;
  scope?: string;
  token_type?: string;
  error?: string;
  error_description?: string;
};

type GoogleIdProfile = {
  sub?: string;
  email?: string;
  name?: string;
  picture?: string;
};

function decodeBase64Url(value: string) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return Buffer.from(padded, "base64").toString("utf8");
}

function parseIdToken(idToken: string): GoogleIdProfile {
  const [, payload] = idToken.split(".");
  if (!payload) return {};
  return JSON.parse(decodeBase64Url(payload)) as GoogleIdProfile;
}

export async function POST(request: NextRequest) {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  const tokenUri = process.env.GOOGLE_TOKEN_URI || "https://oauth2.googleapis.com/token";

  if (!clientId || !clientSecret) {
    return NextResponse.json({ message: "Google sign in is not configured." }, { status: 500 });
  }

  const body = (await request.json()) as {
    code?: string;
    state?: string;
    redirectUri?: string;
  };

  const expectedState = request.cookies.get("google_oauth_state")?.value;
  if (!body.code || !body.state || !expectedState || body.state !== expectedState) {
    return NextResponse.json({ message: "Could not verify Google sign in. Please try again." }, { status: 400 });
  }

  const redirectUri = body.redirectUri || `${request.nextUrl.origin}/dashboard`;
  const form = new URLSearchParams({
    code: body.code,
    client_id: clientId,
    client_secret: clientSecret,
    redirect_uri: redirectUri,
    grant_type: "authorization_code",
  });

  const tokenResponse = await fetch(tokenUri, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  const tokenData = (await tokenResponse.json()) as GoogleTokenResponse;

  if (!tokenResponse.ok || !tokenData.id_token) {
    return NextResponse.json(
      { message: tokenData.error_description || "Google sign in failed. Please try again." },
      { status: 400 }
    );
  }

  const profile = parseIdToken(tokenData.id_token);
  if (!profile.sub) {
    return NextResponse.json({ message: "Google profile was incomplete. Please try again." }, { status: 400 });
  }

  const response = NextResponse.json({
    userId: `google-${profile.sub}`,
    name: profile.name || profile.email || "Learner",
    email: profile.email || "",
    picture: profile.picture || "",
  });
  response.cookies.delete("google_oauth_state");
  response.cookies.set("ai_saathi_google_user", `google-${profile.sub}`, {
    sameSite: "lax",
    secure: request.nextUrl.protocol === "https:",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}
