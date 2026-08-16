import { downloadExport } from '../api'

interface Props {
  docId: string
}

export default function ExportBar({ docId }: Props) {
  return (
    <div className="export-bar">
      <button className="secondary" onClick={() => downloadExport(docId, 'html')} title="Self-contained interactive graph (hostable anywhere)">
        EXPORT .HTML
      </button>
      <button className="secondary" onClick={() => downloadExport(docId, 'report')} title="Readable Markdown report">
        REPORT .MD
      </button>
      <button className="secondary" onClick={() => downloadExport(docId, 'csv')} title="nodes.csv + edges.csv (zip)">
        CSV .ZIP
      </button>
    </div>
  )
}
