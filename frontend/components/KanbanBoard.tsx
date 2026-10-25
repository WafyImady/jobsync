'use client';

import { useState, useEffect } from 'react';
import { DndContext, DragEndEvent, closestCorners, useDroppable, useDraggable } from '@dnd-kit/core';
import { updateApplicationStatus } from '../app/actions';

interface Application {
  id: string;
  company_name: string;
  role_title: string;
  status: string;
  date_received: string | Date;
}

const COLUMNS = [
  { id: 'Applied', color: 'bg-primary', textColor: 'text-primary' },
  { id: 'Interviewing', color: 'bg-tertiary', textColor: 'text-tertiary' },
  { id: 'Offer', color: 'bg-secondary', textColor: 'text-secondary' },
  { id: 'Rejected', color: 'bg-outline', textColor: 'text-outline' }
];

function JobCard({ app, textColor }: { app: Application, textColor: string }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: app.id });
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined;
  
  const formattedDate = app.date_received 
    ? new Date(app.date_received).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : 'Unknown Date';
  const initials = app.company_name.substring(0, 2).toUpperCase();

  return (
    <article ref={setNodeRef} style={style} {...listeners} {...attributes} className="bg-surface-container rounded-xl p-4 shadow-sm hover:shadow-xl hover:-translate-y-0.5 transition-all cursor-grab active:cursor-grabbing group mb-4 z-10 relative border border-surface-container-high">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg bg-surface-container-high flex items-center justify-center text-sm font-bold shadow-inner ${textColor}`}>{initials}</div>
          <span className="font-semibold text-on-surface">{app.company_name}</span>
        </div>
        <span className={`px-2 py-0.5 rounded bg-surface-container-high text-[10px] uppercase font-bold ${textColor}`}>{app.status}</span>
      </div>
      <div className="mb-2">
        <h3 className="text-[15px] text-on-surface font-semibold tracking-tight">{app.role_title}</h3>
      </div>
      <div className="flex items-center justify-between pt-2 bg-surface-container-lowest/40 -mx-4 -mb-4 px-4 py-3 rounded-b-xl mt-4">
        <div className="flex items-center gap-1 text-on-surface-variant text-xs">
          <span className="material-symbols-outlined text-[15px]">calendar_today</span>
          <span>{formattedDate}</span>
        </div>
      </div>
    </article>
  );
}

function Column({ id, name, color, items, textColor }: any) {
  const { setNodeRef } = useDroppable({ id });
  return (
    <div className="flex flex-col bg-surface-container-low rounded-xl p-4 shadow-sm min-h-[640px] border border-surface-container">
      <div className="flex items-center justify-between pb-2 mb-4">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${color}`}></span>
          <h2 className="font-semibold text-lg text-on-surface">{name}</h2>
          <span className="px-2 py-0.5 rounded-full bg-surface-container-high text-xs text-on-surface-variant">{items.length}</span>
        </div>
        <button className="text-on-surface-variant hover:text-on-surface"><span className="material-symbols-outlined text-[18px]">more_horiz</span></button>
      </div>
      <div ref={setNodeRef} className="flex flex-col flex-1 min-h-[500px]">
        {items.map((app: any) => <JobCard key={app.id} app={app} textColor={textColor} />)}
      </div>
    </div>
  );
}

