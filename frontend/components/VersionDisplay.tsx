import { useState, useEffect } from 'react';
import { Popover, PopoverTrigger, PopoverContent } from '@heroui/react';
import { FRONTEND_VERSION } from '../lib/version';
import { apiFetch } from '../lib/api';

type VersionInfo = {
  frontend: string;
  backend: string;
  backendDate?: string;
};

type VersionDisplayProps = {
  compact?: boolean;
};

export function VersionDisplay({ compact = false }: VersionDisplayProps) {
  const [versionInfo, setVersionInfo] = useState<VersionInfo>({
    frontend: FRONTEND_VERSION,
    backend: '加载中...',
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/api/version')
      .then((res) => res.json())
      .then((data) => {
        setVersionInfo({
          frontend: FRONTEND_VERSION,
          backend: data.version || '未知',
          backendDate: data.release_date,
        });
        setLoading(false);
      })
      .catch(() => {
        setVersionInfo({
          frontend: FRONTEND_VERSION,
          backend: '获取失败',
        });
        setLoading(false);
      });
  }, []);

  const versionMatch = versionInfo.frontend === versionInfo.backend;

  if (compact) {
    return (
      <div className="mb-3">
        <Popover placement="top">
          <PopoverTrigger>
            <button className="w-full flex items-center justify-between px-3 py-2 bg-default-100 border-none rounded-md cursor-pointer transition-colors hover:bg-default-200 text-xs text-default-500 font-medium">
              <span>版本</span>
              <span className={`text-sm font-bold ${versionMatch ? 'text-success' : 'text-warning'}`}>
                {versionMatch ? '✓' : '⚠'}
              </span>
            </button>
          </PopoverTrigger>
          <PopoverContent>
            <div className="p-3 min-w-[180px]">
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-default-500 text-xs font-medium">前端:</span>
                <span className="font-mono text-foreground text-xs font-semibold">{versionInfo.frontend}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-default-500 text-xs font-medium">后端:</span>
                <span className="font-mono text-foreground text-xs font-semibold">
                  {loading ? '加载中...' : versionInfo.backend}
                </span>
              </div>
              {!versionMatch && !loading && (
                <div className="mt-2 p-1.5 bg-warning-50 border border-warning rounded text-warning text-[10px] text-center font-medium">
                  前后端版本不一致，建议刷新页面
                </div>
              )}
            </div>
          </PopoverContent>
        </Popover>
      </div>
    );
  }

  return (
    <div className="p-3 bg-default-100 rounded-lg text-xs mb-3">
      <div className="flex items-center justify-between font-semibold text-default-500 mb-2 uppercase text-[10px] tracking-wide">
        <span>版本信息</span>
        {!versionMatch && !loading && (
          <span className="text-warning text-sm" title="版本不一致">⚠</span>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between items-center">
          <span className="text-default-500 text-[11px]">前端</span>
          <span className="font-mono text-foreground font-medium text-[11px]">{versionInfo.frontend}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-default-500 text-[11px]">后端</span>
          <span className="font-mono text-foreground font-medium text-[11px]">
            {loading ? '...' : versionInfo.backend}
          </span>
        </div>
      </div>
      {!versionMatch && !loading && (
        <div className="mt-2 p-1.5 bg-warning text-white rounded text-[10px] text-center font-medium">
          版本不一致，建议刷新
        </div>
      )}
    </div>
  );
}
