export function RouteListSkeleton() {
  return <main className="container community-page header-aligned-content" aria-busy="true" aria-label="직관 코스 불러오는 중"><p className="sr-only" role="status">코스를 불러오고 있어요.</p><div className="community-breadcrumb" aria-hidden="true">홈 › 코스 둘러보기</div><div className="community-header" aria-hidden="true"><div><div className="route-skeleton community-loading-title"/><div className="route-skeleton community-loading-description"/></div></div><div className="route-skeleton community-loading-filter" aria-hidden="true"/><RouteCardsSkeleton count={6} className="route-card-grid route-browse-grid" /></main>;
}

export function RouteCardsSkeleton({ count = 6, className = "route-card-grid" }: { count?: number; className?: string } = {}) {
  return <div className={className} aria-hidden="true">{Array.from({ length: count }, (_, index) => <div className="route-card route-card-skeleton" key={index}><div className="route-skeleton route-card-image"/><div className="route-card-content"><div className="route-skeleton route-skeleton-badge"/><div className="route-skeleton route-skeleton-title"/><div className="route-skeleton route-skeleton-line"/><div className="route-skeleton route-skeleton-line is-short"/><div className="route-skeleton route-skeleton-footer"/></div></div>)}</div>;
}

export function RouteDetailSkeleton() {
  return <main className="container route-detail-page route-detail-skeleton header-aligned-content" aria-busy="true" aria-label="코스 상세 불러오는 중"><p className="route-sr-only" role="status">저장된 코스를 불러오고 있어요.</p><div className="route-skeleton route-skeleton-badge" aria-hidden="true"/><div className="route-skeleton route-skeleton-heading" aria-hidden="true"/><div className="route-skeleton route-skeleton-subheading" aria-hidden="true"/><div className="route-skeleton route-detail-cover" aria-hidden="true"/><div className="route-skeleton route-skeleton-line" aria-hidden="true"/><div className="route-skeleton route-skeleton-line is-short" aria-hidden="true"/></main>;
}
