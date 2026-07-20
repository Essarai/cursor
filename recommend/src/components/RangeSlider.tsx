"use client";

interface Props {
  label: string;
  min: number;
  max: number;
  valueMin: number;
  valueMax: number;
  onChange: (min: number, max: number) => void;
  step?: number;
  format?: (v: number) => string;
}

export default function RangeSlider({
  label,
  min,
  max,
  valueMin,
  valueMax,
  onChange,
  step = 1,
  format = (v) => String(v),
}: Props) {
  const range = max - min || 1;
  const pctMin = ((valueMin - min) / range) * 100;
  const pctMax = ((valueMax - min) / range) * 100;

  const handleMin = (v: number) => {
    onChange(Math.min(v, valueMax), valueMax);
  };

  const handleMax = (v: number) => {
    onChange(valueMin, Math.max(v, valueMin));
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <label className="text-xs font-medium text-slate-600">{label}</label>
        <span className="text-xs tabular-nums text-slate-500">
          {format(valueMin)} – {format(valueMax)}
        </span>
      </div>

      <div className="relative h-6">
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-slate-200">
          <div
            className="absolute h-full rounded-full bg-brand-500"
            style={{ left: `${pctMin}%`, right: `${100 - pctMax}%` }}
          />
        </div>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={valueMin}
          onChange={(e) => handleMin(Number(e.target.value))}
          className="range-thumb pointer-events-none absolute inset-0 z-10 w-full appearance-none bg-transparent"
          style={{ zIndex: valueMin > max - (max - min) * 0.1 ? 20 : 10 }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={valueMax}
          onChange={(e) => handleMax(Number(e.target.value))}
          className="range-thumb pointer-events-none absolute inset-0 w-full appearance-none bg-transparent"
          style={{ zIndex: 10 }}
        />
      </div>

      <div className="mt-1 flex justify-between text-[10px] text-slate-400">
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
    </div>
  );
}
