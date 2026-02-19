import React, { useState } from 'react';
import { ChannelIcon } from '../Icons';
import {
  channelClass,
  interactionStatusClass,
  sentimentColor,
  formatDate,
} from '../../helpers';

function InteractionCard({ interaction }) {
  const [showTranscript, setShowTranscript] = useState(false);

  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium capitalize ${channelClass(
              interaction.channel
            )}`}
          >
            <ChannelIcon channel={interaction.channel} />
            <span>{interaction.channel}</span>
          </span>
          <span className="text-xs text-gray-500 capitalize">{interaction.direction}</span>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs capitalize ${interactionStatusClass(
              interaction.status
            )}`}
          >
            {interaction.status.replace('_', ' ')}
          </span>
        </div>
        <span className="text-xs text-gray-400">{formatDate(interaction.created_at)}</span>
      </div>

      {interaction.summary && (
        <div className="mb-2">
          <p className="text-sm text-gray-700">{interaction.summary}</p>
        </div>
      )}

      <div className="flex items-center gap-4 text-xs text-gray-500">
        {interaction.detected_intent && (
          <span className="flex items-center gap-1">
            Intent: <span className="font-medium">{interaction.detected_intent}</span>
          </span>
        )}
        {interaction.sentiment && (
          <span className="flex items-center gap-1">
            Sentiment:{' '}
            <span className={`font-medium ${sentimentColor(interaction.sentiment)}`}>
              {interaction.sentiment}
            </span>
          </span>
        )}
        {interaction.duration_seconds && <span>{interaction.duration_seconds}s</span>}
      </div>

      {interaction.transcript && (
        <div className="mt-3">
          <button
            onClick={() => setShowTranscript(!showTranscript)}
            className="text-xs text-brand-600 hover:text-brand-700 font-medium"
          >
            {showTranscript ? 'Hide transcript' : 'Show transcript'}
          </button>
          {showTranscript && (
            <div className="mt-2 bg-gray-50 rounded-lg p-3 text-xs text-gray-600 whitespace-pre-wrap max-h-60 overflow-y-auto">
              {interaction.transcript}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function InteractionsTab({ interactions }) {
  return (
    <div className="space-y-4">
      {interactions.map((ix) => (
        <InteractionCard key={ix.id} interaction={ix} />
      ))}
    </div>
  );
}