export default function KanbanBoard({ initialApplications }: { initialApplications: Application[] }) {
  const [applications, setApplications] = useState(initialApplications);
  const [isMounted, setIsMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => setIsMounted(true), []);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const applicationId = String(active.id);
    const newStatus = String(over.id);

    if (COLUMNS.map(c => c.id).includes(newStatus)) {
      setApplications(prev => prev.map(app => String(app.id) === applicationId ? { ...app, status: newStatus } : app));
      updateApplicationStatus(applicationId, newStatus).catch(console.error);
    }
  }

  if (!isMounted) return null;

  // Calculate live metrics based on database rows
  const validApplications = applications.filter(a => a.status.toLowerCase() !== 'ignore');
  const activeCount = validApplications.length;
  const interviewingCount = validApplications.filter(a => a.status.toLowerCase() === 'interviewing').length;
  const offerCount = validApplications.filter(a => a.status.toLowerCase() === 'offer').length;
  const rejectedCount = validApplications.filter(a => a.status.toLowerCase() === 'rejected').length;
  const offerRate = activeCount > 0 ? Math.round((offerCount / activeCount) * 100) : 0;
  const interviewRate = activeCount > 0 ? Math.round((interviewingCount / activeCount) * 100) : 0;
  const rejectedRate = activeCount > 0 ? Math.round((rejectedCount / activeCount) * 100) : 0;

  // Calculate new applications received in the last 7 days
  const oneWeekAgo = new Date();
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
  const newThisWeek = validApplications.filter(app => {
    if (!app.date_received) return false;
    return new Date(app.date_received) >= oneWeekAgo;
  }).length;

  // Filter applications based on search query
  const filteredApplications = applications.filter(app => {
    const searchLower = searchQuery.toLowerCase();
    const company = app.company_name || '';
    const role = app.role_title || '';
    
    return (
      company.toLowerCase().includes(searchLower) ||
      role.toLowerCase().includes(searchLower)
    );
  });

  return (
    <div className="bg-surface text-on-surface min-h-screen font-sans">
      <header className="fixed top-0 left-0 right-0 z-50 bg-surface-container-lowest shadow-md border-b border-surface-container">
        <div className="h-16 w-full px-8 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <span className="material-symbols-outlined text-on-primary text-[20px]">view_kanban</span>
              </div>
              <span className="font-semibold text-lg tracking-tight">JobSync</span>
            </div>
            <div className="hidden md:flex items-center relative w-72 lg:w-96">
              <div className="w-full flex items-center bg-surface-container-low rounded-lg px-3 py-1.5 border border-surface-container">
                <span className="material-symbols-outlined text-on-surface-variant text-[18px] mr-2">search</span>
                <input 
                  className="bg-transparent w-full text-sm placeholder-on-surface-variant focus:outline-none" 
                  placeholder="Search roles, companies..." 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="relative z-0 w-full pt-28 pb-16">
        {/* TOP STATS DASHBOARD */}
        <section className="px-8 mb-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* Box 1: Pipeline Active */}
          <div className="bg-surface-container-low rounded-xl p-5 border border-surface-container flex flex-col justify-between h-32 shadow-sm">
            <div className="flex items-start justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">Pipeline Active</span>
              <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>LIVE
              </span>
            </div>
            <div className="flex items-end justify-between mt-auto">
              <div>
                <div className="text-4xl font-bold text-on-surface tracking-tight leading-none">{activeCount.toString().padStart(2, '0')}</div>
                <svg className="w-20 h-4 mt-2 stroke-primary/50" viewBox="0 0 60 15" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M0 12L15 12L25 8L35 10L45 4L60 2" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="text-[11px] font-medium text-secondary flex items-center gap-1 mb-1">
                <span className="material-symbols-outlined text-[14px]">trending_up</span>
                +{newThisWeek} this wk
              </div>
            </div>
          </div>

          {/* Box 2: In Flight */}
          <div className="bg-surface-container-low rounded-xl p-5 border border-surface-container flex flex-col justify-between h-32 relative shadow-sm">
            <div className="flex items-start justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">In Flight</span>
              <span className="material-symbols-outlined text-[16px] text-tertiary">bolt</span>
            </div>
            <div className="flex items-end justify-between mt-auto mb-3">
              <div className="text-4xl font-bold text-on-surface tracking-tight leading-none">{interviewingCount.toString().padStart(2, '0')}</div>
              <span className="text-[10px] font-bold text-tertiary bg-tertiary/10 px-2 py-0.5 rounded border border-tertiary/20">{interviewRate}% Active</span>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-surface-container m-5 mt-0 rounded-full overflow-hidden">
              <div className="h-full bg-tertiary rounded-full transition-all duration-1000" style={{ width: `${interviewRate}%` }}></div>
            </div>
          </div>

          {/* Box 3: Offers Secured */}
          <div className="bg-surface-container-low rounded-xl p-5 border border-surface-container flex flex-col justify-between h-32 relative shadow-sm">
            <div className="flex items-start justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">Offers Secured</span>
              <span className="material-symbols-outlined text-[16px] text-secondary">verified</span>
            </div>
            <div className="flex items-end justify-between mt-auto mb-3">
              <div className="text-4xl font-bold text-secondary tracking-tight leading-none">{offerCount.toString().padStart(2, '0')}</div>
              <span className="text-[11px] font-medium text-on-surface-variant tracking-wide">{offerRate}% Win Rate</span>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-surface-container m-5 mt-0 rounded-full overflow-hidden">
              <div 
                className="h-full bg-secondary rounded-full shadow-[0_0_8px_rgba(78,222,163,0.4)] transition-all duration-1000" 
                style={{ width: `${offerRate}%` }}
              ></div>
            </div>
          </div>

          {/* Box 4: Archived / Stale */}
          <div className="bg-surface-container-low rounded-xl p-5 border border-surface-container flex flex-col justify-between h-32 relative shadow-sm">
            <div className="flex items-start justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant">Archived / Stale</span>
              <span className="material-symbols-outlined text-[16px] text-outline">history</span>
            </div>
            <div className="flex items-end justify-between mt-auto mb-3">
              <div className="text-4xl font-bold text-on-surface tracking-tight leading-none">{rejectedCount.toString().padStart(2, '0')}</div>
              <span className="text-[11px] font-medium text-on-surface-variant tracking-wide">{rejectedRate}% Closed</span>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-surface-container m-5 mt-0 rounded-full overflow-hidden">
              <div className="h-full bg-outline-variant rounded-full transition-all duration-1000" style={{ width: `${rejectedRate}%` }}></div>
            </div>
          </div>

        </section>

        <section className="px-8 w-full overflow-x-auto">
          <DndContext collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5 min-w-[1240px] xl:min-w-0">
              {COLUMNS.map((column) => (
                <Column 
                  key={column.id} 
                  id={column.id} 
                  name={column.id} 
                  color={column.color} 
                  textColor={column.textColor} 
                  items={filteredApplications.filter(app => app.status.toLowerCase() === column.id.toLowerCase())} 
                />
              ))}
            </div>
          </DndContext>
        </section>
      </main>
    </div>
  );
}