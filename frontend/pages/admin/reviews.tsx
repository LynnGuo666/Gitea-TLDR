import Head from 'next/head';
import Link from 'next/link';
import { Card, CardBody, CardHeader, Button } from '@heroui/react';
import { ArrowLeft } from 'lucide-react';
import PageHeader from '../../components/PageHeader';

export default function AdminReviewsPage() {
  return (
    <>
      <Head>
        <title>审查历史 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto">
        <Card>
          <CardHeader>
            <PageHeader
              title="审查历史"
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
              审查历史界面还在开发中。后端接口准备好后会在此展示审查记录。
            </p>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
