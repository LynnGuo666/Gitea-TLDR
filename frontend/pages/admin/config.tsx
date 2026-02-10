import Head from 'next/head';
import Link from 'next/link';
import { Card, CardBody, CardHeader, Button } from '@heroui/react';
import { ArrowLeft } from 'lucide-react';

export default function AdminConfigPage() {
  return (
    <>
      <Head>
        <title>全局配置 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto">
        <Card>
          <CardHeader className="flex items-center justify-between">
            <h1 className="m-0 text-xl font-semibold">全局配置</h1>
            <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
              返回管理后台
            </Button>
          </CardHeader>
          <CardBody>
            <p className="text-default-500 m-0">
              配置管理界面还在开发中。后端接口已就绪（/api/admin/settings），
              后续会在此处提供可视化编辑。
            </p>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
