import crypto from 'crypto';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

export const AUTH_COOKIE_NAME = 'jobsync_admin_session';

const SESSION_MAX_AGE = 60 * 60 * 24 * 7;

function getAdminCredentials() {
  const username = process.env.ADMIN_USERNAME?.trim() || 'admin';
  const password = process.env.ADMIN_PASSWORD?.trim() || process.env.ADMIN_SECRET?.trim();

  if (!password) {
    return null;
  }

  return { username, password };
}

function createSessionToken(username: string, password: string) {
  return crypto
    .createHmac('sha256', password)
    .update(username)
    .digest('base64url');
}

export async function isAuthenticated() {
  const credentials = getAdminCredentials();

  if (!credentials) {
    return false;
  }

  const cookieStore = await cookies();
  const sessionToken = cookieStore.get(AUTH_COOKIE_NAME)?.value;

  if (!sessionToken) {
    return false;
  }

  const expectedToken = createSessionToken(credentials.username, credentials.password);

  try {
    return crypto.timingSafeEqual(
      Buffer.from(expectedToken),
      Buffer.from(sessionToken)
    );
  } catch {
    return false;
  }
}

export async function requireAdminAccess() {
  if (!(await isAuthenticated())) {
    redirect('/login');
  }
}

export async function loginAdmin(username: string, password: string) {
  const credentials = getAdminCredentials();

  if (!credentials) {
    return false;
  }

  const normalizedUsername = username?.trim() || 'admin';

  if (normalizedUsername !== credentials.username) {
    return false;
  }

  const expectedToken = createSessionToken(credentials.username, credentials.password);
  const submittedToken = createSessionToken(normalizedUsername, password);

  try {
    const matches = crypto.timingSafeEqual(
      Buffer.from(expectedToken),
      Buffer.from(submittedToken)
    );

    if (!matches) {
      return false;
    }
  } catch {
    return false;
  }

  const cookieStore = await cookies();
  cookieStore.set(AUTH_COOKIE_NAME, submittedToken, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: SESSION_MAX_AGE,
  });

  return true;
}

export async function logoutAdmin() {
  const cookieStore = await cookies();
  cookieStore.delete(AUTH_COOKIE_NAME);
}
