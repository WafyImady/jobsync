import { Suspense } from 'react';
import { redirect } from 'next/navigation';
import { isAuthenticated, loginAdmin } from '../../lib/auth';

async function doLogin(formData: FormData) {
  'use server';

  const username = String(formData.get('username') ?? 'admin');
  const password = String(formData.get('password') ?? '');

  const authSucceeded = await loginAdmin(username, password);

  if (authSucceeded) {
    redirect('/');
  }

  redirect('/login?error=1');
}

async function LoginContent({
  searchParams,
}: {
  searchParams?: Promise<{ error?: string }> | { error?: string };
}) {
  if (await isAuthenticated()) {
    redirect('/');
  }

  const params = searchParams ? await Promise.resolve(searchParams) : {};
  const hasAuthConfig = !!(process.env.ADMIN_PASSWORD || process.env.ADMIN_SECRET);

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface px-6 text-on-surface">
      <div className="w-full max-w-md rounded-2xl border border-surface-container bg-surface-container-low p-8 shadow-xl">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold">JobSync Admin</h1>
          <p className="mt-2 text-sm text-on-surface-variant">Sign in to access the application dashboard.</p>
        </div>

        <form action={doLogin} className="space-y-5">
          <div>
            <label htmlFor="username" className="mb-2 block text-sm font-medium">Username</label>
            <input
              id="username"
              name="username"
              defaultValue="admin"
              className="w-full rounded-lg border border-surface-container-high bg-transparent px-3 py-2 outline-none ring-0 focus:border-primary"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-2 block text-sm font-medium">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              required
              className="w-full rounded-lg border border-surface-container-high bg-transparent px-3 py-2 outline-none ring-0 focus:border-primary"
            />
          </div>

          {!hasAuthConfig && (
            <p className="rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
              Warning: ADMIN_PASSWORD/ADMIN_SECRET is not configured. Set one before using this dashboard.
            </p>
          )}

          {params.error === '1' && (
            <p className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">
              Invalid username or password.
            </p>
          )}

          <button type="submit" className="w-full rounded-lg bg-primary px-4 py-3 font-semibold text-on-primary transition hover:opacity-90">
            Sign in
          </button>
        </form>
      </div>
    </main>
  );
}

export default function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<{ error?: string }> | { error?: string };
}) {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-on-surface">Loading...</div>}>
      <LoginContent searchParams={searchParams} />
    </Suspense>
  );
}
