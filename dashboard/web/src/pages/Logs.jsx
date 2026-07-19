import { useEffect, useState } from "react";
import { api, withMarket } from "../api";
import { PageHeader } from "../HelpPanel";
import { SECTION_HELP } from "../helpContent";
import { useMarket } from "../market";

export default function Logs() {
  const market = useMarket();
  const [events, setEvents] = useState([]);
  useEffect(() => {
    async function load() { setEvents(await api(withMarket("/api/events?limit=200", market))); }
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [market]);

  return (
    <>
      <PageHeader title="Logs" help={SECTION_HELP.logs} />
      <div className="card">
        <table>
          <thead><tr><th>Time</th><th>Level</th><th>Kind</th><th>Message</th></tr></thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i}>
                <td className="muted">{String(e.ts).slice(0, 19)}</td>
                <td>{e.level}</td>
                <td>{e.kind}</td>
                <td>{e.message}</td>
              </tr>
            ))}
            {!events.length && <tr><td colSpan={4} className="muted">No events yet for {market}</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
