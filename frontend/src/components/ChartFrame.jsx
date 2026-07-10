import { useLayoutEffect, useRef, useState } from "react";

/**
 * Measures the wrapper's clientWidth and passes numeric {width, height}
 * to the render prop. Renders nothing until width > 0, so charts never
 * mount with -1 sizes and no Recharts warnings fire.
 *
 * Usage:
 *   <ChartFrame height={256}>
 *     {({ width, height }) => (
 *       <BarChart width={width} height={height} data={...}>...</BarChart>
 *     )}
 *   </ChartFrame>
 */
export default function ChartFrame({ height = 256, children, ...rest }) {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    if (!ref.current) return;
    const measure = () => {
      const w = ref.current?.clientWidth || 0;
      setWidth((prev) => (prev !== w ? w : prev));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={ref} style={{ width: "100%", height }} {...rest}>
      {width > 0 ? children({ width, height }) : null}
    </div>
  );
}
