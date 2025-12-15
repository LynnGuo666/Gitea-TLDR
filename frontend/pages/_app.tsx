import type { AppProps } from 'next/app';
import Layout from '../components/Layout';
import { ToastProvider } from '../components/ui';
import '../styles/globals.css';

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <ToastProvider>
      <Layout>
        <Component {...pageProps} />
      </Layout>
    </ToastProvider>
  );
}
