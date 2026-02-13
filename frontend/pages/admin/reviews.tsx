import Head from 'next/head';
import Link from 'next/link';
import { Card, CardBody, CardHeader, Button } from '@heroui/react';
import { ArrowLeft } from 'lucide-react';

export default function AdminReviewsPage() {
  return (
    <>
      <Head>
        <title>审查历史 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto">
        <Card>
          <CardHeader className="flex items-center justify-between">
            <h1 className="m-0 text-2xl font-bold tracking-tight">审查历史</h1>
            <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
              返回管理后台
            </Button>
          </CardHeader>
          <CardBody>
            <p className="text-default-500 m-0">
              审查历史界面还在开发中。后端接口准备好后会在此展示审查记录。
            </p>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
