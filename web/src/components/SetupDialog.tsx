interface SetupDialogProps {
  open: boolean;
  allowCancel: boolean;
  busy?: boolean;
  onStart: (n: number) => void;
  onCancel: () => void;
}

const COUNTS = [2, 3, 4, 5, 6];

export function SetupDialog({
  open,
  allowCancel,
  busy,
  onStart,
  onCancel,
}: SetupDialogProps) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <h2 className="setup-title">New Game</h2>
        <p className="setup-sub">How many players?</p>
        <div className="setup-counts">
          {COUNTS.map((n) => (
            <button
              key={n}
              className="optbtn"
              disabled={busy}
              onClick={() => onStart(n)}
            >
              {n}
            </button>
          ))}
        </div>
        {allowCancel && (
          <button className="optbtn subtle" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
