import React, { useState } from "react";
import { api } from "../api";
import { useToast } from "./Toast";

const COMMON_TZ = [
  "UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "Europe/London", "Europe/Paris", "Africa/Johannesburg", "Asia/Kolkata", "Asia/Tokyo",
  "Australia/Sydney",
];

export default function SettingsView({ settings, refresh }) {
  const toast = useToast();
  const [cookie, setCookie] = useState("");
  const [tz, setTz] = useState(settings?.timezone || "UTC");
  const [slotTimes, setSlotTimes] = useState(settings?.slot_times || "09:00,15:00");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const payload = {
        timezone: tz,
        slot_times: slotTimes,
      };
      if (cookie.trim()) payload.session_cookie = cookie.trim();
      const res = await api.updateSettings(payload);
      setCookie("");
      refresh();
      toast(
        res.connected ? "Saved — Substack connected ✓" : "Saved (Substack not connected)",
        res.connected ? "success" : "error"
      );
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Settings</h2>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-stone-500">Substack connection:</span>
          {settings?.connected ? (
            <span className="text-green-700 font-medium">✓ Connected</span>
          ) : (
            <span className="text-red-600 font-medium">✗ Not connected</span>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-stone-200 p-4 space-y-3">
        <label className="block">
          <span className="text-sm font-medium">Substack session cookie</span>
          <textarea
            rows={4}
            value={cookie}
            placeholder={
              settings?.has_cookie
                ? "A cookie is saved. Paste a new one to replace it."
                : "Paste your Substack cookie string here…"
            }
            onChange={(e) => setCookie(e.target.value)}
            className="mt-1 w-full text-xs font-mono border border-stone-300 rounded-md p-2"
          />
        </label>
        <details className="text-xs text-stone-500">
          <summary className="cursor-pointer text-substack">How do I get my cookie?</summary>
          <ol className="list-decimal ml-5 mt-2 space-y-1">
            <li>Log in to Substack in your browser.</li>
            <li>Open DevTools (F12) → <b>Network</b> tab.</li>
            <li>Reload, click any <code>substack.com</code> request.</li>
            <li>Under Request Headers, copy the entire <code>Cookie:</code> value.</li>
            <li>Paste it above and click Save. (Re-paste when the connection drops.)</li>
          </ol>
        </details>
      </div>

      <div className="bg-white rounded-xl border border-stone-200 p-4 space-y-4">
        <label className="flex flex-col text-sm">
          <span className="font-medium">Timezone</span>
          <select value={tz} onChange={(e) => setTz(e.target.value)}
            className="mt-1 border border-stone-300 rounded-md px-2 py-1.5">
            {COMMON_TZ.includes(tz) ? null : <option value={tz}>{tz}</option>}
            {COMMON_TZ.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </label>
        <label className="flex flex-col text-sm">
          <span className="font-medium">Daily posting times</span>
          <span className="text-xs text-stone-400 mb-1">
            Comma-separated 24h times. Imported notes fill these slots each day, in order.
          </span>
          <input
            type="text"
            value={slotTimes}
            placeholder="09:00,15:00"
            onChange={(e) => setSlotTimes(e.target.value)}
            className="border border-stone-300 rounded-md px-2 py-1.5 font-mono w-40"
          />
        </label>
      </div>

      <button disabled={busy} onClick={save}
        className="px-4 py-2 rounded-md bg-substack text-white hover:opacity-90 disabled:opacity-50">
        {busy ? "Saving…" : "Save settings"}
      </button>
    </div>
  );
}
