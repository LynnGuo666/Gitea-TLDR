import { Skeleton as HeroUISkeleton } from '@heroui/react';

type SkeletonProps = {
  className?: string;
  width?: string | number;
  height?: string | number;
};

export function Skeleton({ className = '', width, height }: SkeletonProps) {
  return (
    <HeroUISkeleton
      className={`rounded-lg ${className}`}
      style={{ width, height }}
    />
  );
}

export function RepoSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {[1, 2, 3].map((i) => (
        <HeroUISkeleton
          key={i}
          className="rounded-xl h-20"
          style={{ animationDelay: `${i * 100}ms` }}
        />
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="p-6 bg-content1 rounded-xl shadow-sm">
      <HeroUISkeleton className="rounded-lg w-2/5 h-5" />
      <div className="mt-4 flex flex-col gap-2">
        <HeroUISkeleton className="rounded-lg h-4 w-full" />
        <HeroUISkeleton className="rounded-lg h-4 w-full" />
        <HeroUISkeleton className="rounded-lg h-4 w-3/5" />
      </div>
    </div>
  );
}
