const fs = require('fs');
const path = require('path');

// 读取 index.html 作为模板
const indexPath = path.join(__dirname, 'out', 'index.html');
let indexHtml = fs.readFileSync(indexPath, 'utf-8');

// 找到 repo 页面的 JS 文件
const repoJsDir = path.join(__dirname, 'out', '_next', 'static', 'chunks', 'pages', 'repo', '[owner]');
const files = fs.readdirSync(repoJsDir);
const repoJs = files.find(f => f.startsWith('[repo]-') && f.endsWith('.js'));

if (!repoJs) {
  console.error('Could not find repo JavaScript file');
  process.exit(1);
}

// 提取 index 页面的 JS 文件名
const indexJsMatch = indexHtml.match(/pages\/index-([a-f0-9]+)\.js/);
if (!indexJsMatch) {
  console.error('Could not find index JavaScript reference');
  process.exit(1);
}

// 替换为 repo 页面的 JS
const repoHtml = indexHtml.replace(
  `pages/index-${indexJsMatch[1]}.js`,
  `pages/repo/[owner]/${repoJs}`
);

// 创建 repo 目录结构
const repoOutDir = path.join(__dirname, 'out', 'repo');
if (!fs.existsSync(repoOutDir)) {
  fs.mkdirSync(repoOutDir, { recursive: true });
}

// 写入 fallback HTML
fs.writeFileSync(path.join(repoOutDir, '_fallback.html'), repoHtml);
console.log('Created repo fallback HTML');
