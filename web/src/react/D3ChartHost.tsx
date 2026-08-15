import { forwardRef } from "react";

type D3ChartHostProps = {
  id?: string;
  className?: string;
  /** Accessible summary when chart has rendered content. */
  ariaLabel?: string;
};

/** Stable DOM host for imperative D3 renders (pixel parity with pre-React shell). */
export const D3ChartHost = forwardRef<HTMLDivElement, D3ChartHostProps>(
  function D3ChartHost({ id, className, ariaLabel }, ref) {
    return (
      <div
        ref={ref}
        id={id}
        className={className}
        role="img"
        aria-label={ariaLabel}
      />
    );
  },
);
