import React from 'react';
import { EventIcon } from '../Icons';
import { eventIconClass, formatDate } from '../../helpers';

export default function TimelineTab({ events }) {
  return (
    <div className="space-y-0">
      {events.map((event) => (
        <div key={event.id} className="timeline-line flex gap-3 pb-4">
          <div
            className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center z-10 ${eventIconClass(
              event.event_type
            )}`}
          >
            <EventIcon eventType={event.event_type} className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900">{event.description}</p>
            <p className="text-xs text-gray-400 mt-0.5">{formatDate(event.created_at)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
