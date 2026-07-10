import { useLayoutEffect, useRef, useState } from "react";

/**
 * Wraps children in a fixed-height div and only mounts them
 * once the container has a measurable non-zero width — avoids
 * Recharts width(-1)/height(-1) console warnings.
 */
export default function ChartFrame({ height = 256, children, ...rest }) {
  const ref = useRef(null);
  const [ready, setReady] = useState(false);

  useLayoutEffect(() => {
    if (!ref.current) return;
    if (ref.current.clientWidth > 0) {
      setReady(true);
      return;
    }
    const ro = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) {
        setReady(true);
        ro.disconnect();
      }
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={ref} style={{ width: "100%", height }} {...rest}>
      {ready ? children : null}
    </div>
  );
}
