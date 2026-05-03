import { NextRequest, NextResponse } from "next/server";

function randomState() {
  return crypto.randomUUID();
}

export async function GET(request: NextRequest) {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const authUri = process.env.GOOGLE_AUTH_URI || "https://accounts.google.com/o/oauth2/auth";

  if (!clientId) {
    return NextResponse.json({ message: "Google sign in is not configured." }, { status: 500 });
  }

  const origin = request.nextUrl.origin;
  const redirectUri = `${origin}/dashboard`;
  const state = randomState();
  const url = new URL(authUri);
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid email profile");
  url.searchParams.set("state", state);
  url.searchParams.set("prompt", "select_account");

  const response = NextResponse.redirect(url);
  response.cookies.set("google_oauth_state", state, {
    httpOnly: true,
    sameSite: "lax",
    secure: request.nextUrl.protocol === "https:",
    path: "/",
    maxAge: 60 * 10,
  });
  return response;
}
