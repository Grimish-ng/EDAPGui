import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin } from "@decky/api";
import { useEffect, useState } from "react";

type Resp = { ok: boolean; error?: string; state?: any };

const status = callable<[], Resp>("status");
const startAssist = callable<[assist: string], Resp>("start_assist");
const stopAssist = callable<[assist: string], Resp>("stop_assist");
const stopAll = callable<[], Resp>("stop_all");

const ASSISTS: Array<[key: string, label: string]> = [
  ["fsd", "FSD Route Assist"],
  ["sc", "Supercruise Assist"],
  ["waypoint", "Waypoint Assist"],
];

function Panel() {
  const [st, setSt] = useState<any>(null);
  const [err, setErr] = useState<string>("");

  const refresh = async () => {
    const r = await status();
    if (r.ok) { setSt(r.state); setErr(""); }
    else setErr(r.error ?? "unknown error");
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  const toggle = async (key: string, active: boolean) => {
    await (active ? stopAssist(key) : startAssist(key));
    await refresh();
  };

  return (
    <>
      <PanelSection title="Assists">
        {ASSISTS.map(([key, label]) => {
          const active = !!st?.active?.[key];
          return (
            <PanelSectionRow key={key}>
              <ButtonItem layout="below" onClick={() => toggle(key, active)}>
                {(active ? "Stop " : "Start ") + label}
              </ButtonItem>
            </PanelSectionRow>
          );
        })}
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={async () => { await stopAll(); refresh(); }}>
            STOP ALL
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title="Status">
        <PanelSectionRow>
          <div className={staticClasses.Text}>
            {err ? `⚠ ${err}` :
              `${st?.engine ?? "?"} · ${st?.statusline || "idle"}` +
              (st?.jumpcount ? ` · jumps: ${st.jumpcount}` : "")}
          </div>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}

export default definePlugin(() => ({
  name: "EDAP Autopilot",
  titleView: <div className={staticClasses.Title}>EDAP Autopilot</div>,
  content: <Panel />,
  icon: <span>🚀</span>,
}));
