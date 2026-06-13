import React, { useState } from "react";
import { api } from "../api";
import { useToast } from "./Toast";
import { isoToLocalInput, localInputToIso, formatWhen, STATUS_STYLES } from "../util";

export default function NoteCard({ note, selectable, selected, onToggleSelect, refresh }) {
  const toast = useToast();
  const [body, setBody] = useState(note.body);
  const [busy, setBusy] = useState(false);
  const dirty = body !== note.body;

  async function run(fn, okMsg) {
    setBusy(true);
    try {
      await fn();
      if (okMsg) toast(okMsg, "success");
      refresh();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  // Anything not yet posted can still be edited (body + time).
  const editable = note.status !== "posted";
  // Approving only applies to notes that aren't already on the schedule.
  const canApprove = note.status === "draft" || note.status === "failed";

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-3 shadow-sm">
      <div className="flex items-start gap-2 mb-2">
        {selectable && (
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggleSelect(note.id)}
            className="mt-1 accent-substack"
          />
        )}
        <span className={"text-xs px-2 py-0.5 rounded-full " + STATUS_STYLES[note.status]}>
          {note.status}
        </span>
        <span className="text-xs text-stone-400 ml-auto">#{note.id}</span>
      </div>

      <textarea
        value={body}
        disabled={!editable || busy}
        onChange={(e) => setBody(e.target.value)}
        rows={Math.min(8, Math.max(2, body.split("\n").length))}
        className="w-full text-sm border border-stone-200 rounded-md p-2 resize-y disabled:bg-stone-50 disabled:text-stone-500"
      />

      {note.status === "failed" && note.error && (
        <p className="text-xs text-red-600 mt-1">⚠ {note.error}</p>
      )}
      {note.status === "posted" && note.substack_note_url && (
        <a
          href={note.substack_note_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-substack underline mt-1 inline-block"
        >
          View on Substack ({formatWhen(note.posted_at)})
        </a>
      )}

      <div className="flex flex-wrap items-center gap-2 mt-2">
        {editable && (
          <>
            {note.status === "scheduled" && <span className="text-xs text-blue-700">⏰</span>}
            <input
              type="datetime-local"
              value={isoToLocalInput(note.scheduled_at)}
              onChange={(e) =>
                run(() => api.updateNote(note.id, { scheduled_at: localInputToIso(e.target.value) }))
              }
              className="text-xs border border-stone-200 rounded-md px-2 py-1"
            />
          </>
        )}

        <div className="ml-auto flex gap-1">
          {dirty && editable && (
            <button
              disabled={busy}
              onClick={() => run(() => api.updateNote(note.id, { body }), "Saved")}
              className="text-xs px-2 py-1 rounded-md bg-stone-800 text-white hover:opacity-90"
            >
              Save
            </button>
          )}
          {canApprove && (
            <button
              disabled={busy || !note.scheduled_at}
              title={note.scheduled_at ? "Approve & schedule" : "Set a time first"}
              onClick={() => run(() => api.approve([note.id]), "Scheduled")}
              className="text-xs px-2 py-1 rounded-md bg-blue-600 text-white hover:opacity-90 disabled:opacity-40"
            >
              Approve
            </button>
          )}
          {note.status !== "posted" && (
            <button
              disabled={busy}
              onClick={() =>
                run(() => api.postNow(note.id), "Posted to Substack")
              }
              className="text-xs px-2 py-1 rounded-md bg-substack text-white hover:opacity-90"
            >
              Post now
            </button>
          )}
          <button
            disabled={busy}
            onClick={() => {
              if (confirm("Delete this note?")) run(() => api.deleteNote(note.id));
            }}
            className="text-xs px-2 py-1 rounded-md border border-stone-300 hover:bg-stone-100"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
