import Head from 'next/head';
import Link from 'next/link';
import { Card, CardBody, CardHeader, Button } from '@heroui/react';
import { ArrowLeft } from 'lucide-react';
import PageHeader from '../../components/PageHeader';

export default function AdminWebhooksPage() {
  return (
    <>
      <Head>
        <title>Webhook 日志 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto">
        <Card>
          <CardHeader>
            <PageHeader
              title="Webhook 日志"
              actions={
                <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
                  返回管理后台
                </Button>
              }
              className="w-full"
            />
          </CardHeader>
          <CardBody>
            <p className="text-default-500 m-0">
              Webhook 日志界面还在开发中。后端接口已就绪（/api/admin/webhooks/logs），
              后续会在此展示日志列表与详情。
            </p>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
