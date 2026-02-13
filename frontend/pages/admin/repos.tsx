import Head from 'next/head';
import Link from 'next/link';
import { Card, CardBody, CardHeader, Button } from '@heroui/react';
import { ArrowLeft } from 'lucide-react';

export default function AdminReposPage() {
  return (
    <>
      <Head>
        <title>仓库管理 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto">
        <Card>
          <CardHeader className="flex items-center justify-between">
            <h1 className="m-0 text-2xl font-bold tracking-tight">仓库管理</h1>
            <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
              返回管理后台
            </Button>
          </CardHeader>
          <CardBody>
            <p className="text-default-500 m-0">
              仓库管理界面还在开发中。后端接口就绪后会在此支持批量启停与配置。
            </p>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
