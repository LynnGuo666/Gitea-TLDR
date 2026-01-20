import Head from 'next/head';
import Link from 'next/link';

export default function AdminConfigPage() {
  return (
    <>
      <Head>
        <title>全局配置 - 管理后台</title>
      </Head>
      <main className="dashboard">
        <section className="card">
          <div className="panel-header">
            <h1>全局配置</h1>
            <Link href="/admin" className="ghost-button">
              返回管理后台
            </Link>
          </div>
          <p className="muted">
            配置管理界面还在开发中。后端接口已就绪（/api/admin/settings），
            后续会在此处提供可视化编辑。
          </p>
        </section>
      </main>
    </>
  );
}
