const fs = require('fs');
const path = require('path');

const repoPagePath = path.join(__dirname, 'out', 'repo', '[owner]', '[repo]', 'index.html');
if (!fs.existsSync(repoPagePath)) {
  console.error('Could not find exported repo page HTML');
  process.exit(1);
}

const repoHtml = fs.readFileSync(repoPagePath, 'utf-8');

const repoOutDir = path.join(__dirname, 'out', 'repo');
if (!fs.existsSync(repoOutDir)) {
  fs.mkdirSync(repoOutDir, { recursive: true });
}

// 写入 fallback HTML
fs.writeFileSync(path.join(repoOutDir, '_fallback.html'), repoHtml);
console.log('Created repo fallback HTML');
