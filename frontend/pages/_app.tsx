import type { AppProps } from 'next/app';
import { Component, ErrorInfo, ReactNode } from 'react';
import Head from 'next/head';
import { HeroUIProvider, ToastProvider } from '@heroui/react';
import { Agentation } from 'agentation';
import { ThemeProvider as NextThemesProvider } from 'next-themes';
import Layout from '../components/Layout';
import '../styles/globals.css';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: ReactNode; fallback?: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="flex min-h-screen items-center justify-center p-8">
            <div className="max-w-md text-center">
              <h2 className="text-xl font-semibold text-danger mb-2">页面出错了</h2>
              <p className="text-default-500 text-sm mb-4">
                {this.state.error?.message ?? '发生了未知错误'}
              </p>
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.reload();
                }}
                className="px-4 py-2 bg-primary text-white rounded-lg text-sm hover:opacity-90 transition-opacity"
              >
                刷新页面
              </button>
            </div>
          </div>
        )
      );
    }

    return this.props.children;
  }
}

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
            <ErrorBoundary>
              <Component {...pageProps} />
            </ErrorBoundary>
          </Layout>
          {process.env.NODE_ENV === 'development' && <Agentation />}
        </HeroUIProvider>
      </NextThemesProvider>
    </>
  );
}
