'use server';

import { revalidatePath } from 'next/cache';
import { isAuthenticated } from '../lib/auth';
import pool from '../lib/db';

const VALID_STATUSES = new Set([
  'Applied',
  'Interviewing',
  'Offer',
  'Rejected',
  'Ignore',
]);

export async function updateApplicationStatus(id: number | string, newStatus: string) {
  try {
    if (!(await isAuthenticated())) {
      return { success: false, error: 'Unauthorized' };
    }

    const applicationId = Number(id);
    const normalizedStatus = String(newStatus).trim();

    if (!Number.isInteger(applicationId) || applicationId <= 0) {
      return { success: false, error: 'Invalid application id' };
    }

    if (!VALID_STATUSES.has(normalizedStatus)) {
      return { success: false, error: 'Invalid status' };
    }

    await pool.query(
      'UPDATE applications SET status = $1, last_updated = CURRENT_TIMESTAMP WHERE id = $2',
      [normalizedStatus, applicationId]
    );

    revalidatePath('/');

    return { success: true };
  } catch (error) {
    console.error('Failed to update application status:', error);
    return { success: false, error: 'Database update failed' };
  }
}