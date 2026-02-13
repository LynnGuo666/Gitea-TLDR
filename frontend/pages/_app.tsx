import type { AppProps } from 'next/app';
import Head from 'next/head';
import { HeroUIProvider, ToastProvider } from '@heroui/react';
import { ThemeProvider as NextThemesProvider } from 'next-themes';
import Layout from '../components/Layout';
import '../styles/globals.css';

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#609926" />
      </Head>
      <NextThemesProvider attribute="class" defaultTheme="system">
        <HeroUIProvider>
          <ToastProvider placement="bottom-right" />
          <Layout>
            <Component {...pageProps} />
          </Layout>
        </HeroUIProvider>
      </NextThemesProvider>
    </>
  );
}
