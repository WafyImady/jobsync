import { Suspense } from 'react';
import pool from '../lib/db';
import KanbanBoard from '../components/KanbanBoard';

// 1. We move the database fetch into its own async component
async function BoardData() {
  const { rows: applications } = await pool.query(
    'SELECT * FROM applications ORDER BY last_updated DESC'
  );

  return <KanbanBoard initialApplications={applications} />;
}

// 2. The main page renders instantly, and waits for the database component inside Suspense
export default function Home() {
  return (
    <main className="min-h-screen bg-white p-8 text-black">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Reverse ATS Board</h1>
        
        <Suspense fallback={<div className="p-4 text-gray-500 font-medium">Loading applications from Neon...</div>}>
          <BoardData />
        </Suspense>
      </div>
    </main>
  );
}