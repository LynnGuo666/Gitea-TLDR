type SkeletonProps = {
  className?: string;
  variant?: 'text' | 'card' | 'avatar' | 'button';
  width?: string | number;
  height?: string | number;
  count?: number;
};

export function Skeleton({
  className = '',
  variant = 'text',
  width,
  height,
  count = 1,
}: SkeletonProps) {
  const baseClass = 'skeleton';
  const variantClass = variant === 'text' ? 'skeleton-text' : variant === 'card' ? 'skeleton-card' : '';

  const style: React.CSSProperties = {
    width: width ?? (variant === 'avatar' ? 40 : variant === 'button' ? 100 : undefined),
    height: height ?? (variant === 'avatar' ? 40 : variant === 'button' ? 36 : undefined),
    borderRadius: variant === 'avatar' ? '50%' : undefined,
  };

  if (count === 1) {
    return <div className={`${baseClass} ${variantClass} ${className}`} style={style} />;
  }

  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`${baseClass} ${variantClass} ${className}`}
          style={{ ...style, width: i === count - 1 && variant === 'text' ? '60%' : style.width }}
        />
      ))}
    </>
  );
}

export function RepoSkeleton() {
  return (
    <div className="repo-list">
      {[1, 2, 3].map((i) => (
        <div key={i} className="skeleton skeleton-card" style={{ animationDelay: `${i * 100}ms` }} />
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="card">
      <div className="skeleton skeleton-text" style={{ width: '40%', height: '1.2rem' }} />
      <div style={{ marginTop: '1rem' }}>
        <Skeleton variant="text" count={3} />
      </div>
    </div>
  );
}
