import Head from 'next/head';
import Link from 'next/link';

export default function AdminReposPage() {
  return (
    <>
      <Head>
        <title>仓库管理 - 管理后台</title>
      </Head>
      <main className="dashboard">
        <section className="card">
          <div className="panel-header">
            <h1>仓库管理</h1>
            <Link href="/admin" className="ghost-button">
              返回管理后台
            </Link>
          </div>
          <p className="muted">
            仓库管理界面还在开发中。后端接口就绪后会在此支持批量启停与配置。
          </p>
        </section>
      </main>
    </>
  );
}
