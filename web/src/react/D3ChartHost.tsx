import { forwardRef } from "react";

type D3ChartHostProps = {
  id?: string;
  className?: string;
};

/** Stable DOM host for imperative D3 renders (pixel parity with pre-React shell). */
export const D3ChartHost = forwardRef<HTMLDivElement, D3ChartHostProps>(
  function D3ChartHost({ id, className }, ref) {
    return <div ref={ref} id={id} className={className} />;
  },
);
