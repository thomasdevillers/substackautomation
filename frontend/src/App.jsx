import React, { useCallback, useEffect, useState } from "react";
import { api, getPassword, setPassword } from "./api";
import { ToastProvider } from "./components/Toast";
import ImportView from "./components/ImportView";
import BoardView from "./components/BoardView";
import SettingsView from "./components/SettingsView";

const TABS = [
  { key: "board", label: "Board" },
  { key: "import", label: "Import" },
  { key: "settings", label: "Settings" },
];

function PasswordGate({ onUnlock }) {
  const [pw, setPw] = useState("");
  return (
    <div className="min-h-screen flex items-center justify-center">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setPassword(pw);
          onUnlock();
        }}
        className="bg-white p-6 rounded-xl border border-stone-200 shadow-sm w-80"
      >
        <h1 className="font-semibold mb-3">Enter dashboard password</h1>
        <input
          type="password"
          autoFocus
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="w-full border border-stone-300 rounded-md px-3 py-2 mb-3"
        />
        <button className="w-full bg-substack text-white rounded-md py-2 hover:opacity-90">
          Unlock
        </button>
      </form>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("board");
  const [notes, setNotes] = useState([]);
  const [settings, setSettings] = useState(null);
  const [locked, setLocked] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [n, s] = await Promise.all([api.listNotes(), api.getSettings()]);
      setNotes(n);
      setSettings(s);
      setLocked(false);
    } catch (e) {
      if (e.status === 401) setLocked(true);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (locked) return <PasswordGate onUnlock={refresh} />;
  if (!loaded) return <div className="p-10 text-stone-400">Loading…</div>;

  return (
    <ToastProvider>
      <div className="min-h-screen">
        <header className="bg-white border-b border-stone-200 sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">
            <span className="font-semibold text-substack">📝 Notes Scheduler</span>
            <nav className="flex gap-1">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={
                    "px-3 py-1.5 rounded-md text-sm " +
                    (tab === t.key ? "bg-stone-100 font-medium" : "text-stone-500 hover:bg-stone-50")
                  }
                >
                  {t.label}
                </button>
              ))}
            </nav>
            <span className="ml-auto text-xs">
              {settings?.connected ? (
                <span className="text-green-600">● Substack connected</span>
              ) : (
                <button onClick={() => setTab("settings")} className="text-red-500">
                  ● Not connected
                </button>
              )}
            </span>
          </div>
        </header>

        <main className="max-w-6xl mx-auto px-4 py-6">
          {tab === "board" && <BoardView notes={notes} settings={settings} refresh={refresh} />}
          {tab === "import" && (
            <ImportView onImported={refresh} goToBoard={() => setTab("board")} />
          )}
          {tab === "settings" && <SettingsView settings={settings} refresh={refresh} />}
        </main>
      </div>
    </ToastProvider>
  );
}
