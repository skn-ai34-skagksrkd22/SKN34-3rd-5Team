import Link from "next/link";
import { MemberHeaderActions } from "./member-header-actions";
import { HeaderMenu } from "./header-menu";
import { HeaderContentBounds } from "./header-content-bounds";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link href="/" aria-label="KBO ROUTE 홈" className="brand">KBO<span className="brand-dot" /></Link>
        <HeaderContentBounds />
        <div className="header-actions">
          <HeaderMenu />
          <MemberHeaderActions />
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-top">
        <div><Link href="/" className="brand">KBO<span className="brand-dot" /></Link><p>야구를 좋아하는 마음에<br />나만의 하루를 더하다.</p></div>
        <nav aria-label="하단 메뉴"><Link href="/routes/new">루트 만들기</Link><Link href="/routes">루트 둘러보기</Link><Link href="/stadiums">구장 정보</Link><Link href="/guide">야구 가이드</Link></nav>
        <div className="footer-note">경기 전부터, 경기 후까지.<br /><strong>우리의 직관은 계속됩니다.</strong></div>
      </div>
      <div className="container footer-bottom"><span>© 2026 KBO ROUTE. 팬이 만드는 직관의 하루.</span><span>샘플 코스 사진은 구장 분위기를 위한 예시입니다. <a href="/images/SOURCES.md" target="_blank" rel="noreferrer">사진 출처</a></span></div>
    </footer>
  );
}
