#!/usr/bin/env node

const { spawn } = require('child_process');

// Forward CLI args to Next.js and determine port
const args = process.argv.slice(2);
const portFromArgs = (() => {
  const idxP = args.indexOf('-p');
  if (idxP !== -1 && args[idxP + 1]) return args[idxP + 1];
  const portFlag = args.find(a => a.startsWith('--port'));
  if (portFlag) {
    const eq = portFlag.indexOf('=');
    if (eq !== -1) return portFlag.slice(eq + 1);
    const nextIdx = args.indexOf(portFlag) + 1;
    if (args[nextIdx]) return args[nextIdx];
  }
  return process.env.PORT || '3000';
})();


// Flag to ensure browser opens only once
let browserOpened = false;

// Check if auto-open is disabled via environment variable
const shouldOpenBrowser = process.env.BROWSER !== 'false' && process.env.BROWSER !== 'none';

// Function to open browser after a delay
const openBrowserOnce = () => {
  if (browserOpened || !shouldOpenBrowser) return;
  browserOpened = true;

  // Wait for server to be ready, then open browser
  setTimeout(async () => {
    try {
      const url = `http://localhost:${portFromArgs}`;
      // Dynamic import for ESM module
      const open = (await import('open')).default;
      await open(url);
      console.log(`\n🚀 Browser opened at ${url}`);
    } catch (error) {
      console.log(`\n⚠️  Could not open browser automatically. Please visit http://localhost:3000 manually.`);
      console.log('Error:', error.message);
    }
  }, 4000); // 4 second delay to ensure server is ready
};

// Start Next.js dev server (forward args so port flags are honored)
const next = spawn('npx', ['next', 'dev', '--turbo', ...args], {
  stdio: 'inherit',
  shell: true
});

// Log which URL we will open (based on port detection)
console.log(`Dev server launching on http://localhost:${portFromArgs}`);

// Open browser once after server starts
openBrowserOnce();

// Handle process termination
process.on('SIGINT', () => {
  next.kill('SIGINT');
  process.exit();
});

next.on('error', (error) => {
  console.error('\n❌ Failed to start Next.js dev server');
  console.error('Error:', error.message);
  process.exit(1);
});

next.on('exit', (code) => {
  if (code !== 0 && code !== null) {
    console.error(`\n❌ Next.js dev server exited with code ${code}`);
    process.exit(code);
  }
});