/** Skeleton day cards while events load before WASM init or first fetch. */
export function EventsLoadingPlaceholder() {
  return (
    <div
      data-testid="events-loading-placeholder"
      aria-hidden="true"
      className="events-loading-placeholder"
    >
      {[0, 1, 2].map((index) => (
        <article
          key={index}
          className="events-day-card events-day-card--skeleton"
        >
          {index > 0 ? <hr className="events-day-divider" /> : null}
          <div className="events-skeleton-header" />
          <div className="events-skeleton-columns">
            <div className="events-skeleton-col" />
            <div className="events-skeleton-col" />
            <div className="events-skeleton-col" />
          </div>
        </article>
      ))}
    </div>
  );
}
