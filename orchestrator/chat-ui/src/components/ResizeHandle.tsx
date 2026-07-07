import { useCallback, useRef } from "react";

type ResizeHandleProps = {
  getWidth: () => number;
  setWidth: (width: number) => void;
  min: number;
  max: number;
  onResizeEnd?: () => void;
  /** Right panel: drag left to widen */
  invert?: boolean;
};

export function ResizeHandle({
  getWidth,
  setWidth,
  min,
  max,
  onResizeEnd,
  invert = false,
}: ResizeHandleProps) {
  const dragging = useRef(false);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      dragging.current = true;
      const startX = e.clientX;
      const startW = getWidth();

      const onMove = (ev: MouseEvent) => {
        if (!dragging.current) return;
        const delta = ev.clientX - startX;
        const next = invert ? startW - delta : startW + delta;
        setWidth(Math.min(max, Math.max(min, next)));
      };

      const onUp = () => {
        dragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        onResizeEnd?.();
      };

      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [getWidth, setWidth, min, max, invert, onResizeEnd],
  );

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      onMouseDown={onMouseDown}
      className="group relative z-10 w-1.5 shrink-0 cursor-col-resize bg-transparent hover:bg-registry/20 active:bg-registry/30"
    >
      <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border group-hover:bg-registry/40" />
    </div>
  );
}
