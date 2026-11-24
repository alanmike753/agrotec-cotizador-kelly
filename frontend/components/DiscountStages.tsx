type Props = {
  values: string[];
  onChange: (values: string[]) => void;
  compact?: boolean;
  lockedCount?: number;
  allowStructureChanges?: boolean;
};

export default function DiscountStages({ values, onChange, compact = false, lockedCount = 0, allowStructureChanges = true }: Props) {
  function replace(index: number, value: string) {
    onChange(values.map((item, itemIndex) => itemIndex === index ? value : item));
  }
  function move(index: number, direction: -1 | 1) {
    const destination = index + direction;
    if (destination < 0 || destination >= values.length) return;
    const next = [...values];
    [next[index], next[destination]] = [next[destination], next[index]];
    onChange(next);
  }

  return <div className={`discount-stages ${compact ? "compact" : ""}`}>
    {values.map((value, index) => <div className="discount-stage" key={index}>
      <span className="stage-number">{index + 1}</span>
      <label><span>Etapa {index + 1}</span><div className="input-suffix"><input aria-label={`Descuento etapa ${index + 1}`} type="number" min="0" max="100" step="0.01" value={value} onChange={event => replace(index, event.target.value)} placeholder="0" disabled={index < lockedCount} /><b>{index < lockedCount ? "🔒" : "%"}</b></div></label>
      {allowStructureChanges && <div className="stage-actions">
        <button type="button" className="mini-button" onClick={() => move(index, -1)} disabled={index === 0} aria-label={`Subir etapa ${index + 1}`}>↑</button>
        <button type="button" className="mini-button" onClick={() => move(index, 1)} disabled={index === values.length - 1} aria-label={`Bajar etapa ${index + 1}`}>↓</button>
        <button type="button" className="mini-button danger" onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))} disabled={values.length === 1} aria-label={`Eliminar etapa ${index + 1}`}>×</button>
      </div>}
    </div>)}
    {allowStructureChanges && <button type="button" className="add-stage" onClick={() => onChange([...values, ""])}>+ Agregar etapa</button>}
  </div>;
}
