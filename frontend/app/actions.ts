'use server';

import pool from '../lib/db';
import { revalidatePath } from 'next/cache';

export async function updateApplicationStatus(id: number | string, newStatus: string) {
  try {
    // Update the record in the Neon database
    await pool.query(
      'UPDATE applications SET status = $1, last_updated = CURRENT_TIMESTAMP WHERE id = $2',
      [newStatus, id]
    );
    
    // Tell Next.js to refresh the homepage data in the background
    revalidatePath('/');
    
    return { success: true };
  } catch (error) {
    console.error('Failed to update application status:', error);
    return { success: false, error: 'Database update failed' };
  }
}