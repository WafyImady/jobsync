import { Suspense } from 'react';
import pool from '../lib/db';
import { requireAdminAccess } from '../lib/auth';
import KanbanBoard from '../components/KanbanBoard';

async function BoardData() {
  const { rows: applications } = await pool.query(
    'SELECT * FROM applications ORDER BY last_updated DESC'
  );

  return <KanbanBoard initialApplications={applications} />;
}

async function ProtectedBoard() {
  await requireAdminAccess();
  return <BoardData />;
}

export default function Home() {
  return (
    <main className="min-h-screen bg-surface">
      <Suspense fallback={<div className="p-8 text-on-surface">Loading pipeline...</div>}>
        <ProtectedBoard />
      </Suspense>
    </main>
  );
}