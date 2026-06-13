import React, { useMemo, useState } from "react";
import { api } from "../api";
import { useToast } from "./Toast";
import NoteCard from "./NoteCard";

const COLUMNS = [
  { key: "draft", label: "Drafts" },
  { key: "scheduled", label: "Scheduled" },
  { key: "posted", label: "Posted" },
  { key: "failed", label: "Failed" },
];

export default function BoardView({ notes, settings, refresh }) {
  const toast = useToast();
  const [selected, setSelected] = useState([]);
  const tz = settings?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;

  const today = new Date().toISOString().slice(0, 10);
  const [startDate, setStartDate] = useState(today);
  const [timeOfDay, setTimeOfDay] = useState(settings?.default_post_time || "09:00");
  const [cadence, setCadence] = useState(settings?.default_cadence_days || 1);

  const grouped = useMemo(() => {
    const g = { draft: [], scheduled: [], posted: [], failed: [] };
    notes.forEach((n) => g[n.status]?.push(n));
    return g;
  }, [notes]);

  const toggle = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  async function applySpread() {
    if (selected.length === 0) return toast("Select some draft notes first", "error");
    try {
      await api.autoSpread({
        note_ids: selected,
        start_date: startDate,
        time_of_day: timeOfDay,
        cadence_days: Number(cadence),
        timezone: tz,
      });
      toast(`Spread ${selected.length} notes across the schedule`, "success");
      refresh();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function approveSelected() {
    if (selected.length === 0) return toast("Select some notes first", "error");
    try {
      const res = await api.approve(selected);
      toast(`Scheduled ${res.approved} notes`, "success");
      setSelected([]);
      refresh();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  return (
    <div>
      {/* Bulk toolbar */}
      <div className="bg-white rounded-xl border border-stone-200 p-4 mb-5">
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <div className="font-medium text-stone-700 mr-2">
            Bulk schedule
            <span className="block text-xs text-stone-400 font-normal">
              {selected.length} selected · times in {tz}
            </span>
          </div>
          <label className="flex flex-col">
            <span className="text-xs text-stone-500">Start date</span>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
              className="border border-stone-300 rounded-md px-2 py-1" />
          </label>
          <label className="flex flex-col">
            <span className="text-xs text-stone-500">Time</span>
            <input type="time" value={timeOfDay} onChange={(e) => setTimeOfDay(e.target.value)}
              className="border border-stone-300 rounded-md px-2 py-1" />
          </label>
          <label className="flex flex-col">
            <span className="text-xs text-stone-500">Every N days</span>
            <input type="number" min="1" value={cadence} onChange={(e) => setCadence(e.target.value)}
              className="border border-stone-300 rounded-md px-2 py-1 w-20" />
          </label>
          <button onClick={applySpread}
            className="px-3 py-1.5 rounded-md border border-stone-300 hover:bg-stone-100">
            Auto-spread times
          </button>
          <button onClick={approveSelected}
            className="px-3 py-1.5 rounded-md bg-blue-600 text-white hover:opacity-90">
            Approve & schedule selected
          </button>
        </div>
      </div>

      {/* Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {COLUMNS.map((col) => (
          <div key={col.key}>
            <h3 className="font-semibold text-sm text-stone-600 mb-2 flex items-center gap-2">
              {col.label}
              <span className="text-xs bg-stone-200 rounded-full px-2">{grouped[col.key].length}</span>
            </h3>
            <div className="space-y-3">
              {grouped[col.key].length === 0 && (
                <p className="text-xs text-stone-400 italic">No notes</p>
              )}
              {grouped[col.key].map((note) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  selectable={col.key === "draft" || col.key === "failed"}
                  selected={selected.includes(note.id)}
                  onToggleSelect={toggle}
                  refresh={refresh}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
