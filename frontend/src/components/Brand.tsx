interface BrandProps {
  size?: "sm" | "md" | "lg";
}

export function Brand({ size = "md" }: BrandProps) {
  const sizes = {
    sm: { box: "w-7 h-7", text: "text-sm" },
    md: { box: "w-8 h-8", text: "text-base" },
    lg: { box: "w-10 h-10", text: "text-lg" },
  };
  const s = sizes[size];
  return (
    <div className="flex items-center gap-2">
      <div
        className={`${s.box} rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white grid place-items-center font-bold`}
        aria-hidden="true"
      >
        AQ
      </div>
      <span
        className={`font-semibold text-slate-900 ${s.text} hidden sm:inline`}
      >
        Adaptive Quiz
      </span>
    </div>
  );
}
