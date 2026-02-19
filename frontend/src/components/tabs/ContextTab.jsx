import React from 'react';
import { artifactTypeColor, tryParseJson } from '../../helpers';

export default function ContextTab({ contextArtifacts }) {
  if (!contextArtifacts || contextArtifacts.length === 0) {
    return (
      <div className="text-center py-6 text-gray-400 text-sm">No context artifacts yet.</div>
    );
  }

  return (
    <div className="space-y-3">
      {contextArtifacts.map((artifact) => (
        <div key={artifact.id} className="border border-gray-200 rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <span
              className={`text-xs font-semibold uppercase tracking-wide ${artifactTypeColor(
                artifact.artifact_type
              )}`}
            >
              {artifact.artifact_type.replace('_', ' ')}
            </span>
            <span className="text-xs text-gray-400">v{artifact.version}</span>
          </div>
          <p className="text-sm text-gray-700">{tryParseJson(artifact.content)}</p>
        </div>
      ))}
    </div>
  );
}
