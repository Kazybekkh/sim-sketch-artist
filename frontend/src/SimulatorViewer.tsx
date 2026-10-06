import { useState } from 'react';
import { ArrowLeft, PenLine } from 'lucide-react';
import { initialApi } from './apiConfig';
import LiveSimulator from './LiveSimulator';

export default function SimulatorViewer() {
  const [api] = useState(initialApi);
  return <main className="simulator-viewer-shell">
    <header className="simulator-viewer-header"><a href="/" className="viewer-back"><ArrowLeft size={15} />Back to portrait studio</a><span><PenLine size={15} />SIM / SKETCH</span></header>
    <LiveSimulator api={api} job={null} standalone />
  </main>;
}
