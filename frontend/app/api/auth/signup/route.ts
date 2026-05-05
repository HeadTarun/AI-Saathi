import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

type SignupBody = {
  email?: string;
  password?: string;
  name?: string;
};

function jsonError(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

function getSupabaseAdminClient() {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceRoleKey) {
    throw new Error(
      "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for confirmed server-side signup."
    );
  }

  return createClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

async function findUserByEmail(
  supabaseAdmin: ReturnType<typeof getSupabaseAdminClient>,
  email: string
) {
  for (let page = 1; page <= 10; page += 1) {
    const { data, error } = await supabaseAdmin.auth.admin.listUsers({
      page,
      perPage: 100,
    });

    if (error) throw error;

    const match = data.users.find((user) => user.email?.toLowerCase() === email);
    if (match || data.users.length < 100) return match ?? null;
  }

  return null;
}

export async function POST(request: Request) {
  let body: SignupBody;
  try {
    body = (await request.json()) as SignupBody;
  } catch {
    return jsonError("Invalid signup request.");
  }

  const email = body.email?.trim().toLowerCase();
  const password = body.password ?? "";
  const name = body.name?.trim() || "Learner";

  if (!email || password.length < 6) {
    return jsonError("Enter an email and a password with at least 6 characters.");
  }

  try {
    const supabaseAdmin = getSupabaseAdminClient();
    const metadata = { name, full_name: name };

    const created = await supabaseAdmin.auth.admin.createUser({
      email,
      password,
      email_confirm: true,
      user_metadata: metadata,
    });

    if (!created.error && created.data.user) {
      return NextResponse.json({
        user: {
          id: created.data.user.id,
          email: created.data.user.email,
          name,
        },
      });
    }

    const message = created.error?.message ?? "";
    if (!/already|registered|exists/i.test(message)) {
      throw created.error;
    }

    const existingUser = await findUserByEmail(supabaseAdmin, email);
    if (!existingUser) {
      throw created.error;
    }

    const updated = await supabaseAdmin.auth.admin.updateUserById(existingUser.id, {
      password,
      email_confirm: true,
      user_metadata: metadata,
    });

    if (updated.error) throw updated.error;

    return NextResponse.json({
      user: {
        id: updated.data.user.id,
        email: updated.data.user.email,
        name,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not create Supabase user.";
    const status = message.includes("SUPABASE_SERVICE_ROLE_KEY") ? 500 : 400;
    return jsonError(message, status);
  }
}
