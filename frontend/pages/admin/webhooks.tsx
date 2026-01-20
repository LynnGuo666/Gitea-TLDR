import Head from 'next/head';
import Link from 'next/link';

export default function AdminWebhooksPage() {
  return (
    <>
      <Head>
        <title>Webhook 日志 - 管理后台</title>
      </Head>
      <main className="dashboard">
        <section className="card">
          <div className="panel-header">
            <h1>Webhook 日志</h1>
            <Link href="/admin" className="ghost-button">
              返回管理后台
            </Link>
          </div>
          <p className="muted">
            Webhook 日志界面还在开发中。后端接口已就绪（/api/admin/webhooks/logs），
            后续会在此展示日志列表与详情。
          </p>
        </section>
      </main>
    </>
  );
}
