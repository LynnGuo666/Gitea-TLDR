import type { AppProps } from 'next/app';
import { HeroUIProvider, ToastProvider } from '@heroui/react';
import { ThemeProvider as NextThemesProvider } from 'next-themes';
import Layout from '../components/Layout';
import '../styles/globals.css';

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system">
      <HeroUIProvider>
        <ToastProvider placement="bottom-right" />
        <Layout>
          <Component {...pageProps} />
        </Layout>
      </HeroUIProvider>
    </NextThemesProvider>
  );
}
