import { useState, useEffect } from 'react';
import { FRONTEND_VERSION } from '../lib/version';

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
  const [showDetails, setShowDetails] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/version')
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
      <div className="version-compact">
        <button
          className="version-trigger"
          onClick={() => setShowDetails(!showDetails)}
          title="查看版本信息"
        >
          <span className="version-label">版本</span>
          <span className={`version-status ${versionMatch ? 'match' : 'mismatch'}`}>
            {versionMatch ? '✓' : '⚠'}
          </span>
        </button>
        {showDetails && (
          <div className="version-popup">
            <div className="version-row">
              <span className="version-key">前端:</span>
              <span className="version-value">{versionInfo.frontend}</span>
            </div>
            <div className="version-row">
              <span className="version-key">后端:</span>
              <span className="version-value">
                {loading ? '加载中...' : versionInfo.backend}
              </span>
            </div>
            {!versionMatch && !loading && (
              <div className="version-warning">
                前后端版本不一致，建议刷新页面
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="version-display">
      <div className="version-header">
        <span>版本信息</span>
        {!versionMatch && !loading && (
          <span className="version-badge warning" title="版本不一致">
            ⚠
          </span>
        )}
      </div>
      <div className="version-details">
        <div className="version-item">
          <span className="version-label">前端</span>
          <span className="version-number">{versionInfo.frontend}</span>
        </div>
        <div className="version-item">
          <span className="version-label">后端</span>
          <span className="version-number">
            {loading ? '...' : versionInfo.backend}
          </span>
        </div>
      </div>
      {!versionMatch && !loading && (
        <div className="version-hint">
          版本不一致，建议刷新
        </div>
      )}
    </div>
  );
}
