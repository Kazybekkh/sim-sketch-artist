import { ArrowLeft, PenLine } from 'lucide-react';
import ConnectionSetup from './ConnectionSetup';
import useStudioConnection from './useStudioConnection';
import LiveSimulator from './LiveSimulator';

export default function SimulatorViewer() {
  const studio = useStudioConnection();
  const { connection } = studio;
  return <main className="simulator-viewer-shell">
    <header className="simulator-viewer-header"><a href="/" className="viewer-back"><ArrowLeft size={15} />Back to portrait studio</a><span><PenLine size={15} />SIM / SKETCH</span></header>
    {connection.backend && connection.simulatorOnline && connection.endpoint
      ? <LiveSimulator api={connection.endpoint} job={null} standalone />
      : <ConnectionSetup {...studio} />}
  </main>;
}
