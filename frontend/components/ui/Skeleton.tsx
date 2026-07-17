import { Skeleton as HeroUISkeleton } from '@heroui/react';

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
