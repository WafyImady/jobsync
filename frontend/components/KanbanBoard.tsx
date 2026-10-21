'use client';
import { useState, useEffect } from 'react';
import { DndContext, DragEndEvent, closestCorners, useDroppable, useDraggable } from '@dnd-kit/core';
import { updateApplicationStatus } from '../app/actions';

// The four statuses we mapped in our Python script
const COLUMNS = ['Applied', 'Interviewing', 'Offer', 'Rejected'];

// 1. Draggable Job Card Component
function JobCard({ app }: { app: any }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: app.id,
  });

  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
  } : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 cursor-grab active:cursor-grabbing mb-3 hover:border-blue-400 transition-colors"
    >
      <h3 className="font-semibold text-gray-800 break-words">{app.company_name}</h3>
      <p className="text-xs text-gray-400 mt-2">
        Updated: {new Date(app.last_updated).toLocaleDateString('en-GB')}
      </p>
    </div>
  );
}

// 2. Droppable Column Component
function Column({ id, items }: { id: string, items: any[] }) {
  const { setNodeRef } = useDroppable({ id });

  return (
    // Changed from w-80 flex-shrink-0 to flex-1 min-w-0
    <div className="bg-gray-50 border border-gray-200 p-4 rounded-xl flex-1 flex flex-col min-w-0">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-bold text-gray-700">{id}</h2>
        <span className="bg-gray-200 text-gray-600 text-xs py-1 px-2 rounded-full font-medium">
          {items.length}
        </span>
      </div>
      <div ref={setNodeRef} className="flex-1 min-h-[500px]">
        {items.map((app) => (
          <JobCard key={app.id} app={app} />
        ))}
      </div>
    </div>
  );
}

// 3. Main Board Component
export default function KanbanBoard({ initialApplications }: { initialApplications: any[] }) {
  const [applications, setApplications] = useState(initialApplications);
  const [isMounted, setIsMounted] = useState(false);

  // Tell React we are safely in the browser
  useEffect(() => {
    setIsMounted(true);
  }, []);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;

    const applicationId = active.id;
    const newStatus = String(over.id);

    if (COLUMNS.includes(newStatus)) {
      setApplications((prev) =>
        prev.map((app) =>
          app.id === applicationId ? { ...app, status: newStatus } : app
        )
      );
      
      updateApplicationStatus(applicationId, newStatus).catch(console.error);
    }
  }

  // Prevent rendering the DndContext on the server to avoid ID mismatches
  if (!isMounted) {
    return null; 
  }

  return (
    <DndContext collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
      <div className="flex gap-4 w-full pb-8">
        {COLUMNS.map((columnId) => (
          <Column 
            key={columnId} 
            id={columnId} 
            items={applications.filter(app => app.status === columnId)} 
          />
        ))}
      </div>
    </DndContext>
  );
}