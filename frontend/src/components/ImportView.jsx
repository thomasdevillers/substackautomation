import React, { useRef, useState } from "react";
import { api } from "../api";
import { useToast } from "./Toast";

export default function ImportView({ onImported, goToBoard }) {
  const toast = useToast();
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null); // { fileName, notes:[] }
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  function readFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      const notes = text
        .replace(/\r\n/g, "\n")
        .split(/\n(?:[ \t]*\n){2,}/)
        .map((s) => s.trim())
        .filter(Boolean);
      setPreview({ fileName: file.name, file, notes });
    };
    reader.readAsText(file);
  }

  async function confirmImport() {
    if (!preview) return;
    setBusy(true);
    try {
      const res = await api.importFile(preview.file);
      toast(
        `Imported & scheduled ${res.imported} notes (${res.slot_times} ${res.timezone})`,
        "success"
      );
      setPreview(null);
      onImported();
      goToBoard();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-xl font-semibold mb-1">Import notes</h2>
      <p className="text-stone-500 mb-5 text-sm">
        Upload a <code>.txt</code> file. Separate each note with{" "}
        <span className="font-medium">two blank lines</span> — a single blank line
        stays inside a note as a paragraph break. On import, notes are{" "}
        <span className="font-medium">automatically scheduled</span> into your daily
        posting slots (set them in Settings), continuing after anything already scheduled.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          readFile(e.dataTransfer.files[0]);
        }}
        onClick={() => inputRef.current?.click()}
        className={
          "cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition " +
          (dragOver ? "border-substack bg-orange-50" : "border-stone-300 bg-white")
        }
      >
        <p className="text-stone-600">
          Drag & drop a <span className="font-medium">.txt</span> file here, or{" "}
          <span className="text-substack font-medium">browse</span>
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".txt,text/plain"
          className="hidden"
          onChange={(e) => readFile(e.target.files[0])}
        />
      </div>

      {preview && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium">
              {preview.notes.length} notes found in{" "}
              <span className="text-stone-500">{preview.fileName}</span>
            </h3>
            <div className="flex gap-2">
              <button
                onClick={() => setPreview(null)}
                className="px-3 py-1.5 text-sm rounded-md border border-stone-300 hover:bg-stone-100"
              >
                Cancel
              </button>
              <button
                disabled={busy || preview.notes.length === 0}
                onClick={confirmImport}
                className="px-3 py-1.5 text-sm rounded-md bg-substack text-white hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Importing…" : "Import as drafts"}
              </button>
            </div>
          </div>
          <div className="space-y-2 max-h-96 overflow-auto">
            {preview.notes.map((n, i) => (
              <div key={i} className="bg-white rounded-lg border border-stone-200 p-3 text-sm whitespace-pre-wrap">
                <span className="text-stone-400 mr-2">#{i + 1}</span>
                {n}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
