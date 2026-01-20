import Head from 'next/head';
import Link from 'next/link';

export default function AdminReviewsPage() {
  return (
    <>
      <Head>
        <title>审查历史 - 管理后台</title>
      </Head>
      <main className="dashboard">
        <section className="card">
          <div className="panel-header">
            <h1>审查历史</h1>
            <Link href="/admin" className="ghost-button">
              返回管理后台
            </Link>
          </div>
          <p className="muted">
            审查历史界面还在开发中。后端接口准备好后会在此展示审查记录。
          </p>
        </section>
      </main>
    </>
  );
}
